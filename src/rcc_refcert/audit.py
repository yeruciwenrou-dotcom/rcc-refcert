from __future__ import annotations

import itertools
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal

import numpy as np

from .bellman_choi import BellmanChoiReport, verify_bellman_choi
from .cases import (
    CASES,
    H1_REALIZATION,
    H2_LINEAR_FIXED_POINT,
    H3_BELLMAN_CHOI,
    H4_REFERENCE_POTENTIAL,
    H6_GAIN_COST,
    H34_DOMINATION,
    CaseStudy,
)
from .domination import DominationResult, minimum_domination_constant
from .examples import (
    gamma5_summary,
    global_reset_family_constants,
    make_f5_two_qubit_witness,
    make_global_reset_loop_model,
    make_same_space_reference_envelopes,
    natural_c_gt_one_interval,
)
from .fixed_point import FixedPointResult, linear_fixed_point
from .gain_cost import GainCostReport, analyze_reference_gain_cost
from .model import FiniteControlModel, require_valid_model
from .quantum import Array
from .rank_encoding import decode_word, encode_word
from .reference_potential import CertificateReport, verify_reference_potential
from .semantics import (
    depth_contribution_by_enumeration,
    depth_contribution_by_maps,
    truncated_semidensity,
)
from .status import CheckOutcome, EvidenceLevel


def _linear_fixed_point_outcome(
    result: FixedPointResult,
    tolerance: float,
) -> CheckOutcome:
    if not result.applicable:
        return CheckOutcome.NOT_APPLICABLE
    if (
        result.output is None
        or result.condition_number is None
        or result.solve_residual is None
        or not np.isfinite(result.condition_number)
        or not np.isfinite(result.solve_residual)
        or result.solve_residual > tolerance
        or result.condition_number * np.finfo(float).eps > tolerance
    ):
        return CheckOutcome.INCONCLUSIVE
    return CheckOutcome.PASS


@dataclass(frozen=True)
class DepthAgreement:
    """One finite-depth check of the Appendix-H realization identity."""

    action_depth: int
    spectral_norm_error: float
    outcome: CheckOutcome
    evidence: EvidenceLevel = EvidenceLevel.NUMERICAL


@dataclass(frozen=True)
class ModelAnalysis:
    """Numerical H.1, H.2, and H.34 results for one finite-control model."""

    model_name: str
    tolerance: float
    realization_checks: tuple[DepthAgreement, ...]
    max_transient_steps: int
    truncated_trace: float
    fixed_point: FixedPointResult
    fixed_model_domination: DominationResult | None
    notes: tuple[str, ...]
    truncated_output: Array = field(repr=False, compare=False)

    @property
    def maximum_realization_error(self) -> float:
        return max(
            (check.spectral_norm_error for check in self.realization_checks),
            default=0.0,
        )

    @property
    def realization_outcome(self) -> CheckOutcome:
        return (
            CheckOutcome.PASS
            if all(
                check.outcome is CheckOutcome.PASS for check in self.realization_checks
            )
            else CheckOutcome.FAIL
        )

    @property
    def linear_fixed_point_outcome(self) -> CheckOutcome:
        return _linear_fixed_point_outcome(self.fixed_point, self.tolerance)

    @property
    def domination_outcome(self) -> CheckOutcome:
        if self.fixed_model_domination is None:
            return CheckOutcome.INCONCLUSIVE
        return self.fixed_model_domination.outcome


@dataclass(frozen=True)
class CaseAnalysis:
    """A bundled case with every supplied certificate checked once."""

    case: CaseStudy
    model: FiniteControlModel = field(repr=False, compare=False)
    model_analysis: ModelAnalysis
    bellman_choi: BellmanChoiReport | None
    reference_potentials: tuple[CertificateReport, ...]
    gain_cost: GainCostReport | None

    def observed_outcomes(self) -> tuple[tuple[str, CheckOutcome], ...]:
        outcomes: list[tuple[str, CheckOutcome]] = [
            (H1_REALIZATION, self.model_analysis.realization_outcome),
            (H2_LINEAR_FIXED_POINT, self.model_analysis.linear_fixed_point_outcome),
            (H34_DOMINATION, self.model_analysis.domination_outcome),
        ]
        if self.bellman_choi is not None:
            outcomes.append((H3_BELLMAN_CHOI, self.bellman_choi.outcome))
        if self.reference_potentials:
            outcomes.append(
                (
                    H4_REFERENCE_POTENTIAL,
                    _aggregate_outcomes(
                        report.outcome for report in self.reference_potentials
                    ),
                )
            )
        if self.gain_cost is not None:
            outcomes.append((H6_GAIN_COST, self.gain_cost.outcome))
        return tuple(outcomes)

    @property
    def expectation_mismatches(self) -> tuple[str, ...]:
        observed = dict(self.observed_outcomes())
        mismatches = []
        for name, expected in self.case.expected_outcomes:
            actual = observed.get(name, CheckOutcome.NOT_APPLICABLE)
            if actual is not expected:
                mismatches.append(
                    f"{name}: expected {expected.value}, observed {actual.value}"
                )
        return tuple(mismatches)

    @property
    def matches_expectations(self) -> bool:
        return not self.expectation_mismatches


