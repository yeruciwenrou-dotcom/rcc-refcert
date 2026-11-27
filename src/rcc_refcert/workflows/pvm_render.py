"""Report certified intervals and the measured scope of finite PVM data."""

import csv
import io
from collections import Counter
from decimal import ROUND_CEILING
from fractions import Fraction
from math import log2
from textwrap import TextWrapper
from typing import NamedTuple

from ..bounds.scalar import decimal_string
from .pvm import _window_difference_lower


def _rows(record):
    for batch in record["batches"]:
        items = [(batch["window_id"], batch["window"])]
        items.extend(batch["coarse_windows"].items())
        if batch["product"]:
            items.extend(batch["product"]["marginals"].items())
        for name, window in items:
            values = window["window_st_R"] if window else {"lower": None, "upper": None}
            yield (
                batch["state_id"],
                name,
                values["lower"],
                values["upper"],
                batch["status"],
                batch["dataset_id"],
                batch["event_id"],
                window["scope"] if window else batch["window_scope"],
            )
        if batch["product"]:
            c = batch["product"]["classical_correlation_st_R"]
            yield (
                batch["state_id"],
                "classical correlation",
                c["lower"],
                c["upper"],
                batch["status"],
                batch["dataset_id"],
                batch["event_id"],
                "classical_blocks",
            )


def _comparison_line(left, right, forward):
    key = "state_id" if left["state_id"] != right["state_id"] else "dataset_id"
    a, b = left[key], right[key]
    scope = left["window_id"]
    reverse = _window_difference_lower(right, left)
    lower = Fraction(forward) if forward is not None else None
    other = Fraction(reverse) if reverse is not None else None

    for first, second, gap in ((a, b, lower), (b, a, other)):
        if gap is not None and gap > 0:
            return f"Window RCC is at least {decimal_string(gap, 10)} st_R higher for {first} than for {second} in {scope}."
    if lower == 0 and other == 0:
        return f"{a} and {b} have equal window RCC in {scope}."
    if lower == 0 or other == 0:
        first, second = (a, b) if lower == 0 else (b, a)
        return (
            f"Window RCC for {first} is at least as large as for {second} in {scope}."
        )
    difference = f"For {scope}, the window RCC difference ({a} minus {b})"
    if lower is not None and other is not None:
        return f"{difference} lies between {decimal_string(lower, 10)} and {decimal_string(-other, 10, ROUND_CEILING)} st_R."
    if lower is not None:
        return f"{difference} is at least {decimal_string(lower, 10)} st_R."
    if other is not None:
        return (
            f"{difference} is at most {decimal_string(-other, 10, ROUND_CEILING)} st_R."
        )
    return f"The measurements leave the ordering of {a} and {b} open in {scope}."


def window_scale_line(classes):
    bandwidth = log2(classes)
    relation = "=" if classes & (classes - 1) == 0 else "is approximately"
    return (
        f"Window scale: Gamma={classes} action classes, g_R=log2({classes}) bits per slot. "
        f"1 st_R {relation} {bandwidth:.10g} bits."
    )


