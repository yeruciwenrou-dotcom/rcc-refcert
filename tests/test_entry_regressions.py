"""Regressions for source upgrades and paired frozen evidence."""

import importlib.util
from pathlib import Path

import pytest

from rcc_refcert.cli import main

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("absolute", [False, True])
@pytest.mark.parametrize("data_state", ["match", "missing", "changed"])
def test_canonical_report_checks_json_independent_of_path(
    tmp_path, monkeypatch, absolute, data_state
):
    results = tmp_path / "results"
    results.mkdir()
    for name in ("reference_report.md", "reference_suite.json"):
        (results / name).write_bytes((ROOT / "results" / name).read_bytes())
    if data_state == "missing":
        (results / "reference_suite.json").unlink()
    elif data_state == "changed":
        (results / "reference_suite.json").write_text("{}", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    path = (
        results / "reference_report.md"
        if absolute
        else Path("results/reference_report.md")
    )
    if data_state == "missing":
        with pytest.raises(SystemExit) as exc:
            main(["reproduce", "--check", str(path)])
        assert exc.value.code == 2
    else:
        assert main(["reproduce", "--check", str(path)]) == (
            0 if data_state == "match" else 1
        )


def test_user_markdown_report_still_works_without_json(tmp_path):
    custom = tmp_path / "my-report.md"
    custom.write_bytes((ROOT / "results/reference_report.md").read_bytes())
    assert main(["reproduce", "--check", str(custom)]) == 0


def test_quickstart_version_change_invalidates_installed_environment(
    tmp_path, monkeypatch
):
    spec = importlib.util.spec_from_file_location(
        "quickstart_version_test", ROOT / "quickstart.py"
    )
    quickstart = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(quickstart)
    (tmp_path / "src/rcc_refcert").mkdir(parents=True)
    for name in (
        "pyproject.toml",
        "requirements-quickstart.txt",
        "src/rcc_refcert/_version.py",
    ):
        (tmp_path / name).write_bytes((ROOT / name).read_bytes())
    monkeypatch.setattr(quickstart, "ROOT", tmp_path)
    monkeypatch.setattr(
        quickstart, "LOCK_FILE", tmp_path / "requirements-quickstart.txt"
    )
    before = quickstart._dependency_fingerprint()
    version_file = tmp_path / "src/rcc_refcert/_version.py"
    version_file.write_text('__version__ = "0.1.2rc2"\n', encoding="utf-8")
    assert quickstart._dependency_fingerprint() != before
