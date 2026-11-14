"""Installed resources, legacy producer fixtures and presentation semantics."""

import csv
import json
from copy import deepcopy
from importlib.resources import files
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from rcc_refcert.bundle import inspect_analysis_bundle, verify_analysis_bundle
from rcc_refcert.cli import main
from rcc_refcert.workflows import (
    analyze_cost,
    analyze_windows,
    export_probe,
    load_probe,
    load_workflow_template,
    render_workflow_result,
    save_workflow_bundle,
)
from rcc_refcert.workflows.windows import export_window_files


@pytest.mark.parametrize("name", ["certificate", "spectrum", "counts"])
def test_genuine_020_bundle_is_preserved_and_reverified(name):
    path = Path(__file__).parent / "fixtures" / "bundles-0.2.0" / (name + ".rccbundle")
    before = path.read_bytes()
    assert inspect_analysis_bundle(path)["producer"]["version"] == "0.2.0"
    result = verify_analysis_bundle(path)
    assert result["fresh_verification"]["outcome"] == "pass"
    assert result["historical_results_supported"] is True
    assert path.read_bytes() == before


def test_templates_results_and_states_obey_packaged_structural_schemas():
    data = files("rcc_refcert.workflows").joinpath("data")
    validators = {
        name: Draft202012Validator(
            json.loads(data.joinpath(name + ".schema.json").read_text())
        )
        for name in ("request", "result", "state")
    }
    for name in ("cyclic-reset", "algorithmic-cooling", "window-state"):
        request = load_workflow_template(name)
        validators["request"].validate(request)
        result = (
            analyze_cost if request["kind"] == "cost_analysis" else analyze_windows
        )(request)
        validators["result"].validate(result)
        effective = result["effective_request"]
        validators["request"].validate(effective)
        states = (
            [effective["target"]]
            if request["kind"] == "cost_analysis"
            else [r["state"] for r in effective["states"]]
        )
        for state in states:
            validators["state"].validate(state)


def test_text_width_markdown_json_and_csv_use_stored_values(tmp_path):
    result = analyze_cost(load_workflow_template("cyclic-reset"))
    result["candidates"][0]["id"] = "Long candidate label " * 25
    for width in (80, 120):
        text = render_workflow_result(result, width=width)
        assert all(len(line) <= width for line in text.splitlines())
        assert "[5, 5]" in text
    assert "[5, 5]" in render_workflow_result(result, format="markdown")
    assert json.loads(render_workflow_result(result, format="json")) == result
    windows = analyze_windows(export_probe("w1-quantum-organization"))
    path = tmp_path / "values.csv"
    export_window_files(windows, csv_path=path)
    assert len(path.read_text().splitlines()) == 7
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    expected = [
        (profile["id"], window)
        for profile in windows["profiles"]
        for window in profile["windows"]
    ]
    assert len(rows) == len(expected)
    for row, (state_id, window) in zip(rows, expected, strict=True):
        assert row["state"] == state_id
        assert row["window"] == window["id"]
        assert float(row["entropy_bits"]) == window["entropy_bits"]
        assert float(row["deficit_bits"]) == window["entropy_deficit_bits"]
        assert float(row["rcc_main_term"]) == window["rcc_main_term"]
    with pytest.raises(FileExistsError):
        export_window_files(windows, csv_path=path)


def test_partial_budget_preserves_and_revalidates_completed_prefix(tmp_path):
    request = load_workflow_template("cyclic-reset")
    request["limits"]["max_dp_updates"] = 3
    result = analyze_cost(request)
    assert result["execution"]["state"] == "partial"
    path = tmp_path / "partial.rccbundle"
    save_workflow_bundle(path, request, result)
    replay = verify_analysis_bundle(path)
    assert replay["fresh_verification"]["outcome"] == "inconclusive"
    assert replay["historical_results_supported"] is True
    assert replay["fresh_result"]["cost"] == result["cost"]


def test_large_exact_parameters_survive_full_execution_and_transfer(tmp_path):
    from fractions import Fraction

    from rcc_refcert.workflows.core import exact_text

    request = load_workflow_template("cyclic-reset")
    request["model"]["parameters"] = {
        "qubits": 1,
        "p": exact_text(Fraction(2**15000 - 1, 2**15000)),
    }
    request["epsilon"] = "0"
    request["max_cost"] = 4
    result = analyze_cost(request)
    assert result["cost"]["interval_slots"] == [2, 2]
    path = tmp_path / "large.rccbundle"
    save_workflow_bundle(path, request, result)
    assert verify_analysis_bundle(path)["historical_results_supported"] is True


@pytest.mark.parametrize(
    "probe,command",
    [
        ("w1-quantum-organization", "window"),
        ("w2-noise-distribution", "window"),
        ("w3-cooling-trajectory", "cost"),
    ],
)
def test_probe_cards_keep_complete_machine_records_and_runnable_next_steps(
    capsys, probe, command
):
    assert main(["probe", "show", probe]) == 0
    card = capsys.readouterr().out
    assert len(card.splitlines()) < 80
    assert "Expected results at the default parameters" in card
    assert f"python -m rcc_refcert {command} analyze probe.json" in card
    assert "request_template" not in card
    assert main(["probe", "show", probe, "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out) == load_probe(probe)
    assert main(["probe", "export", probe]) == 0
    assert json.loads(capsys.readouterr().out) == export_probe(probe)


def test_cooling_details_expose_actions_cost_and_windows_without_changing_results():
    result = analyze_cost(export_probe("w3-cooling-trajectory"))
    before = deepcopy(result)
    summary = render_workflow_result(result)
    detailed = render_workflow_result(result, details=True)
    assert "Use --details" in summary
    assert "Step 1: R; cumulative cost 1 atomic slot" in detailed
    assert "subsystem entropy=" in detailed
    assert "Total correlation" in detailed
    assert result == before
    assert json.loads(render_workflow_result(result, format="json")) == before


def test_near_zero_display_preserves_json_and_csv_precision(tmp_path):
    result = analyze_windows(export_probe("w1-quantum-organization"))
    quantity = result["profiles"][0]["windows"][0]
    quantity["entropy_bits"] = -2e-16
    before = deepcopy(result)
    assert "subsystem entropy=~0 bits" in render_workflow_result(result)
    assert json.loads(render_workflow_result(result, format="json")) == before
    path = tmp_path / "precision.csv"
    export_window_files(result, csv_path=path)
    with path.open(newline="") as stream:
        row = next(csv.DictReader(stream))
    assert float(row["entropy_bits"]) == -2e-16
    assert result == before