def render_pvm(record, *, markdown=False, details=False):
    lines = [
        ("# " if markdown else "") + "Finite-sample window RCC",
        f"Joint sampling coverage is at least {decimal_string(100 * Fraction(record['coverage']['at_least']), 9)}%.",
    ]
    lines.append(window_scale_line(record["atomic_action_classes"]))
    if any(batch["product"] for batch in record["batches"]):
        lines.append(
            "The classical correlation row bounds I(X:Y)/g_R, the contribution of "
            "correlations between outcomes X and Y to RCC in the measured classical window."
        )
    # A report can contain several references or measurements. Keep each
    # window attached to its declared support even when their labels coincide.
    contexts = {}
    for batch in record["batches"]:
        context = (
            batch["window_id"],
            batch["measurement_id"],
            batch["window_scope"],
            batch["reference_id"],
            batch["dimension"],
        )
        contexts.setdefault(context, []).append(batch["dataset_id"])
    for (
        window,
        measurement,
        scope,
        reference,
        dimension,
    ), datasets in contexts.items():
        kind = (
            "classical measurement window"
            if scope == "classical_blocks"
            else "containing quantum window"
        )
        label = f"{window} ({', '.join(datasets)})" if len(contexts) > 1 else window
        lines.append(
            f"{label}: {kind} for {measurement}, uniform reference {reference} (support dimension {dimension})."
        )
    missing_by_reason = {}
    rows = list(_rows(record))
    repeated = Counter((state, name) for state, name, *_ in rows)
    for state, name, lo, hi, status, dataset, _, _ in rows:
        if lo is None:
            value = status.replace("_", " ")
        else:
            value = f">= {decimal_string(Fraction(lo), 9)}"
            if hi is not None:
                value += f", <= {decimal_string(Fraction(hi), 9, ROUND_CEILING)}"
            value += " st_R"
        label = f"{state} | {name}"
        if repeated[state, name] > 1:
            label += f" ({dataset})"
        lines.append(f"{label}: {value}")
    for batch in record["batches"]:
        origin = {
            "observed_counts": "observed counts",
            "simulation": "simulated counts",
            "synthetic_fixture": "synthetic counts",
        }[batch["origin"]]
        retention = batch["retention"]
        trials = batch["analyzed_samples"]
        sampling = origin
        if retention:
            kept, discarded = retention["retained"], retention["discarded"]
            trials = kept + discarded
            sampling = f"{origin}, {kept:,} retained and {discarded:,} discarded"
        unit = "trial" if trials == 1 else "trials"
        lines.append(f"{batch['event_id']}: {trials:,} {unit} ({sampling}).")
        if details:
            lines.extend(
                [
                    f"Dataset {batch['dataset_id']} measures {batch['state_id']} against {batch['reference_id']}.",
                    f"Protocol SHA-256: {batch['protocol_sha256']}",
                    f"Data SHA-256: {batch['data_sha256']}",
                ]
            )
        if batch["window_scope"] == "containing_quantum":
            lines.append(
                "The measured blocks give a lower bound for the containing quantum window."
            )
        if retention:
            if "discounted_state_exact_st_R" in retention:
                value = decimal_string(
                    Fraction(retention["discounted_state_exact_st_R"]), 9
                )
                lines.append(
                    f"The retention-weighted contribution is exactly {value} st_R."
                )
            else:
                value = decimal_string(
                    Fraction(retention["discounted_state_lower_st_R"]), 9
                )
                lines.append(
                    f"The retention-weighted lower bound for the projected state is {value} st_R."
                )
        for point in batch["process"]:
            cost = point["cost"]
            lines.append(
                f"At trace-distance tolerance {point['epsilon']}, the one-shot information lower bound is {decimal_string(Fraction(point['one_shot_lower_bits']), 9)} bits."
            )
            if cost:
                line = f"Preparation cost >= {decimal_string(Fraction(cost['lower_bound_slots']), 9)} slots"
                if cost["integer_lower_bound_slots"] is not None:
                    line += f" (integer bound {cost['integer_lower_bound_slots']})"
                lines.append(line + ".")
            else:
                missing = tuple(point["missing_process_premises"])
                missing_by_reason.setdefault(missing, {})[batch["state_id"]] = None
            if point["cap_ratio_exact"] == "1":
                lines.append(
                    "The reference distribution lies within the sampling and smoothing allowance."
                )
            elif cost and cost["zero_reason"] == "model_overhead_exhausted":
                lines.append(
                    "The information bound fits within the declared model overhead."
                )
    by_event = {b["event_id"]: b for b in record["batches"]}
    for comparison in record["comparisons"]:
        left, right = (by_event[event] for event in comparison["events"])
        lines.append(_comparison_line(left, right, comparison["difference_lower_st_R"]))
    for missing, states in missing_by_reason.items():
        *others, last = states
        names = f"{', '.join(others)} and {last}" if others else last
        if missing == ("model",):
            lines.append(
                f"To bound the preparation cost for {names}, supply a preparation model."
            )
        elif missing == ("process contract for leakage",):
            lines.append(
                f"To bound the preparation cost of the retained branch for {names}, specify how the model treats leakage."
            )
        else:
            lines.append(
                f"To bound the preparation cost for {names}, supply the missing model qualifications: {', '.join(missing)}."
            )
    if details:
        lines.append(f"Run: {record['run_id']}")
    return ("\n\n" if markdown else "\n").join(lines) + "\n"


