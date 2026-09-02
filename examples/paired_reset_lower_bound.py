"""Run the fixed paired-reset RCC lower-bound example."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from rcc_refcert.metadata import source_revision_from_environment
from rcc_refcert.paired_reset_example import (
    render_paired_reset_report,
    run_paired_reset_example,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the fixed Appendix-F paired-reset example from model "
            "qualification to a one-shot RCC lower bound."
        )
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the same fixed result as structured JSON",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        source_revision = source_revision_from_environment() if arguments.json else None
    except ValueError as exc:
        parser.error(str(exc))
    result = run_paired_reset_example(source_revision=source_revision)
    if arguments.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(render_paired_reset_report(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
