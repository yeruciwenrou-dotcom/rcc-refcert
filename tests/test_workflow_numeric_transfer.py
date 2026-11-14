"""Numerical handoffs retain identities without requiring identical eigensystems."""

import json
from copy import deepcopy

import numpy as np
import pytest
from test_workflow_bundles import _rehash
from test_workflow_windows import request_for

from rcc_refcert.bundle import inspect_analysis_bundle, verify_analysis_bundle
from rcc_refcert.cli import main
from rcc_refcert.model import Action, FiniteControlModel
from rcc_refcert.workflows import (
    StateInput,
    analyze_cost,
    analyze_windows,
    compare_cost_results,
    load_workflow_template,
    save_workflow_bundle,
    serialize_numeric_model,
)
from rcc_refcert.workflows.core import InputError

POLICY = {"mode": "roundoff_only", "tolerance": 1e-10, "repair_budget": 1e-10}


def _numeric_request(*, trajectory=False):
    eye = np.eye(2, dtype=complex)
    delta = 8e-11
    actions = (
        Action(
            "grow", "00", "s", continue_kraus={("q", "q"): (np.sqrt(1 + delta) * eye,)}
        ),
        Action(
            "shrink",
            "01",
            "s",
            continue_kraus={("q", "q"): (np.sqrt(1 - delta) * eye,)},
        ),
        Action("halt", "1", None, halt_kraus={"q": (eye,)}),
    )
    initial = np.diag([1, 0]) if trajectory else np.array([[0.55, 0.2], [0.2, 0.45]])
    model = FiniteControlModel(
        ("s",),
        {"q": 2},
        {"s": actions},
        "s",
        {"q": initial},
        2,
        eye / 2,
        "numeric-transfer",
    )
    reference = {
        "kind": "uniform_product_support",
        "gamma": 3,
        "source": "Three actions",
    }
    cost = {
        "kind": "integer_atomic_slots",
        "action_slots": 1,
        "halt_slots": 1,
        "initial_preparation": "Supplied state",
        "auxiliary_systems": "One control block",
        "output_rule": "complete_unconditional_output",
    }
    target = initial if trajectory else np.array([[0.7, 0.1j], [-0.1j, 0.3]])
    request = {
        "schema": "rcc-refcert.workflow-request",
        "schema_version": 1,
        "kind": "cost_analysis",
        "mode": "numerical",
        "model": serialize_numeric_model(
            model,
            subsystem_dims=[2],
            subsystem_labels=["q"],
            reference=reference,
            cost=cost,
            tolerance=POLICY["tolerance"],
        ),
        "target": StateInput.numeric(target, [2], ["q"], policy=POLICY).as_dict(),
        "epsilon": "1/10",
        "max_cost": 5,
        "candidates": [
            {
                "id": "candidate",
                "source": "Declared program",
                "action_names": ["grow", "grow", "shrink", "halt"]
                if trajectory
                else ["halt"],
                "codeword": "0000011" if trajectory else "1",
            }
        ],
    }
    if trajectory:
        request["windows"] = {"windows": [{"id": "whole", "keep": ["q"]}]}
    return request


def _case(kind, tmp_path, *, uniform=False):
    request = _numeric_request()
    if uniform:
        request["target"] = StateInput.numeric(
            np.eye(2) / 2, [2], ["q"], policy=POLICY
        ).as_dict()
    if kind == "window":
        request = request_for(
            StateInput.from_dict(request["target"]), [{"id": "q", "keep": ["q"]}]
        )
        result = analyze_windows(request)
    else:
        result = analyze_cost(request)
    path = tmp_path / "numeric.rccbundle"
    save_workflow_bundle(path, request, result)
    return path


def _diagnostic(history, kind):
    if kind == "target":
        return history["diagnostics"]["target"], history["effective_request"]["target"]
    if kind == "output":
        candidate = history["candidates"][0]
        return candidate["output_diagnostics"], candidate["output"]
    return history["profiles"][0]["input_diagnostics"], history["effective_request"][
        "states"
    ][0]["state"]


def _bind_derived(diagnostic):
    document = diagnostic["derived_state"]
    document.pop("content_digest", None)
    state = StateInput.from_dict(document)
    document["content_digest"] = state.content_digest
    diagnostic["derived_digest"] = state.content_digest


@pytest.mark.parametrize("kind", ["target", "output", "window"])
@pytest.mark.parametrize("uniform", [False, True])
def test_equivalent_roundoff_record_completes_full_handoff(tmp_path, kind, uniform):
    path = _case(kind, tmp_path, uniform=uniform)

    def equivalent_record(data):
        diagnostic, original = _diagnostic(data["history.json"], kind)
        # A different valid reconstruction, with its own honest identity and
        # perturbation. This exercises full readers without mocking linalg.
        matrix = diagnostic["derived_state"]["data"]
        matrix[0][0][0] += 2e-16
        matrix[1][1][0] -= 2e-16
        _bind_derived(diagnostic)
        raw = StateInput.from_dict(original).matrix()
        derived = StateInput.from_dict(diagnostic["derived_state"]).matrix()
        perturbation = float(np.linalg.svd(derived - raw, compute_uv=False).sum() / 2)
        diagnostic["perturbation_trace_norm_half"] = perturbation
        diagnostic["repair_applied"] = bool(perturbation)

    _rehash(path, equivalent_record)
    before = path.read_bytes()
    assert inspect_analysis_bundle(path)["record_consistency"] == "pass"
    verified = verify_analysis_bundle(path)
    assert verified["historical_results_supported"] is True
    assert verified["same_version_replay"]["status"] == "mismatch"
    assert path.read_bytes() == before


