import numpy as np
import pytest

from rcc_refcert.bellman_choi import BellmanChoiCertificate, verify_bellman_choi
from rcc_refcert.examples import (
    make_dark_nonhalting_loop_model,
    make_dephase_or_halt_model,
    make_multiblock_rectangular_model,
)
from rcc_refcert.fixed_point import linear_value_choi_envelopes
from rcc_refcert.quantum import choi_from_kraus
from rcc_refcert.status import CheckOutcome


def _dephase_or_halt_value_choi() -> np.ndarray:
    """J(V) for V = 1/2 id + 1/2 Delta."""
    scale = np.sqrt(0.5)
    identity = np.eye(2, dtype=complex)
    p0 = np.array([[1, 0], [0, 0]], dtype=complex)
    p1 = np.array([[0, 0], [0, 1]], dtype=complex)
    return choi_from_kraus((scale * identity, scale * p0, scale * p1))


def test_supplied_bellman_choi_certificate_passes() -> None:
    model = make_dephase_or_halt_model()
    block = ("s", "q")
    certificate = BellmanChoiCertificate(
        choi_envelopes={block: _dephase_or_halt_value_choi()},
        constant=1.0,
        name="dephase-or-halt minimal value map",
    )
    report = verify_bellman_choi(model, certificate)
    assert report.outcome == CheckOutcome.PASS
    assert report.constant == 1.0
    assert all(check.outcome == CheckOutcome.PASS for check in report.checks)
    assert all(check.residual is not None for check in report.checks)


def test_scaled_down_bellman_choi_envelope_is_rejected() -> None:
    model = make_dephase_or_halt_model()
    block = ("s", "q")
    certificate = BellmanChoiCertificate(
        choi_envelopes={block: 0.9 * _dephase_or_halt_value_choi()},
        constant=1.0,
        name="undersized Bellman envelope",
    )
    report = verify_bellman_choi(model, certificate)
    assert report.outcome == CheckOutcome.FAIL
    assert any(
        check.name.startswith("bellman-residual") and check.outcome == CheckOutcome.FAIL
        for check in report.checks
    )


def test_too_small_output_constant_is_rejected() -> None:
    model = make_dephase_or_halt_model()
    block = ("s", "q")
    certificate = BellmanChoiCertificate(
        choi_envelopes={block: _dephase_or_halt_value_choi()},
        constant=0.9,
        name="undersized output constant",
    )
    report = verify_bellman_choi(model, certificate)
    assert report.outcome == CheckOutcome.FAIL
    assert any(
        check.name.startswith("output-domination")
        and check.outcome == CheckOutcome.FAIL
        for check in report.checks
    )


def test_multiblock_minimum_value_map_passes_independent_verifier() -> None:
    model = make_multiblock_rectangular_model()
    envelopes = linear_value_choi_envelopes(model)
    certificate = BellmanChoiCertificate(
        choi_envelopes=envelopes,
        constant=15.0 / 14.0,
        name="multiblock minimum value-map certificate",
    )
    report = verify_bellman_choi(model, certificate)
    assert report.outcome == CheckOutcome.PASS
    assert report.constant == 15.0 / 14.0
    assert set(envelopes) == set(model.transient_keys())
    for key, matrix in envelopes.items():
        expected = model.control_dims[key[1]] * model.output_dim
        assert matrix.shape == (expected, expected)


def test_multiblock_tampered_value_map_is_rejected() -> None:
    model = make_multiblock_rectangular_model()
    envelopes = linear_value_choi_envelopes(model)
    envelopes[("s0", "q2")] *= 0.9
    report = verify_bellman_choi(
        model,
        BellmanChoiCertificate(envelopes, 15.0 / 14.0, "tampered multiblock"),
    )
    assert report.outcome == CheckOutcome.FAIL


def test_value_map_constructor_rejects_dark_transient_sector() -> None:
    with pytest.raises(ValueError, match="spectral radius below one"):
        linear_value_choi_envelopes(make_dark_nonhalting_loop_model())
