from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .model import BlockKey, FiniteControlModel, require_valid_model
from .quantum import Array, apply_kraus, is_density_matrix, min_hermitian_eigenvalue
from .status import CheckOutcome, CheckResult, EvidenceLevel


@dataclass
class ReferencePotentialCertificate:
    """Supplied fixed-model H.4 reference-potential proof object."""

    theta: dict[BlockKey, Array]
    a: dict[BlockKey, float]
    transition_coefficients: dict[tuple[BlockKey, BlockKey], float]
    halt_coefficients: dict[BlockKey, float]
    potential: dict[BlockKey, float]
    name: str = "reference-potential-certificate"


@dataclass
class CertificateReport:
    """Outcome and residual checks for one H.4 proof object."""

    name: str
    outcome: CheckOutcome
    constant: float | None
    checks: list[CheckResult] = field(default_factory=list)
    evidence: EvidenceLevel = EvidenceLevel.NUMERICAL


def _local_transient_image(
    model: FiniteControlModel,
    source_key: BlockKey,
    operator: Array,
) -> dict[BlockKey, Array]:
    syntax_state, source_control = source_key
    output = {
        key: np.zeros(
            (model.control_dims[key[1]], model.control_dims[key[1]]), dtype=complex
        )
        for key in model.transient_keys()
    }
    for action in model.actions_by_syntax[syntax_state]:
        if action.is_halt:
            continue
        assert action.successor is not None
        weight = 2.0 ** (-action.code_length)
        for (q, target), kraus in action.continue_kraus.items():
            if q == source_control:
                output[(action.successor, target)] += weight * apply_kraus(
                    kraus, operator
                )
    return output


def _local_halt_image(
    model: FiniteControlModel, source_key: BlockKey, operator: Array
) -> Array:
    syntax_state, source_control = source_key
    output = np.zeros((model.output_dim, model.output_dim), dtype=complex)
    for action in model.actions_by_syntax[syntax_state]:
        if not action.is_halt:
            continue
        weight = 2.0 ** (-action.code_length)
        output += weight * apply_kraus(action.halt_kraus[source_control], operator)
    return output


