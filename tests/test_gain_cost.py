import numpy as np

from rcc_refcert.examples import (
    make_dephase_or_halt_model,
    make_global_reset_loop_model,
    make_multiblock_rectangular_model,
    make_multiblock_reference_potential_certificate,
)
from rcc_refcert.gain_cost import analyze_reference_gain_cost
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
