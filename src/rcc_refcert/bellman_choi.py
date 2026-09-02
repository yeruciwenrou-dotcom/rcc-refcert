from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

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


@dataclass
class BellmanChoiCertificate:
    """Supplied fixed-model H.3 proof object.

    ``choi_envelopes[x]`` is ``X_x = J(W_x)`` in the RCC paper's
    input-tensor-output convention.  This object does not include a solver or
    a model-family proof.
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
        scale = math.sqrt(2.0 ** (-action.code_length))
        for matrix in action.continue_kraus.get((source_control, target_control), ()):
            matrices.append(scale * np.asarray(matrix, dtype=complex))
    return tuple(matrices)


def _weighted_halt_kraus(
    model: FiniteControlModel, source: BlockKey
) -> tuple[Array, ...]:
    syntax_state, source_control = source
    matrices: list[Array] = []
    for action in model.actions_by_syntax[syntax_state]:
        if not action.is_halt:
            continue
        scale = math.sqrt(2.0 ** (-action.code_length))
        for matrix in action.halt_kraus[source_control]:
            matrices.append(scale * np.asarray(matrix, dtype=complex))
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

    The outcome and its numerical evidence level are reported separately. A
    passing report does not certify complete TC or model-family uniformity.
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

    for source in keys:
        source_dim = model.control_dims[source[1]]
        halt_kraus = _weighted_halt_kraus(model, source)
        halt_choi = (
            choi_from_kraus(halt_kraus)
            if halt_kraus
            else _zero_choi(source_dim, model.output_dim)
        )
        future = _zero_choi(source_dim, model.output_dim)
        for target in keys:
            transition_kraus = _weighted_continue_kraus(model, source, target)
            if not transition_kraus:
                continue
            target_dim = model.control_dims[target[1]]
            future += precompose_choi_with_kraus(
                envelopes[target],
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

    status = CheckOutcome.FAIL if rejected else CheckOutcome.PASS
    return BellmanChoiReport(
        certificate.name, status, float(certificate.constant), checks
    )
