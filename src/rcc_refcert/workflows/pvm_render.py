"""Report certified intervals and the measured scope of finite PVM data."""

import csv
import io
from collections import Counter
from decimal import ROUND_CEILING
from fractions import Fraction

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


def render_pvm(record, *, markdown=False, details=False):
    lines = [
        ("# " if markdown else "") + "Finite-sample window RCC",
        f"Joint sampling coverage is at least {decimal_string(100 * Fraction(record['coverage']['at_least']), 9)}%.",
    ]
    missing_by_reason = {}
    rows = list(_rows(record))
    repeated = Counter((state, name) for state, name, *_ in rows)
    for state, name, lo, hi, status, dataset, _ in rows:
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
        lines.append(
            f"{batch['event_id']}: {batch['analyzed_samples']} trials ({origin})."
        )
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
        if batch["retention"]:
            r = batch["retention"]
            lines.append(
                f"Of the shots, {r['retained']} were retained and {r['discarded']} discarded. The retention-weighted lower bound for the projected state is {r['discounted_state_lower_st_R']} st_R."
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


def export_pvm(record, csv_path, plot_path, overwrite):
    from .cli import write_atomic
    from .windows import save_window_figure

    rows = list(_rows(record))
    if csv_path is not None:
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(
            (
                "state",
                "window",
                "lower_st_R",
                "upper_st_R",
                "status",
                "dataset_id",
                "event_id",
            )
        )
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
    for i, (_, _, lo, hi, *_) in enumerate(rows):
        if lo is not None:
            ax.plot(i, float(lo), marker="^" if hi is None else "o", color="C0")
            if hi is not None:
                ax.vlines(i, float(lo), float(hi), color="C0")
                ax.plot(i, float(hi), marker="_", color="C0")
    duplicate = Counter((state, window) for state, window, *_ in rows)
    labels = [
        f"{state}\n{window}\n{dataset}"
        if duplicate[state, window] > 1
        else f"{state}\n{window}"
        for state, window, _, _, _, dataset, _ in rows
    ]
    ax.set_xticks(range(len(rows)), labels, rotation=20, ha="right")
    if any(lo is not None and hi is not None for _, _, lo, hi, *_ in rows):
        ax.plot([], [], "o", color="C0", label="Interval lower endpoint")
        ax.plot([], [], "_", color="C0", label="Interval upper endpoint")
    if any(lo is not None and hi is None for _, _, lo, hi, *_ in rows):
        ax.plot([], [], "^", color="C0", label="One-sided lower bound")
    if ax.get_legend_handles_labels()[0]:
        ax.legend()
    if any(b["product"] for b in record["batches"]):
        ax.set_title("Window RCC and classical correlation")
        ax.set_ylabel(r"Value ($\mathrm{st}_R$)")
    else:
        ax.set_title("Measured intervals and one-sided lower bounds")
        ax.set_ylabel(r"Window RCC ($\mathrm{st}_R$)")
    save_window_figure(fig, plot_path, overwrite)
