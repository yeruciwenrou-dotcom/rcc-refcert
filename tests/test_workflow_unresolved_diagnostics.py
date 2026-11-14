"""Unresolved correction records obey their domain, reason and saved policy."""

from copy import deepcopy

import numpy as np
import pytest
from test_workflow_bundles import _rehash
from test_workflow_numeric_transfer import _numeric_request
from test_workflow_windows import request_for

from rcc_refcert.bundle import inspect_analysis_bundle, verify_analysis_bundle
from rcc_refcert.cli import main
from rcc_refcert.model import Action, FiniteControlModel
from rcc_refcert.workflows import (
    StateInput,
    analyze_cost,
    analyze_windows,
    save_workflow_bundle,
    serialize_numeric_model,
)
from rcc_refcert.workflows.core import InputError
from rcc_refcert.workflows.states import (
    check_numeric_diagnostics,
    prepare_numeric_state,
)


def _unresolved(kind):
    delta = 2.0**-50
    state = StateInput.numeric(
        np.diag([1 + delta, -delta]),
        [2],
        ["q"],
        policy={"mode": "roundoff_only", "tolerance": 1e-10, "repair_budget": 1e-18},
    )
    request = _numeric_request()
    if kind == "window":
        request = request_for(state, [{"id": "q", "keep": ["q"]}])
        return request, analyze_windows(request)
    if kind == "target":
        request["target"] = state.as_dict()
    else:
        eye = np.eye(4)
        residue = 7.5e-11
        model = FiniteControlModel(
            ("s",),
            {"q": 4},
            {"s": (Action("halt", "1", None, halt_kraus={"q": (eye,)}),)},
            "s",
            {"q": np.diag([0.5 + residue, 0.5 + residue, -residue, -residue])},
            4,
            eye / 4,
            "unresolved-output",
        )
        request["model"] = serialize_numeric_model(
            model,
            subsystem_dims=[2, 2],
            subsystem_labels=["a", "b"],
            reference=request["model"]["reference"],
            cost=request["model"]["cost"],
            tolerance=1e-10,
        )
        request["target"] = StateInput.numeric(eye / 4, [2, 2], ["a", "b"]).as_dict()
    return request, analyze_cost(request)


def _diagnostic(result, kind):
    if kind == "window":
        return result["profiles"][0]["input_diagnostics"]
    if kind == "target":
        return result["diagnostics"]["target"]
    return result["candidates"][0]["output_diagnostics"]


def _wrong_magnitude(diagnostic, value):
    budget = diagnostic["policy"]["repair_budget"]
    diagnostic["perturbation_trace_norm_half"] = {
        "negative": -(2.0**-50),
        "zero": 0.0,
        "below_budget": budget / 2,
        "at_budget": budget,
        "null": None,
        "string": "0",
        "boolean": False,
        "list": [],
    }[value]


@pytest.mark.parametrize("kind", ["window", "target", "output"])
@pytest.mark.parametrize(
    "value",
    [
        "negative",
        "zero",
        "below_budget",
        "at_budget",
        "null",
        "string",
        "boolean",
        "list",
    ],
)
def test_unresolved_false_magnitudes_rejected_across_full_readers(
    tmp_path, kind, value
):
    request, result = _unresolved(kind)
    diagnostic = _diagnostic(result, kind)
    assert diagnostic["reason"] == "roundoff correction exceeds repair_budget"
    assert "derived_state" not in diagnostic
    path = tmp_path / "history.rccbundle"
    save_workflow_bundle(path, request, result)
    original = path.read_bytes()
    wrong = deepcopy(result)
    _wrong_magnitude(_diagnostic(wrong, kind), value)
    with pytest.raises(InputError):
        save_workflow_bundle(path, request, wrong, overwrite=True)
    assert path.read_bytes() == original
    _rehash(
        path,
        lambda data: _wrong_magnitude(_diagnostic(data["history.json"], kind), value),
    )
    before = path.read_bytes()
    for read in [inspect_analysis_bundle, verify_analysis_bundle]:
        with pytest.raises(InputError):
            read(path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("kind", ["window", "target", "output"])
@pytest.mark.parametrize("different_reconstruction", [False, True])
def test_genuine_unresolved_history_retains_policy_scale(
    tmp_path, kind, different_reconstruction
):
    request, result = _unresolved(kind)
    if different_reconstruction:
        # No corrected array was saved. A different attempted reconstruction
        # can change this roundoff-scale norm by many ULPs and remain unresolved.
        _diagnostic(result, kind)["perturbation_trace_norm_half"] *= 1.25
    path = tmp_path / "unresolved.rccbundle"
    save_workflow_bundle(path, request, result)
    before = path.read_bytes()
    assert inspect_analysis_bundle(path)["record_consistency"] == "pass"
    verified = verify_analysis_bundle(path)
    assert verified["fresh_verification"]["outcome"] == "inconclusive"
    assert verified["historical_results_supported"] is True
    assert verified["fresh_result"]["execution"]["state"] == "partial"
    if kind == "window":
        assert verified["fresh_result"]["profiles"][0]["global_quantity"] is None
    else:
        assert verified["fresh_result"]["cost"]["interval_slots"] is None
    assert path.read_bytes() == before


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), 10**1000])
def test_unresolved_magnitude_domain_is_structured_even_without_json(value):
    request, result = _unresolved("window")
    state = StateInput.from_dict(request["states"][0]["state"])
    diagnostic = _diagnostic(result, "window")
    diagnostic["perturbation_trace_norm_half"] = value
    with pytest.raises(InputError):
        check_numeric_diagnostics(state, diagnostic)


