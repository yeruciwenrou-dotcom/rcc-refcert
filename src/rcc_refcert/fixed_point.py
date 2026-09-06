from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .domination import _validate_semidensity
from .model import BlockKey, FiniteControlModel, require_valid_model
from .quantum import Array, choi_from_linear_map, unvec, vec
from .semantics import block_slices, flatten_state, halt_matrix, transient_matrix


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


def linear_fixed_point(
    model: FiniteControlModel, tol: float = 1e-12
) -> FixedPointResult:
    """Evaluate ``H(I-T)^(-1) Omega_0`` when the full transient gate passes."""

    if not np.isfinite(tol) or tol <= 0:
        raise ValueError("tol must be finite and positive")
    require_valid_model(model, tol=tol)
    t_matrix = transient_matrix(model)
    h_matrix = halt_matrix(model)
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
    output = unvec(h_matrix @ value, model.output_dim)
    output_valid = True
    message = (
        "full transient-space spectral radius is below one; numerical "
        "conditioning, solve residual and output validity are reported separately"
    )
    try:
        _validate_semidensity(output, model.reference_state, tol)
    except ValueError as error:
        output_valid = False
        message = f"linear output is unresolved: {error}"
    return FixedPointResult(
        spectral_radius=radius,
        output=output,
        applicable=True,
        message=message,
        condition_number=condition_number,
        solve_residual=solve_residual,
        output_valid=output_valid,
    )


def linear_value_choi_envelopes(
    model: FiniteControlModel, tol: float = 1e-12
) -> dict[BlockKey, Array]:
    """Construct the minimum H.3 value-map Choi blocks when ``rho(T) < 1``.

    Build numerical candidates from ``H (I-T)^(-1)`` and pass the returned
    blocks through the independent Bellman--Choi verifier.
    """
    if not np.isfinite(tol) or tol <= 0:
        raise ValueError("tol must be finite and positive")
    require_valid_model(model, tol=tol)
    t_matrix = transient_matrix(model)
    h_matrix = halt_matrix(model)
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
