"""Human and machine views of the same stored scientific result."""

from __future__ import annotations

import json
import textwrap

from .core import InputError


def _decision_label(value):
    return {
        "certified_optimal": "certified optimum",
        "certified_interval": "certified interval; gap remains",
        "lower_bound_only": "lower bound established",
        "numerical_analysis": "numerical candidate diagnostics",
        "evidence_conflict": "conflicting evidence; no valid interval",
        "window_analysis": "window profiles evaluated",
        "numerical_unresolved": "numerical evidence unresolved",
    }.get(value, str(value).replace("_", " "))


def render_workflow_result(result, *, format="text", details=False, width=80):
    if format == "json":
        return json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if format not in {"text", "markdown"}:
        raise InputError("format: choose text, json or markdown")
    if type(width) is not int or not 40 <= width <= 240:
        raise InputError("width: choose an integer from 40 to 240")
    if result.get("schema") == "rcc-refcert.cost-comparison":
        lines = [
            "RCC cost comparison",
            "Common task and tolerance: "
            + ("yes" if result["comparable_task"] else "no; displayed separately"),
        ]
        for row in result["rows"]:
            lower = row["lower_bound_slots"]
            upper = row["upper_bound_slots"]
            lower_text = "unavailable" if lower is None else str(lower)
            upper_text = "unavailable" if upper is None else str(upper)
            lines.append(
                f"{row['run_id']}: lower={lower_text}, upper={upper_text}; "
                f"{_decision_label(row['decision'])}"
            )
    elif result["kind"] == "cost_analysis":
        cost = result["cost"]
        lines = [
            "RCC preparation-cost analysis",
            f"Model: {result['effective_request']['model']['id']}",
            f"Decision: {_decision_label(result['decision'])}",
        ]
        if cost["interval_slots"] is not None:
            lines.append(
                f"Cost interval: [{cost['lower_bound_slots']}, {cost['upper_bound_slots']}] atomic slots (halt included)"
            )
        else:
            lines.append(
                "Strict lower bound: unavailable"
                if cost["lower_bound_slots"] is None
                else f"Lower bound: {cost['lower_bound_slots']} atomic slots"
            )
            lines.append(
                "Feasible upper bound: unavailable"
                if cost["upper_bound_slots"] is None
                else f"Feasible upper bound: {cost['upper_bound_slots']} atomic slots"
            )
        lines.append(f"Target trace-distance tolerance: {cost['epsilon_exact']}")
        if cost["additive_overhead_upper"] is not None:
            lines.append(
                "Best supplied candidate attains the optimum."
                if cost["additive_overhead_upper"] == 0
                else f"Best supplied candidate is within {cost['additive_overhead_upper']} slots of the optimum."
            )
        lines.append("Candidate programs:")
        if not result["candidates"]:
            lines.append("  No candidate supplied.")
        for c in result["candidates"]:
            if c["legality"] != "pass":
                lines.append(f"  {c['id']}: invalid program; {c['error']}")
            else:
                distance = (
                    c["trace_distance_exact"]
                    if c["evidence"] == "exact_rational"
                    else c["trace_distance_numeric"]
                )
                status = (
                    ("met" if c["target_satisfied"] else "not met")
                    if c["evidence"] == "exact_rational"
                    else c["numerical_target_status"].replace("_", " ") + " (numerical)"
                )
                lines.append(
                    f"  {c['id']}: {c['slots']} slots; trace distance {distance}; target {status}"
                )
        if result["epsilon_scan"]:
            lines.append("Tolerance scan:")
            for point in result["epsilon_scan"]:
                c = point["cost"]
                lines.append(
                    f"  epsilon={point['epsilon_exact']}: lower={c['lower_bound_slots']}, upper={c['upper_bound_slots']}; {_decision_label(c['decision'])}"
                )
        if details and result["gain_bound"] is not None:
            lines.extend(
                [
                    "Lower-bound method: exact reference-envelope gain budget",
                    f"Task identity: {result['digests']['task_core']}",
                    f"Gain threshold: {result['gain_bound']['threshold_exact']}",
                    f"Budget stop: {result['gain_bound']['stop_reason'].replace('_', ' ')}",
                ]
            )
        lines.append(
            "Scope: the declared model, full target, tolerance and atomic cost."
        )
        if result.get("windows"):
            lines.append(
                "Candidate trajectory windows: "
                + _decision_label(
                    result["windows"].get("decision", result["windows"].get("status"))
                )
            )
    else:
        from .windows import window_report_lines

        lines = window_report_lines(result, details=details)
    for name, delivery in result.get("delivery", {}).items():
        if delivery.get("state") == "failed":
            lines.append(f"{name.capitalize()} was not saved: {delivery['reason']}")
    if "execution" in result:
        lines.append(f"Execution: {result['execution']['state']}")
        if result["execution"].get("reason"):
            lines.append(f"Reason: {result['execution']['reason'].replace('_', ' ')}")
        lines.append(f"Run: {result['run_id']}")
    safe = ["".join(max(c, " ") for c in line) for line in lines]
    if format == "markdown":
        return (
            "# "
            + safe[0]
            + "\n\n"
            + "\n\n".join(line.replace("|", "\\|") for line in safe[1:])
            + "\n"
        )
    return (
        "\n".join(
            textwrap.fill(
                line,
                width=width,
                subsequent_indent="  ",
                break_long_words=True,
                break_on_hyphens=False,
            )
            for line in safe
        )
        + "\n"
    )