@pytest.mark.parametrize("value", ["negative", "zero", "at_budget"])
def test_unresolved_invalid_bundle_cli_preserves_error_protocol(
    tmp_path, capsys, value
):
    request, result = _unresolved("window")
    path = tmp_path / "wrong.rccbundle"
    save_workflow_bundle(path, request, result)
    _rehash(
        path,
        lambda data: _wrong_magnitude(
            _diagnostic(data["history.json"], "window"), value
        ),
    )
    for operation in ["inspect", "verify"]:
        assert main(["bundle", operation, str(path), "--format", "json"]) == 2
        output = capsys.readouterr()
        assert "Traceback" not in output.out + output.err


@pytest.mark.parametrize("mode", ["no_repair", "density_failed", "budget_exceeded"])
def test_other_unresolved_branches_keep_their_original_status(tmp_path, capsys, mode):
    request, _ = _unresolved("window")
    state = request["states"][0]["state"]
    state.pop("content_digest")
    if mode == "no_repair":
        state["numeric_policy"] = {"mode": "none", "tolerance": 1e-10}
    elif mode == "density_failed":
        state["data"] = [[[1.000001, 0], [0, 0]], [[0, 0], [-0.000001, 0]]]
    result = analyze_windows(request)
    path = tmp_path / "unresolved.rccbundle"
    save_workflow_bundle(path, request, result)
    assert main(["bundle", "inspect", str(path), "--format", "json"]) == 0
    capsys.readouterr()
    assert main(["bundle", "verify", str(path), "--format", "json"]) == 1
    capsys.readouterr()
    assert prepare_numeric_state(StateInput.from_dict(state))[0] is None


def _partition_request(mode=None):
    policy = {"mode": "roundoff_only", "tolerance": 1e-10, "repair_budget": 1e-18}
    if mode is None:
        matrix = np.zeros((4, 4))
        matrix[0, 0] = matrix[0, 3] = matrix[3, 0] = matrix[3, 3] = 0.5
        policy["repair_budget"] = 1e-10
    else:
        delta = 1e-6 if mode == "density_failed" else 2.0**-50
        matrix = np.diag([1 + delta, -delta, 0, 0])
        if mode == "no_repair":
            policy = {"mode": "none", "tolerance": 1e-10}
    state = StateInput.numeric(matrix, [2, 2], ["a", "b"], policy=policy)
    return request_for(
        state,
        [{"id": "a", "keep": ["a"]}],
        {"left": ["a"], "right": ["b"]},
    )


@pytest.mark.parametrize("mode", ["no_repair", "density_failed", "budget_exceeded"])
@pytest.mark.parametrize("field", ["global_quantity", "windows", "partition"])
def test_unresolved_profiles_reject_all_asserted_scientific_values(
    tmp_path, capsys, mode, field
):
    request = _partition_request(mode)
    result = analyze_windows(request)
    assert result["decision"] == "numerical_unresolved"
    normal = analyze_windows(_partition_request())["profiles"][0]
    asserted = deepcopy(normal[field])
    path = tmp_path / "unresolved.rccbundle"
    save_workflow_bundle(path, request, result)
    original = path.read_bytes()
    wrong = deepcopy(result)
    wrong["profiles"][0][field] = asserted
    with pytest.raises(InputError, match="unresolved state"):
        save_workflow_bundle(path, request, wrong, overwrite=True)
    assert path.read_bytes() == original
    _rehash(
        path,
        lambda data: data["history.json"]["profiles"][0].update({field: asserted}),
    )
    before = path.read_bytes()
    for reader in (inspect_analysis_bundle, verify_analysis_bundle):
        with pytest.raises(InputError, match="unresolved state"):
            reader(path)
    for operation in ("inspect", "verify"):
        assert main(["bundle", operation, str(path), "--format", "json"]) == 2
        captured = capsys.readouterr()
        assert "Traceback" not in captured.out + captured.err
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "mode", [None, "no_repair", "density_failed", "budget_exceeded"]
)
def test_partition_records_keep_normal_and_unresolved_controls(tmp_path, mode):
    request = _partition_request(mode)
    result = analyze_windows(request)
    path = tmp_path / "control.rccbundle"
    save_workflow_bundle(path, request, result)
    before = path.read_bytes()
    assert inspect_analysis_bundle(path)["record_consistency"] == "pass"
    checked = verify_analysis_bundle(path)
    assert checked["historical_results_supported"] is True
    profile = checked["fresh_result"]["profiles"][0]
    if mode is None:
        assert checked["fresh_verification"]["outcome"] == "pass"
        assert profile["partition"]["total_correlation_bits"] == pytest.approx(2)
    else:
        assert checked["fresh_verification"]["outcome"] == "inconclusive"
        assert profile["global_quantity"] is None
        assert profile["windows"] == []
        assert profile["partition"] is None
    assert path.read_bytes() == before
