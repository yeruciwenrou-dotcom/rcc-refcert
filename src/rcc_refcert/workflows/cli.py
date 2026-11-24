"""Installed workflows and explicit, atomic result delivery."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

from ..limits import ResourceLimitError, _resource_diagnostic
from .api import analyze_cost, compare_cost_results
from .bundles import save_workflow_bundle
from .core import (
    MAX_JSON_BYTES,
    BudgetError,
    InputError,
    WorkflowLimits,
    mapping,
    read_json,
)
from .gain import GainCertificateError
from .render import render_probe, render_workflow_result, validate_width
from .templates import load_workflow_template


def add_commands(commands):
    for name, help_text in (
        ("cost", "bound preparation cost and check complete programs"),
        (
            "window",
            "resolve complexity profiles across subsystems of pure and mixed states",
        ),
    ):
        parent = commands.add_parser(name, help=help_text, description=help_text)
        sub = parent.add_subparsers(dest="workflow_command", required=True)
        template = sub.add_parser("template", help="print an editable JSON request")
        if name == "cost":
            template.add_argument(
                "name", choices=("cyclic-reset", "algorithmic-cooling")
            )
        else:
            template.add_argument(
                "name",
                nargs="?",
                default="window-state",
                choices=(
                    "window-state",
                    "pvm-counts",
                    "bell-ghz-counts",
                    "product-counts",
                    "retained-counts",
                ),
            )
            freeze = sub.add_parser(
                "prepare-protocol",
                help="freeze a complete PVM acquisition before collecting counts",
            )
            freeze.add_argument("input", type=Path)
        analyze = sub.add_parser(
            "analyze", help="analyze a request and optionally save complete evidence"
        )
        analyze.add_argument("input", type=Path, help="JSON analysis request")
        analyze.add_argument(
            "--bundle",
            type=Path,
            help="save complete inputs and results for independent verification",
        )
        analyze.add_argument(
            "--max-matrix-elements",
            type=int,
            help="override the working-element budget saved in the request",
        )
        analyze.add_argument(
            "--width",
            type=int,
            default=80,
            help="text line width, 40–240 columns (default: 80)",
        )
        _output_options(analyze)
        if name == "window":
            analyze.add_argument(
                "--plot",
                type=Path,
                help="save window values as SVG, PNG or PDF; requires the plots extra",
            )
            analyze.add_argument(
                "--csv", type=Path, help="save window quantities as CSV"
            )
        if name == "cost":
            compare = sub.add_parser(
                "compare", help="compare saved cost result JSON files"
            )
            compare.add_argument(
                "inputs",
                type=Path,
                nargs="+",
                help="cost result JSON files; comparisons preserve full task identity",
            )
            compare.add_argument(
                "--width",
                type=int,
                default=80,
                help="text line width, 40–240 columns (default: 80)",
            )
            threshold = compare.add_mutually_exclusive_group()
            threshold.add_argument(
                "--additive-gap", help="certify an additive overhead in slots"
            )
            threshold.add_argument(
                "--multiplicative-factor", help="certify a multiplicative overhead"
            )
            _output_options(compare)
    study = commands.add_parser(
        "study",
        help="compare finite-data graph-state measurements or algorithmic cooling programs",
    )
    sub = study.add_subparsers(dest="workflow_command", required=True)
    template = sub.add_parser(
        "template", help="create editable study inputs with synthetic example counts"
    )
    template.add_argument("name", choices=("cluster", "cooling"))
    template.add_argument("--noise", help="cluster: phase-flip probability per qubit")
    template.add_argument(
        "--bath", help="cooling: ground-state probability of each fresh bath qubit"
    )
    template.add_argument(
        "--false-positive",
        help="cooling: probability of recording 0 when the target is 1",
    )
    template.add_argument(
        "--false-negative",
        help="cooling: probability of recording 1 when the target is 0",
    )
    template.add_argument(
        "--failure", help="sampling failure budget per measurement strategy"
    )
    template.add_argument(
        "--cycles",
        type=int,
        help="cooling: number of cycles in the target program (1–12)",
    )
    template.add_argument(
        "--shots",
        type=int,
        help="shots per color or cooling acquisition (the cluster Z control uses twice this count)",
    )
    analyze = sub.add_parser(
        "analyze", help="report what the counts and preparation model establish"
    )
    analyze.add_argument(
        "input", type=Path, help="study request with counts and acquisition protocols"
    )
    analyze.add_argument(
        "--bundle", type=Path, help="save the evidence for independent verification"
    )
    analyze.add_argument(
        "--max-matrix-elements",
        type=int,
        help="set the matrix-element budget for the analysis",
    )
    analyze.add_argument(
        "--max-dp-updates", type=int, help="set the cooling cost-bound update budget"
    )
    analyze.add_argument(
        "--width",
        type=int,
        default=80,
        help="text line width, 40–240 columns (default: 80)",
    )
    analyze.add_argument(
        "--csv",
        type=Path,
        help="export scientific quantities with units and interval endpoints",
    )
    _output_options(analyze)
    freeze = sub.add_parser(
        "prepare-protocol",
        help="freeze a study measurement and wire mapping before collecting counts",
    )
    freeze.add_argument("input", type=Path)
    convert = sub.add_parser(
        "import-counts",
        help="reorder raw counts or joint shots using an explicit register layout",
    )
    convert.add_argument("input", type=Path)
    convert.add_argument("layout", type=Path)
    probe = commands.add_parser(
        "probe", help="find and export executable research probes"
    )
    sub = probe.add_subparsers(dest="workflow_command", required=True)
    sub.add_parser("list", help="list installed probe questions")
    for name, help_text in (
        ("show", "show a probe's question, inputs, parameters and controls"),
        ("export", "print the probe's complete editable JSON request"),
    ):
        command = sub.add_parser(name, help=help_text, description=help_text)
        command.add_argument("probe_id", help="probe identifier from 'probe list'")
        if name == "show":
            command.add_argument(
                "--format",
                dest="output_format",
                choices=("text", "json"),
                default="text",
                help="readable summary or complete JSON record (default: text)",
            )
            command.add_argument(
                "--width", type=int, default=80, help="text width, 40–240 columns"
            )


def _output_options(parser):
    parser.add_argument(
        "--format",
        dest="output_format",
        choices=("text", "json", "markdown"),
        default="text",
        help="output format (default: text)",
    )
    parser.add_argument(
        "--output", type=Path, help="save the report to a file instead of printing it"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace existing output files atomically",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="include evidence diagnostics and input identities",
    )


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


def _read_request(path, *, document=False, pvm_protocol=False):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_JSON_BYTES + 1)
    parsed = read_json(data, document=document)
    if (
        pvm_protocol
        or isinstance(parsed, dict)
        and parsed.get("schema")
        in ("rcc-refcert.pvm-windows", "rcc-refcert.finite-study")
    ):
        # Keep numeric JSON tokens exact after the bounded, duplicate-key-aware preflight.
        from decimal import Decimal

        from ..bounds.contracts import json_ready

        exact = json.loads(data, parse_float=Decimal)
        if (
            isinstance(parsed, dict)
            and parsed.get("schema") == "rcc-refcert.finite-study"
        ):
            from .core import json_value

            return json_value(exact)
        return json_ready(exact)
    return parsed


def _delivery_failed(result, name, path, exc):
    result.setdefault("delivery", {})[name] = {
        "state": "failed",
        "path": str(path),
        "reason": str(exc),
    }
    if result.get("execution", {}).get("state") != "partial":
        result["execution"] = {"state": "partial", "reason": f"{name}_write_failed"}


def run(arguments):
    run_id = uuid.uuid4().hex
    try:
        if (
            arguments.command == "study"
            and arguments.workflow_command == "import-counts"
        ):
            from .readouts import import_readout

            print(
                json.dumps(
                    import_readout(
                        _read_request(arguments.input), _read_request(arguments.layout)
                    ),
                    indent=2,
                )
            )
            return 0
        if arguments.command == "study" and arguments.workflow_command == "template":
            from .studies import study_template

            params = {
                k: getattr(arguments, k)
                for k in (
                    "noise",
                    "bath",
                    "cycles",
                    "shots",
                    "false_positive",
                    "false_negative",
                    "failure",
                )
                if getattr(arguments, k) is not None
            }
            print(json.dumps(study_template(arguments.name, **params), indent=2))
            return 0
        if arguments.workflow_command == "template":
            print(
                json.dumps(
                    load_workflow_template(arguments.name), ensure_ascii=False, indent=2
                )
            )
            return 0
        if arguments.workflow_command == "prepare-protocol":
            if arguments.command == "study":
                from .studies import prepare_study_protocol as prepare
            else:
                from .pvm import prepare_pvm_protocol as prepare

            print(
                json.dumps(
                    prepare(_read_request(arguments.input, pvm_protocol=True)),
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 0
        if arguments.command == "probe":
            from .probes import export_probe, list_probes, load_probe

            if arguments.workflow_command == "list":
                value = list_probes()
            elif arguments.workflow_command == "show":
                value = load_probe(arguments.probe_id)
                if arguments.output_format == "text":
                    print(render_probe(value, width=arguments.width), end="")
                    return 0
            else:
                value = export_probe(arguments.probe_id)
            print(json.dumps(value, ensure_ascii=False, indent=2))
            return 0
        destinations = [
            getattr(arguments, k, None) for k in ("output", "bundle", "plot", "csv")
        ]
        destinations = [p.resolve() for p in destinations if p is not None]
        if arguments.output_format != "json":
            validate_width(arguments.width)
        if getattr(arguments, "plot", None) is not None:
            from .windows import validate_plot_path

            validate_plot_path(arguments.plot)
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
        saved_outputs = {}
        if arguments.workflow_command == "compare":
            criterion = None
            if arguments.additive_gap is not None:
                criterion = {"additive_gap": arguments.additive_gap}
            elif arguments.multiplicative_factor is not None:
                criterion = {"multiplicative_factor": arguments.multiplicative_factor}
            result = compare_cost_results(
                [_read_request(p, document=True) for p in arguments.inputs],
                criterion=criterion,
            )
        else:
            request = _read_request(arguments.input)
            mapping(request, "analysis request")
            limits = None
            overrides = {
                name: getattr(arguments, name)
                for name in ("max_matrix_elements", "max_dp_updates")
                if getattr(arguments, name, None) is not None
            }
            if overrides:
                limits = WorkflowLimits.from_value(
                    {
                        **mapping(request.get("limits", {}), "limits"),
                        **overrides,
                    }
                )
            if arguments.command == "study":
                from .studies import analyze_study

                result = analyze_study(request, limits=limits)
                if arguments.csv is not None:
                    from .study_tables import study_table

                    try:
                        write_atomic(
                            arguments.csv,
                            study_table(result),
                            overwrite=arguments.overwrite,
                        )
                    except OSError as exc:
                        _delivery_failed(result, "csv", arguments.csv, exc)
                    else:
                        saved_outputs["csv"] = arguments.csv
            elif arguments.command == "cost":
                result = analyze_cost(request, limits=limits)
            else:
                from .windows import analyze_windows, export_window_files

                result = analyze_windows(request, limits=limits)
                for name, path in (("csv", arguments.csv), ("plot", arguments.plot)):
                    if path is not None:
                        try:
                            export_window_files(
                                result,
                                **{f"{name}_path": path},
                                overwrite=arguments.overwrite,
                            )
                        except OSError as exc:
                            _delivery_failed(result, name, path, exc)
                        else:
                            stop = result.get("execution", {}).get("reason") or ""
                            if name != "plot" or not stop.startswith("optional_plot_"):
                                saved_outputs[name] = path
            run_id = result["run_id"]
            if arguments.bundle is not None:
                try:
                    save_workflow_bundle(
                        arguments.bundle, request, result, overwrite=arguments.overwrite
                    )
                except (ValueError, TypeError, KeyError, OSError, OverflowError) as exc:
                    # Delivery failure must not erase an already computed result.
                    _delivery_failed(result, "bundle", arguments.bundle, exc)
                else:
                    saved_outputs["bundle"] = arguments.bundle
        view = {
            "format": arguments.output_format,
            "details": arguments.details,
            "width": arguments.width,
        }
        rendered = render_workflow_result(result, **view)
        if arguments.output is not None:
            try:
                write_atomic(arguments.output, rendered, overwrite=arguments.overwrite)
            except OSError as exc:
                _delivery_failed(result, "report", arguments.output, exc)
                for name, path in saved_outputs.items():
                    result["delivery"][name] = {"state": "saved", "path": str(path)}
                print(render_workflow_result(result, **view), end="")
                return 1
        else:
            print(rendered, end="")
        return (
            0
            if result.get("execution", {"state": "completed"})["state"] == "completed"
            and result.get("analysis_state") != "partial"
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
    except GainCertificateError as exc:
        state = (
            "certificate_failed"
            if exc.diagnostic["outcome"] == "failed"
            else "invalid_input"
        )
        error = {"state": state, "message": str(exc), "gain_selection": exc.diagnostic}
        status = 1 if state == "certificate_failed" else 2
    except (ValueError, TypeError, KeyError, OSError, OverflowError) as exc:
        error = {"state": "invalid_input", "message": str(exc)}
        status = 2
    error.update(schema="rcc-refcert.workflow-error", schema_version=1, run_id=run_id)
    if getattr(arguments, "output_format", "text") == "json":
        print(json.dumps(error, ensure_ascii=False, indent=2))
    else:
        print(f"RCC {error['state']}: {error['message']}", file=sys.stderr)
    return status
