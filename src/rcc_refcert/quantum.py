from __future__ import annotations

from collections.abc import Callable, Iterable

import numpy as np

Array = np.ndarray


def dagger(matrix: Array) -> Array:
    return np.asarray(matrix, dtype=complex).conj().T


def hermitian_part(matrix: Array) -> Array:
    matrix = np.asarray(matrix, dtype=complex)
    return 0.5 * (matrix + dagger(matrix))


def hermiticity_error(matrix: Array) -> float:
    """Return the spectral-norm distance from Hermiticity.

    PSD checks report Hermiticity separately so that symmetrization cannot
    silently hide a tensor-convention or proof-object error.
    """
    matrix = np.asarray(matrix, dtype=complex)
    return float(np.linalg.norm(matrix - dagger(matrix), ord=2))


def min_hermitian_eigenvalue(matrix: Array) -> float:
    return float(np.linalg.eigvalsh(hermitian_part(matrix)).min())


def max_hermitian_eigenvalue(matrix: Array) -> float:
    return float(np.linalg.eigvalsh(hermitian_part(matrix)).max())


def is_psd(matrix: Array, tol: float = 1e-10) -> bool:
    return min_hermitian_eigenvalue(matrix) >= -tol


def operator_leq(left: Array, right: Array, tol: float = 1e-10) -> bool:
    return is_psd(np.asarray(right) - np.asarray(left), tol=tol)


def apply_kraus(kraus: Iterable[Array], operator: Array) -> Array:
    operator = np.asarray(operator, dtype=complex)
    terms = [np.asarray(k, dtype=complex) @ operator @ dagger(k) for k in kraus]
    if not terms:
        raise ValueError("at least one Kraus operator is required")
    return sum(terms, np.zeros_like(terms[0], dtype=complex))


def completeness_operator(kraus: Iterable[Array]) -> Array:
    matrices = [np.asarray(k, dtype=complex) for k in kraus]
    if not matrices:
        raise ValueError("at least one Kraus operator is required")
    input_dim = matrices[0].shape[1]
    return sum(
        (dagger(k) @ k for k in matrices),
        np.zeros((input_dim, input_dim), dtype=complex),
    )


def is_trace_preserving(kraus: Iterable[Array], tol: float = 1e-10) -> bool:
    matrices = [np.asarray(k, dtype=complex) for k in kraus]
    if not matrices:
        return False
    input_dim = matrices[0].shape[1]
    return np.allclose(
        completeness_operator(matrices), np.eye(input_dim), atol=tol, rtol=0.0
    )


def is_density_matrix(matrix: Array, tol: float = 1e-10) -> bool:
    matrix = np.asarray(matrix, dtype=complex)
    return (
        matrix.ndim == 2
        and matrix.shape[0] == matrix.shape[1]
        and np.allclose(matrix, dagger(matrix), atol=tol, rtol=0.0)
        and is_psd(matrix, tol=tol)
        and abs(float(np.trace(matrix).real) - 1.0) <= tol
        and abs(float(np.trace(matrix).imag)) <= tol
    )


def vec(matrix: Array) -> Array:
    return np.asarray(matrix, dtype=complex).reshape(-1, order="F")


def unvec(vector: Array, rows: int, cols: int | None = None) -> Array:
    cols = rows if cols is None else cols
    return np.asarray(vector, dtype=complex).reshape((rows, cols), order="F")


def superoperator_from_kraus(kraus: Iterable[Array]) -> Array:
    matrices = [np.asarray(k, dtype=complex) for k in kraus]
    if not matrices:
        raise ValueError("at least one Kraus operator is required")
    return sum(
        (np.kron(k.conj(), k) for k in matrices),
        np.zeros((matrices[0].shape[0] ** 2, matrices[0].shape[1] ** 2), dtype=complex),
    )


