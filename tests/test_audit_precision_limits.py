"""Independent binary-input oracles and refusal boundaries for model audits."""

import json
from dataclasses import replace
from fractions import Fraction

import numpy as np
import pytest

from rcc_refcert import (
    Action,
    BellmanChoiCertificate,
    CheckOutcome,
    ComputationLimits,
    FiniteControlModel,
    ModelValidationError,
    NumericalRangeError,
    ResourceLimitError,
    audit_case,
    audit_model,
    get_case,
    verify_bellman_choi,
)
from rcc_refcert.domination import minimum_domination_constant
from rcc_refcert.fixed_point import linear_fixed_point, linear_value_choi_envelopes
from rcc_refcert.gain_cost import analyze_reference_gain_cost
from rcc_refcert.model import validate_model
from rcc_refcert.render import case_payload, format_case
from rcc_refcert.semantics import (
    AcceptedProgram,
    depth_contribution_by_enumeration,
    depth_contribution_by_maps,
    enumerate_accepted_programs,
    halt_matrix,
    program_output,
    transient_matrix,
    truncated_semidensity,
)
from rcc_refcert.weights import code_weight, weighted_operator


def weak_reset(length=32, reset=1e-12):
    identity = np.eye(2, dtype=complex)
    a, b = np.sqrt(1 - reset), np.sqrt(reset)
    kraus = (
        a * identity,
        np.array([[b, 0], [0, 0]], complex),
        np.array([[0, b], [0, 0]], complex),
    )
    actions = tuple(
        Action(f"continue-{i}", "1" * i + "0", "s", continue_kraus={("q", "q"): kraus})
        for i in range(length)
    )
    halt = Action("halt", "1" * length, None, halt_kraus={"q": (identity,)})
    model = FiniteControlModel(
        ("s",),
        {"q": 2},
        {"s": actions + (halt,)},
        "s",
        {"q": identity / 2},
        2,
        identity / 2,
    )
    # Exact rational reference for the actual rounded Kraus entries.
    q = Fraction(1, 2**length)
    c = 1 - q
    a2, b2 = Fraction(float(a)) ** 2, Fraction(float(b)) ** 2
    v11 = Fraction(1, 2) / (1 - c * a2)
    v00 = (Fraction(1, 2) + c * b2 * v11) / (1 - c * (a2 + b2))
    return model, (q * v00, q * v11)


@pytest.mark.parametrize("length,reset", [(4, 1e-6), (20, 1e-7), (32, 1e-12)])
def test_assembly_allowance_covers_independent_binary_input_oracle(length, reset):
    model, exact_diagonal = weak_reset(length, reset)
    result = audit_model(model, max_depth=1, max_transient_steps=1)
    fixed = result.fixed_point
    error = np.linalg.norm(fixed.output - np.diag([float(v) for v in exact_diagonal]))
    assert fixed.output_error_estimate >= error
    if length == 32:
        assert fixed.output_valid is True
        assert fixed.condition_number < 1.01
        estimate = minimum_domination_constant(
            fixed.output, model.reference_state
        ).constant
        constant_error = abs(Fraction(estimate) - 2 * max(exact_diagonal))
        assert float(constant_error) > 100 * result.tolerance
        assert result.linear_fixed_point_outcome is CheckOutcome.INCONCLUSIVE
        assert result.fixed_model_domination is None
    if result.domination_outcome is CheckOutcome.PASS:
        domination = result.fixed_model_domination
        actual_error = abs(Fraction(domination.constant) - 2 * max(exact_diagonal))
        assert float(actual_error) <= domination.constant_error_estimate
        assert domination.constant_error_estimate <= result.tolerance * max(
            1, domination.constant
        )


def halt_model(reference, code="0"):
    dim = len(reference)
    halt = Action("halt", code, None, halt_kraus={"q": (np.eye(dim),)})
    return FiniteControlModel(
        ("s",), {"q": dim}, {"s": (halt,)}, "s", {"q": reference}, dim, reference
    )


@pytest.mark.parametrize("length", [1023, 1074, 1075])
def test_unsupported_prefix_weights_are_rejected_before_zero_certification(length):
    model = halt_model(np.eye(1), "0" * length)
    assert any("weight range" in error for error in validate_model(model))
    zero = BellmanChoiCertificate({("s", "q"): np.zeros((1, 1))}, 0)
    for action in (
        lambda: audit_model(model),
        lambda: verify_bellman_choi(model, zero),
    ):
        with pytest.raises(ModelValidationError, match="weight range"):
            action()
    with pytest.raises(NumericalRangeError):
        _ = AcceptedProgram(("halt",), "0" * length).weight
    assert code_weight(1022) == np.finfo(float).tiny


