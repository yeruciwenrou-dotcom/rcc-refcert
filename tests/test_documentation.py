import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

import quickstart
import rcc_refcert

ROOT = Path(__file__).resolve().parents[1]


def _python_blocks(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    blocks = re.findall(r"```python\n(.*?)\n```", text, flags=re.DOTALL)
    assert blocks, f"no Python example found in {path.name}"
    return "\n\n".join(blocks)


def test_reader_facing_python_examples_execute() -> None:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")
    for relative in ("README.md", "docs/MODEL_GUIDE.md"):
        path = ROOT / relative
        completed = subprocess.run(
            [sys.executable, "-c", _python_blocks(path)],
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr


def test_guided_quickstart_executes_from_repository_root() -> None:
    notebook = json.loads((ROOT / "RCC_Quickstart.ipynb").read_text(encoding="utf-8"))
    source = "\n\n".join(
        "".join(cell["source"])
        for cell in notebook["cells"]
        if cell["cell_type"] == "code"
    )
    completed = subprocess.run(
        [sys.executable, "-c", source],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Reference expectations: MATCH" in completed.stdout
    assert "Reference data: MATCH" in completed.stdout
    assert "Reference report: MATCH" in completed.stdout


def test_one_command_quickstart_runs_reader_workflow(
    monkeypatch, tmp_path, capsys
) -> None:
    calls = []

    def record(command, **kwargs):
        calls.append((command, kwargs))
        stdout = (
            '{"artifact_role": "fresh-run-evidence", '
            '"schema": "rcc-refcert.reference-suite"}\n'
            if kwargs.get("capture_output")
            else None
        )
        return subprocess.CompletedProcess(command, 0, stdout=stdout)

    monkeypatch.setattr(quickstart, "ensure_environment", lambda: Path(sys.executable))
    monkeypatch.setattr(quickstart, "ensure_installation", lambda python: None)
    monkeypatch.setattr(quickstart, "GENERATED_RESULTS", tmp_path)
    monkeypatch.setattr(quickstart.subprocess, "run", record)

    assert quickstart.main([]) == 0
    assert calls[0][0][-2:] == ["-m", "pytest"]
    assert calls[1][0][-3:-1] == ["reproduce", "--check"]
    assert calls[1][0][-1] == str(ROOT / "results" / "reference_report.md")
    assert calls[2][0][-3:] == ["--format", "json", "--details"]
    assert all(kwargs["check"] is True for _, kwargs in calls)
    assert json.loads((tmp_path / "reference_suite.json").read_text()) == {
        "artifact_role": "fresh-run-evidence",
        "schema": "rcc-refcert.reference-suite",
    }
    output = capsys.readouterr().out
    assert "passed its reader verification workflow" in output
    assert "generated_results/reference_report.md" in output


def test_quickstart_reproduce_only_skips_tests(monkeypatch, tmp_path) -> None:
    calls = []

    def record(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=(
                '{"artifact_role": "fresh-run-evidence", '
                '"schema": "rcc-refcert.reference-suite"}\n'
            ),
        )

    monkeypatch.setattr(quickstart, "ensure_environment", lambda: Path(sys.executable))
    monkeypatch.setattr(quickstart, "ensure_installation", lambda python: None)
    monkeypatch.setattr(quickstart, "GENERATED_RESULTS", tmp_path)
    monkeypatch.setattr(quickstart.subprocess, "run", record)

    assert quickstart.main(["--reproduce-only"]) == 0
    assert not any("pytest" in command for command in calls)
    assert any(command[-3:-1] == ["reproduce", "--check"] for command in calls)


def test_quickstart_installs_locked_dependencies_once(monkeypatch, tmp_path) -> None:
    calls = []

    def record(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0)

    stamp = tmp_path / "environment-stamp"
    monkeypatch.setattr(quickstart, "STAMP_FILE", stamp)
    monkeypatch.setattr(quickstart.subprocess, "run", record)

    quickstart.ensure_installation(Path(sys.executable))
    quickstart.ensure_installation(Path(sys.executable))

    assert len(calls) == 1
    assert calls[0][0][-4:] == ["-e", ".[dev]", "-c", "requirements-quickstart.txt"]
    assert calls[0][1]["check"] is True
    assert stamp.read_text(encoding="utf-8").strip() == (
        quickstart._dependency_fingerprint()
    )


def test_quickstart_rejects_old_python_before_environment_creation(
    monkeypatch,
) -> None:
    monkeypatch.setattr(quickstart.sys, "version_info", (3, 9, 18))
    monkeypatch.setattr(quickstart.sys, "platform", "darwin")
    monkeypatch.setattr(
        quickstart,
        "ensure_environment",
        lambda: pytest.fail("the environment must not be created"),
    )

    with pytest.raises(SystemExit) as error:
        quickstart.main([])

    message = str(error.value)
    assert "requires Python 3.10 or newer" in message
    assert "current interpreter is Python 3.9.18" in message
    assert "python3 --version" in message
    assert "python3 quickstart.py" in message


def test_readme_documents_mac_and_notebook_entry_points() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    notebook = json.loads((ROOT / "RCC_Quickstart.ipynb").read_text(encoding="utf-8"))

    assert "python3 --version" in readme
    assert "python3 quickstart.py" in readme
    assert ".[notebook]" in readme
    assert "Python (rcc-refcert)" in readme
    assert notebook["metadata"]["kernelspec"] == {
        "display_name": "Python (rcc-refcert)",
        "language": "python",
        "name": "rcc-refcert",
    }


def test_notebook_cells_have_valid_unique_ids() -> None:
    notebook = json.loads((ROOT / "RCC_Quickstart.ipynb").read_text(encoding="utf-8"))
    cell_ids = [cell.get("id") for cell in notebook["cells"]]

    assert notebook["nbformat"] == 4
    assert notebook["nbformat_minor"] >= 5
    assert all(
        isinstance(cell_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", cell_id)
        for cell_id in cell_ids
    )
    assert len(cell_ids) == len(set(cell_ids))


def test_local_document_links_resolve() -> None:
    documents = (
        "README.md",
        "CONTRIBUTING.md",
        "docs/SCIENTIFIC_SCOPE.md",
        "docs/END_TO_END_EXAMPLE.md",
        "docs/PAPER_MAP.md",
        "docs/CONVENTIONS.md",
        "docs/MODEL_GUIDE.md",
        "docs/OUTPUT_CONTRACT.md",
    )
    for relative in documents:
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
            if "://" in target or target.startswith("#"):
                continue
            file_target = target.partition("#")[0]
            assert (path.parent / file_target).is_file(), (
                f"broken link in {relative}: {target}"
            )


def test_public_text_omits_internal_revision_vocabulary() -> None:
    public_text = (
        ROOT / "README.md",
        ROOT / "CHANGELOG.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "RCC_Quickstart.ipynb",
        ROOT / "quickstart.py",
        *(ROOT / "examples").glob("*.py"),
        *(ROOT / "docs").glob("*.md"),
        ROOT / "results" / "reference_report.md",
        ROOT / "src" / "rcc_refcert" / "cli.py",
        ROOT / "src" / "rcc_refcert" / "report.py",
    )
    internal_patterns = (
        re.compile(r"\brcc\s+v\d+\b"),
        re.compile(r"\bchinese\s+scientific-content\b"),
        re.compile(r"\bpublic\s+arxiv\s+record\b"),
        re.compile(r"\bearlier\s+revision\b"),
        re.compile(r"\bauthors\s+update\s+it\b"),
    )

    for path in public_text:
        text = path.read_text(encoding="utf-8").casefold()
        for pattern in internal_patterns:
            assert pattern.search(text) is None, (
                f"internal revision language in {path.name}"
            )


def test_manuscript_alignment_is_explicit_and_scoped() -> None:
    for relative in ("README.md", "docs/PAPER_MAP.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert text.count("**Manuscript alignment.**") == 1
        assert "aligned with version 4 of the\n> RCC manuscript" in text
        assert "[arXiv:2509.18205v3](https://arxiv.org/abs/2509.18205v3)" in text
        assert (
            "equation numbers in this repository therefore refer to manuscript version 4"
            in text.replace("\n> ", " ")
        )
        assert (
            "The repository provides executable finite-model evidence for selected"
            in text.replace("\n> ", " ")
        )
        assert (
            "the paper remains responsible for the analytic and model-family arguments"
            in text.replace("\n> ", " ")
        )


def test_github_markdown_avoids_known_unsupported_math_syntax() -> None:
    public_documents = (
        ROOT / "README.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "RCC_Quickstart.ipynb",
        *(ROOT / "docs").glob("*.md"),
        ROOT / "results" / "reference_report.md",
    )
    unsupported = (r"\(", r"\[", r"\operatorname", r"\#")

    for path in public_documents:
        text = path.read_text(encoding="utf-8")
        for token in unsupported:
            assert token not in text, (
                f"GitHub-incompatible math token {token!r} in {path.name}"
            )


def test_github_markdown_tables_have_consistent_column_counts() -> None:
    public_documents = (
        ROOT / "README.md",
        ROOT / "CHANGELOG.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "NOTICE.md",
        *(ROOT / "docs").glob("*.md"),
        ROOT / "results" / "reference_report.md",
    )

    for path in public_documents:
        expected_cells = None
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if line.startswith("|") and line.endswith("|"):
                cells = len(re.findall(r"(?<!\\)\|", line)) - 1
                if expected_cells is None:
                    expected_cells = cells
                assert cells == expected_cells, (
                    f"malformed Markdown table row in {path.name}:{line_number}"
                )
            else:
                expected_cells = None


def test_public_math_is_not_presented_as_source_code() -> None:
    rejected = {
        ROOT / "docs" / "PAPER_MAP.md": (
            "`c_{s,a}`",
            "`ell_{s,a}`",
            "`nu(s,a)`",
            "`Omega_0`",
            "`H(I-T)^(-1)`",
            "`X_x=J(W_x)`",
            "`C_n^*=2^n`",
        ),
        ROOT / "docs" / "CONVENTIONS.md": (
            "`2^(-ell)`",
            "`2^(-|p|)`",
            "`2^(-ell/2)`",
            "`(I-T)^(-1)`",
        ),
    }

    for path, tokens in rejected.items():
        text = path.read_text(encoding="utf-8")
        for token in tokens:
            assert token not in text, f"unrendered mathematical source in {path.name}"


def test_public_complexity_framing_preserves_relationality() -> None:
    public_documents = (
        ROOT / "README.md",
        ROOT / "docs" / "SCIENTIFIC_SCOPE.md",
    )
    rejected_overstatements = (
        "not a property of the state",
        "property of a target together with a",
    )

    for path in public_documents:
        text = path.read_text(encoding="utf-8").casefold()
        assert "relational physical quantity" in text
        for statement in rejected_overstatements:
            assert statement not in text, (
                f"overstated intrinsic-property claim in {path.name}"
            )

    readme = (ROOT / "README.md").read_text(encoding="utf-8").casefold()
    assert (
        "rcc is a structure-fair, model-relative framework for defining and\n"
        "lower-bounding quantum circuit complexity"
    ) in readme


def test_end_to_end_docs_preserve_theorem_and_unit_hierarchy() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    paper_map = (ROOT / "docs" / "PAPER_MAP.md").read_text(encoding="utf-8")
    example = (ROOT / "docs" / "END_TO_END_EXAMPLE.md").read_text(encoding="utf-8")

    for text in (readme, paper_map, example):
        assert "Theorem 3.1" in text
        assert "st}_R" in text or "st_R" in text

    assert "Appendix A" in paper_map
    assert "Appendix A" in example
    assert "one-$" not in example
    assert (
        "D_{\\max}^{0}(\\lvert0\\rangle\\langle0\\rvert\\Vert I/2)\n"
        "=1\\ \\mathrm{bit}\n"
        "=1\\,\\mathrm{st}_R."
    ) in readme
    assert "C_{\\mathrm{opt}}^{(0)}\\ge1" in readme


def test_public_exports_are_resolvable() -> None:
    for name in rcc_refcert.__all__:
        assert hasattr(rcc_refcert, name)

    assert {
        "Action",
        "FiniteControlModel",
        "audit_model",
        "audit_case",
        "audit_reference_suite",
        "get_case",
        "minimum_domination_constant",
        "verify_bellman_choi",
        "verify_reference_potential",
        "analyze_reference_gain_cost",
    } <= set(rcc_refcert.__all__)
