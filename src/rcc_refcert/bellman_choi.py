from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .certificate_error import (
    accepted_constant,
    final_constant_check,
    psd_deficit,
    reference_floor,
    residual_correction,
    roundoff_allowance,
)
from .model import BlockKey, FiniteControlModel, require_valid_model
from .quantum import (
    Array,
    apply_choi_map,
    choi_from_kraus,
    hermiticity_error,
    min_hermitian_eigenvalue,
    precompose_choi_with_kraus,
)
from .status import CheckOutcome, CheckResult, EvidenceLevel
from .weights import code_weight, weighted_operator


@dataclass
class BellmanChoiCertificate:
    """Supplied fixed-model H.3 proof object.

    ``choi_envelopes[x]`` is ``X_x = J(W_x)`` in the RCC paper's
    input-tensor-output convention.
    """

    choi_envelopes: dict[BlockKey, Array]
    constant: float
    name: str = "bellman-choi-certificate"


@dataclass
class BellmanChoiReport:
    """Outcome and residual checks for one supplied H.3 certificate."""

    name: str
    outcome: CheckOutcome
    constant: float | None
    checks: list[CheckResult] = field(default_factory=list)
    evidence: EvidenceLevel = EvidenceLevel.NUMERICAL
    candidate_constant: float | None = None
    constant_error_bound: float | None = None


def _weighted_continue_kraus(
    model: FiniteControlModel,
    source: BlockKey,
    target: BlockKey,
) -> tuple[Array, ...]:
    source_syntax, source_control = source
    target_syntax, target_control = target
    matrices: list[Array] = []
    for action in model.actions_by_syntax[source_syntax]:
        if action.is_halt or action.successor != target_syntax:
            continue
        scale = math.sqrt(code_weight(action.code_length))
        for matrix in action.continue_kraus.get((source_control, target_control), ()):
            matrices.append(weighted_operator(scale, np.asarray(matrix, dtype=complex)))
    return tuple(matrices)


def _weighted_halt_kraus(
    model: FiniteControlModel, source: BlockKey
) -> tuple[Array, ...]:
    syntax_state, source_control = source
    matrices: list[Array] = []
    for action in model.actions_by_syntax[syntax_state]:
        if not action.is_halt:
            continue
        scale = math.sqrt(code_weight(action.code_length))
        for matrix in action.halt_kraus[source_control]:
            matrices.append(weighted_operator(scale, np.asarray(matrix, dtype=complex)))
    return tuple(matrices)


def _zero_choi(input_dim: int, output_dim: int) -> Array:
    size = input_dim * output_dim
    return np.zeros((size, size), dtype=complex)


def _append_hermitian_psd_checks(
    checks: list[CheckResult],
    name: str,
    matrix: Array,
    tol: float,
) -> bool:
    """Append numerical Hermiticity/PSD checks and return whether rejected."""
    if not np.all(np.isfinite(matrix)):
        checks.append(
            CheckResult(
                f"{name}-finite",
                CheckOutcome.FAIL,
                "matrix contains non-finite entries",
            )
        )
        return True
    herm_error = hermiticity_error(matrix)
    herm_status = CheckOutcome.PASS if herm_error <= tol else CheckOutcome.FAIL
    checks.append(
        CheckResult(
            f"{name}-hermiticity",
            herm_status,
            "matrix is Hermitian in the frozen convention",
            herm_error,
            tol,
            np.asarray(matrix, dtype=complex).copy(),
        )
    )
    minimum = min_hermitian_eigenvalue(matrix)
    psd_status = CheckOutcome.PASS if minimum >= -tol else CheckOutcome.FAIL
    checks.append(
        CheckResult(
            f"{name}-psd",
            psd_status,
            "matrix is positive semidefinite",
            minimum,
            tol,
            np.asarray(matrix, dtype=complex).copy(),
        )
    )
    return herm_status is CheckOutcome.FAIL or psd_status is CheckOutcome.FAIL


