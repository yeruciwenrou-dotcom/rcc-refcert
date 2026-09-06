"""Closed-form loops distinguish local tolerances from usable constants."""

import json
from dataclasses import replace
from decimal import Decimal

import numpy as np
import pytest

from rcc_refcert import (
    Action,
    BellmanChoiCertificate,
    FiniteControlModel,
    ReferencePotentialCertificate,
    audit_case,
    audit_model,
    get_case,
    verify_bellman_choi,
    verify_reference_potential,
)
from rcc_refcert.fixed_point import linear_fixed_point
from rcc_refcert.model import ModelValidationError, validate_model
from rcc_refcert.numeric import canonical_upper_float, format_certificate_constant
from rcc_refcert.quantum import choi_from_kraus, reset_kraus_qubit
from rcc_refcert.render import case_payload, format_case
from rcc_refcert.status import CheckOutcome


def rare_halt(k: int, dimension: int = 2) -> FiniteControlModel:
    identity = np.eye(dimension, dtype=complex)
    actions = tuple(
        Action(
            name=f"continue-{j}",
            codeword="1" * j + "0",
            successor="s",
            continue_kraus={("q", "q"): (identity,)},
        )
        for j in range(k)
    )
    halt = Action(
        name="halt", codeword="1" * k, successor=None, halt_kraus={"q": (identity,)}
    )
    return FiniteControlModel(
        syntax_states=("s",),
        control_dims={"q": dimension},
        actions_by_syntax={"s": actions + (halt,)},
        start_syntax="s",
        initial_blocks={"q": identity / dimension},
        output_dim=dimension,
        reference_state=identity / dimension,
    )


def reports(k: int, constant: float, dimension: int = 2):
    model = rare_halt(k, dimension)
    key = ("s", "q")
    q = 2.0**-k
    # H = q id and T = (1-q) id give M = I/d and C* = 1.
    choi = verify_bellman_choi(
        model,
        BellmanChoiCertificate(
            {key: constant * choi_from_kraus((np.eye(dimension),))},
            constant,
        ),
    )
    potential = verify_reference_potential(
        model,
        ReferencePotentialCertificate(
            theta={key: model.reference_state},
            a={key: 1.0},
            transition_coefficients={(key, key): 1.0 - q},
            halt_coefficients={key: constant * q},
            potential={key: constant},
        ),
    )
    return model, choi, potential


@pytest.mark.parametrize("dimension", [1, 2, 4])
@pytest.mark.parametrize("k,constant", [(32, 0.8), (35, 0.0), (36, 0.0)])
def test_rare_halt_cannot_pass_an_understated_constant(k, constant, dimension) -> None:
    model, choi, potential = reports(k, constant, dimension)
    for result in (choi, potential):
        assert result.outcome in {CheckOutcome.FAIL, CheckOutcome.INCONCLUSIVE}
        assert result.constant is None
        assert result.candidate_constant == constant
        if result.outcome is CheckOutcome.INCONCLUSIVE:
            assert any(
                c.name == "constant-error-budget"
                and c.outcome is CheckOutcome.INCONCLUSIVE
                for c in result.checks
            )
    if k == 32:
        assert linear_fixed_point(model).condition_number == pytest.approx(1.0)


@pytest.mark.parametrize("k", [1, 4, 32, 36])
def test_correct_loop_constant_is_supported_or_explicitly_unresolved(k) -> None:
    _, choi, potential = reports(k, 1.0)
    for result in (choi, potential):
        if k <= 4:
            assert result.outcome is CheckOutcome.PASS
        assert result.outcome is not CheckOutcome.FAIL
        if result.outcome is CheckOutcome.PASS:
            assert 1.0 <= result.constant <= 1.0 + 2e-10
            assert result.constant_error_bound == result.constant - 1.0
        else:
            assert result.constant is None


def test_unresolved_constant_survives_default_rendering() -> None:
    _, choi, potential = reports(35, 0.0)
    case = replace(
        audit_case(get_case("dephase-or-halt")),
        bellman_choi=choi,
        reference_potentials=(potential,),
    )
    payload = json.loads(json.dumps(case_payload(case), allow_nan=False))
    first = payload["checks"]["h3_bellman_choi"]
    second = payload["checks"]["h4_reference_potential"]["certificates"][0]
    for certificate in (first, second):
        assert certificate["outcome"] == "inconclusive"
        assert certificate["constant"] is None
        assert certificate["candidate_constant"] == 0.0
    assert "INCONCLUSIVE" in format_case(case)
    assert "no usable constant" in format_case(case)