@pytest.mark.parametrize("kind", ["target", "output", "window"])
@pytest.mark.parametrize(
    "change",
    [
        "derived_digest",
        "state_digest",
        "missing_digest",
        "layout",
        "policy",
        "original_digest",
        "repair_marker",
        "negative_perturbation",
        "incorrect_perturbation",
        "over_budget",
    ],
)
def test_rehashed_derived_record_tampering_is_rejected(tmp_path, kind, change):
    path = _case(kind, tmp_path)

    def mutate(data):
        diagnostic, _ = _diagnostic(data["history.json"], kind)
        state = diagnostic["derived_state"]
        if change == "derived_digest":
            diagnostic["derived_digest"] = "0" * 64
        elif change == "state_digest":
            state["data"][0][0][0] += 1e-6
        elif change == "missing_digest":
            state.pop("content_digest")
        elif change == "layout":
            state["subsystem_labels"] = ["other"]
            _bind_derived(diagnostic)
        elif change == "policy":
            state["numeric_policy"]["tolerance"] = 1e-5
            _bind_derived(diagnostic)
        elif change == "original_digest":
            diagnostic["original_digest"] = "0" * 64
        elif change == "repair_marker":
            diagnostic["repair_applied"] = not diagnostic["repair_applied"]
        elif change == "negative_perturbation":
            diagnostic["perturbation_trace_norm_half"] = -1e-16
        elif change == "incorrect_perturbation":
            diagnostic["perturbation_trace_norm_half"] += 1e-12
        elif change == "over_budget":
            state["data"][0][0][0] += 1e-7
            state["data"][1][1][0] -= 1e-7
            _bind_derived(diagnostic)

    _rehash(path, mutate)
    before = path.read_bytes()
    for read in [inspect_analysis_bundle, verify_analysis_bundle]:
        with pytest.raises(InputError):
            read(path)
    assert path.read_bytes() == before


def test_custom_support_description_survives_numeric_correction(tmp_path):
    request = _numeric_request()
    request["target"].pop("content_digest")
    request["target"]["support"]["source"] = "Calibrated complete working support"
    result = analyze_cost(request)
    path = tmp_path / "support.rccbundle"
    save_workflow_bundle(path, request, result)
    assert verify_analysis_bundle(path)["historical_results_supported"] is True


@pytest.mark.parametrize(
    "invalid",
    [
        None,
        [],
        "result",
        1,
        {},
        {
            "schema": "rcc-refcert.workflow-result",
            "schema_version": 1,
            "kind": "cost_analysis",
        },
    ],
)
def test_compare_invalid_records_are_structured_errors(tmp_path, capsys, invalid):
    with pytest.raises(InputError):
        compare_cost_results([invalid])
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(invalid))
    assert main(["cost", "compare", str(path), "--format", "json"]) == 2
    output = capsys.readouterr()
    assert not output.err
    error = json.loads(output.out)
    assert error["state"] == "invalid_input" and error["run_id"]


@pytest.mark.parametrize(
    "field", ["cost", "digests", "run_id", "epsilon", "interval", "identity"]
)
def test_compare_rejects_malformed_nested_cost_records(field):
    result = analyze_cost(load_workflow_template("cyclic-reset"))
    if field in {"cost", "digests", "run_id"}:
        result[field] = []
    elif field == "epsilon":
        result["cost"]["epsilon_exact"] = []
    elif field == "interval":
        result["cost"]["interval_slots"] = [0, 0]
    else:
        result["cost"]["task_core_digest"] = "different"
    with pytest.raises(InputError):
        compare_cost_results([result])


def test_compare_preserves_task_separation_and_cost_criteria():
    first = analyze_cost(load_workflow_template("cyclic-reset"))
    second = deepcopy(first)
    second["run_id"] = "second"
    comparison = compare_cost_results([first, second], criterion={"additive_gap": 0})
    assert comparison["comparable_task"]
    assert all(row["meets_criterion"] for row in comparison["rows"])
    request = load_workflow_template("cyclic-reset")
    request["epsilon"] = "11/25"
    different = analyze_cost(request)
    assert not compare_cost_results([first, different])["comparable_task"]


def test_unresolved_nested_window_retains_the_real_reason(tmp_path, capsys):
    request = _numeric_request(trajectory=True)
    result = analyze_cost(request)
    assert result["candidates"][0]["numerical_target_status"] == "within_tolerance"
    assert result["execution"] == {
        "state": "partial",
        "reason": "optional_windows_numerical_evidence_unresolved",
    }
    profiles = result["windows"]["profiles"]
    assert len(profiles) == 5
    assert sum(p["global_quantity"] is not None for p in profiles) == 4
    path = tmp_path / "trajectory.json"
    path.write_text(json.dumps(request))
    assert main(["cost", "analyze", str(path), "--format", "json"]) == 1
    assert json.loads(capsys.readouterr().out)["execution"] == result["execution"]
    bundle = tmp_path / "trajectory.rccbundle"
    save_workflow_bundle(bundle, request, result)
    assert verify_analysis_bundle(bundle)["historical_results_supported"] is True


def test_window_resource_limit_does_not_hide_primary_numerical_failure():
    request = _numeric_request(trajectory=True)
    result = analyze_cost(request, limits={"max_windows": 1})
    assert result["execution"]["reason"] == "optional_windows_resource_limited"
    request["epsilon"] = "0"
    result = analyze_cost(request, limits={"max_windows": 1})
    assert result["windows"]["execution"]["reason"] == "resource_limited"
    assert result["execution"]["reason"] == "numerical_evidence_unresolved"
