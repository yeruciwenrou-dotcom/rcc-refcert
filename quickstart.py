from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENVIRONMENT = ROOT / ".venv"
LOCK_FILE = ROOT / "requirements-quickstart.txt"
STAMP_FILE = ENVIRONMENT / ".rcc-refcert-quickstart"
GENERATED_RESULTS = ROOT / "generated_results"
MINIMUM_PYTHON = (3, 10)


def require_supported_python() -> None:
    if sys.version_info[:2] >= MINIMUM_PYTHON:
        return

    detected = ".".join(str(part) for part in sys.version_info[:3])
    if sys.platform == "darwin":
        guidance = (
            "On macOS, install Python 3.10 or newer from python.org or with "
            "Homebrew, then run:\n"
            "  python3 --version\n"
            "  python3 quickstart.py"
        )
    elif sys.platform == "win32":
        guidance = (
            "On Windows, install Python 3.10 or newer, then run:\n"
            "  py -3 --version\n"
            "  py -3 quickstart.py"
        )
    else:
        guidance = (
            "Install Python 3.10 or newer, then run:\n"
            "  python3 --version\n"
            "  python3 quickstart.py"
        )
    raise SystemExit(
        "rcc-refcert requires Python 3.10 or newer; "
        f"the current interpreter is Python {detected}.\n{guidance}"
    )


def _environment_python() -> Path:
    if sys.platform == "win32":
        return ENVIRONMENT / "Scripts" / "python.exe"
    return ENVIRONMENT / "bin" / "python"


def ensure_environment() -> Path:
    python = _environment_python()
    if not python.is_file():
        subprocess.run(
            [sys.executable, "-m", "venv", str(ENVIRONMENT)],
            cwd=ROOT,
            check=True,
        )
    return python


def _dependency_fingerprint() -> str:
    digest = hashlib.sha256()
    for path in (ROOT / "pyproject.toml", LOCK_FILE):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def ensure_installation(python: Path) -> None:
    fingerprint = _dependency_fingerprint()
    current = (
        STAMP_FILE.read_text(encoding="utf-8").strip() if STAMP_FILE.is_file() else ""
    )
    if current == fingerprint:
        print("Reusing the locked quickstart environment.")
        return

    print("Installing the package and locked verification dependencies ...")
    subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "-e",
            ".[dev]",
            "-c",
            LOCK_FILE.name,
        ],
        cwd=ROOT,
        check=True,
    )
    STAMP_FILE.write_text(f"{fingerprint}\n", encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Set up RCC RefCert and run its reader verification workflow."
    )
    parser.add_argument(
        "--reproduce-only",
        action="store_true",
        help="skip the test suite and only verify plus regenerate the reference evidence",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    require_supported_python()
    arguments = _build_parser().parse_args(argv)
    python = ensure_environment()
    ensure_installation(python)

    if not arguments.reproduce_only:
        print("Running the independent test suite ...")
        subprocess.run(
            [str(python), "-W", "error", "-m", "pytest"],
            cwd=ROOT,
            check=True,
        )

    print("Checking the frozen reference evidence ...")
    subprocess.run(
        [
            str(python),
            "-m",
            "rcc_refcert",
            "reproduce",
            "--check",
            str(ROOT / "results" / "reference_report.md"),
        ],
        cwd=ROOT,
        check=True,
    )

    print("Writing a fresh report and machine-readable result ...")
    GENERATED_RESULTS.mkdir(exist_ok=True)
    report = GENERATED_RESULTS / "reference_report.md"
    structured = GENERATED_RESULTS / "reference_suite.json"
    completed = subprocess.run(
        [
            str(python),
            "-m",
            "rcc_refcert",
            "reproduce",
            "--output",
            str(report),
            "--format",
            "json",
            "--details",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    json.loads(completed.stdout)
    structured.write_text(completed.stdout, encoding="utf-8")

    print(
        "\nRCC RefCert passed its reader verification workflow.\n"
        "Frozen evidence: results/reference_report.md\n"
        "Fresh evidence: generated_results/reference_report.md and "
        "generated_results/reference_suite.json"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