def test_invalid_internal_semidensity_preserves_partial_audit() -> None:
    model = rare_halt(32)
    r = 5e-11
    kraus = (np.sqrt(1 - r) * np.eye(2),) + tuple(
        np.sqrt(r) * matrix for matrix in reset_kraus_qubit(0)
    )
    for action in model.actions_by_syntax["s"]:
        if not action.is_halt:
            action.continue_kraus = {("q", "q"): kraus}
    assert validate_model(model) == []
    result = audit_model(model, max_depth=1, max_transient_steps=1)
    assert result.realization_outcome is CheckOutcome.PASS
    assert 0 < result.truncated_trace < 1e-8
    assert result.fixed_point.output_valid is False
    assert np.trace(result.fixed_point.output).real > 1 + result.tolerance
    assert result.linear_fixed_point_outcome is CheckOutcome.INCONCLUSIVE
    assert result.domination_outcome is CheckOutcome.INCONCLUSIVE
    assert result.fixed_model_domination is None
    case = replace(audit_case(get_case("dephase-or-halt")), model_analysis=result)
    payload = json.loads(json.dumps(case_payload(case), allow_nan=False))["checks"]
    assert payload["h2_linear_fixed_point"]["outcome"] == "inconclusive"
    assert payload["h2_linear_fixed_point"]["output_valid"] is False
    assert payload["h34_domination"]["constant"] is None
    assert "INCONCLUSIVE" in format_case(case)
    assert "trace" in format_case(case, detailed=True)
    model.initial_blocks["q"] = 2 * model.reference_state
    with pytest.raises(ModelValidationError):
        audit_model(model, max_depth=1, max_transient_steps=1)


def test_unresolved_linear_solve_returns_structured_result(monkeypatch) -> None:
    def unresolved(*args, **kwargs):
        raise np.linalg.LinAlgError("singular working-precision system")

    monkeypatch.setattr(np.linalg, "solve", unresolved)
    result = audit_model(rare_halt(4), max_depth=1, max_transient_steps=1)
    assert result.realization_outcome is CheckOutcome.PASS
    assert result.linear_fixed_point_outcome is CheckOutcome.INCONCLUSIVE
    assert result.fixed_model_domination is None
    assert result.fixed_point.output is None


@pytest.mark.parametrize("constant", [0.5, 1.0, 15.0 / 14.0, 1e5])
def test_display_and_frozen_bounds_do_not_erase_the_correction(constant) -> None:
    upper = float(np.nextafter(constant + 1e-10 * max(1.0, constant), np.inf))
    error = upper - constant
    assert canonical_upper_float(upper) >= upper
    assert canonical_upper_float(error) >= error > 0
    display = format_certificate_constant(upper, constant, error)
    upper_text = display.split(";", 1)[0].removeprefix("C <= ")
    error_text = display.rsplit(" <= ", 1)[1]
    assert Decimal(upper_text) >= Decimal.from_float(upper)
    assert Decimal(error_text) >= Decimal.from_float(error)


def test_certificates_remain_available_with_a_dark_recurrent_class() -> None:
    identity = np.eye(2, dtype=complex)
    sigma = identity / 2
    start, dark = ("start", "q"), ("dark", "q")
    model = FiniteControlModel(
        syntax_states=("start", "dark"),
        control_dims={"q": 2},
        actions_by_syntax={
            "start": (
                Action("halt", "0", None, halt_kraus={"q": (identity,)}),
                Action(
                    "enter-dark", "1", "dark", continue_kraus={("q", "q"): (identity,)}
                ),
            ),
            "dark": tuple(
                Action(
                    f"loop-{bit}", bit, "dark", continue_kraus={("q", "q"): (identity,)}
                )
                for bit in ("0", "1")
            ),
        },
        start_syntax="start",
        initial_blocks={"q": sigma},
        output_dim=2,
        reference_state=sigma,
    )
    assert not linear_fixed_point(model).applicable
    choi = verify_bellman_choi(
        model,
        BellmanChoiCertificate(
            {
                start: 0.5 * choi_from_kraus((identity,)),
                dark: np.zeros((4, 4)),
            },
            0.5,
        ),
    )
    potential = verify_reference_potential(
        model,
        ReferencePotentialCertificate(
            theta={start: sigma, dark: sigma},
            a={start: 1.0, dark: 0.0},
            transition_coefficients={(start, dark): 0.5, (dark, dark): 1.0},
            halt_coefficients={start: 0.5, dark: 0.0},
            potential={start: 0.5, dark: 0.0},
        ),
    )
    for result in (choi, potential):
        assert result.outcome is CheckOutcome.PASS
        assert 0.5 <= result.constant <= 0.5 + 2e-10
