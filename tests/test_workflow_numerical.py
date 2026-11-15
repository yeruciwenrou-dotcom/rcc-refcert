"""Numerical model migration preserves physical output and evidence level."""

import numpy as np
import pytest

from rcc_refcert.bundle import verify_analysis_bundle
from rcc_refcert.semantics import AcceptedProgram, program_output
from rcc_refcert.workflows import (
    StateInput,
    analyze_cost,
    load_workflow_template,
    save_workflow_bundle,
    serialize_numeric_model,
)
from rcc_refcert.workflows.api import normalize_cost_request


def numerical_request():
    request = load_workflow_template("cyclic-reset")
    _, effective, model, target, _, _ = normalize_cost_request(request)
    numerical = model.numerical_view()
    effective.pop("gain_certificate", None)
    effective["mode"] = "numerical"
    effective["model"] = serialize_numeric_model(
        numerical,
        subsystem_dims=model.dims,
        subsystem_labels=model.labels,
        reference=model.document["reference"],
        cost=model.document["cost"],
    )
    effective["target"] = StateInput.numeric(
        target.matrix(),
        model.dims,
        model.labels,
        policy={"mode": "roundoff_only", "tolerance": 1e-10, "repair_budget": 1e-10},
    ).as_dict()
    return effective, numerical


def test_unweighted_numerical_output_trace_distance_and_no_strict_endpoint(tmp_path):
    request, model = numerical_request()
    result = analyze_cost(request)
    target = StateInput.from_dict(request["target"]).matrix()
    for raw, got in zip(request["candidates"], result["candidates"]):
        expected = program_output(
            model, AcceptedProgram(tuple(raw["action_names"]), raw["codeword"])
        )
        assert StateInput.from_dict(got["output"]).matrix() == pytest.approx(
            expected, abs=1e-14
        )
        assert got["trace_distance_numeric"] == pytest.approx(
            np.linalg.svd(expected - target, compute_uv=False).sum() / 2
        )
        assert got["target_satisfied"] is None
    assert result["cost"]["interval_slots"] is None
    assert result["cost"]["upper_bound_slots"] is None
    assert result["candidates"][-1]["numerical_target_status"] == "within_tolerance"
    path = tmp_path / "numeric.rccbundle"
    save_workflow_bundle(path, request, result)
    assert verify_analysis_bundle(path)["historical_results_supported"] is True
    request["epsilon"] = "0"
    assert (
        analyze_cost(request)["candidates"][-1]["numerical_target_status"]
        == "unresolved"
    )


def test_numeric_candidate_errors_and_non_cptp_input():
    request, _ = numerical_request()
    request["candidates"][0]["codeword"] = "wrong"
    assert analyze_cost(request)["candidates"][0]["legality"] == "fail"
    request["model"]["actions"][request["model"]["start_syntax"]][0]["continue_kraus"][
        0
    ]["matrices"][0][0][0] = [9, 0]
    with pytest.raises(ValueError):
        analyze_cost(request)
