import numpy as np

from rcc_refcert.examples import make_f5_two_qubit_witness


def test_f5_two_qubit_witness_is_reference_balanced_and_nontrivial() -> None:
    witness = make_f5_two_qubit_witness()
    expected_zero = np.zeros((4, 4), dtype=complex)
    expected_zero[0, 0] = 1.0
    assert max(witness.reset_pair_balance_errors) < 1e-12
    assert np.allclose(witness.after_resets, expected_zero, atol=1e-12, rtol=0.0)
    assert witness.generation_error < 1e-12
    assert abs(witness.initial_purity - 0.25) < 1e-12
    assert abs(witness.final_purity - 1.0) < 1e-12
