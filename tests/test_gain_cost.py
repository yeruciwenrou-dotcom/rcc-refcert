import json
from dataclasses import replace
from fractions import Fraction

import numpy as np
import pytest

from rcc_refcert import Action, FiniteControlModel, audit_case, get_case
from rcc_refcert.examples import (
    make_dephase_or_halt_model,
    make_global_reset_loop_model,
    make_multiblock_rectangular_model,
    make_multiblock_reference_potential_certificate,
)
from rcc_refcert.gain_bounds import branch_gain_bounds
from rcc_refcert.gain_cost import analyze_reference_gain_cost
from rcc_refcert.model import validate_model
from rcc_refcert.prefix import is_prefix_free
from rcc_refcert.quantum import reset_kraus_qubit
from rcc_refcert.render import case_payload, format_case
from rcc_refcert.report import _case_section
from rcc_refcert.status import CheckOutcome


def test_dephase_model_satisfies_current_h70_condition() -> None:
    model = make_dephase_or_halt_model()
    theta = {("s", "q"): model.reference_state}
    report = analyze_reference_gain_cost(model, theta)
    assert report.outcome == CheckOutcome.PASS
    assert abs(report.fixed_model_initial_constant - 1.0) < 1e-12
    syntax = report.syntax_reports[0]
    assert syntax.current_condition_satisfied
    assert syntax.suggested_condition_satisfied
    assert abs(syntax.current_weighted_sum - 1.0) < 1e-12
    assert abs(syntax.suggested_weighted_sum - 1.0) < 1e-12
    assert all(abs(action.reference_gain - 1.0) < 1e-12 for action in syntax.actions)
    assert {action.suggested_code_length for action in syntax.actions} == {1}


def test_multiblock_h70_failure_is_only_a_certificate_failure() -> None:
    model = make_multiblock_rectangular_model()
    certificate = make_multiblock_reference_potential_certificate()
    report = analyze_reference_gain_cost(model, certificate.theta)
    assert report.outcome == CheckOutcome.FAIL
    assert abs(report.fixed_model_initial_constant - 1.0) < 1e-12
    by_syntax = {item.syntax_state: item for item in report.syntax_reports}
    assert abs(by_syntax["s0"].current_weighted_sum - 2.0) < 1e-12
    assert abs(by_syntax["s1"].current_weighted_sum - 1.5) < 1e-12
    assert all(item.suggested_condition_satisfied for item in report.syntax_reports)
    assert "does not establish failure of RA" in report.caveat


def test_global_reset_requires_extensive_effective_length() -> None:
    for n in range(1, 5):
        model = make_global_reset_loop_model(n)
        report = analyze_reference_gain_cost(model, {("s", "q"): model.reference_state})
        assert report.outcome == CheckOutcome.FAIL
        syntax = report.syntax_reports[0]
        assert abs(syntax.current_weighted_sum - (0.5 + 2 ** (n - 1))) < 1e-12
        assert abs(syntax.suggested_weighted_sum - 1.0) < 1e-12
        actions = {action.action_name: action for action in syntax.actions}
        assert abs(actions["continue"].reference_gain - 1.0) < 1e-12
        assert actions["continue"].suggested_code_length == 1
        assert abs(actions["global-reset-and-halt"].reference_gain - 2**n) < 1e-12
        assert actions["global-reset-and-halt"].suggested_code_length == n + 1


def test_gain_cost_rejects_missing_or_invalid_envelopes() -> None:
    model = make_dephase_or_halt_model()
    missing = analyze_reference_gain_cost(model, {})
    assert missing.outcome == CheckOutcome.FAIL
    invalid = analyze_reference_gain_cost(
        model, {("s", "q"): np.array([[1.0, 0.0], [0.0, 0.0]])}
    )
    assert invalid.outcome == CheckOutcome.FAIL


def biased_loop(k: int, r: float) -> FiniteControlModel:
    identity = np.eye(2, dtype=complex)
    sigma = identity / 2
    kraus = (np.sqrt(1 - r) * identity,) + tuple(
        np.sqrt(r) * matrix for matrix in reset_kraus_qubit(0)
    )
    actions = tuple(
        Action(f"continue-{j}", "1" * j + "0", "s", continue_kraus={("q", "q"): kraus})
        for j in range(k)
    ) + (Action("halt", "1" * k, None, halt_kraus={"q": (identity,)}),)
    return FiniteControlModel(
        ("s",), {"q": 2}, {"s": actions}, "s", {"q": sigma}, 2, sigma
    )


