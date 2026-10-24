"""Reader-visible parameter changes, independent analytic check, and recovery."""

import json
import os
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from examples.custom_model_workflow import analytic_reference_constant, build_model
from rcc_refcert import prepare_bellman_choi, verify_bellman_choi
from rcc_refcert.bundle import verify_analysis_bundle
from rcc_refcert.bundle_cli import render_bundle_report

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "p,q",
    [("2/5", "1/5"), ("3/5", "1/5"), ("0", "0"), ("1", "0"), ("0", "1"), ("1", "1")],
)
def test_analytic_comparison_matches_independent_terminal_sum(p, q):
    p, q = Fraction(p), Fraction(q)
    model = build_model(p, q)
    rho = np.eye(2) / 2
    terminal = np.zeros((2, 2), complex)
    for n in range(100):
        terminal += 2.0 ** (-n - 1) * rho
        phase = "A" if n % 2 == 0 else "B"
        kraus = model.actions_by_syntax[phase][1].continue_kraus[("q", "q")]
        rho = sum(k @ rho @ k.conj().T for k in kraus)
    expected = float(analytic_reference_constant(p, q))
    assert float(2 * np.linalg.eigvalsh(terminal).max()) == pytest.approx(
        expected, abs=1e-14
    )
    prepared = prepare_bellman_choi(model)
    report = verify_bellman_choi(model, prepared.certificate)
    assert report.outcome.value == "pass"
    assert expected <= report.constant <= expected + 1e-8


def _run(script, *args):
    return subprocess.run(
        [sys.executable, str(ROOT / "examples" / script), *map(str, args)],
        env={**os.environ, "PYTHONPATH": str(ROOT / "src")},
        capture_output=True,
        text=True,
        check=False,
    )


def test_changed_parameter_exports_and_reverifies(tmp_path):
    path = tmp_path / "changed.rccbundle"
    result = _run("custom_model_workflow.py", "--p", "2/5", "--bundle", path)
    assert result.returncode == 0, result.stderr
    output = json.loads(result.stdout)
    assert output["parameters"] == {"p": "2/5", "q": "1/5"}
    assert output["analytic_reference_constant"] == "307/264"
    assert output["local_H70"] == "fail"
    assert verify_analysis_bundle(path)["historical_results_supported"] is True


@pytest.mark.parametrize(
    "script", ["custom_model_workflow.py", "cyclic_reset_workflow.py"]
)
def test_example_preserves_existing_output_with_recovery_hint(tmp_path, script):
    path = tmp_path / "existing.rccbundle"
    path.write_bytes(b"existing evidence")
    result = _run(script, "--bundle", path)
    assert result.returncode == 2
    assert "Choose an unused --bundle path" in result.stderr
    assert "Traceback" not in result.stderr
    assert path.read_bytes() == b"existing evidence"
    blocked = tmp_path / "parent-file"
    blocked.write_text("not a directory")
    result = _run(script, "--bundle", blocked / "output.rccbundle")
    assert result.returncode == 2
    assert "Check the destination" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("value", ["-1/5", "6/5", "nan", "1/0"])
def test_invalid_channel_probability_is_actionable(value):
    result = _run("custom_model_workflow.py", "--p=" + value)
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_larger_fresh_constant_explains_unchanged_integer_bound(tmp_path):
    path = tmp_path / "cyclic.rccbundle"
    assert _run("cyclic_reset_workflow.py", "--bundle", path).returncode == 0
    original = path.read_bytes()
    report = verify_analysis_bundle(path, tol=1e-8)
    assert report["fresh_verification"]["outcome"] == "pass"
    assert report["historical_results_supported"] is False
    assert all(
        r["fresh_bound"]["cost"]["integer_lower_bound_slots"] == 2
        for r in report["requests"]
    )
    rendered = render_bundle_report(report)
    assert "Usable constants: fresh" in rendered
    assert "larger fresh constant" in rendered
    assert "integer bound is unchanged" in rendered
    assert path.read_bytes() == original