def choi_from_linear_map(
    input_dim: int,
    output_dim: int,
    linear_map: Callable[[Array], Array],
) -> Array:
    """Construct a Choi matrix in the RCC paper's input-tensor-output convention."""
    if input_dim <= 0 or output_dim <= 0:
        raise ValueError("input and output dimensions must be positive")
    choi = np.zeros((input_dim * output_dim, input_dim * output_dim), dtype=complex)
    for i in range(input_dim):
        for j in range(input_dim):
            basis = np.zeros((input_dim, input_dim), dtype=complex)
            basis[i, j] = 1.0
            image = np.asarray(linear_map(basis), dtype=complex)
            if image.shape != (output_dim, output_dim):
                raise ValueError(
                    f"linear map returned shape {image.shape}, expected {(output_dim, output_dim)}"
                )
            row = slice(i * output_dim, (i + 1) * output_dim)
            col = slice(j * output_dim, (j + 1) * output_dim)
            choi[row, col] = image
    return choi


def choi_from_kraus(kraus: Iterable[Array]) -> Array:
    """RCC paper convention: input tensor output."""
    matrices = [np.asarray(k, dtype=complex) for k in kraus]
    if not matrices:
        raise ValueError("at least one Kraus operator is required")
    output_dim, input_dim = matrices[0].shape
    return choi_from_linear_map(
        input_dim, output_dim, lambda operator: apply_kraus(matrices, operator)
    )


def apply_choi_map(
    choi: Array, operator: Array, input_dim: int, output_dim: int
) -> Array:
    """Apply the map represented by an input-tensor-output Choi matrix.

    With J(Phi)=sum_ij |i><j| tensor Phi(|i><j|),

        Phi(X) = Tr_in[(X^T tensor I) J(Phi)].
    """
    choi = np.asarray(choi, dtype=complex)
    operator = np.asarray(operator, dtype=complex)
    expected = input_dim * output_dim
    if choi.shape != (expected, expected):
        raise ValueError(
            f"Choi shape {choi.shape} does not match {(expected, expected)}"
        )
    if operator.shape != (input_dim, input_dim):
        raise ValueError(
            f"operator shape {operator.shape} does not match {(input_dim, input_dim)}"
        )
    tensor = choi.reshape(input_dim, output_dim, input_dim, output_dim)
    return np.einsum("ij,iajb->ab", operator, tensor)


def precompose_choi_with_kraus(
    choi: Array,
    kraus: Iterable[Array],
    source_dim: int,
    intermediate_dim: int,
    output_dim: int,
) -> Array:
    """Return J(W o T) from J(W) and the Kraus operators of T.

    Under the RCC paper convention this is Appendix-H Eq. (H.28):

        sum_mu (K_mu^T tensor I) X (conj(K_mu) tensor I).
    """
    choi = np.asarray(choi, dtype=complex)
    expected = intermediate_dim * output_dim
    if choi.shape != (expected, expected):
        raise ValueError(
            f"Choi shape {choi.shape} does not match {(expected, expected)}"
        )
    identity_out = np.eye(output_dim, dtype=complex)
    result_dim = source_dim * output_dim
    result = np.zeros((result_dim, result_dim), dtype=complex)
    for matrix in (np.asarray(k, dtype=complex) for k in kraus):
        if matrix.shape != (intermediate_dim, source_dim):
            raise ValueError(
                f"Kraus shape {matrix.shape} does not match {(intermediate_dim, source_dim)}"
            )
        left = np.kron(matrix.T, identity_out)
        right = np.kron(matrix.conj(), identity_out)
        result += left @ choi @ right
    return result


def identity_kraus(dim: int) -> tuple[Array, ...]:
    return (np.eye(dim, dtype=complex),)


def dephasing_kraus_qubit() -> tuple[Array, ...]:
    p0 = np.array([[1, 0], [0, 0]], dtype=complex)
    p1 = np.array([[0, 0], [0, 1]], dtype=complex)
    return (p0, p1)


def reset_kraus_qubit(bit: int) -> tuple[Array, ...]:
    if bit not in (0, 1):
        raise ValueError("bit must be 0 or 1")
    ket = (
        np.array([[1.0], [0.0]], dtype=complex)
        if bit == 0
        else np.array([[0.0], [1.0]], dtype=complex)
    )
    bra0 = np.array([[1.0, 0.0]], dtype=complex)
    bra1 = np.array([[0.0, 1.0]], dtype=complex)
    return (ket @ bra0, ket @ bra1)
