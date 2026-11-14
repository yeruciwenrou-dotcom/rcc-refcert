"""Saved evidence retains full inputs and detects inconsistent author claims."""

import hashlib
import json
import os
import subprocess
import sys
import zipfile
from copy import deepcopy
from pathlib import Path

import pytest

from rcc_refcert.bundle import inspect_analysis_bundle, verify_analysis_bundle
from rcc_refcert.workflows import (
    analyze_cost,
    load_workflow_template,
    save_workflow_bundle,
)
from rcc_refcert.workflows.core import canonical_bytes, digest


def _saved(tmp_path, name="cyclic-reset"):
    request = load_workflow_template(name)
    result = analyze_cost(request)
    path = tmp_path / "evidence.rccbundle"
    save_workflow_bundle(path, request, result)
    return path, request, result


def _rehash(path, mutate):
    with zipfile.ZipFile(path) as archive:
        data = {n: json.loads(archive.read(n)) for n in archive.namelist()}
    mutate(data)
    manifest = data["manifest.json"]
    payload = {n: canonical_bytes(v) for n, v in data.items() if n != "manifest.json"}
    manifest["members"] = {
        n: {"bytes": len(v), "sha256": hashlib.sha256(v).hexdigest()}
        for n, v in payload.items()
    }
    manifest["request_digest"] = digest(data["request.json"]["effective"])
    manifest["manifest_sha256"] = digest(
        {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", canonical_bytes(manifest))
        for name, value in payload.items():
            archive.writestr(name, value)


@pytest.mark.parametrize("name", ["cyclic-reset", "algorithmic-cooling"])
def test_independent_replay(tmp_path, name):
    path, _, original = _saved(tmp_path, name)
    before = path.read_bytes()
    inspection = inspect_analysis_bundle(path)
    assert inspection["physical_revalidation"] == "not_run"
    verified = verify_analysis_bundle(path)
    assert verified["historical_results_supported"] is True
    assert verified["fresh_result"]["cost"] == original["cost"]
    assert verified["fresh_result"]["run_id"] != original["run_id"]
    assert path.read_bytes() == before


@pytest.mark.parametrize("field", ["lower", "error", "coefficient", "target", "cost"])
def test_rehashed_semantic_tampering_rejected(tmp_path, field):
    path, _, _ = _saved(tmp_path)

    def mutate(data):
        h = data["history.json"]
        if field == "lower":
            h["cost"]["lower_bound_slots"] = 4
        if field == "error":
            h["candidates"][-1]["trace_distance_exact"] = "1/5"
        if field == "coefficient":
            h["gain_certificate"]["verification"]["checks"][0]["supplied_exact"] = "1"
        if field == "target":
            h["effective_request"]["target"]["data"].reverse()
        if field == "cost":
            h["candidates"][-1]["slots"] = 4

    _rehash(path, mutate)
    with pytest.raises(ValueError):
        inspect_analysis_bundle(path)
    with pytest.raises(ValueError):
        verify_analysis_bundle(path)


def test_saved_result_bound_to_original_request(tmp_path):
    request = load_workflow_template("cyclic-reset")
    result = analyze_cost(request)
    other = deepcopy(request)
    other["epsilon"] = "1/5"
    with pytest.raises(ValueError):
        save_workflow_bundle(tmp_path / "wrong.rccbundle", other, result)
    assert not (tmp_path / "wrong.rccbundle").exists()


def test_exclusive_writes_and_duplicate_members(tmp_path):
    path, request, result = _saved(tmp_path)
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        save_workflow_bundle(path, request, result)
    assert path.read_bytes() == before
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr("unexpected.txt", "unrelated")
    with pytest.raises(ValueError):
        inspect_analysis_bundle(path)


def _cli(*args, cwd):
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    return subprocess.run(
        [sys.executable, "-m", "rcc_refcert", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_cli_complete_path_and_no_old_success(tmp_path):
    template = _cli("cost", "template", "cyclic-reset", cwd=tmp_path)
    assert template.returncode == 0, template.stderr
    request = tmp_path / "request.json"
    request.write_text(template.stdout)
    output, bundle = tmp_path / "result.json", tmp_path / "run.rccbundle"
    run = _cli(
        "cost",
        "analyze",
        str(request),
        "--format",
        "json",
        "--output",
        str(output),
        "--bundle",
        str(bundle),
        cwd=tmp_path,
    )
    assert run.returncode == 0, run.stderr + run.stdout
    assert not run.stdout
    first = json.loads(output.read_text())
    assert first["cost"]["interval_slots"] == [5, 5]
    verify = _cli("bundle", "verify", str(bundle), "--format", "json", cwd=tmp_path)
    assert verify.returncode == 0, verify.stdout + verify.stderr
    assert json.loads(verify.stdout)["historical_results_supported"] is True
    repeat = _cli(
        "cost",
        "analyze",
        str(request),
        "--output",
        str(output),
        "--format",
        "json",
        cwd=tmp_path,
    )
    assert repeat.returncode == 2
    error = json.loads(repeat.stdout)
    assert error["schema"] == "rcc-refcert.workflow-error"
    assert error["run_id"] != first["run_id"]
    assert json.loads(output.read_text()) == first


def test_cli_bad_inputs_and_budget(tmp_path):
    req = load_workflow_template("cyclic-reset")
    path = tmp_path / "task.json"
    req["model"]["parameters"]["p"] = 0.95
    path.write_text(json.dumps(req))
    failed = _cli("cost", "analyze", str(path), "--format", "json", cwd=tmp_path)
    assert failed.returncode == 2
    assert "exact" in json.loads(failed.stdout)["message"]
    req = load_workflow_template("cyclic-reset")
    req["limits"]["max_dp_cells"] = 4
    path.write_text(json.dumps(req))
    limited = _cli("cost", "analyze", str(path), "--format", "json", cwd=tmp_path)
    assert limited.returncode == 3
    assert json.loads(limited.stdout)["resource"] == "dp_cells"
