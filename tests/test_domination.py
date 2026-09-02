import numpy as np
import pytest

from rcc_refcert.domination import minimum_domination_constant
from rcc_refcert.examples import global_reset_family_constants
from rcc_refcert.status import CheckOutcome


def test_minimum_domination_constant_matches_direct_formula() -> None:
    reference = np.diag([0.75, 0.25]).astype(complex)
    plus = np.array([1.0, 1.0], dtype=complex) / np.sqrt(2.0)
    semidensity = 0.4 * np.outer(plus, plus.conj())
    observed = minimum_domination_constant(semidensity, reference)
    inverse_sqrt = np.diag(1.0 / np.sqrt(np.diag(reference).real))
    expected = np.linalg.eigvalsh(inverse_sqrt @ semidensity @ inverse_sqrt).max()
    assert observed.outcome == CheckOutcome.PASS
    assert observed.support_compatible
    assert abs(observed.reference_condition_number - 3.0) < 1e-12
    assert abs(observed.constant - expected) < 1e-12
    assert observed.witness_effect is not None
    numerator = np.trace(observed.witness_effect @ semidensity).real
    denominator = np.trace(observed.witness_effect @ reference).real
    assert denominator > 0
    assert abs(numerator / denominator - observed.constant) < 1e-12


def test_support_failure_returns_infinite_constant_and_witness() -> None:
    reference = np.diag([1.0, 0.0]).astype(complex)
    semidensity = np.diag([0.0, 1.0]).astype(complex)
    observed = minimum_domination_constant(semidensity, reference)
    assert observed.outcome == CheckOutcome.FAIL
    assert not observed.support_compatible
    assert np.isinf(observed.constant)
    assert observed.witness_effect is not None
    assert np.trace(observed.witness_effect @ semidensity).real > 0.9
    assert abs(np.trace(observed.witness_effect @ reference)) < 1e-12


def test_global_reset_constants_are_computed_from_h34() -> None:
    constants = global_reset_family_constants(6)
    assert constants == [(n, 2**n) for n in range(1, 7)]
    for n, constant in constants:
        dim = 2**n
        semidensity = np.zeros((dim, dim), dtype=complex)
        semidensity[0, 0] = 1.0
        reference = np.eye(dim, dtype=complex) / dim
        assert (
            abs(minimum_domination_constant(semidensity, reference).constant - constant)
            < 1e-9
        )


def test_domination_rejects_invalid_or_support_erasing_tolerance() -> None:
    reference = np.eye(2, dtype=complex) / 2.0
    semidensity = reference.copy()
    with pytest.raises(ValueError, match="finite and positive"):
        minimum_domination_constant(semidensity, reference, tol=0.0)
    with pytest.raises(ValueError, match="entire numerical support"):
        minimum_domination_constant(semidensity, reference, tol=0.6)
