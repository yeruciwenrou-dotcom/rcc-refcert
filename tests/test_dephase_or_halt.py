import numpy as np

from rcc_refcert.examples import make_dephase_or_halt_model
from rcc_refcert.fixed_point import linear_fixed_point
from rcc_refcert.model import Action, FiniteControlModel, require_valid_model
from rcc_refcert.quantum import dephasing_kraus_qubit, identity_kraus
from rcc_refcert.reference_potential import (
    ReferencePotentialCertificate,
    verify_reference_potential,
)
from rcc_refcert.semantics import (
    AcceptedProgram,
    depth_contribution_by_enumeration,
    depth_contribution_by_maps,
    program_output,
    truncated_semidensity,
)
from rcc_refcert.status import CheckOutcome


def test_realization_matches_enumeration() -> None:
    model = make_dephase_or_halt_model()
    require_valid_model(model)
    for depth in range(1, 8):
        enum = depth_contribution_by_enumeration(model, depth)
        mapped = depth_contribution_by_maps(model, depth)
        assert np.allclose(enum, mapped, atol=1e-12, rtol=0.0)
        assert np.allclose(
            mapped, (2.0**-depth) * model.reference_state, atol=1e-12, rtol=0.0
        )


def test_truncation_and_linear_fixed_point() -> None:
    model = make_dephase_or_halt_model()
    for n in (0, 1, 5, 12):
        observed = truncated_semidensity(model, n)
        expected = (1.0 - 2.0 ** (-(n + 1))) * model.reference_state
        assert np.allclose(observed, expected, atol=1e-12, rtol=0.0)
    result = linear_fixed_point(model)
    assert result.applicable
    assert abs(result.spectral_radius - 0.5) < 1e-12
    assert result.output is not None
    assert result.condition_number is not None
    assert result.solve_residual is not None
    assert result.condition_number >= 1.0
    assert result.solve_residual < 1e-12
    assert np.allclose(result.output, model.reference_state, atol=1e-12, rtol=0.0)


def test_reference_potential_certificate() -> None:
    model = make_dephase_or_halt_model()
    block = ("s", "q")
    certificate = ReferencePotentialCertificate(
        theta={block: model.reference_state},
        a={block: 1.0},
        transition_coefficients={(block, block): 0.5},
        halt_coefficients={block: 0.5},
        potential={block: 1.0},
    )
    report = verify_reference_potential(model, certificate)
    assert report.outcome == CheckOutcome.PASS
    assert report.candidate_constant == 1.0
    assert 1.0 <= report.constant <= 1.0 + 2e-10
    matrix_checks = [check for check in report.checks if "domination" in check.name]
    assert matrix_checks
    assert all(check.residual is not None for check in matrix_checks)
    assert all(
        np.allclose(check.residual, check.residual.conj().T) for check in matrix_checks
    )


def test_tampered_reference_potential_certificate_is_rejected() -> None:
    model = make_dephase_or_halt_model()
    block = ("s", "q")
    certificate = ReferencePotentialCertificate(
        theta={block: model.reference_state},
        a={block: 1.0},
        transition_coefficients={(block, block): 0.4},
        halt_coefficients={block: 0.5},
        potential={block: 1.0},
        name="tampered-transition-bound",
    )
    report = verify_reference_potential(model, certificate)
    assert report.outcome == CheckOutcome.FAIL
    assert any(check.outcome == CheckOutcome.FAIL for check in report.checks)


def test_insufficient_bellman_margin_is_rejected() -> None:
    model = make_dephase_or_halt_model()
    block = ("s", "q")
    certificate = ReferencePotentialCertificate(
        theta={block: model.reference_state},
        a={block: 1.0},
        transition_coefficients={(block, block): 0.5},
        halt_coefficients={block: 0.5},
        potential={block: 0.9},
        name="insufficient Bellman margin",
    )
    report = verify_reference_potential(model, certificate)
    assert report.outcome == CheckOutcome.FAIL
    assert any(
        check.name.startswith("bellman") and check.outcome == CheckOutcome.FAIL
        for check in report.checks
    )


def test_variable_code_lengths_are_weighted_exactly_once() -> None:
    sigma = np.eye(2, dtype=complex) / 2.0
    model = FiniteControlModel(
        syntax_states=("s",),
        control_dims={"q": 2},
        actions_by_syntax={
            "s": (
                Action(
                    name="two-bit-continue",
                    codeword="10",
                    successor="s",
                    continue_kraus={("q", "q"): dephasing_kraus_qubit()},
                ),
                Action(
                    name="one-bit-halt",
                    codeword="0",
                    successor=None,
                    halt_kraus={"q": identity_kraus(2)},
                ),
            )
        },
        start_syntax="s",
        initial_blocks={"q": sigma},
        output_dim=2,
        reference_state=sigma,
        name="variable-code-length-loop",
    )
    require_valid_model(model)
    for depth in range(1, 6):
        expected = (2.0 ** (-(2 * depth - 1))) * sigma
        enumerated = depth_contribution_by_enumeration(model, depth)
        mapped = depth_contribution_by_maps(model, depth)
        assert np.allclose(enumerated, expected, atol=1e-12, rtol=0.0)
        assert np.allclose(mapped, expected, atol=1e-12, rtol=0.0)


def test_reference_potential_rejects_undeclared_certificate_block() -> None:
    model = make_dephase_or_halt_model()
    block = ("s", "q")
    certificate = ReferencePotentialCertificate(
        theta={block: model.reference_state, ("ghost", "q"): model.reference_state},
        a={block: 1.0},
        transition_coefficients={(block, block): 0.5},
        halt_coefficients={block: 0.5},
        potential={block: 1.0},
        name="certificate with ignored-looking extra block",
    )
    report = verify_reference_potential(model, certificate)
    assert report.outcome == CheckOutcome.FAIL
    assert report.checks[0].name == "certificate-domain"


def test_program_output_rejects_codeword_action_mismatch() -> None:
    model = make_dephase_or_halt_model()
    with np.testing.assert_raises_regex(ValueError, "does not match"):
        program_output(model, AcceptedProgram(("halt",), "00"))


def test_reference_potential_accepts_list_envelope_and_rejects_overflow() -> None:
    model = make_dephase_or_halt_model()
    block = ("s", "q")
    list_certificate = ReferencePotentialCertificate(
        theta={block: [[0.5, 0.0], [0.0, 0.5]]},
        a={block: 1.0},
        transition_coefficients={(block, block): 0.5},
        halt_coefficients={block: 0.5},
        potential={block: 1.0},
        name="list-valued envelope",
    )
    assert (
        verify_reference_potential(model, list_certificate).outcome == CheckOutcome.PASS
    )

    overflow = ReferencePotentialCertificate(
        theta={block: model.reference_state},
        a={block: 1e308},
        transition_coefficients={(block, block): 1e308},
        halt_coefficients={block: 1e308},
        potential={block: 1e308},
        name="overflowing scalar certificate",
    )
    report = verify_reference_potential(model, overflow)
    assert report.outcome == CheckOutcome.FAIL
    assert any("non-finite" in check.message for check in report.checks)
