from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .quantum import Array, dagger, hermitian_part, hermiticity_error, is_density_matrix
from .status import CheckOutcome, EvidenceLevel


@dataclass(frozen=True)
class DominationResult:
    """Numerical evaluation of Appendix-H Eq. (H.34) for a fixed model."""

    outcome: CheckOutcome
    constant: float
    support_compatible: bool
    reference_rank: int
    reference_condition_number: float
    support_leakage: float
    message: str
    scaled_semidensity: Array | None = field(default=None, repr=False, compare=False)
    witness_effect: Array | None = field(default=None, repr=False, compare=False)
    evidence: EvidenceLevel = EvidenceLevel.NUMERICAL


def _validate_semidensity(
    semidensity: Array, reference_state: Array, tol: float
) -> tuple[Array, Array]:
    matrix = np.asarray(semidensity, dtype=complex)
    reference = np.asarray(reference_state, dtype=complex)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError("semidensity must be a square matrix")
    if reference.shape != matrix.shape:
        raise ValueError("semidensity and reference state must have the same shape")
    if not np.all(np.isfinite(matrix)) or not np.all(np.isfinite(reference)):
        raise ValueError(
            "semidensity and reference state must contain only finite entries"
        )
    if hermiticity_error(matrix) > tol:
        raise ValueError("semidensity is not Hermitian within tolerance")
    matrix = hermitian_part(matrix)
    if float(np.linalg.eigvalsh(matrix).min()) < -tol:
        raise ValueError("semidensity is not positive semidefinite within tolerance")
    trace = float(np.trace(matrix).real)
    if trace < -tol or trace > 1.0 + tol:
        raise ValueError(
            "program semidensity must have trace in [0,1] within tolerance"
        )
    if not is_density_matrix(reference, tol=tol):
        raise ValueError("reference state must be a density matrix")
    return matrix, hermitian_part(reference)


def minimum_domination_constant(
    semidensity: Array,
    reference_state: Array,
    tol: float = 1e-10,
) -> DominationResult:
    """Evaluate the least fixed-model constant C with M <= C sigma.

    On compatible support this is

        || sigma^{-1/2} M sigma^{-1/2} ||_infinity.

    If ``M`` has positive mass on the kernel of ``sigma``, the least constant
    is infinite and a kernel-supported effect is returned as a numerical
    rejection witness.  No model-family conclusion is inferred.
    """

    if not np.isfinite(tol) or tol <= 0:
        raise ValueError("tol must be finite and positive")
    matrix, reference = _validate_semidensity(semidensity, reference_state, tol)
    eigenvalues, eigenvectors = np.linalg.eigh(reference)
    support_mask = eigenvalues > tol
    reference_rank = int(np.count_nonzero(support_mask))
    if reference_rank == 0:
        raise ValueError(
            "tolerance eliminates the entire numerical support of the reference state"
        )
    support = eigenvectors[:, support_mask]
    reference_condition_number = float(
        eigenvalues[support_mask].max() / eigenvalues[support_mask].min()
    )
    support_projector = support @ dagger(support)
    kernel_projector = np.eye(reference.shape[0], dtype=complex) - support_projector
    support_leakage = float(np.linalg.norm(kernel_projector @ matrix, ord=2))

    if reference_rank < reference.shape[0]:
        kernel_block = hermitian_part(kernel_projector @ matrix @ kernel_projector)
        kernel_values, kernel_vectors = np.linalg.eigh(kernel_block)
        largest_kernel_mass = float(kernel_values[-1])
        if largest_kernel_mass > tol:
            direction = kernel_vectors[:, -1]
            witness = np.outer(direction, direction.conj())
            return DominationResult(
                outcome=CheckOutcome.FAIL,
                constant=float("inf"),
                support_compatible=False,
                reference_rank=reference_rank,
                reference_condition_number=reference_condition_number,
                support_leakage=support_leakage,
                message="semidensity has positive mass outside the reference support",
                witness_effect=witness,
            )
        if support_leakage > tol:
            return DominationResult(
                outcome=CheckOutcome.INCONCLUSIVE,
                constant=float("inf"),
                support_compatible=False,
                reference_rank=reference_rank,
                reference_condition_number=reference_condition_number,
                support_leakage=support_leakage,
                message="cross-support leakage exceeds tolerance without a stable kernel witness",
            )

    inverse_sqrt = (
        support @ np.diag(eigenvalues[support_mask] ** -0.5) @ dagger(support)
    )
    scaled = hermitian_part(inverse_sqrt @ matrix @ inverse_sqrt)
    scaled_values, scaled_vectors = np.linalg.eigh(scaled)
    constant = max(0.0, float(scaled_values[-1]))

    direction = scaled_vectors[:, -1]
    raw_witness = inverse_sqrt @ np.outer(direction, direction.conj()) @ inverse_sqrt
    witness_norm = float(np.linalg.eigvalsh(hermitian_part(raw_witness)).max())
    witness = raw_witness if witness_norm <= 1.0 else raw_witness / witness_norm

    return DominationResult(
        outcome=CheckOutcome.PASS,
        constant=constant,
        support_compatible=True,
        reference_rank=reference_rank,
        reference_condition_number=reference_condition_number,
        support_leakage=support_leakage,
        message="fixed-model minimum evaluated from Appendix-H Eq. (H.34)",
        scaled_semidensity=scaled,
        witness_effect=hermitian_part(witness),
    )
