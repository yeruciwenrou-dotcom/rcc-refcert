"""Installed resources, legacy producer fixtures and presentation semantics."""

import csv
import json
import shlex
from copy import deepcopy
from fractions import Fraction
from importlib.resources import files
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from rcc_refcert.bundle import inspect_analysis_bundle, verify_analysis_bundle
from rcc_refcert.cli import main
from rcc_refcert.workflows import (
    StateInput,
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
@pytest.mark.parametrize("width", [40, 80, 240])
def test_probe_cards_keep_complete_machine_records_and_runnable_next_steps(
    capsys, tmp_path, monkeypatch, probe, command, width
):
    monkeypatch.chdir(tmp_path)
    assert main(["probe", "show", probe, "--width", str(width)]) == 0
    card = capsys.readouterr().out
    assert "Expected results at the default parameters" in " ".join(card.split())
    assert f"python -m rcc_refcert {command} analyze probe.json" in card
    assert "request_template" not in card
    commands = card.split("Run this probe:\n", 1)[1].split("\n\n", 1)[0].splitlines()
    assert len(commands) == 2
    for line in card.splitlines():
        assert line in commands or len(line) <= width
    for line in commands:
        tokens = shlex.split(line)
        assert tokens[:3] == ["python", "-m", "rcc_refcert"]
        args = tokens[3:]
        if ">" in args:
            assert args[-2:] == [">", "probe.json"]
            assert main(args[:-2]) == 0
            Path("probe.json").write_text(capsys.readouterr().out, encoding="utf-8")
        else:
            assert main(args) == 0
            assert "Execution: completed" in capsys.readouterr().out
    assert main(["probe", "show", probe, "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out) == load_probe(probe)
    assert main(["probe", "export", probe]) == 0
    assert json.loads(capsys.readouterr().out) == export_probe(probe)


def _window_request_with_metadata(metadata):
    request = load_workflow_template("window-state")
    request.update(
        states=[
            {
                "id": "correlated",
                "state": StateInput.diagonal(
                    [Fraction(1, 2), 0, 0, Fraction(1, 2)], [2, 2], ["a", "b"]
                ).as_dict(),
                **metadata,
            }
        ],
        windows=[{"id": "a", "keep": ["a"]}, {"id": "b", "keep": ["b"]}],
        partition={"left": ["a"], "right": ["b"]},
    )
    request["reference"]["gamma"] = "4"
    return request


@pytest.mark.parametrize(
    "metadata",
    [
        {},
        {"step": 3},
        {"action": "prepare"},
        {"slots": 2},
        {"step": 3, "action": "prepare"},
        {"step": 3, "slots": 2},
        {"action": "prepare", "slots": 2},
        {"step": 3, "action": "prepare", "slots": 2},
        {"step": 0, "action": None, "slots": 0},
        {"step": 3, "action": None, "slots": 2},
        {"action": None},
        {"slots": 1},
    ],
)
@pytest.mark.parametrize("format", ["text", "markdown", "json"])
def test_optional_window_metadata_survives_cli_delivery_and_reverification(
    tmp_path, capsys, metadata, format
):
    source = tmp_path / "request.json"
    source.write_text(json.dumps(_window_request_with_metadata(metadata)))
    output = tmp_path / "result.txt"
    bundle = tmp_path / "result.rccbundle"
    args = ["window", "analyze", str(source), "--bundle", str(bundle)]
    if format != "text":
        args += ["--format", format]
    assert main([*args, "--output", str(output)]) == 0
    assert capsys.readouterr().err == ""
    rendered = output.read_text()
    if format != "json":
        if "step" in metadata:
            assert f"Step {metadata['step']}" in rendered
        else:
            assert "Step " not in rendered
        assert ("prepare" in rendered) == (metadata.get("action") == "prepare")
        assert "initial state" not in rendered
        if "slots" in metadata:
            unit = "slot" if metadata["slots"] == 1 else "slots"
            assert (
                f"cumulative cost {metadata['slots']} atomic {unit}" in rendered.lower()
            )
        else:
            assert "cumulative cost" not in rendered.lower()
    original_bundle = bundle.read_bytes()
    original_output = output.read_bytes()
    assert main([*args, "--output", str(output)]) == 2
    capsys.readouterr()
    assert output.read_bytes() == original_output
    assert bundle.read_bytes() == original_bundle
    assert main(["bundle", "inspect", str(bundle)]) == 0
    capsys.readouterr()
    for verify_format in ("text", "json"):
        verification = tmp_path / f"verification-{verify_format}.json"
        verify_args = ["bundle", "verify", str(bundle), "--output", str(verification)]
        if verify_format == "json":
            verify_args += ["--format", "json"]
        assert main(verify_args) == 0
        captured = capsys.readouterr()
        assert captured.err == ""
        report = json.loads(verification.read_text())
        assert report["fresh_verification"]["outcome"] == "pass"
        assert report["historical_results_supported"] is True
        fresh = report["fresh_result"]
        profile = fresh["profiles"][0]
        assert profile["global_quantity"]["entropy_bits"] == 1
        assert profile["global_quantity"]["rcc_main_term"] == 0.5
        assert profile["partition"]["total_correlation_bits"] == 1
        record = fresh["effective_request"]["states"][0]
        assert {k: v for k, v in record.items() if k not in {"id", "state"}} == metadata
        if verify_format == "json":
            assert json.loads(captured.out) == report
        if format == "json":
            assert json.loads(rendered) == report["historical_result"]
        before = verification.read_bytes()
        assert main(verify_args) == 2
        capsys.readouterr()
        assert verification.read_bytes() == before
        assert bundle.read_bytes() == original_bundle


@pytest.mark.parametrize(
    "metadata",
    [{key: value} for key in ("step", "slots") for value in (-1, True, 1.5, None)]
    + [{"action": ""}, {"action": 1}],
)
def test_invalid_window_metadata_is_rejected_before_delivery(
    tmp_path, capsys, metadata
):
    source = tmp_path / "invalid.json"
    source.write_text(json.dumps(_window_request_with_metadata(metadata)))
    bundle = tmp_path / "invalid.rccbundle"
    assert main(["window", "analyze", str(source), "--bundle", str(bundle)]) == 2
    assert "invalid_input" in capsys.readouterr().err
    assert not bundle.exists()


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
