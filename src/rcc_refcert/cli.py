from __future__ import annotations

import argparse
import json
import math
from collections.abc import Sequence
from importlib import resources
from pathlib import Path

from . import __version__
from .audit import audit_case, audit_reference_suite
from .cases import CASES, case_names, get_case
from .metadata import source_revision_from_environment
from .render import (
    case_payload,
    cases_payload,
    format_case,
    format_case_list,
    format_suite,
    reference_payload_matches,
    reference_payload_text_matches,
    suite_payload,
)
from .report import build_reference_report, write_reference_report

_BUNDLED_CHECK = object()
_BUNDLED_REFERENCE_DIRECTORY = "reference_data"
_BUNDLED_REPORT_NAME = "reference_report.md"
_BUNDLED_DATA_NAME = "reference_suite.json"


def _bundled_reference_text(name: str) -> str:
    return (
        resources.files("rcc_refcert")
        .joinpath(_BUNDLED_REFERENCE_DIRECTORY)
        .joinpath(name)
        .read_text(encoding="utf-8")
    )


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def _nonnegative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return parsed


def _positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be finite and positive")
    return parsed


def _add_numerical_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--max-depth",
        type=_positive_int,
        default=8,
        help="largest action depth used in the H.1 realization check (default: 8)",
    )
    parser.add_argument(
        "--truncation-steps",
        dest="max_transient_steps",
        type=_nonnegative_int,
        default=16,
        help=(
            "largest number of transient continuations included in the H.2 "
            "partial sum (default: 16)"
        ),
    )
    parser.add_argument(
        "--tolerance",
        type=_positive_float,
        default=1e-10,
        help="matrix tolerance and relative certificate-error budget (default: 1e-10)",
    )


def _add_format_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=("text", "json"),
        default="text",
        help="output format (default: text)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rcc-refcert",
        description=(
            "Construct and audit finite-control RCC semidensities, reference "
            "certificates, and gain-cost assignments."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    examples = commands.add_parser(
        "examples", help="list the bundled reference cases and their purpose"
    )
    _add_format_argument(examples)

    example = commands.add_parser(
        "example", help="run one model and all proof objects supplied for it"
    )
    example.add_argument("name", choices=case_names(), help="stable case name")
    example.add_argument(
        "--details",
        action="store_true",
        help="show residuals, margins, and suggested codewords",
    )
    _add_format_argument(example)
    _add_numerical_arguments(example)

    reproduce = commands.add_parser(
        "reproduce", help="run the complete deterministic reference suite"
    )
    destination = reproduce.add_mutually_exclusive_group()
    destination.add_argument(
        "--output",
        type=Path,
        help="write the generated Markdown report to this explicit path",
    )
    destination.add_argument(
        "--check",
        nargs="?",
        type=Path,
        const=_BUNDLED_CHECK,
        metavar="PATH",
        help=(
            "compare with PATH without overwriting it "
            "(default: frozen evidence installed with the package)"
        ),
    )
    reproduce.add_argument(
        "--details",
        action="store_true",
        help="include individual case checks in JSON output",
    )
    _add_format_argument(reproduce)
    _add_numerical_arguments(reproduce)
    return parser


def _dump_json(payload: dict[str, object]) -> None:
    print(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
    )


def _run_reproduce(
    arguments: argparse.Namespace,
    parser: argparse.ArgumentParser,
    *,
    source_revision: str | None = None,
) -> int:
    suite = audit_reference_suite(
        max_depth=arguments.max_depth,
        max_transient_steps=arguments.max_transient_steps,
        tol=arguments.tolerance,
    )
    report_match: bool | None = None
    report_path: Path | str | None = None
    reference_match: bool | None = None
    reference_path: Path | str | None = None

    if arguments.output is not None:
        report_path = write_reference_report(arguments.output, suite)
    elif arguments.check is _BUNDLED_CHECK:
        report_path = f"package:{_BUNDLED_REFERENCE_DIRECTORY}/{_BUNDLED_REPORT_NAME}"
        report_match = _bundled_reference_text(
            _BUNDLED_REPORT_NAME
        ) == build_reference_report(suite)
        reference_path = f"package:{_BUNDLED_REFERENCE_DIRECTORY}/{_BUNDLED_DATA_NAME}"
        reference_match = reference_payload_text_matches(
            _bundled_reference_text(_BUNDLED_DATA_NAME), suite
        )
    elif arguments.check is not None:
        report_path = arguments.check
        if not report_path.is_file():
            parser.error(f"reference report not found: {report_path}")
        report_match = report_path.read_text(
            encoding="utf-8"
        ) == build_reference_report(suite)
        candidate = report_path.with_name("reference_suite.json")
        if candidate.is_file():
            reference_path = candidate
            reference_match = reference_payload_matches(candidate, suite)
        elif report_path == Path("results/reference_report.md"):
            parser.error(f"structured reference result not found: {candidate}")

    if arguments.output_format == "json":
        payload = suite_payload(
            suite,
            detailed=arguments.details,
            source_revision=source_revision,
        )
        payload["report"] = {
            "path": str(report_path) if report_path is not None else None,
            "written": arguments.output is not None,
            "matches": report_match,
        }
        payload["reference_data"] = {
            "path": str(reference_path) if reference_path is not None else None,
            "matches": reference_match,
        }
        _dump_json(payload)
    else:
        print(format_suite(suite))
        if arguments.output is not None:
            print(f"\nReport written: {report_path}")
        elif arguments.check is not None:
            if reference_path is not None:
                label = "MATCH" if reference_match else "MISMATCH"
                print(f"\nReference data: {label} ({reference_path})")
            label = "MATCH" if report_match else "MISMATCH"
            prefix = "" if reference_path is not None else "\n"
            print(f"{prefix}Reference report: {label} ({report_path})")

    return (
        0
        if (
            suite.matches_reference_expectations
            and reference_match is not False
            and report_match is not False
        )
        else 1
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        source_revision = (
            source_revision_from_environment()
            if arguments.output_format == "json"
            else None
        )
        if arguments.command == "examples":
            if arguments.output_format == "json":
                _dump_json(cases_payload(CASES, source_revision=source_revision))
            else:
                print(format_case_list(CASES))
            return 0

        if arguments.command == "example":
            result = audit_case(
                get_case(arguments.name),
                max_depth=arguments.max_depth,
                max_transient_steps=arguments.max_transient_steps,
                tol=arguments.tolerance,
            )
            if arguments.output_format == "json":
                _dump_json(
                    case_payload(
                        result,
                        detailed=arguments.details,
                        source_revision=source_revision,
                    )
                )
            else:
                print(format_case(result, detailed=arguments.details))
            return 0 if result.matches_expectations else 1

        return _run_reproduce(
            arguments,
            parser,
            source_revision=source_revision,
        )
    except (KeyError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
