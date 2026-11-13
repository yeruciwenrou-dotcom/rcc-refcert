"""Installed workflows and explicit, atomic result delivery."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

from ..bundle_storage import _read_json
from ..limits import ResourceLimitError, _resource_diagnostic
from .api import analyze_cost, compare_cost_results
from .bundles import save_workflow_bundle
from .core import BudgetError, InputError, WorkflowLimits
from .render import render_workflow_result
from .templates import load_workflow_template


def add_commands(commands):
    for name, help_text in (
        ("cost", "bound preparation cost and check complete programs"),
        ("window", "analyze quantum-state windows and correlations"),
    ):
        parent = commands.add_parser(name, help=help_text)
        sub = parent.add_subparsers(dest="workflow_command", required=True)
        template = sub.add_parser(
            "template", help="print an editable installed request"
        )
        if name == "cost":
            template.add_argument(
                "name", choices=("cyclic-reset", "algorithmic-cooling")
            )
        else:
            template.set_defaults(name="window-state")
        analyze = sub.add_parser(
            "analyze", help="analyze a request and optionally save complete evidence"
        )
        analyze.add_argument("input", type=Path)
        analyze.add_argument("--bundle", type=Path)
        analyze.add_argument("--max-matrix-elements", type=int)
        analyze.add_argument("--width", type=int, default=80)
        _output_options(analyze)
        if name == "window":
            analyze.add_argument("--plot", type=Path)
            analyze.add_argument("--csv", type=Path)
        if name == "cost":
            compare = sub.add_parser(
                "compare", help="compare saved cost result JSON files"
            )
            compare.add_argument("inputs", type=Path, nargs="+")
            compare.add_argument("--width", type=int, default=80)
            _output_options(compare)
    probe = commands.add_parser(
        "probe", help="find and export executable research probes"
    )
    sub = probe.add_subparsers(dest="workflow_command", required=True)
    sub.add_parser("list", help="list installed probe questions")
    for name in ("show", "export"):
        command = sub.add_parser(name)
        command.add_argument("probe_id")


def _output_options(parser):
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=("text", "json", "markdown"),
        default="text",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--details", action="store_true")


def write_atomic(path, content, *, overwrite=False):
    destination = Path(path)
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=".rcc-output-", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(temporary, destination)
        else:
            os.link(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _read_request(path):
    with Path(path).open("rb") as stream:
        data = stream.read(32 * 1024 * 1024 + 1)
    if len(data) > 32 * 1024 * 1024:
        raise BudgetError("input JSON exceeds the 32 MiB budget")
    return _read_json(data)


def run(arguments):
    run_id = uuid.uuid4().hex
    try:
        if arguments.workflow_command == "template":
            print(
                json.dumps(
                    load_workflow_template(arguments.name), ensure_ascii=False, indent=2
                )
            )
            return 0
        if arguments.command == "probe":
            from .probes import export_probe, list_probes, load_probe

            if arguments.workflow_command == "list":
                value = list_probes()
            elif arguments.workflow_command == "show":
                value = load_probe(arguments.probe_id)
            else:
                value = export_probe(arguments.probe_id)
            print(json.dumps(value, ensure_ascii=False, indent=2))
            return 0
        destinations = [
            getattr(arguments, k, None) for k in ("output", "bundle", "plot", "csv")
        ]
        destinations = [p.resolve() for p in destinations if p is not None]
        if len(set(destinations)) != len(destinations):
            raise InputError("output paths must be distinct")
        sources = (
            arguments.inputs
            if arguments.workflow_command == "compare"
            else [arguments.input]
        )
        if any(p in {s.resolve() for s in sources} for p in destinations):
            raise InputError("output paths must not overwrite input files")
        for path in destinations:
            if path.exists() and not arguments.overwrite:
                raise FileExistsError(
                    f"{path}: already exists; select a new path or explicitly use --overwrite"
                )
        if arguments.workflow_command == "compare":
            result = compare_cost_results([_read_request(p) for p in arguments.inputs])
        else:
            request = _read_request(arguments.input)
            limits = None
            if arguments.max_matrix_elements is not None:
                limits = WorkflowLimits.from_value(
                    {
                        **request.get("limits", {}),
                        "max_matrix_elements": arguments.max_matrix_elements,
                    }
                )
            if arguments.command == "cost":
                result = analyze_cost(request, limits=limits)
            else:
                from .windows import analyze_windows, export_window_files

                result = analyze_windows(request, limits=limits)
                export_window_files(
                    result,
                    csv_path=arguments.csv,
                    plot_path=arguments.plot,
                    overwrite=arguments.overwrite,
                )
            run_id = result["run_id"]
            if arguments.bundle is not None:
                save_workflow_bundle(
                    arguments.bundle, request, result, overwrite=arguments.overwrite
                )
        rendered = render_workflow_result(
            result,
            format=arguments.output_format,
            details=arguments.details,
            width=arguments.width,
        )
        if arguments.output is not None:
            write_atomic(arguments.output, rendered, overwrite=arguments.overwrite)
        else:
            print(rendered, end="")
        return (
            0
            if result.get("execution", {"state": "completed"})["state"] == "completed"
            else 1
        )
    except KeyboardInterrupt:
        print(
            f"RCC workflow interrupted; run {run_id} did not complete.", file=sys.stderr
        )
        return 130
    except ResourceLimitError as exc:
        error = {
            "state": "resource_limited",
            "message": str(exc),
            "resource": exc.resource,
            "estimate": _resource_diagnostic(exc.estimate),
            "limit": _resource_diagnostic(exc.limit),
        }
        status = 3
    except BudgetError as exc:
        error = {"state": "resource_limited", "message": str(exc)}
        status = 3
    except (ValueError, TypeError, KeyError, OSError, OverflowError) as exc:
        error = {"state": "invalid_input", "message": str(exc)}
        status = 2
    error.update(schema="rcc-refcert.workflow-error", schema_version=1, run_id=run_id)
    if getattr(arguments, "output_format", "text") == "json":
        print(json.dumps(error, ensure_ascii=False, indent=2))
    else:
        print(f"RCC {error['state']}: {error['message']}", file=sys.stderr)
    return status