@dataclass(frozen=True)
class AppendixFWitnesses:
    """Structured results for executable witnesses outside the case models."""

    rank_roundtrip_count: int
    rank_roundtrip_failures: int
    gamma5_reference_balance_error: float
    gamma5_word_average_errors: tuple[float, ...]
    gamma5_partial_kraft_mass: float
    f5_reset_balance_error: float
    f5_generation_error: float
    f5_initial_purity: float
    f5_final_purity: float
    natural_constant_lower: Decimal
    natural_constant_upper: Decimal
    global_reset_constants: tuple[tuple[int, int], ...]
    global_reset_gain_costs: tuple[GainCostReport, ...]

    def matches_reference_expectations(self, tolerance: float) -> bool:
        expected_rank_count = sum(5**length for length in range(5))
        expected_reset_constants = tuple((n, 2**n) for n in range(1, 9))
        natural_interval_ok = Decimal(
            1
        ) < self.natural_constant_lower <= self.natural_constant_upper < Decimal(
            2
        ) and self.natural_constant_upper - self.natural_constant_lower < Decimal(
            "1e-29"
        )
        gain_cost_expected = all(
            report.outcome is CheckOutcome.FAIL
            and all(
                syntax.suggested_condition_satisfied for syntax in report.syntax_reports
            )
            for report in self.global_reset_gain_costs
        )
        return (
            self.rank_roundtrip_count == expected_rank_count
            and self.rank_roundtrip_failures == 0
            and self.gamma5_reference_balance_error <= tolerance
            and len(self.gamma5_word_average_errors) == 5
            and max(self.gamma5_word_average_errors, default=0.0) <= tolerance
            and self.gamma5_partial_kraft_mass <= 1.0 + tolerance
            and self.f5_reset_balance_error <= tolerance
            and self.f5_generation_error <= tolerance
            and abs(self.f5_initial_purity - 0.25) <= tolerance
            and abs(self.f5_final_purity - 1.0) <= tolerance
            and natural_interval_ok
            and self.global_reset_constants == expected_reset_constants
            and len(self.global_reset_gain_costs) == 4
            and gain_cost_expected
        )


@dataclass(frozen=True)
class ReferenceSuite:
    """One deterministic execution of the bundled RCC reference suite."""

    max_depth: int
    max_transient_steps: int
    tolerance: float
    cases: tuple[CaseAnalysis, ...]
    appendix_f: AppendixFWitnesses

    @property
    def matches_reference_expectations(self) -> bool:
        return all(case.matches_expectations for case in self.cases) and (
            self.appendix_f.matches_reference_expectations(self.tolerance)
        )


def _aggregate_outcomes(outcomes: Iterable[CheckOutcome]) -> CheckOutcome:
    values = tuple(outcomes)
    if not values or all(value is CheckOutcome.NOT_APPLICABLE for value in values):
        return CheckOutcome.NOT_APPLICABLE
    if any(value is CheckOutcome.FAIL for value in values):
        return CheckOutcome.FAIL
    if any(value is CheckOutcome.INCONCLUSIVE for value in values):
        return CheckOutcome.INCONCLUSIVE
    return CheckOutcome.PASS


