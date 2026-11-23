import os
import re
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell 5.1 example")
def test_documented_spectrum_with_released_package(tmp_path: Path) -> None:
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text("utf-8")
    command = re.search(r"```powershell\n([^\n]+)\n```", readme)
    assert command
    package = tmp_path / "package"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--only-binary=:all:",
            "--target",
            str(package),
            "rcc-refcert==0.3.0",
        ],
        check=True,
        cwd=tmp_path,
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(package)
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env["PATH"]
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        "if ($PSVersionTable.PSVersion.Major -ne 5 -or "
        "$PSVersionTable.PSVersion.Minor -ne 1) { throw 'Expected 5.1' }\n"
        + command.group(1)
        + "\nif ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }\n"
        + "python -m rcc_refcert bound spectrum spectrum.json\nexit $LASTEXITCODE"
    )
    proc = subprocess.run(
        ["powershell.exe", "-NoLogo", "-NoProfile", "-Command", script],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Integer-slot lower bound: 1" in proc.stdout
    assert (tmp_path / "spectrum.json").read_bytes().isascii()
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as stream:
            stream.write(
                "\nWindows PowerShell 5.1 ran the README template command with "
                "PyPI 0.3.0. Integer-slot lower bound: **1**.\n"
            )
