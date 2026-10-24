"""Exercise documentation links and the Notebook's last manual command."""

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


def _prose(path):
    if path.suffix == ".ipynb":
        notebook = json.loads(path.read_text(encoding="utf-8"))
        return "\n\n".join(
            "".join(cell["source"])
            for cell in notebook["cells"]
            if cell["cell_type"] == "markdown"
        )
    return path.read_text(encoding="utf-8")


def _anchors(path):
    prose = re.sub(r"```.*?```", "", _prose(path), flags=re.DOTALL)
    anchors, counts = set(), {}
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*$", prose, re.MULTILINE):
        heading = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", heading)
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        number = counts.get(slug, 0)
        counts[slug] = number + 1
        anchors.add(slug + (f"-{number}" if number else ""))
    anchors.update(re.findall(r'<a\s+(?:name|id)="([^"]+)"', prose))
    return anchors


def test_all_guides_and_notebooks_link_to_existing_files_and_sections():
    documents = [*ROOT.glob("*.md"), *ROOT.glob("*.ipynb")]
    for directory in ("docs", ".github", "results", "src/rcc_refcert/reference_data"):
        documents.extend((ROOT / directory).rglob("*.md"))
    for path in documents:
        for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", _prose(path)):
            if "://" in target or target.startswith("mailto:"):
                continue
            relative, _, fragment = target.partition("#")
            destination = (
                (path.parent / unquote(relative)).resolve() if relative else path
            )
            assert destination.is_file(), f"{path.name}: missing {target}"
            if fragment and destination.suffix in {".md", ".ipynb"}:
                assert unquote(fragment) in _anchors(destination), (
                    f"{path.name}: missing section {target}"
                )


def test_bounds_notebook_terminal_followup_runs_without_shell_activation(tmp_path):
    notebook = json.loads(
        (ROOT / "RCC_Bounds_Quickstart.ipynb").read_text(encoding="utf-8")
    )
    source = "\n\n".join(
        "".join(cell["source"])
        for cell in notebook["cells"]
        if cell["cell_type"] == "code"
    )
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PATH": os.defpath}
    environment.pop("VIRTUAL_ENV", None)
    execution = subprocess.run(
        [sys.executable, "-c", source],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert execution.returncode == 0, execution.stderr
    cell = next(
        cell for cell in notebook["cells"] if cell["id"] == "bounds-bundle-next"
    )
    blocks = re.findall(
        r"```bash\n(.*?)\n```", "".join(cell["source"]), flags=re.DOTALL
    )
    assert len(blocks) == 1
    command = shlex.split(blocks[0])
    assert command[:3] == [".venv/bin/python", "-m", "rcc_refcert"]
    # Use the test installation, as documented for a reader-managed environment.
    command[0] = sys.executable
    bundle = tmp_path / command[-1]
    original = bundle.read_bytes()
    verification = subprocess.run(
        command,
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert verification.returncode == 0, verification.stderr
    assert "Fresh matrix verification: pass" in verification.stdout
    assert "Historical results supported: yes" in verification.stdout
    assert "Integer lower bound: 1" in verification.stdout
    assert bundle.read_bytes() == original
