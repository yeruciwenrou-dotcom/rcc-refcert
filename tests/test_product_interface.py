import json
import os
import subprocess
import sys
from importlib import resources
from pathlib import Path

import pytest

from rcc_refcert import __version__
from rcc_refcert.audit import audit_reference_suite
from rcc_refcert.cli import main
from rcc_refcert.render import write_reference_payload


def test_examples_command_explains_why_cases_exist(capsys) -> None:
    assert main(["examples"]) == 0
    output = capsys.readouterr().out
    assert "Bundled RCC cases" in output
    assert "dephase-or-halt" in output
    assert "multiblock-rectangular" in output
    assert "dark-nonhalting" in output
    assert "RCC paper:" in output


def test_case_text_uses_expected_boundary_language(capsys) -> None:
    assert main(["example", "multiblock-rectangular"]) == 0
    output = capsys.readouterr().out
    assert "Reference result: EXPECTED ROUTE FAILURE" in output
    assert "EXPECTED FAIL" in output
    assert "sufficient condition in Eq. (H.70)" in output
    assert "CheckOutcome" not in output
    assert "NUMERICAL_CHECK" not in output

    assert main(["example", "dark-nonhalting"]) == 0
    boundary = capsys.readouterr().out
    assert "Reference result: EXPECTED BOUNDARY" in boundary
    assert "linear inverse" in boundary.lower()

    assert main(["example", "dark-nonhalting", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["checks"]["h2_linear_fixed_point"]["outcome"] == "not_applicable"
    assert payload["checks"]["h34_domination"]["outcome"] == "inconclusive"


def test_case_json_covers_h3_h4_and_h6(capsys) -> None:
    assert (
        main(
            [
                "example",
                "multiblock-rectangular",
                "--format",
                "json",
                "--details",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "rcc-refcert.case-audit"
    assert payload["schema_version"] == 1
    assert payload["producer"] == {"name": "rcc-refcert", "version": __version__}
    assert payload["matches_reference_expectations"] is True
    checks = payload["checks"]
    assert checks["h3_bellman_choi"]["outcome"] == "pass"
    assert checks["h4_reference_potential"]["outcome"] == "pass"
    assert checks["h6_gain_cost"]["outcome"] == "fail"
    assert checks["h6_gain_cost"]["expected_outcome"] == "fail"
    assert checks["h6_gain_cost"]["evidence"] == "numerical"
    assert "sufficient condition in Eq. (H.70)" in payload["case"]["interpretation"]
    assert checks["h1_realization"]["action_depth_range"] == {
        "first": 1,
        "last": 8,
    }


def test_json_commands_report_explicit_source_revision(monkeypatch, capsys) -> None:
    revision = "b" * 40
    monkeypatch.setenv("RCC_REFCERT_SOURCE_REVISION", revision)
    assert main(["examples", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["producer"] == {"name": "rcc-refcert", "version": __version__}
    assert payload["provenance"] == {
        "repository": "https://github.com/yeruciwenrou-dotcom/rcc-refcert",
        "tested_revision": revision,
    }


def test_invalid_source_revision_exits_cleanly(monkeypatch, capsys) -> None:
    monkeypatch.setenv("RCC_REFCERT_SOURCE_REVISION", "not-a-full-commit")
    with pytest.raises(SystemExit) as error:
        main(["examples", "--format", "json"])
    assert error.value.code == 2
    stderr = capsys.readouterr().err
    assert "full 40-character hexadecimal Git commit" in stderr
    assert "Traceback" not in stderr


@pytest.mark.parametrize(
    "arguments",
    [
        ["example", "dephase-or-halt", "--max-depth", "0"],
        ["example", "dephase-or-halt", "--truncation-steps", "-1"],
        ["example", "dephase-or-halt", "--tolerance", "0"],
        ["example", "dephase-or-halt", "--tolerance", "nan"],
    ],
)
def test_invalid_cli_values_exit_cleanly(arguments, capsys) -> None:
    with pytest.raises(SystemExit) as error:
        main(arguments)
    assert error.value.code == 2
    stderr = capsys.readouterr().err
    assert "error:" in stderr
    assert "Traceback" not in stderr


def test_reproduce_can_write_and_check_without_silent_overwrite(
    tmp_path, capsys
) -> None:
    report = tmp_path / "reference.md"
    assert main(["reproduce", "--output", str(report)]) == 0
    assert report.is_file()
    assert "Report written:" in capsys.readouterr().out

    assert main(["reproduce", "--check", str(report)]) == 0
    assert "Reference report: MATCH" in capsys.readouterr().out

    report.write_text(
        report.read_text(encoding="utf-8") + "\ndrift\n", encoding="utf-8"
    )
    assert main(["reproduce", "--check", str(report)]) == 1
    assert "Reference report: MISMATCH" in capsys.readouterr().out


def test_default_check_compares_the_structured_reference(
    tmp_path, monkeypatch, capsys
) -> None:
    results = tmp_path / "results"
    report = results / "reference_report.md"
    data = results / "reference_suite.json"
    monkeypatch.chdir(tmp_path)

    assert main(["reproduce", "--output", str(report)]) == 0
    capsys.readouterr()
    write_reference_payload(data, audit_reference_suite())

    assert main(["reproduce", "--check"]) == 0
    bundled_output = capsys.readouterr().out
    assert "package:reference_data/reference_suite.json" in bundled_output
    assert "Reference data: MATCH" in bundled_output
    assert "Reference report: MATCH" in bundled_output

    assert main(["reproduce", "--check", str(report)]) == 0
    output = capsys.readouterr().out
    assert "Reference data: MATCH" in output
    assert "Reference report: MATCH" in output

    payload = json.loads(data.read_text(encoding="utf-8"))
    payload["suite"]["matches_reference_expectations"] = False
    data.write_text(json.dumps(payload), encoding="utf-8")
    assert main(["reproduce", "--check", str(report)]) == 1
    output = capsys.readouterr().out
    assert "Reference data: MISMATCH" in output
    assert "Reference report: MATCH" in output


def test_bundled_reference_resources_match_repository_evidence() -> None:
    bundled = resources.files("rcc_refcert").joinpath("reference_data")
    root = Path(__file__).resolve().parents[1]
    for name in ("reference_report.md", "reference_suite.json"):
        repository_text = (root / "results" / name).read_text(encoding="utf-8")
        assert bundled.joinpath(name).read_text(encoding="utf-8") == repository_text


def test_python_module_entrypoint_runs() -> None:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = "src"
    completed = subprocess.run(
        [sys.executable, "-m", "rcc_refcert", "examples"],
        cwd=os.fspath(os.path.dirname(os.path.dirname(__file__))),
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert "Bundled RCC cases" in completed.stdout