def test_weighting_and_accumulated_code_length_cannot_silently_underflow():
    with pytest.raises(NumericalRangeError):
        weighted_operator(code_weight(1022), np.array([[2.0**-100]]))
    model = weak_reset(1)[0]
    model.actions_by_syntax["s"][0].codeword = "0" * 600
    model.actions_by_syntax["s"][1].codeword = "1" * 600
    assert not validate_model(model)
    with pytest.raises(NumericalRangeError):
        enumerate_accepted_programs(model, 2)
    with pytest.raises(NumericalRangeError):
        depth_contribution_by_maps(model, 2)


def test_custom_tolerance_reaches_every_revalidating_semantic_entry():
    model = halt_model(np.diag([1e-11, 1 - 1e-11]))
    tol = 1e-12
    assert not validate_model(model, tol)
    assert validate_model(model)
    (program,) = enumerate_accepted_programs(model, 1, tol=tol)
    np.testing.assert_allclose(
        program_output(model, program, tol=tol), model.reference_state
    )
    expected = model.reference_state / 2
    for output in (
        depth_contribution_by_enumeration(model, 1, tol=tol),
        depth_contribution_by_maps(model, 1, tol=tol),
        truncated_semidensity(model, 0, tol=tol),
        linear_fixed_point(model, tol=tol).output,
    ):
        np.testing.assert_allclose(output, expected)
    assert transient_matrix(model, tol=tol).shape == (4, 4)
    assert halt_matrix(model, tol=tol).shape == (4, 4)
    assert linear_value_choi_envelopes(model, tol=tol)
    result = audit_model(model, max_depth=1, max_transient_steps=0, tol=tol)
    assert result.linear_fixed_point_outcome is CheckOutcome.PASS
    assert result.domination_outcome is CheckOutcome.INCONCLUSIVE
    assert result.fixed_model_domination.constant is None
    assert result.fixed_model_domination.constant_estimate == pytest.approx(0.5)
    case = replace(audit_case(get_case("dephase-or-halt")), model_analysis=result)
    payload = json.loads(json.dumps(case_payload(case), allow_nan=False))["checks"]
    assert payload["h34_domination"]["constant_estimate"] == pytest.approx(0.5)
    assert payload["h34_domination"]["constant_upper_bound"] is None
    assert "reference scaling" in format_case(case, detailed=True)


def test_empty_branch_is_rejected_consistently_and_omission_is_valid():
    identity = np.eye(1)
    branches = {("a", "a"): (identity,), ("a", "b"): (), ("b", "b"): (identity,)}
    actions = (
        Action("continue", "0", "s", continue_kraus=branches),
        Action("halt", "1", None, halt_kraus={"a": (identity,), "b": (identity,)}),
    )
    model = FiniteControlModel(
        ("s",), {"a": 1, "b": 1}, {"s": actions}, "s", {"a": identity}, 1, identity
    )
    for action in (
        lambda: audit_model(model),
        lambda: analyze_reference_gain_cost(
            model, {("s", "a"): identity, ("s", "b"): identity}
        ),
    ):
        with pytest.raises(ModelValidationError, match="empty Kraus"):
            action()
    del branches[("a", "b")]
    assert audit_model(model).domination_outcome is CheckOutcome.PASS


def test_enumeration_budget_checks_default_audit_before_work(monkeypatch):
    model = weak_reset()[0]

    def unexpected(*args, **kwargs):
        pytest.fail("large enumeration was started")

    monkeypatch.setattr(
        "rcc_refcert.audit.depth_contribution_by_enumeration", unexpected
    )
    with pytest.raises(ResourceLimitError) as caught:
        audit_model(model)
    assert caught.value.resource == "enumeration_nodes"
    assert caught.value.outcome is CheckOutcome.INCONCLUSIVE
    assert caught.value.estimate > caught.value.limit


def test_budget_counts_nonhalting_prefixes_and_is_configurable():
    model = weak_reset(2)[0]
    # Delete halting entirely: the prefix tree still grows exponentially.
    model.actions_by_syntax["s"] = model.actions_by_syntax["s"][:-1]
    with pytest.raises(ResourceLimitError):
        enumerate_accepted_programs(model, 30)
    model = weak_reset(2)[0]
    with pytest.raises(ResourceLimitError):
        enumerate_accepted_programs(
            model, 3, limits=ComputationLimits(max_enumeration_nodes=20)
        )
    assert (
        len(
            enumerate_accepted_programs(
                model, 3, limits=ComputationLimits(max_enumeration_nodes=21)
            )
        )
        == 7
    )


def test_dense_budget_refuses_before_allocation(monkeypatch):
    model = halt_model(np.eye(2) / 2)
    original = np.zeros

    def unexpected(shape, *args, **kwargs):
        if shape == (4, 4):
            pytest.fail("dense allocation was started")
        return original(shape, *args, **kwargs)

    monkeypatch.setattr("rcc_refcert.semantics.np.zeros", unexpected)
    with pytest.raises(ResourceLimitError) as caught:
        transient_matrix(model, limits=ComputationLimits(max_matrix_elements=31))
    assert caught.value.resource == "dense_matrix_elements"
    assert caught.value.estimate == 32
