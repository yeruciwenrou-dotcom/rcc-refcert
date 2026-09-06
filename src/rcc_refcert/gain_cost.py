from __future__ import annotations

import math
from dataclasses import dataclass, field
from fractions import Fraction

import numpy as np

from .gain_bounds import GainBounds, branch_gain_bounds, ceil_log2, upper_float
from .model import BlockKey, FiniteControlModel, require_valid_model
from .prefix import is_prefix_free
from .quantum import Array, is_density_matrix, min_hermitian_eigenvalue
from .status import CheckOutcome, CheckResult, EvidenceLevel


@dataclass(frozen=True)
class ActionGainCost:
    """One action's fixed-model quantities from Appendix-H Eqs. (H.67)--(H.76)."""

    syntax_state: str
    action_name: str
    current_codeword: str
    reference_gain: float
    control_gains: dict[str, float] = field(repr=False, compare=False)
    suggested_code_length: int = 0
    suggested_codeword: str = ""
    reference_gain_upper: float | None = None


@dataclass(frozen=True)
class SyntaxGainCost:
    """H.70 sums and the H.76 completion for one syntax state."""

    syntax_state: str
    current_weighted_sum: float
    suggested_weighted_sum: float
    current_condition_satisfied: bool
    suggested_condition_satisfied: bool
    actions: tuple[ActionGainCost, ...]
    current_outcome: CheckOutcome = CheckOutcome.INCONCLUSIVE
    suggested_outcome: CheckOutcome = CheckOutcome.INCONCLUSIVE
    current_weighted_sum_upper: float | None = None
    suggested_weighted_sum_upper: float | None = None


@dataclass
class GainCostReport:
    """Numerical H.6 analysis of supplied envelopes and actual local codewords.

    ``outcome`` concerns the current codewords. Suggested codewords are an
    explicit H.76 re-encoding witness, not a mutation of the supplied model.
    Family-uniformity and faithful transcription of the re-encoding remain
    separate analytic obligations.
    """

    model_name: str
    outcome: CheckOutcome
    syntax_reports: tuple[SyntaxGainCost, ...]
    initial_coefficients: dict[BlockKey, float]
    fixed_model_initial_constant: float | None
    constant: float | None = None
    checks: list[CheckResult] = field(default_factory=list)
    caveat: str = (
        "H.70 is a sufficient local gain–cost condition. Rejection does not "
        "establish failure of RA; H.72 family uniformity and TC are not inferred."
    )
    evidence: EvidenceLevel = EvidenceLevel.NUMERICAL


def _canonical_codebook(lengths: dict[str, int]) -> dict[str, str]:
    """Construct a deterministic canonical prefix code with prescribed lengths."""
    ordered = sorted(lengths.items(), key=lambda item: (item[1], item[0]))
    code = 0
    previous_length = 0
    result: dict[str, str] = {}
    for name, length in ordered:
        if length <= 0:
            raise ValueError("prefix-code lengths must be positive")
        code <<= length - previous_length
        if code >= 2**length:
            raise ValueError("prescribed lengths violate the Kraft inequality")
        result[name] = format(code, f"0{length}b")
        code += 1
        previous_length = length
    if not is_prefix_free(result.values()):  # pragma: no cover - construction guard
        raise RuntimeError("canonical prefix-code construction failed")
    return result


def _rejected_report(
    model: FiniteControlModel,
    name: str,
    message: str,
    outcome: CheckOutcome = CheckOutcome.FAIL,
) -> GainCostReport:
    return GainCostReport(
        model_name=model.name,
        outcome=outcome,
        syntax_reports=(),
        initial_coefficients={},
        fixed_model_initial_constant=None,
        checks=[CheckResult(name, outcome, message)],
    )