def verify_bellman_choi(
    model: FiniteControlModel,
    certificate: BellmanChoiCertificate,
    tol: float = 1e-10,
) -> BellmanChoiReport:
    """Numerically verify the supplied fixed-model conditions H.31--H.33.

    A passing report carries the candidate constant plus its propagated
    numerical correction. Unresolved error budgets return ``inconclusive``.
    """
    require_valid_model(model, tol=tol)
    keys = model.transient_keys()
    key_set = set(keys)
    supplied = set(certificate.choi_envelopes)
    missing = [key for key in keys if key not in supplied]
    extra = sorted(supplied - key_set)
    if missing or extra:
        return BellmanChoiReport(
            certificate.name,
            CheckOutcome.FAIL,
            None,
            [
                CheckResult(
                    "certificate-domain",
                    CheckOutcome.FAIL,
                    f"missing Choi blocks={missing}, undeclared Choi blocks={extra}",
                )
            ],
        )
    if not np.isfinite(certificate.constant) or certificate.constant < 0:
        return BellmanChoiReport(
            certificate.name,
            CheckOutcome.FAIL,
            None,
            [
                CheckResult(
                    "certificate-constant",
                    CheckOutcome.FAIL,
                    f"candidate constant must be finite and nonnegative, got {certificate.constant}",
                )
            ],
        )

    checks: list[CheckResult] = []
    rejected = False
    envelopes: dict[BlockKey, Array] = {}

    for key in keys:
        input_dim = model.control_dims[key[1]]
        expected = input_dim * model.output_dim
        matrix = np.asarray(certificate.choi_envelopes[key], dtype=complex)
        if matrix.shape != (expected, expected):
            return BellmanChoiReport(
                certificate.name,
                CheckOutcome.FAIL,
                None,
                [
                    CheckResult(
                        f"choi-shape[{key}]",
                        CheckOutcome.FAIL,
                        f"shape {matrix.shape} does not match {(expected, expected)}",
                    )
                ],
            )
        if not np.all(np.isfinite(matrix)):
            return BellmanChoiReport(
                certificate.name,
                CheckOutcome.FAIL,
                None,
                [
                    CheckResult(
                        f"choi-finite[{key}]",
                        CheckOutcome.FAIL,
                        "Choi block contains non-finite entries",
                    )
                ],
            )
        envelopes[key] = matrix
        rejected |= _append_hermitian_psd_checks(checks, f"choi[{key}]", matrix, tol)

    sigma_floor = reference_floor(model.reference_state)
    if sigma_floor <= 0:
        checks.append(final_constant_check(float(certificate.constant), None, tol))
        return BellmanChoiReport(
            certificate.name,
            CheckOutcome.INCONCLUSIVE,
            None,
            checks,
            candidate_constant=float(certificate.constant),
        )
    positive_envelopes = {}
    shifts = np.zeros(len(keys))
    transition = np.zeros((len(keys), len(keys)))
    deficits = np.zeros(len(keys))
    for index, key in enumerate(keys):
        matrix = envelopes[key]
        shifts[index] = (
            psd_deficit(matrix, float(np.linalg.norm(matrix, ord=2))) / sigma_floor
        )
        positive_envelopes[key] = matrix + shifts[index] * np.kron(
            np.eye(model.control_dims[key[1]]), model.reference_state
        )

    for source_index, source in enumerate(keys):
        source_dim = model.control_dims[source[1]]
        halt_kraus = _weighted_halt_kraus(model, source)
        halt_choi = (
            choi_from_kraus(halt_kraus)
            if halt_kraus
            else _zero_choi(source_dim, model.output_dim)
        )
        future = _zero_choi(source_dim, model.output_dim)
        corrected_future = future.copy()
        operations = len(halt_kraus) + 1
        for target_index, target in enumerate(keys):
            transition_kraus = _weighted_continue_kraus(model, source, target)
            if not transition_kraus:
                continue
            target_dim = model.control_dims[target[1]]
            operations += len(transition_kraus)
            effect = sum(k.conj().T @ k for k in transition_kraus)
            norm = float(np.linalg.norm(effect, ord=2))
            transition[source_index, target_index] = norm + roundoff_allowance(
                norm, source_dim, len(transition_kraus)
            )
            future += precompose_choi_with_kraus(
                envelopes[target],
                transition_kraus,
                source_dim=source_dim,
                intermediate_dim=target_dim,
                output_dim=model.output_dim,
            )
            corrected_future += precompose_choi_with_kraus(
                positive_envelopes[target],
                transition_kraus,
                source_dim=source_dim,
                intermediate_dim=target_dim,
                output_dim=model.output_dim,
            )
        residual = envelopes[source] - halt_choi - future
        rejected |= _append_hermitian_psd_checks(
            checks,
            f"bellman-residual[{source}]",
            residual,
            tol,
        )
        corrected = positive_envelopes[source] - halt_choi - corrected_future
        scale = sum(
            float(np.linalg.norm(x, ord=2))
            for x in (positive_envelopes[source], halt_choi, corrected_future)
        )
        deficits[source_index] = psd_deficit(corrected, scale, operations) / sigma_floor

    initial = model.initial_transient_state()
    output = np.zeros((model.output_dim, model.output_dim), dtype=complex)
    for key in keys:
        input_dim = model.control_dims[key[1]]
        output += apply_choi_map(
            envelopes[key],
            initial[key],
            input_dim=input_dim,
            output_dim=model.output_dim,
        )
    output_residual = certificate.constant * model.reference_state - output
    rejected |= _append_hermitian_psd_checks(
        checks,
        "output-domination",
        output_residual,
        tol,
    )

    candidate = float(certificate.constant)
    if rejected:
        return BellmanChoiReport(
            certificate.name,
            CheckOutcome.FAIL,
            None,
            checks,
            candidate_constant=candidate,
        )
    propagated = residual_correction(transition, deficits)
    correction = None
    if propagated is not None:
        scale = float(np.linalg.norm(output, ord=2)) + candidate * float(
            np.linalg.norm(model.reference_state, ord=2)
        )
        correction = psd_deficit(output_residual, scale, len(keys)) / sigma_floor
        correction += sum(
            float(np.trace(initial[key]).real) * (shifts[index] + propagated[index])
            for index, key in enumerate(keys)
        )
        if correction > 0:
            correction = float(np.nextafter(candidate + correction, np.inf)) - candidate
    check = final_constant_check(candidate, correction, tol)
    checks.append(check)
    upper, bound = (None, correction)
    if check.outcome is CheckOutcome.PASS:
        upper, bound = accepted_constant(candidate, correction, tol)
    return BellmanChoiReport(
        certificate.name,
        check.outcome,
        upper,
        checks,
        candidate_constant=candidate,
        constant_error_bound=bound,
    )
