"""Human and machine views of the same stored scientific result."""

from __future__ import annotations

import json
import textwrap

from .core import InputError

PLOT_FAILURE_MESSAGES = {
    "optional_plot_dependency_missing": 'install Matplotlib with python -m pip install "matplotlib>=3.8" and rerun the command.',
    "optional_plot_row_limit": "the figure supports up to 128 rows. Select fewer windows or export the full table with --csv.",
}


def validate_width(width):
    if type(width) is not int or not 40 <= width <= 240:
        raise InputError("width: choose an integer from 40 to 240")


def render_probe(entry, *, width=80):
    """Read a probe's scientific purpose before exporting its matrix inputs."""
    validate_width(width)
    parameters = ", ".join(
        f"{key}={value}" for key, value in entry["parameter_defaults"].items()
    )
    windows = "; ".join(
        f"{window['id']} ({', '.join(window['keep'])})" for window in entry["windows"]
    )
    command = (
        "cost" if entry["request_template"]["kind"] == "cost_analysis" else "window"
    )
    run_commands = [
        f"python -m rcc_refcert probe export {entry['probe_id']} > probe.json",
        f"python -m rcc_refcert {command} analyze probe.json",
    ]
    lines = [
        entry["title"],
        f"Probe: {entry['probe_id']} (revision {entry['revision']})",
        "",
        f"Question: {entry['research_question']}",
        f"Input: {entry['data_origin']}",
        f"Reference: {entry['reference']}",
        f"Default parameters: {parameters}",
        f"Windows: {windows}",
        (
            "Readouts: state-side complexity C = deficit / log2(Gamma) in st_R; "
            "correlation contribution I(A:B) / log2(Gamma) in st_R. "
            "Entropy, deficit and total correlation are also reported in bits."
        ),
        "",
        "Expected results at the default parameters:",
    ]
    for key, value in entry["expected_checks"].items():
        label = key.replace("_", " ")
        lines.append(
            f"  {label[0].upper() + label[1:]}: {json.dumps(value, ensure_ascii=False)}"
        )
    lines.extend(
        [
            "",
            f"Comparison: {entry['distinguishes']}",
            f"Control and interpretation: {entry['known_counterexample']}",
            f"Parameter changes: {entry['parameter_guidance']}",
            "",
            "Run this probe:",
            *run_commands,
            "",
            "Use 'probe show ID --format json' for the complete probe record.",
        ]
    )
    return (
        "\n".join(
            textwrap.fill(
                line, width=width, subsequent_indent="  ", break_on_hyphens=False
            )
            if line and line not in run_commands
            else line
            for line in lines
        )
        + "\n"
    )


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


def _delivery_lines(result):
    lines = []
    for name, delivery in result.get("delivery", {}).items():
        label = "CSV" if name == "csv" else name.capitalize()
        if delivery["state"] == "failed":
            reason = delivery["reason"]
            if name == "plot":
                reason = PLOT_FAILURE_MESSAGES.get(reason, reason)
            lines.append(f"{label} was not saved to {delivery['path']}: {reason}")
        elif delivery["state"] == "saved":
            lines.append(f"{label} saved to {delivery['path']}.")
    return lines


def _comparison_task(row):
    model = row.get("model_id")
    target = row.get("target_source") or row.get("target_digest")
    label = (
        f"Model {model}, full target: {target}"
        if model and target
        else f"Task {row['task_core_digest'][:12]}"
    )
    return f"{label.rstrip('.')}. Trace-distance tolerance: {row['epsilon_exact']}."


def _slot_unit(count):
    return "slot" if count == 1 else "slots"


