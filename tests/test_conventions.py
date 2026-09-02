import numpy as np

from rcc_refcert.quantum import (
    apply_kraus,
    choi_from_kraus,
    identity_kraus,
    precompose_choi_with_kraus,
    superoperator_from_kraus,
    vec,
)


def _partial_trace_output(
    choi: np.ndarray, input_dim: int, output_dim: int
) -> np.ndarray:
    reshaped = choi.reshape(input_dim, output_dim, input_dim, output_dim)
    return np.einsum("iaja->ij", reshaped)


def test_choi_identity_uses_input_tensor_output_order() -> None:
    choi = choi_from_kraus(identity_kraus(2))
    omega = np.array([1, 0, 0, 1], dtype=complex)
    expected = np.outer(omega, omega.conj())
    assert np.allclose(choi, expected, atol=1e-12, rtol=0.0)
    assert np.allclose(
        _partial_trace_output(choi, 2, 2), np.eye(2), atol=1e-12, rtol=0.0
    )


def test_column_major_superoperator_matches_direct_action() -> None:
    kraus = identity_kraus(2)
    operator = np.array([[1, 2j], [-2j, 3]], dtype=complex)
    matrix = superoperator_from_kraus(kraus)
    assert np.allclose(
        matrix @ vec(operator), vec(apply_kraus(kraus, operator)), atol=1e-12, rtol=0.0
    )


def test_h28_choi_precomposition_uses_transpose_and_conjugate() -> None:
    # A complex, nonsymmetric unitary is used so that the common wrong
    # adjoint/no-conjugation convention cannot pass accidentally.
    k = np.array([[0, 1], [1j, 0]], dtype=complex)
    l = np.diag([1.0, np.exp(0.37j)]).astype(complex)
    x = choi_from_kraus((l,))
    observed = precompose_choi_with_kraus(
        x,
        (k,),
        source_dim=2,
        intermediate_dim=2,
        output_dim=2,
    )
    expected = choi_from_kraus((l @ k,))
    assert np.allclose(observed, expected, atol=1e-12, rtol=0.0)

    identity_out = np.eye(2, dtype=complex)
    wrong = np.kron(k.conj().T, identity_out) @ x @ np.kron(k, identity_out)
    assert np.linalg.norm(wrong - expected, ord=2) > 1e-3
