from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .domination import minimum_domination_constant
from .model import BlockKey, FiniteControlModel, require_valid_model
from .prefix import is_prefix_free
from .quantum import Array, apply_kraus, is_density_matrix, min_hermitian_eigenvalue
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


@dataclass(frozen=True)
class SyntaxGainCost:
    """H.70 sums and the H.76 completion for one syntax state."""

    syntax_state: str
    current_weighted_sum: float
    suggested_weighted_sum: float
    current_condition_satisfied: bool
    suggested_condition_satisfied: bool
    actions: tuple[ActionGainCost, ...]


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
) -> GainCostReport:
    return GainCostReport(
        model_name=model.name,
        outcome=CheckOutcome.FAIL,
        syntax_reports=(),
        initial_coefficients={},
        fixed_model_initial_constant=None,
        checks=[CheckResult(name, CheckOutcome.FAIL, message)],
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


def _suggested_length(action_count: int, gain: float, tol: float) -> int:
    base = math.ceil(math.log2(max(2, action_count)))
    log_gain = math.log2(max(1.0, gain))
    nearest_integer = round(log_gain)
    gain_cost = (
        int(nearest_integer)
        if abs(log_gain - nearest_integer) <= tol
        else math.ceil(log_gain)
    )
    return base + gain_cost


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
    current_rejected = False

    for syntax_state in sorted(model.syntax_states):
        actions = model.actions_by_syntax[syntax_state]
        gains_by_action: dict[str, tuple[float, dict[str, float]]] = {}
        lengths: dict[str, int] = {}

        for action in actions:
            control_gains: dict[str, float] = {}
            for source_control in sorted(model.control_dims):
                source_key = (syntax_state, source_control)
                source_theta = envelopes[source_key]
                if action.is_halt:
                    output = apply_kraus(
                        action.halt_kraus[source_control], source_theta
                    )
                    gain = minimum_domination_constant(
                        output, model.reference_state, tol=tol
                    ).constant
                else:
                    assert action.successor is not None
                    gain = 0.0
                    for target_control in sorted(model.control_dims):
                        kraus = action.continue_kraus.get(
                            (source_control, target_control), ()
                        )
                        if not kraus:
                            continue
                        output = apply_kraus(kraus, source_theta)
                        target_theta = envelopes[(action.successor, target_control)]
                        gain += minimum_domination_constant(
                            output, target_theta, tol=tol
                        ).constant
                if not np.isfinite(gain):
                    return _rejected_report(
                        model,
                        f"reference-gain[{syntax_state},{action.name},{source_control}]",
                        "reference gain is not finite on the supplied supports",
                    )
                control_gains[source_control] = float(gain)

            reference_gain = max(control_gains.values())
            gains_by_action[action.name] = (reference_gain, control_gains)
            lengths[action.name] = _suggested_length(len(actions), reference_gain, tol)

        suggested_codes = _canonical_codebook(lengths)
        action_reports: list[ActionGainCost] = []
        current_sum = 0.0
        suggested_sum = 0.0
        for action in actions:
            gain, control_gains = gains_by_action[action.name]
            effective_gain = max(1.0, gain)
            current_sum += 2.0 ** (-action.code_length) * effective_gain
            suggested_sum += 2.0 ** (-lengths[action.name]) * effective_gain
            action_reports.append(
                ActionGainCost(
                    syntax_state=syntax_state,
                    action_name=action.name,
                    current_codeword=action.codeword,
                    reference_gain=gain,
                    control_gains=control_gains,
                    suggested_code_length=lengths[action.name],
                    suggested_codeword=suggested_codes[action.name],
                )
            )

        current_ok = current_sum <= 1.0 + tol
        suggested_ok = suggested_sum <= 1.0 + tol
        current_rejected |= not current_ok
        checks.append(
            CheckResult(
                f"H.70-current[{syntax_state}]",
                CheckOutcome.PASS if current_ok else CheckOutcome.FAIL,
                "actual local codewords satisfy the gain-weighted Kraft condition"
                if current_ok
                else "actual local codewords violate this sufficient H.70 certificate",
                float(current_sum),
                tol,
            )
        )
        checks.append(
            CheckResult(
                f"H.76-suggested[{syntax_state}]",
                CheckOutcome.PASS if suggested_ok else CheckOutcome.FAIL,
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
            )
        )

    initial = model.initial_transient_state()
    initial_coefficients: dict[BlockKey, float] = {}
    for key in model.transient_keys():
        coefficient = minimum_domination_constant(
            initial[key], envelopes[key], tol=tol
        ).constant
        initial_coefficients[key] = float(coefficient)
    fixed_constant = float(sum(initial_coefficients.values()))
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

    return GainCostReport(
        model_name=model.name,
        outcome=CheckOutcome.FAIL if current_rejected else CheckOutcome.PASS,
        syntax_reports=tuple(syntax_reports),
        initial_coefficients=initial_coefficients,
        fixed_model_initial_constant=fixed_constant,
        checks=checks,
    )