class _WindowExportRow(NamedTuple):
    state: str
    window: str
    lower_st_R: str | None
    upper_st_R: str | None
    status: str
    dataset_id: str
    event_id: str
    kind: str
    retained: int | None
    discarded: int | None
    window_scope: str


def export_pvm(record, csv_path, plot_path, overwrite):
    from .cli import write_atomic
    from .windows import save_window_figure

    by_event = {b["event_id"]: b for b in record["batches"]}
    rows = []
    for state, name, lo, hi, status, dataset, event, scope in _rows(record):
        retention = by_event[event]["retention"]
        kept, discarded = (
            (retention["retained"], retention["discarded"])
            if retention
            else (None, None)
        )
        kind = "conditional_window" if retention else "measured_window"
        rows.append(
            _WindowExportRow(
                state,
                name,
                lo,
                hi,
                status,
                dataset,
                event,
                kind,
                kept,
                discarded,
                scope,
            )
        )
    for event, batch in by_event.items():
        r = batch["retention"]
        if r:
            exact = r.get("discounted_state_exact_st_R")
            rows.append(
                _WindowExportRow(
                    batch["state_id"],
                    batch["window_id"],
                    exact if exact is not None else r["discounted_state_lower_st_R"],
                    exact,
                    "exact" if exact is not None else batch["status"],
                    batch["dataset_id"],
                    event,
                    "retention_weighted_exact"
                    if exact is not None
                    else "retention_weighted_lower",
                    r["retained"],
                    r["discarded"],
                    batch["window_scope"],
                )
            )
    for comparison in record.get("comparisons", []):
        left, right = (by_event[event] for event in comparison["events"])
        reverse = _window_difference_lower(right, left)
        key = "state_id" if left["state_id"] != right["state_id"] else "dataset_id"
        rows.append(
            _WindowExportRow(
                f"{left[key]} minus {right[key]}",
                left["window_id"],
                comparison["difference_lower_st_R"],
                decimal_string(-Fraction(reverse), rounding=ROUND_CEILING)
                if reverse is not None
                else None,
                "ordering_undetermined"
                if reverse is None and comparison["difference_lower_st_R"] is None
                else "comparison",
                f"{left['dataset_id']} minus {right['dataset_id']}",
                " minus ".join(comparison["events"]),
                "signed_difference",
                None,
                None,
                left["window_scope"],
            )
        )
    if csv_path is not None:
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(_WindowExportRow._fields)
        writer.writerows(rows)
        write_atomic(csv_path, stream.getvalue(), overwrite=overwrite)
    if plot_path is None:
        return
    from .windows import window_figure

    figure = window_figure(record, plot_path, len(rows))
    if figure is None:
        reason = {
            "optional_plot_dependency_missing": "install the plots extra to render the figure",
            "optional_plot_row_limit": "the figure supports up to 128 rows",
        }[record["execution"]["reason"]]
        record.setdefault("delivery", {})["plot"] = {
            "state": "failed",
            "path": str(plot_path),
            "reason": reason,
        }
        return
    fig, ax = figure
    repeated = Counter((row.state, row.window) for row in rows)
    labels, positions = [], []
    height = 0.0
    color = "#266c85"
    single_retention = (
        record["batches"][0]["retention"] if len(record["batches"]) == 1 else None
    )
    scope_labels = {
        "classical_blocks": "Measured classical window",
        "containing_quantum": "Containing quantum window",
    }
    scopes = {row.window_scope for row in rows}
    for index, row in enumerate(rows):
        lo, hi = row.lower_st_R, row.upper_st_R
        wrap = TextWrapper(width=38, max_lines=2, placeholder=f"… [row {index + 1}]")
        label = wrap.fill(f"{row.state} / {row.window}")
        if row.retained is not None:
            label += (
                "\n"
                + {
                    "retention_weighted_lower": "Retention-weighted lower bound",
                    "retention_weighted_exact": "Retention-weighted contribution",
                    "conditional_window": "Conditional window",
                }[row.kind]
            )
            if single_retention is None:
                label += f" · {row.retained:,} retained / {row.discarded:,} discarded"
        if repeated[row.state, row.window] > 1 and row.retained is None:
            label += "\n" + wrap.fill(row.dataset_id)
        if len(scopes) > 1:
            label += "\n" + scope_labels[row.window_scope]
        row_height = 0.13 + 0.21 * (1 + label.count("\n"))
        y = height + row_height / 2
        height += row_height
        labels.append(label)
        positions.append(y)
        if row.kind == "retention_weighted_exact":
            ax.plot(float(Fraction(lo)), y, marker="D", color=color, clip_on=False)
        elif lo is not None:
            ax.plot(
                float(Fraction(lo)),
                y,
                marker=">" if hi is None else "o",
                color=color,
                clip_on=False,
            )
            if hi is not None:
                ax.hlines(y, float(Fraction(lo)), float(Fraction(hi)), color=color)
                ax.plot(
                    float(Fraction(hi)),
                    y,
                    marker="|",
                    markersize=9,
                    color=color,
                    clip_on=False,
                )
        elif hi is not None:
            ax.plot(float(Fraction(hi)), y, marker="<", color=color, clip_on=False)
        else:
            ax.text(
                0.03,
                y,
                row.status.replace("_", " ").capitalize(),
                transform=ax.get_yaxis_transform(),
                va="center",
                color="0.30",
            )
    if all(
        row.kind != "signed_difference" or row.status == "ordering_undetermined"
        for row in rows
    ):
        ax.set_xlim(left=0, right=max(0.01, ax.get_xlim()[1]))
    else:
        ax.axvline(0, color="0.55", linewidth=0.8)
    fig.set_size_inches(9, max(3.2, height + 1.65))
    ax.set_yticks(positions, labels)
    for label in ax.get_yticklabels():
        label.set_parse_math(False)
    ax.set_ylim(max(height, 0.3), 0)
    ax.set_axisbelow(True)
    ax.grid(axis="x", color="0.9", linewidth=0.7)
    if any(
        row.lower_st_R is not None
        and row.upper_st_R is not None
        and row.kind != "retention_weighted_exact"
        for row in rows
    ):
        ax.plot([], [], "o", color=color, label="Interval lower endpoint")
        ax.plot([], [], "|", color=color, markersize=9, label="Interval upper endpoint")
    if any(row.lower_st_R is not None and row.upper_st_R is None for row in rows):
        ax.plot([], [], ">", color=color, label="One-sided lower bound")
    if any(row.lower_st_R is None and row.upper_st_R is not None for row in rows):
        ax.plot([], [], "<", color=color, label="One-sided upper bound")
    if any(row.kind == "retention_weighted_exact" for row in rows):
        ax.plot([], [], "D", color=color, label="Exact value")
    handles, keys = ax.get_legend_handles_labels()
    if handles:
        fig.legend(
            handles, keys, loc="outside lower center", ncols=len(keys), frameon=False
        )
    product = any(b["product"] for b in record["batches"])
    title = (
        "Window RCC and the classical correlation contribution"
        if product
        else "Finite-sample bounds on window RCC"
    )
    fig.suptitle(title, fontweight="semibold")
    coverage = decimal_string(100 * Fraction(record["coverage"]["at_least"]), 9)
    subtitle = f"Joint sampling coverage at least {coverage}%"
    if single_retention:
        subtitle += f"   |   {single_retention['retained']:,} retained / {single_retention['discarded']:,} discarded"
    ax.set_title(subtitle, loc="left", fontsize=10)
    quantity = "State-side complexity" if product else "Window RCC"
    if len(scopes) == 1:
        quantity += " in the " + scope_labels[next(iter(scopes))].lower()
    units = r"$\mathrm{st}_R$"
    if "atomic_action_classes" in record:
        units += rf", $\Gamma_R={record['atomic_action_classes']}$"
    ax.set_xlabel(f"{quantity} ({units})")
    save_window_figure(fig, plot_path, overwrite)