def render_workflow_result(result, *, format="text", details=False, width=80):
    """Render a workflow result as a text or Markdown research report."""
    if format == "json":
        return json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if format not in {"text", "markdown"}:
        raise InputError("format: choose text, json or markdown")
    validate_width(width)
    if result.get("kind") in ("finite_study", "pvm_windows"):
        if result["kind"] == "finite_study":
            from .studies import render_study as render_measurement
        else:
            from .pvm_render import render_pvm as render_measurement
        lines = render_measurement(result, details=details).splitlines()
        lines.extend(_delivery_lines(result))
        return _format_report(lines, format, width, break_long_words=False)
    if result.get("schema") == "rcc-refcert.cost-comparison":
        lines = [
            "RCC cost comparison",
            "Common task and tolerance: "
            + ("yes" if result["comparable_task"] else "no; displayed separately"),
        ]
        lines.append("Cost unit: atomic slots, including halt.")
        if result["comparable_task"]:
            lines.append(_comparison_task(result["rows"][0]))
        for row in result["rows"]:
            if not result["comparable_task"]:
                lines.append(_comparison_task(row))
            lower = row["lower_bound_slots"]
            upper = row["upper_bound_slots"]
            lower_text = "unavailable" if lower is None else str(lower)
            upper_text = "unavailable" if upper is None else str(upper)
            lines.append(
                f"Run {row['run_id'] if details else row['run_id'][:12]}: "
                f"lower={lower_text}, upper={upper_text}; {_decision_label(row['decision'])}."
            )
            if row.get("additive_overhead_upper", 0) and upper is not None:
                gap = row["additive_overhead_upper"]
                witnesses = ", ".join(row.get("upper_witness_ids", ()))
                program = (
                    f"Upper-bound program ({witnesses})"
                    if witnesses
                    else "The program attaining the upper bound"
                )
                lines.append(f"  {program} can save at most {gap} {_slot_unit(gap)}.")
            if details:
                lines.append(f"  Task identity: {row['task_core_digest']}")
            if "criterion_status" in row:
                name, threshold = next(iter(result["criterion"].items()))
                label = (
                    "additive gap (slots)"
                    if name == "additive_gap"
                    else "multiplicative factor"
                )
                lines.append(f"  {label} <= {threshold}: {row['criterion_status']}")
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
        elif cost["decision"] != "numerical_analysis":
            lower = cost["lower_bound_slots"]
            upper = cost["upper_bound_slots"]
            lines.append(
                "Strict lower bound: unavailable"
                if lower is None
                else f"Lower bound: {lower} atomic {_slot_unit(lower)}"
            )
            lines.append(
                "Feasible upper bound: unavailable"
                if upper is None
                else f"Feasible upper bound: {upper} atomic {_slot_unit(upper)}"
            )
        lines.append(f"Target trace-distance tolerance: {cost['epsilon_exact']}")
        gap = cost["additive_overhead_upper"]
        if gap is not None:
            lines.append(
                "Best supplied candidate attains the optimum."
                if gap == 0
                else f"The best supplied program costs at most {gap} {_slot_unit(gap)} more than the optimum."
            )
        selection = result.get("gain_selection")
        if selection:
            if "submitted" in selection:
                rejection = selection["submitted"]
                lines.append(
                    f"Submitted gain certificate ({rejection['outcome']}): {rejection['message']}"
                )
            source = {
                "user": "supplied in the request",
                "saved_certificate": "verified certificate from the saved bundle",
                "preset": "model preset",
                "reference": "constructed from the reference",
            }[selection["source"]]
            lines.append(f"Verified gain certificate: {source}.")
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
                    else (
                        "unresolved"
                        if c["trace_distance_numeric"] is None
                        else f"{c['trace_distance_numeric']:.10g}"
                    )
                )
                status = (
                    ("met" if c["target_satisfied"] else "not met")
                    if c["evidence"] == "exact_rational"
                    else c["numerical_target_status"].replace("_", " ") + " (numerical)"
                )
                slots = c["slots"]
                lines.append(
                    f"  {c['id']}: {slots} {_slot_unit(slots)}; trace distance {distance}; target {status}"
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
        if cost["decision"] == "numerical_analysis":
            lines.append(
                "Trace distances are numerical estimates. The strict preparation-cost interval is unresolved."
            )
        if result.get("windows"):
            lines.append(
                "Candidate trajectory windows: "
                + _decision_label(
                    result["windows"].get("decision", result["windows"].get("status"))
                )
            )
            if details and "profiles" in result["windows"]:
                from .windows import window_report_lines

                lines.extend(window_report_lines(result["windows"], details=False))
            elif "profiles" in result["windows"]:
                lines.append("Use --details to read the trajectory window values.")
    else:
        from .windows import window_report_lines

        lines = window_report_lines(result, details=details)
    lines.extend(_delivery_lines(result))
    if "execution" in result:
        lines.append(f"Execution: {result['execution']['state']}")
        if result["execution"].get("reason"):
            reason = result["execution"]["reason"]
            explanation = {
                "optional_windows_numerical_evidence_unresolved": "Some trajectory windows remain unresolved under the numerical policy.",
                "optional_windows_resource_limited": "Trajectory windows reached the resource limit.",
            }.get(reason, reason.replace("_", " "))
            lines.append(f"Reason: {explanation}")
        lines.append(f"Run: {result['run_id']}")
    return _format_report(lines, format, width)


def _format_report(lines, format, width, *, break_long_words=True):
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
                break_long_words=break_long_words,
                break_on_hyphens=False,
            )
            for line in safe
        )
        + "\n"
    )