def audit_model(
    model: FiniteControlModel,
    *,
    max_depth: int = 8,
    max_transient_steps: int = 16,
    tol: float = 1e-10,
) -> ModelAnalysis:
    """Compute bounded H.1 checks, H.2 diagnostics, and the H.34 constant."""

    if max_depth < 1:
        raise ValueError("max_depth must be at least one")
    if max_transient_steps < 0:
        raise ValueError("max_transient_steps must be nonnegative")
    if not np.isfinite(tol) or tol <= 0:
        raise ValueError("tol must be finite and positive")
    require_valid_model(model, tol=tol)

    realization: list[DepthAgreement] = []
    for depth in range(1, max_depth + 1):
        enumerated = depth_contribution_by_enumeration(model, depth)
        realized = depth_contribution_by_maps(model, depth)
        error = float(np.linalg.norm(enumerated - realized, ord=2))
        realization.append(
            DepthAgreement(
                action_depth=depth,
                spectral_norm_error=error,
                outcome=(CheckOutcome.PASS if error <= tol else CheckOutcome.FAIL),
            )
        )

    truncated = truncated_semidensity(model, max_transient_steps)
    fixed = linear_fixed_point(model, tol=tol)
    fixed_outcome = _linear_fixed_point_outcome(fixed, tol)
    domination = (
        minimum_domination_constant(fixed.output, model.reference_state, tol=tol)
        if fixed_outcome is CheckOutcome.PASS and fixed.output is not None
        else None
    )
    notes = [
        "Finite-depth agreement provides numerical implementation evidence for H.1.",
        "The H.34 constant belongs to this fixed model; family uniformity adds a uniform analytic bound.",
    ]
    if not fixed.applicable:
        notes.append(
            "The linear inverse is at its spectral boundary. The minimum fixed-point "
            "semantics remains in force, and H.34 awaits the completed semidensity."
        )
    elif fixed_outcome is CheckOutcome.INCONCLUSIVE:
        notes.append(
            "The linear solve is inconclusive at this tolerance; inspect its condition "
            "number and residual."
        )

    return ModelAnalysis(
        model_name=model.name,
        tolerance=float(tol),
        realization_checks=tuple(realization),
        max_transient_steps=max_transient_steps,
        truncated_trace=float(np.trace(truncated).real),
        fixed_point=fixed,
        fixed_model_domination=domination,
        notes=tuple(notes),
        truncated_output=truncated,
    )


def audit_case(
    case: CaseStudy,
    *,
    max_depth: int = 8,
    max_transient_steps: int = 16,
    tol: float = 1e-10,
) -> CaseAnalysis:
    """Run the process and every supplied proof object for one bundled case."""

    model = case.model_factory()
    model_analysis = audit_model(
        model,
        max_depth=max_depth,
        max_transient_steps=max_transient_steps,
        tol=tol,
    )
    bellman = (
        verify_bellman_choi(model, case.bellman_factory(model), tol=tol)
        if case.bellman_factory is not None
        else None
    )
    potentials = (
        tuple(
            verify_reference_potential(model, certificate, tol=tol)
            for certificate in case.potential_factory(model)
        )
        if case.potential_factory is not None
        else ()
    )
    gain_cost = (
        analyze_reference_gain_cost(model, case.envelope_factory(model), tol=tol)
        if case.envelope_factory is not None
        else None
    )
    return CaseAnalysis(
        case=case,
        model=model,
        model_analysis=model_analysis,
        bellman_choi=bellman,
        reference_potentials=potentials,
        gain_cost=gain_cost,
    )


def _appendix_f_witnesses(tol: float) -> AppendixFWitnesses:
    gamma = 5
    rank_count = 0
    rank_failures = 0
    for length in range(5):
        for word in itertools.product(range(gamma), repeat=length):
            rank_count += 1
            if decode_word(encode_word(word, gamma), gamma) != word:
                rank_failures += 1

    gamma5 = gamma5_summary(5)
    f5 = make_f5_two_qubit_witness()
    lower, upper = natural_c_gt_one_interval(100)

    reset_reports = []
    for n in range(1, 5):
        model = make_global_reset_loop_model(n)
        reset_reports.append(
            analyze_reference_gain_cost(
                model,
                make_same_space_reference_envelopes(model),
                tol=tol,
            )
        )

    return AppendixFWitnesses(
        rank_roundtrip_count=rank_count,
        rank_roundtrip_failures=rank_failures,
        gamma5_reference_balance_error=gamma5.reference_balance_error,
        gamma5_word_average_errors=gamma5.word_average_errors,
        gamma5_partial_kraft_mass=gamma5.partial_kraft_mass,
        f5_reset_balance_error=max(f5.reset_pair_balance_errors),
        f5_generation_error=f5.generation_error,
        f5_initial_purity=f5.initial_purity,
        f5_final_purity=f5.final_purity,
        natural_constant_lower=lower,
        natural_constant_upper=upper,
        global_reset_constants=tuple(global_reset_family_constants(8)),
        global_reset_gain_costs=tuple(reset_reports),
    )


def audit_reference_suite(
    *,
    max_depth: int = 8,
    max_transient_steps: int = 16,
    tol: float = 1e-10,
) -> ReferenceSuite:
    """Run every bundled case and Appendix F witness deterministically."""

    cases = tuple(
        audit_case(
            case,
            max_depth=max_depth,
            max_transient_steps=max_transient_steps,
            tol=tol,
        )
        for case in CASES
    )
    return ReferenceSuite(
        max_depth=max_depth,
        max_transient_steps=max_transient_steps,
        tolerance=float(tol),
        cases=cases,
        appendix_f=_appendix_f_witnesses(tol),
    )
