from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .certificate_error import roundoff_allowance
from .domination import _validate_semidensity
from .limits import DEFAULT_LIMITS, ComputationLimits
from .model import BlockKey, FiniteControlModel, require_valid_model
from .quantum import Array, choi_from_linear_map, unvec, vec
from .semantics import block_slices, flatten_state, halt_matrix, transient_matrix
from .weights import code_weight


@dataclass(frozen=True)
class FixedPointResult:
    """Result of the optional full-space linear fixed-point calculation."""

    spectral_radius: float
    output: Array | None
    applicable: bool
    message: str
    condition_number: float | None = None
    solve_residual: float | None = None
    output_valid: bool | None = None
    assembly_error_estimate: float | None = None
    output_error_estimate: float | None = None


def _assembly_error(model: FiniteControlModel, *, halt: bool) -> float:
    """Working-precision allowance for the basis-assembled superoperator.

    The absolute Kraus superoperator has Frobenius norm ||K||_F^2.
    Sum these scales before cancellation; include both matrix products,
    Kraus sums, action weighting and accumulation in the operation count.
    """
    scales = []
    terms = 0
    actions = 0
    size = max(model.output_dim, *model.control_dims.values())
    for local_actions in model.actions_by_syntax.values():
        for action in local_actions:
            if action.is_halt != halt:
                continue
            actions += 1
            branches = action.halt_kraus if halt else action.continue_kraus
            for kraus in branches.values():
                for matrix in kraus:
                    terms += 1
                    scales.append(
                        code_weight(action.code_length)
                        * float(np.linalg.norm(matrix, "fro")) ** 2
                    )
    return roundoff_allowance(math.fsum(scales), size, 2 * terms + actions + 1)


def _output_error(
    model: FiniteControlModel,
    system: Array,
    transient: Array,
    halt: Array,
    value: Array,
    omega: Array,
    residual: float,
) -> tuple[float, float | None]:
    """Propagate assembly and solve roundoff through the absolute inverse.

    These are numerical allowances, using the same working-precision model
    as the certificate verifiers; they are not interval-arithmetic proofs.
    """
    size = len(system)
    system_error = _assembly_error(model, halt=False) + roundoff_allowance(
        math.sqrt(size) + float(np.linalg.norm(transient, "fro")), size
    )
    try:
        inverse = np.linalg.solve(system, np.eye(size))
    except np.linalg.LinAlgError:
        return system_error, None
    inverse_norm = float(np.linalg.norm(inverse, ord=2))
    system_norm = float(np.linalg.norm(system, ord=2))
    inverse_defect = float(np.linalg.norm(np.eye(size) - inverse @ system, ord=2))
    inverse_defect += roundoff_allowance(inverse_norm * system_norm + 1, size)
    if not np.isfinite(inverse_defect) or inverse_defect >= 1:
        return system_error, None
    inverse_bound = inverse_norm / (1 - inverse_defect)
    margin = 1 - inverse_bound * system_error
    if not np.isfinite(margin) or margin <= 0:
        return system_error, None
    value_norm = float(np.linalg.norm(value))
    residual_error = roundoff_allowance(
        system_norm * value_norm + float(np.linalg.norm(omega)), size
    )
    value_error = (
        inverse_bound * (residual + residual_error + system_error * value_norm) / margin
    )
    halt_error = _assembly_error(model, halt=True)
    halt_norm = float(np.linalg.norm(halt, ord=2))
    output_error = (halt_norm + halt_error) * value_error + halt_error * value_norm
    output_error += roundoff_allowance(
        halt_norm * value_norm, max(size, model.output_dim**2)
    )
    return system_error, output_error if np.isfinite(output_error) else None


def linear_fixed_point(
    model: FiniteControlModel,
    tol: float = 1e-12,
    *,
    limits: ComputationLimits = DEFAULT_LIMITS,
) -> FixedPointResult:
    """Evaluate ``H(I-T)^(-1) Omega_0`` when the full transient gate passes."""

    if not np.isfinite(tol) or tol <= 0:
        raise ValueError("tol must be finite and positive")
    require_valid_model(model, tol=tol)
    t_matrix = transient_matrix(model, tol=tol, limits=limits)
    h_matrix = halt_matrix(model, tol=tol, limits=limits)
    radius = float(max(abs(np.linalg.eigvals(t_matrix)))) if t_matrix.size else 0.0
    if radius >= 1.0 - tol:
        return FixedPointResult(
            spectral_radius=radius,
            output=None,
            applicable=False,
            message="Neumann/linear inverse is not certified on the full transient space",
        )
    omega = flatten_state(model, model.initial_transient_state())
    system = np.eye(t_matrix.shape[0], dtype=complex) - t_matrix
    try:
        condition_number = float(np.linalg.cond(system))
        value = np.linalg.solve(system, omega)
    except np.linalg.LinAlgError:
        return FixedPointResult(
            spectral_radius=radius,
            output=None,
            applicable=True,
            message="linear system could not be resolved numerically",
        )
    solve_residual = float(np.linalg.norm(system @ value - omega, ord=2))
    assembly_error, output_error = _output_error(
        model, system, t_matrix, h_matrix, value, omega, solve_residual
    )
    output = unvec(h_matrix @ value, model.output_dim)
    output_valid = True
    message = (
        "full transient-space spectral radius is below one; numerical "
        "assembly and solve errors are propagated to the output"
    )
    try:
        _validate_semidensity(output, model.reference_state, tol)
    except ValueError as error:
        output_valid = False
        message = f"linear output is unresolved: {error}"
    if output_valid and (output_error is None or output_error > tol):
        message = "linear output precision is unresolved after assembly and solve error propagation"
    return FixedPointResult(
        spectral_radius=radius,
        output=output,
        applicable=True,
        message=message,
        condition_number=condition_number,
        solve_residual=solve_residual,
        output_valid=output_valid,
        assembly_error_estimate=assembly_error,
        output_error_estimate=output_error,
    )


def linear_value_choi_envelopes(
    model: FiniteControlModel,
    tol: float = 1e-12,
    *,
    limits: ComputationLimits = DEFAULT_LIMITS,
) -> dict[BlockKey, Array]:
    """Construct the minimum H.3 value-map Choi blocks when ``rho(T) < 1``.

    Build numerical candidates from ``H (I-T)^(-1)`` and pass the returned
    blocks through the independent Bellman--Choi verifier.
    """
    if not np.isfinite(tol) or tol <= 0:
        raise ValueError("tol must be finite and positive")
    require_valid_model(model, tol=tol)
    t_matrix = transient_matrix(model, tol=tol, limits=limits)
    h_matrix = halt_matrix(model, tol=tol, limits=limits)
    radius = float(max(abs(np.linalg.eigvals(t_matrix)))) if t_matrix.size else 0.0
    if radius >= 1.0 - tol:
        raise ValueError(
            "minimum value-map construction requires full transient spectral radius below one"
        )

    identity_minus_t = np.eye(t_matrix.shape[0], dtype=complex) - t_matrix
    value_matrix = np.linalg.solve(identity_minus_t.T, h_matrix.T).T
    keys, slices = block_slices(model)
    envelopes: dict[BlockKey, Array] = {}
    for key in keys:
        input_dim = model.control_dims[key[1]]
        local_matrix = value_matrix[:, slices[key]].copy()

        def local_value_map(operator: Array, matrix: Array = local_matrix) -> Array:
            return unvec(matrix @ vec(operator), model.output_dim)

        envelopes[key] = choi_from_linear_map(
            input_dim, model.output_dim, local_value_map
        )
    return envelopes
