import json
import os
import re
import subprocess
import sys
from functools import cache
from pathlib import Path
from urllib.parse import unquote, urlsplit

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
    for relative in (
        "README.md",
        "docs/MODEL_GUIDE.md",
        "docs/TERMINAL_BOUNDS.md",
    ):
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


def test_one_command_quickstart_runs_complete_gate(
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
    assert "matched its reference results" in output
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


@cache
def _git_document(ref, relative):
    # Source archives and shallow CI clones only carry the current file tree.
    if not (ROOT / ".git").exists():
        return None
    command = ["git", "-C", str(ROOT)]
    if subprocess.run(
        [*command, "cat-file", "-e", f"{ref}^{{commit}}"],
        capture_output=True,
        check=False,
    ).returncode:
        return None
    kind = subprocess.run(
        [*command, "cat-file", "-t", f"{ref}:{relative}"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert kind.returncode == 0, f"{ref}:{relative}"
    if kind.stdout.strip() == "tree" or not relative.lower().endswith(".md"):
        return ""
    return subprocess.check_output([*command, "show", f"{ref}:{relative}"]).decode()


def _anchors(markdown):
    anchors = set(re.findall(r'(?:id|name)="([^"]+)"', markdown))
    headings = {}
    for title in re.findall(
        r"^#{1,6} (.+)$",
        re.sub(r"^```.*?^```[^\n]*", "", markdown, flags=re.MULTILINE | re.DOTALL),
        flags=re.MULTILINE,
    ):
        base = re.sub(r"[^\w -]", "", title.strip().lower()).replace(" ", "-")
        n = headings.get(base, 0)
        anchors.add(f"{base}-{n}" if n else base)
        headings[base] = n + 1
    return anchors


def test_local_document_links_resolve() -> None:
    repo = "/yeruciwenrou-dotcom/rcc-refcert/"
    paths = [
        ROOT / n
        for n in ("README.md", "CHANGELOG.md", "CONTRIBUTING.md", ".zenodo.json")
    ]
    for path in [*paths, *(ROOT / "docs").glob("*.md")]:
        source = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            source = json.loads(source)["description"]
        links = re.findall(r"\[([^]\n]*)\]\(([^)\s]+)\)", source)
        links += [("", url) for url in re.findall(r'href="([^"]+)"', source)]
        for label, target in links:
            url = urlsplit(target)
            ref = None
            if url.netloc:
                if url.netloc != "github.com" or not url.path.startswith(repo):
                    continue
                parts = unquote(url.path.removeprefix(repo)).split("/", 2)
                if parts[0] == "commit":
                    displayed = re.search(
                        r"(?<![0-9a-f])[0-9a-f]{7,40}(?![0-9a-f])", label
                    )
                    if displayed:
                        assert parts[1].startswith(displayed[0]), (path, target, label)
                if parts[0] not in ("blob", "tree") or len(parts) < 3:
                    continue
                _, ref, relative = parts
                dest = ROOT / relative
            else:
                if url.scheme:
                    continue
                dest = (path.parent / unquote(url.path)).resolve() if url.path else path
            historical = _git_document(ref, relative) if ref else None
            if historical is None:
                assert dest.exists(), (path, target)
            if url.fragment and dest.suffix.lower() == ".md":
                document = (
                    historical
                    if historical is not None
                    else dest.read_text(encoding="utf-8")
                )
                assert unquote(url.fragment) in _anchors(document), (path, target)
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    pin = re.search(r"git switch --detach ([0-9a-f]{40})", readme)[1]
    assert f"/archive/{pin}.zip" in readme
    assert f"/commit/{pin}" in readme
    if _git_document(pin, "examples/half_erasure.json") is None:
        assert (ROOT / "examples/half_erasure.json").is_file()


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
        alignment = re.search(
            r"^> \*\*Manuscript alignment\.\*\*.*(?:\n>.*)*", text, flags=re.MULTILINE
        )
        assert alignment is not None
        prose = " ".join(re.sub(r"(?m)^>\s*", "", alignment.group()).split())
        assert "aligned with version 4" in prose
        assert "manuscript version 4" in prose
        assert "[RCC manuscript](https://arxiv.org/abs/2509.18205)" in prose


def test_github_markdown_avoids_known_unsupported_math_syntax() -> None:
    public_documents = (
        ROOT / "README.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "RCC_Quickstart.ipynb",
        *(ROOT / "docs").glob("*.md"),
        ROOT / "results" / "reference_report.md",
    )
    unsupported = (r"\(", r"\[", r"\operatorname", r"\#", r"\,", r"\!")

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

    assert "docs/END_TO_END_EXAMPLE.md)" in readme
    assert "Appendix A" in paper_map and "Appendix A" in example
    assert "one-$" not in example
    assert r"D_{\max}^{0}(\rho\Vert\sigma_R)=\log_2 2=1." in example
    assert r"1\thinspace{\rm st}_R" in example
    assert "C_{\\rm opt}^{(0)}(\\rho;\\mathfrak M_R)\n\\ge\nF_{1,0}(1)\n=1." in example
    assert r"C_{\rm opt}^{(0)}(\rho;\mathfrak M_R)=1" in example


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
