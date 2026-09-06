from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

import numpy as np

from .certificate_error import roundoff_allowance
from .quantum import Array, dagger, hermitian_part, hermiticity_error, is_density_matrix
from .status import CheckOutcome, EvidenceLevel


@dataclass(frozen=True)
class DominationResult:
    """Numerical evaluation of Appendix-H Eq. (H.34) for a fixed model."""

    outcome: CheckOutcome
    constant: float | None
    support_compatible: bool | None
    reference_rank: int
    reference_condition_number: float
    support_leakage: float
    message: str
    scaled_semidensity: Array | None = field(default=None, repr=False, compare=False)
    witness_effect: Array | None = field(default=None, repr=False, compare=False)
    evidence: EvidenceLevel = EvidenceLevel.NUMERICAL
    constant_estimate: float | None = None
    constant_error_estimate: float | None = None

    @property
    def constant_upper_bound(self) -> None:
        """H.34 evaluates a point estimate; supplied H.3/H.4 certify upper bounds."""
        return None


def _exactly_annihilates(matrix: Array, vector: Array) -> bool:
    """Check a proposed null vector over the exact binary input values."""
    for row in matrix:
        real = Fraction(0)
        imag = Fraction(0)
        for entry, value in zip(row, vector):
            a, b = Fraction(float(entry.real)), Fraction(float(entry.imag))
            c, d = Fraction(float(value.real)), Fraction(float(value.imag))
            real += a * c - b * d
            imag += a * d + b * c
        if real or imag:
            return False
    return True


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
    *,
    input_error_estimate: float | None = None,
) -> DominationResult:
    """Evaluate the least fixed-model constant C with M <= C sigma.

    On compatible support this is

        || sigma^{-1/2} M sigma^{-1/2} ||_infinity.

    A resolved kernel witness gives an infinite constant. Eigenvalues below
    ``tol`` whose nullspace cannot be established give ``inconclusive`` and
    ``constant=None``. ``reference_rank`` counts resolved positive directions.
    A positive ``input_error_estimate`` allows perturbations outside the
    reference support, so this precision check requires resolved full rank.
    """

    if not np.isfinite(tol) or tol <= 0:
        raise ValueError("tol must be finite and positive")
    if input_error_estimate is not None and (
        not np.isfinite(input_error_estimate) or input_error_estimate < 0
    ):
        raise ValueError("input_error_estimate must be finite and nonnegative")
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
        if input_error_estimate is not None and input_error_estimate > 0:
            # An unstructured perturbation can add or remove kernel mass.
            # Check this before either finite or infinite nominal conclusions.
            return DominationResult(
                outcome=CheckOutcome.INCONCLUSIVE,
                constant=None,
                support_compatible=None,
                reference_rank=reference_rank,
                reference_condition_number=reference_condition_number,
                support_leakage=support_leakage,
                message="input error leaves reference-support compatibility unresolved; no finite or infinite constant is established",
            )
        kernel_block = hermitian_part(kernel_projector @ matrix @ kernel_projector)
        kernel_values, kernel_vectors = np.linalg.eigh(kernel_block)
        largest_kernel_mass = float(kernel_values[-1])
        direction = kernel_vectors[:, -1]
        if largest_kernel_mass > tol and _exactly_annihilates(reference, direction):
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
        unresolved = any(
            not _exactly_annihilates(reference, direction)
            or not _exactly_annihilates(matrix, direction)
            for direction in eigenvectors[:, ~support_mask].T
        )
        if unresolved:
            return DominationResult(
                outcome=CheckOutcome.INCONCLUSIVE,
                constant=None,
                support_compatible=None,
                reference_rank=reference_rank,
                reference_condition_number=reference_condition_number,
                support_leakage=support_leakage,
                message="reference support is unresolved at this tolerance; no finite or infinite constant is established",
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

    error_estimate = None
    outcome = CheckOutcome.PASS
    message = "fixed-model minimum estimated from Appendix-H Eq. (H.34)"
    if input_error_estimate is not None:
        # In these coordinates the generalized reference metric should be I.
        # Its residual controls whitening error without identifying cond(A)
        # with a forward-error guarantee for the assembled linear system.
        whitener = np.diag(eigenvalues[support_mask] ** -0.5) @ dagger(support)
        norm_squared = float(np.linalg.norm(whitener, ord=2)) ** 2
        metric = whitener @ reference @ dagger(whitener)
        metric_error = float(np.linalg.norm(metric - np.eye(reference_rank), ord=2))
        metric_error += roundoff_allowance(
            norm_squared * float(np.linalg.norm(reference, ord=2)), len(reference), 2
        )
        if metric_error < 1:
            matrix_error = roundoff_allowance(
                norm_squared * float(np.linalg.norm(matrix, ord=2)), len(matrix), 2
            )
            eigen_error = roundoff_allowance(
                float(np.linalg.norm(scaled, ord=2)), len(matrix)
            )
            error_estimate = (
                norm_squared * input_error_estimate
                + matrix_error
                + eigen_error
                + constant * metric_error
            ) / (1 - metric_error)
        if (
            error_estimate is None
            or not np.isfinite(error_estimate)
            or error_estimate > tol * max(1.0, constant)
        ):
            outcome = CheckOutcome.INCONCLUSIVE
            message = "constant precision is unresolved after output-error propagation and reference scaling"

    return DominationResult(
        outcome=outcome,
        constant=constant if outcome is CheckOutcome.PASS else None,
        support_compatible=True,
        reference_rank=reference_rank,
        reference_condition_number=reference_condition_number,
        support_leakage=support_leakage,
        message=message,
        scaled_semidensity=scaled,
        witness_effect=hermitian_part(witness),
        constant_estimate=constant,
        constant_error_estimate=error_estimate,
    )