def _normalize_envelopes(
    model: FiniteControlModel,
    theta: dict[BlockKey, Array],
    tol: float,
) -> tuple[dict[BlockKey, Array] | None, GainCostReport | None]:
    keys = model.transient_keys()
    key_set = set(keys)
    missing = [key for key in keys if key not in theta]
    extra = sorted(set(theta) - key_set)
    if missing or extra:
        return None, _rejected_report(
            model,
            "envelope-domain",
            f"missing envelope blocks={missing}, undeclared envelope blocks={extra}",
        )

    normalized: dict[BlockKey, Array] = {}
    for key in keys:
        matrix = np.asarray(theta[key], dtype=complex)
        dim = model.control_dims[key[1]]
        if matrix.shape != (dim, dim):
            return None, _rejected_report(
                model,
                f"theta[{key}]",
                f"shape {matrix.shape} does not match {(dim, dim)}",
            )
        if not np.all(np.isfinite(matrix)):
            return None, _rejected_report(
                model, f"theta[{key}]", "envelope contains non-finite entries"
            )
        if not is_density_matrix(matrix, tol=tol):
            return None, _rejected_report(
                model, f"theta[{key}]", "envelope is not a density matrix"
            )
        minimum = min_hermitian_eigenvalue(matrix)
        if minimum <= tol:
            return None, _rejected_report(
                model,
                f"theta[{key}]",
                "envelope is not numerically full rank on its declared block",
            )
        normalized[key] = matrix
    return normalized, None


def _weighted_outcome(lower: Fraction, upper: Fraction) -> CheckOutcome:
    if upper <= 1:
        return CheckOutcome.PASS
    if lower > 1:
        return CheckOutcome.FAIL
    return CheckOutcome.INCONCLUSIVE