def verify_reference_potential(
    model: FiniteControlModel,
    certificate: ReferencePotentialCertificate,
    tol: float = 1e-10,
) -> CertificateReport:
    """Numerically check a supplied fixed-model H.4 certificate."""

    require_valid_model(model, tol=tol)
    keys = model.transient_keys()
    key_set = set(keys)
    checks: list[CheckResult] = []
    rejected = False

    missing_theta = [key for key in keys if key not in certificate.theta]
    missing_a = [key for key in keys if key not in certificate.a]
    missing_b = [key for key in keys if key not in certificate.halt_coefficients]
    missing_v = [key for key in keys if key not in certificate.potential]
    extra_theta = sorted(set(certificate.theta) - key_set)
    extra_a = sorted(set(certificate.a) - key_set)
    extra_b = sorted(set(certificate.halt_coefficients) - key_set)
    extra_v = sorted(set(certificate.potential) - key_set)
    invalid_transitions = sorted(
        edge
        for edge in certificate.transition_coefficients
        if edge[0] not in key_set or edge[1] not in key_set
    )
    if (
        missing_theta
        or missing_a
        or missing_b
        or missing_v
        or extra_theta
        or extra_a
        or extra_b
        or extra_v
        or invalid_transitions
    ):
        message = (
            f"missing theta={missing_theta}, a={missing_a}, b={missing_b}, v={missing_v}; "
            f"extra theta={extra_theta}, a={extra_a}, b={extra_b}, v={extra_v}; "
            f"invalid transitions={invalid_transitions}"
        )
        return CertificateReport(
            name=certificate.name,
            outcome=CheckOutcome.FAIL,
            constant=None,
            checks=[CheckResult("certificate-domain", CheckOutcome.FAIL, message)],
        )

    invalid_scalars = []
    normalized_scalars: dict[str, dict[object, float]] = {}
    for label, mapping in (
        ("a", certificate.a),
        ("b", certificate.halt_coefficients),
        ("v", certificate.potential),
        ("A", certificate.transition_coefficients),
    ):
        normalized: dict[object, float] = {}
        for key, value in mapping.items():
            try:
                scalar = float(value)
            except (TypeError, ValueError, OverflowError):
                invalid_scalars.append(f"{label}[{key}]={value!r}")
                continue
            if not np.isfinite(scalar) or scalar < 0:
                invalid_scalars.append(f"{label}[{key}]={value!r}")
                continue
            normalized[key] = scalar
        normalized_scalars[label] = normalized
    if invalid_scalars:
        return CertificateReport(
            name=certificate.name,
            outcome=CheckOutcome.FAIL,
            constant=None,
            checks=[
                CheckResult(
                    "certificate-domain",
                    CheckOutcome.FAIL,
                    "certificate scalars must be finite, real, and nonnegative: "
                    + ", ".join(invalid_scalars),
                )
            ],
        )

    a_values = normalized_scalars["a"]
    b_values = normalized_scalars["b"]
    v_values = normalized_scalars["v"]
    transition_values = normalized_scalars["A"]

    theta_matrices: dict[BlockKey, Array] = {}
    for key in keys:
        theta = np.asarray(certificate.theta[key], dtype=complex)
        expected_dim = model.control_dims[key[1]]
        if theta.shape != (expected_dim, expected_dim):
            rejected = True
            checks.append(
                CheckResult(
                    f"theta[{key}]",
                    CheckOutcome.FAIL,
                    f"theta shape {theta.shape} does not match {(expected_dim, expected_dim)}",
                )
            )
        elif not np.all(np.isfinite(theta)):
            rejected = True
            checks.append(
                CheckResult(
                    f"theta[{key}]",
                    CheckOutcome.FAIL,
                    "theta contains non-finite entries",
                )
            )
        elif not is_density_matrix(theta, tol=tol):
            rejected = True
            checks.append(
                CheckResult(
                    f"theta[{key}]",
                    CheckOutcome.FAIL,
                    "theta is not a density matrix",
                )
            )
        elif min_hermitian_eigenvalue(theta) <= tol:
            rejected = True
            checks.append(
                CheckResult(
                    f"theta[{key}]",
                    CheckOutcome.FAIL,
                    "theta is not numerically certifiable as full rank on the declared block support",
                    min_hermitian_eigenvalue(theta),
                    tol,
                )
            )
        else:
            theta_matrices[key] = theta
            checks.append(
                CheckResult(
                    f"theta[{key}]",
                    CheckOutcome.PASS,
                    "theta is normalized and full-rank PSD",
                )
            )

    if rejected:
        return CertificateReport(certificate.name, CheckOutcome.FAIL, None, checks)

    initial = model.initial_transient_state()
    for key in keys:
        a = a_values[key]
        with np.errstate(over="ignore", invalid="ignore"):
            residual = a * theta_matrices[key] - initial[key]
        if not np.all(np.isfinite(residual)):
            rejected = True
            checks.append(
                CheckResult(
                    f"initial-domination[{key}]",
                    CheckOutcome.FAIL,
                    "initial-domination residual is non-finite",
                )
            )
            continue
        minimum = min_hermitian_eigenvalue(residual)
        status = CheckOutcome.PASS if minimum >= -tol else CheckOutcome.FAIL
        rejected |= status is CheckOutcome.FAIL
        checks.append(
            CheckResult(
                f"initial-domination[{key}]",
                status,
                "Omega_x <= a_x Theta_x",
                minimum,
                tol,
                residual.copy(),
            )
        )

    for source in keys:
        local = _local_transient_image(model, source, theta_matrices[source])
        for target in keys:
            coefficient = transition_values.get((source, target), 0.0)
            with np.errstate(over="ignore", invalid="ignore"):
                residual = coefficient * theta_matrices[target] - local[target]
            if not np.all(np.isfinite(residual)):
                rejected = True
                checks.append(
                    CheckResult(
                        f"transition-domination[{source}->{target}]",
                        CheckOutcome.FAIL,
                        "transition-domination residual is non-finite",
                    )
                )
                continue
            minimum = min_hermitian_eigenvalue(residual)
            status = CheckOutcome.PASS if minimum >= -tol else CheckOutcome.FAIL
            rejected |= status is CheckOutcome.FAIL
            checks.append(
                CheckResult(
                    f"transition-domination[{source}->{target}]",
                    status,
                    "T_{y<-x}(Theta_x) <= A_{x->y} Theta_y",
                    minimum,
                    tol,
                    residual.copy(),
                )
            )

        halt_image = _local_halt_image(model, source, theta_matrices[source])
        coefficient = b_values[source]
        with np.errstate(over="ignore", invalid="ignore"):
            residual = coefficient * model.reference_state - halt_image
        if not np.all(np.isfinite(residual)):
            rejected = True
            checks.append(
                CheckResult(
                    f"halt-domination[{source}]",
                    CheckOutcome.FAIL,
                    "halt-domination residual is non-finite",
                )
            )
        else:
            minimum = min_hermitian_eigenvalue(residual)
            status = CheckOutcome.PASS if minimum >= -tol else CheckOutcome.FAIL
            rejected |= status is CheckOutcome.FAIL
            checks.append(
                CheckResult(
                    f"halt-domination[{source}]",
                    status,
                    "H_x(Theta_x) <= b_x sigma_R",
                    minimum,
                    tol,
                    residual.copy(),
                )
            )

        v_source = v_values[source]
        with np.errstate(over="ignore", invalid="ignore"):
            rhs = float(
                coefficient
                + sum(
                    transition_values.get((source, target), 0.0) * v_values[target]
                    for target in keys
                )
            )
        if not np.isfinite(rhs):
            rejected = True
            checks.append(
                CheckResult(
                    f"bellman[{source}]",
                    CheckOutcome.FAIL,
                    "Bellman right-hand side is non-finite",
                )
            )
            continue
        margin = float(v_source - rhs)
        status = CheckOutcome.PASS if margin >= -tol else CheckOutcome.FAIL
        rejected |= status is CheckOutcome.FAIL
        checks.append(
            CheckResult(
                f"bellman[{source}]",
                status,
                "v_x >= b_x + sum_y A_{x->y} v_y",
                margin,
                tol,
            )
        )

    with np.errstate(over="ignore", invalid="ignore"):
        constant = float(sum(a_values[key] * v_values[key] for key in keys))
    if not np.isfinite(constant):
        rejected = True
        checks.append(
            CheckResult(
                "certificate-constant",
                CheckOutcome.FAIL,
                "computed reference-potential constant is non-finite",
            )
        )
        return CertificateReport(certificate.name, CheckOutcome.FAIL, None, checks)
    status = CheckOutcome.FAIL if rejected else CheckOutcome.PASS
    return CertificateReport(certificate.name, status, constant, checks)