@pytest.mark.parametrize("k", [28, 32, 35])
@pytest.mark.parametrize("r", [1e-11, 5e-11, 2.0**-34])
def test_positive_local_excess_cannot_pass_in_a_slow_loop(k, r) -> None:
    model = biased_loop(k, r)
    assert validate_model(model) == []
    report = analyze_reference_gain_cost(model, {("s", "q"): model.reference_state})
    assert report.outcome is CheckOutcome.FAIL
    assert report.constant is None
    assert not report.syntax_reports[0].current_condition_satisfied
    assert report.syntax_reports[0].suggested_condition_satisfied
    assert 1 < report.syntax_reports[0].current_weighted_sum <= 1 + 1e-10


@pytest.mark.parametrize("delta", [0.0, 1e-11, 2.0**-54])
def test_suggested_codes_cover_exact_gain_across_power_of_two_boundary(delta) -> None:
    sigma = np.diag([0.5 - delta, 0.5 + delta]).astype(complex)
    actions = tuple(
        Action(f"reset-{j}", str(j), None, halt_kraus={"q": reset_kraus_qubit(0)})
        for j in range(2)
    )
    model = FiniteControlModel(
        ("s",), {"q": 2}, {"s": actions}, "s", {"q": sigma}, 2, sigma
    )
    original = tuple(action.codeword for action in actions)
    report = analyze_reference_gain_cost(model, {("s", "q"): sigma})
    syntax = report.syntax_reports[0]
    exact_gain = sum(Fraction(float(x)) for x in np.diag(sigma).real) / Fraction(
        float(sigma[0, 0].real)
    )
    weighted = sum(
        Fraction(1, 2**action.suggested_code_length) * exact_gain
        for action in syntax.actions
    )
    assert weighted <= 1
    assert syntax.suggested_condition_satisfied
    assert syntax.suggested_weighted_sum_upper <= 1
    assert {action.suggested_code_length for action in syntax.actions} == (
        {2} if delta == 0 else {3}
    )
    assert is_prefix_free(action.suggested_codeword for action in syntax.actions)
    assert tuple(action.codeword for action in actions) == original


@pytest.mark.parametrize(
    "length,expected", [(1, CheckOutcome.INCONCLUSIVE), (2, CheckOutcome.PASS)]
)
def test_dense_boundary_and_slack_have_distinct_outcomes(length, expected) -> None:
    sigma = np.eye(2, dtype=complex) / 2
    unitary = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)
    actions = tuple(
        Action(
            f"halt-{j}",
            "0" * (length - 1) + str(j),
            None,
            halt_kraus={"q": (unitary,)},
        )
        for j in range(2)
    )
    model = FiniteControlModel(
        ("s",), {"q": 2}, {"s": actions}, "s", {"q": sigma}, 2, sigma
    )
    report = analyze_reference_gain_cost(model, {("s", "q"): sigma})
    assert report.outcome is expected
    assert report.syntax_reports[0].suggested_condition_satisfied
    if expected is CheckOutcome.PASS:
        assert report.constant >= 1
    else:
        assert report.constant is None
        case = replace(audit_case(get_case("dephase-or-halt")), gain_cost=report)
        payload = json.loads(json.dumps(case_payload(case), allow_nan=False))["checks"][
            "h6_gain_cost"
        ]
        assert payload["outcome"] == "inconclusive"
        assert payload["constant"] is None
        assert payload["syntax_states"][0]["current_outcome"] == "inconclusive"
        assert not payload["syntax_states"][0]["current_condition_satisfied"]
        assert "INCONCLUSIVE" in format_case(case)
        assert "no usable constant for current codewords" in format_case(case)
        assert "inconclusive" in "\n".join(_case_section(case))


def test_dense_complex_gain_bounds_cover_independent_rational_value() -> None:
    amplitude = float(np.sqrt(0.5))
    ket = amplitude * np.array([[1], [1j]])
    kraus = (ket @ np.array([[1, 0]]), ket @ np.array([[0, 1]]))
    source = np.eye(2) / 2
    for numerator in range(1, 16):
        p = Fraction(numerator, 16)
        off = Fraction(1, 64)
        target = np.array(
            [[float(p), float(off)], [float(off), float(1 - p)]], dtype=complex
        )
        exact_gain = Fraction(amplitude) ** 2 / (p * (1 - p) - off**2)
        bounds = branch_gain_bounds(kraus, source, target)
        assert bounds is not None
        assert bounds.lower <= exact_gain <= bounds.upper