def analyze_reference_gain_cost(
    model: FiniteControlModel,
    theta: dict[BlockKey, Array],
    tol: float = 1e-10,
) -> GainCostReport:
    """Evaluate the fixed-model H.6 gain--cost condition and H.76 completion.

    Physical branch maps are evaluated without code weights to obtain
    Eqs. (H.67)--(H.69).  Actual local code lengths are then used exactly once
    in Eq. (H.70).  The function also constructs deterministic local prefix
    codewords at the sufficient H.76 lengths and evaluates the fixed-model
    initial coefficients in H.72.
    """
    require_valid_model(model, tol=tol)
    envelopes, rejected_report = _normalize_envelopes(model, theta, tol)
    if rejected_report is not None:
        return rejected_report
    assert envelopes is not None

    checks: list[CheckResult] = []
    syntax_reports: list[SyntaxGainCost] = []
    current_outcomes: list[CheckOutcome] = []

    for syntax_state in sorted(model.syntax_states):
        actions = model.actions_by_syntax[syntax_state]
        gains_by_action: dict[str, tuple[GainBounds, dict[str, float]]] = {}
        lengths: dict[str, int] = {}

        for action in actions:
            control_gains: dict[str, float] = {}
            control_bounds: list[GainBounds] = []
            for source_control in sorted(model.control_dims):
                source_key = (syntax_state, source_control)
                source_theta = envelopes[source_key]
                if action.is_halt:
                    branches = [
                        (action.halt_kraus[source_control], model.reference_state)
                    ]
                else:
                    assert action.successor is not None
                    branches = []
                    for target_control in sorted(model.control_dims):
                        kraus = action.continue_kraus.get(
                            (source_control, target_control), ()
                        )
                        if not kraus:
                            continue
                        target_theta = envelopes[(action.successor, target_control)]
                        branches.append((kraus, target_theta))
                bounds = [
                    branch_gain_bounds(kraus, source_theta, target)
                    for kraus, target in branches
                ]
                if any(bound is None for bound in bounds):
                    return _rejected_report(
                        model,
                        f"reference-gain[{syntax_state},{action.name},{source_control}]",
                        "reference gain has no resolved numerical upper bound",
                        CheckOutcome.INCONCLUSIVE,
                    )
                resolved = [bound for bound in bounds if bound is not None]
                combined = GainBounds(
                    math.fsum(bound.estimate for bound in resolved),
                    sum((bound.lower for bound in resolved), Fraction(0)),
                    sum((bound.upper for bound in resolved), Fraction(0)),
                )
                control_gains[source_control] = combined.estimate
                control_bounds.append(combined)

            reference_gain = GainBounds(
                max(control_gains.values()),
                max(bound.lower for bound in control_bounds),
                max(bound.upper for bound in control_bounds),
            )
            gains_by_action[action.name] = (reference_gain, control_gains)
            lengths[action.name] = ceil_log2(
                Fraction(max(2, len(actions)))
            ) + ceil_log2(reference_gain.upper)

        suggested_codes = _canonical_codebook(lengths)
        action_reports: list[ActionGainCost] = []
        current_sum = Fraction(0)
        suggested_sum = Fraction(0)
        current_lower = current_upper = suggested_lower = suggested_upper = Fraction(0)
        for action in actions:
            gain, control_gains = gains_by_action[action.name]
            effective_gain = max(Fraction(1), Fraction(gain.estimate))
            current_weight = Fraction(1, 2**action.code_length)
            suggested_weight = Fraction(1, 2 ** lengths[action.name])
            current_sum += current_weight * effective_gain
            suggested_sum += suggested_weight * effective_gain
            current_lower += current_weight * max(1, gain.lower)
            current_upper += current_weight * max(1, gain.upper)
            suggested_lower += suggested_weight * max(1, gain.lower)
            suggested_upper += suggested_weight * max(1, gain.upper)
            action_reports.append(
                ActionGainCost(
                    syntax_state=syntax_state,
                    action_name=action.name,
                    current_codeword=action.codeword,
                    reference_gain=gain.estimate,
                    reference_gain_upper=upper_float(gain.upper),
                    control_gains=control_gains,
                    suggested_code_length=lengths[action.name],
                    suggested_codeword=suggested_codes[action.name],
                )
            )

        current_outcome = _weighted_outcome(current_lower, current_upper)
        suggested_outcome = _weighted_outcome(suggested_lower, suggested_upper)
        current_ok = current_outcome is CheckOutcome.PASS
        suggested_ok = suggested_outcome is CheckOutcome.PASS
        current_outcomes.append(current_outcome)
        checks.append(
            CheckResult(
                f"H.70-current[{syntax_state}]",
                current_outcome,
                "actual local codewords satisfy the gain-weighted Kraft condition"
                if current_ok
                else (
                    "actual local codewords violate this sufficient H.70 certificate"
                    if current_outcome is CheckOutcome.FAIL
                    else "gain uncertainty overlaps the H.70 boundary; the condition is unresolved"
                ),
                float(current_sum),
                tol,
            )
        )
        checks.append(
            CheckResult(
                f"H.76-suggested[{syntax_state}]",
                suggested_outcome,
                "constructed prefix code satisfies the H.76 sufficient completion",
                float(suggested_sum),
                tol,
            )
        )
        if not suggested_ok:  # pragma: no cover - mathematical guard
            raise RuntimeError("H.76 construction failed its gain-weighted Kraft check")
        syntax_reports.append(
            SyntaxGainCost(
                syntax_state=syntax_state,
                current_weighted_sum=float(current_sum),
                suggested_weighted_sum=float(suggested_sum),
                current_condition_satisfied=current_ok,
                suggested_condition_satisfied=suggested_ok,
                actions=tuple(action_reports),
                current_outcome=current_outcome,
                suggested_outcome=suggested_outcome,
                current_weighted_sum_upper=upper_float(current_upper),
                suggested_weighted_sum_upper=upper_float(suggested_upper),
            )
        )

    initial = model.initial_transient_state()
    initial_coefficients: dict[BlockKey, float] = {}
    for key in model.transient_keys():
        coefficient = branch_gain_bounds(
            (np.eye(len(initial[key])),), initial[key], envelopes[key]
        )
        if coefficient is None:
            return _rejected_report(
                model,
                "H.72-fixed-model-initial",
                "initial domination has no resolved numerical upper bound",
                CheckOutcome.INCONCLUSIVE,
            )
        initial_coefficients[key] = upper_float(coefficient.upper)
    fixed_constant = upper_float(
        sum((Fraction(x) for x in initial_coefficients.values()), Fraction(0))
    )
    checks.append(
        CheckResult(
            "H.72-fixed-model-initial",
            CheckOutcome.PASS,
            "fixed-model initial blocks are dominated by the supplied envelopes; "
            "family-uniform boundedness is a separate analytic obligation",
            fixed_constant,
            tol,
        )
    )

    outcome = (
        CheckOutcome.FAIL
        if CheckOutcome.FAIL in current_outcomes
        else CheckOutcome.INCONCLUSIVE
        if CheckOutcome.INCONCLUSIVE in current_outcomes
        else CheckOutcome.PASS
    )
    return GainCostReport(
        model_name=model.name,
        outcome=outcome,
        syntax_reports=tuple(syntax_reports),
        initial_coefficients=initial_coefficients,
        fixed_model_initial_constant=fixed_constant,
        constant=fixed_constant if outcome is CheckOutcome.PASS else None,
        checks=checks,
    )
