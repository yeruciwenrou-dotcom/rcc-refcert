"""CLI surface for complete analysis evidence."""

from __future__ import annotations

import json
from pathlib import Path

from .bounds.scalar import decimal_endpoint, decimal_string, rational
from .bundle import inspect_analysis_bundle, verify_analysis_bundle
from .limits import ComputationLimits, ResourceLimitError, _resource_diagnostic


def _constant(value: str) -> str:
    # Seventeen significant digits distinguish neighboring binary64 constants.
    return format(float(rational(value)), ".17g")


def _historical_support(value):
    return {True: "yes", False: "no", None: "unresolved"}[value]


def render_bundle_report(report: dict) -> str:
    if report.get("schema_version") in (2, 3, 4, 5):
        lines = [
            "RCC workflow evidence",
            f"Task: {report['kind']}",
            f"Stored record consistency: {report['record_consistency']}",
        ]
        if report["schema"] == "rcc-refcert.bundle-inspection":
            lines.extend(
                [
                    f"Historical decision: {report['historical_decision']}",
                    "Inspect checks the saved record. Use bundle verify to recompute the result.",
                ]
            )
        else:
            if report["schema_version"] == 3:
                from .bounds.api import render_record as render_result
            else:
                from .workflows.render import render_workflow_result as render_result

            lines.extend(
                [
                    f"Recomputation from the archived inputs: {report['fresh_verification']['outcome']}",
                    f"Historical results supported: {_historical_support(report['historical_results_supported'])}",
                    render_result(report["fresh_result"]).rstrip(),
                ]
            )
            if coverage := report.get("candidate_replay"):
                lines.insert(
                    -1,
                    f"Candidate programs replayed: {coverage['checked']} of {coverage['expected']}.",
                )
                lines.insert(
                    -1,
                    "Historical cost interval supported: "
                    + _historical_support(coverage["historical_interval_supported"]),
                )
        return "\n".join(lines) + "\n"
    lines = [
        "RCC analysis evidence",
        f"Model: {report['model']}",
        f"Stored record consistency: {report['record_consistency']}",
    ]
    if report["schema"] == "rcc-refcert.bundle-inspection":
        lines.extend(
            [
                f"Original producer: {report['producer']['version']}",
                f"Stored requests: {report['request_count']}",
                "Matrix revalidation: not run",
            ]
        )
    else:
        fresh = report["fresh_verification"]
        lines.append(
            f"Fresh matrix verification: {fresh['outcome']} ({fresh['evidence']})"
        )
        if fresh["constant_exact"] is not None:
            lines.append(
                "Fresh certificate constant: " + _constant(fresh["constant_exact"])
            )
        historical = report["historical_verification"]["constant_exact"]
        if historical is not None:
            lines.append("Historical certificate constant: " + _constant(historical))
        lines.append(
            "Historical results supported: "
            + _historical_support(report["historical_results_supported"])
        )
        if report["controls"]["tolerance_overridden"]:
            lines.append("Tolerance: explicit override; original controls retained")
        if (
            report["historical_results_supported"] is False
            and fresh["outcome"] == "pass"
        ):
            lines.append(
                "Historical support is assessed before rounding. The fresh certificate constant must be at most the saved value."
            )
        for index, request in enumerate(report["requests"], 1):
            lines.append(
                f"Request {index} ({request['kind']}): scalar comparison "
                + (
                    "match"
                    if request["current_scalar_comparison"]["matches"]
                    else "mismatch"
                )
            )
            lines.append(
                "  Same-version replay: " + request["same_version_replay"]["status"]
            )
            if request["fresh_bound"] is not None:
                new_c, old_c = (
                    request["fresh_constant_exact"],
                    request["historical_constant_exact"],
                )
                relation = "<=" if request["historical_constant_supported"] else ">"
                lines.append(
                    f"  Usable constants: fresh {_constant(new_c)} {relation} historical {_constant(old_c)}"
                )
                cost = request["fresh_bound"]["cost"]
                lines.append(
                    "  Fresh lower bound: "
                    + decimal_string(decimal_endpoint(cost["lower_bound_slots"]), 8)
                    + " atomic slots (rounded down)"
                )
                if cost["integer_lower_bound_slots"] is not None:
                    old_slots = request["historical_record"]["cost"][
                        "integer_lower_bound_slots"
                    ]
                    if (
                        old_slots is not None
                        and not request["historical_constant_supported"]
                    ):
                        lines.append(
                            f"  Integer lower bounds: fresh {cost['integer_lower_bound_slots']}, historical {old_slots}"
                        )
                    else:
                        lines.append(
                            f"  Integer lower bound: {cost['integer_lower_bound_slots']}"
                        )
            if not request["current_scalar_comparison"]["matches"]:
                lines.append(
                    "  Recomputing the original scalar inputs differs from the saved record; inspect the JSON comparison."
                )
        if fresh["outcome"] != "pass":
            for check in fresh["checks"]:
                if check["outcome"] != "pass":
                    lines.append(f"  {check['name']}: {check['message']}")
    lines.append(
        "Physical model qualification and sampling premises: supplied externally."
    )
    return "\n".join(lines) + "\n"


def run(arguments) -> int:
    try:
        limits = ComputationLimits(max_matrix_elements=arguments.max_matrix_elements)
        if arguments.bundle_command == "inspect":
            report = inspect_analysis_bundle(arguments.input, limits=limits)
            status = 0
        else:
            report = verify_analysis_bundle(
                arguments.input, tol=arguments.tolerance, limits=limits
            )
            status = (
                0
                if (
                    report["fresh_verification"]["outcome"] == "pass"
                    and report["historical_results_supported"] is True
                )
                else 1
            )
        serialized = (
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        )
        if arguments.output is not None:
            # Compute before opening, and preserve existing evidence files.
            with Path(arguments.output).open("x", encoding="utf-8") as handle:
                handle.write(serialized)
        print(
            serialized
            if arguments.output_format == "json"
            else render_bundle_report(report),
            end="",
        )
        return status
    except ResourceLimitError as exc:
        error = {
            "schema": "rcc-refcert.bundle-error",
            "schema_version": 1,
            "state": "resource_limit",
            "message": str(exc),
            "resource": exc.resource,
            "estimate": _resource_diagnostic(exc.estimate),
            "limit": _resource_diagnostic(exc.limit),
        }
        status = 3
    except (ValueError, TypeError, KeyError, OSError, OverflowError) as exc:
        error = {
            "schema": "rcc-refcert.bundle-error",
            "schema_version": 1,
            "state": "invalid_input",
            "message": str(exc),
        }
        status = 2
    if arguments.output_format == "json":
        print(json.dumps(error, ensure_ascii=False, indent=2))
    else:
        print(f"RCC bundle {error['state']}: {error['message']}")
    return status
