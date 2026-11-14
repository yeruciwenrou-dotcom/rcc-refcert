"""Subsystem entropy deficits with explicit axes, references and state policies."""

from __future__ import annotations

import csv
import io
import math
import os
import tempfile
import uuid
from fractions import Fraction
from pathlib import Path

import numpy as np

from .core import (
    InputError,
    WorkflowLimits,
    digest,
    exact,
    exact_text,
    json_value,
    keys,
    text,
)
from .states import StateInput, check_numeric_diagnostics, prepare_numeric_state


def _keep(value, labels):
    if (
        not isinstance(value, list)
        or any(v not in labels for v in value)
        or len(set(value)) != len(value)
    ):
        raise InputError("window.keep: use distinct declared subsystem labels")
    return [label for label in labels if label in value]


def window_configuration(windows, partition, labels):
    if not isinstance(windows, list) or len(windows) > 256:
        raise InputError("windows: supply at most 256 windows")
    normalized = []
    for item in windows:
        keys(item, {"id", "keep"}, name="window")
        normalized.append(
            {"id": text(item["id"], "window.id"), "keep": _keep(item["keep"], labels)}
        )
    if len({w["id"] for w in normalized}) != len(normalized):
        raise InputError("windows: ids must be unique")
    if partition is not None:
        keys(partition, {"left", "right"}, name="partition")
        partition = {k: _keep(partition[k], labels) for k in ("left", "right")}
        if set(partition["left"]) & set(partition["right"]) or set(
            partition["left"] + partition["right"]
        ) != set(labels):
            raise InputError(
                "partition: left and right must be disjoint and cover all subsystems"
            )
    return normalized, partition


def reference_scale(reference, state):
    keys(reference, {"kind", "gamma", "source"}, name="reference")
    if reference["kind"] != "uniform_product_support":
        raise InputError("reference.kind: expected uniform_product_support")
    gamma = exact(reference["gamma"], "reference.gamma")
    if gamma < 2:
        raise InputError("reference.gamma: require Gamma >= 2")
    return {
        "kind": reference["kind"],
        "gamma_exact": exact_text(gamma),
        "g_bits": math.log2(gamma.numerator) - math.log2(gamma.denominator),
        "source": text(reference["source"], "reference.source"),
        "dimension": state.dimension,
        "subsystem_dims": list(state.subsystem_dims),
        "subsystem_labels": list(state.subsystem_labels),
    }


def reduced_matrix(matrix, dims, keep):
    """Trace the complement; retained axes keep their original tensor order."""
    dims = list(dims)
    tensor = np.asarray(matrix).reshape(dims + dims)
    for axis in reversed(range(len(dims))):
        if axis not in keep:
            tensor = np.trace(tensor, axis1=axis, axis2=axis + len(dims))
            dims.pop(axis)
    size = math.prod(dims)
    return tensor.reshape(size, size)


def _diagonal_marginal(state, keep):
    dims = state.subsystem_dims
    kept_dims = [dims[i] for i in keep]
    result = [Fraction(0)] * math.prod(kept_dims)
    for index, value in enumerate(state.data):
        digits = [0] * len(dims)
        for axis in reversed(range(len(dims))):
            index, digits[axis] = divmod(index, dims[axis])
        out = 0
        for axis in keep:
            out = out * dims[axis] + digits[axis]
        result[out] += value
    return result


def _quantity(state, matrix, keep, g):
    axes = [i for i, label in enumerate(state.subsystem_labels) if label in keep]
    size = math.prod(state.subsystem_dims[i] for i in axes)
    if state.kind == "diagonal_exact":
        probabilities = _diagonal_marginal(state, axes)
        entropy = -math.fsum(
            float(p) * (math.log2(p.numerator) - math.log2(p.denominator))
            for p in probabilities
            if p
        )
        spectrum = {"probabilities_exact": [exact_text(p) for p in probabilities]}
    else:
        reduced = reduced_matrix(matrix, state.subsystem_dims, axes)
        eigenvalues = np.linalg.eigvalsh((reduced + reduced.conj().T) / 2)
        tolerance = state.numeric_policy["tolerance"]
        if eigenvalues[0] < -tolerance or abs(float(eigenvalues.sum()) - 1) > tolerance:
            raise InputError("reduced state exceeds its numerical validity tolerance")
        positive = np.maximum(eigenvalues, 0)
        positive /= positive.sum()
        entropy = -math.fsum(float(p) * math.log2(float(p)) for p in positive if p > 0)
        spectrum = {
            "eigenvalues_numeric": eigenvalues.tolist(),
            "entropy_probabilities_numeric": positive.tolist(),
            "roundoff_mass_adjustment": float(np.abs(positive - eigenvalues).sum()),
        }
    deficit = math.log2(size) - entropy
    return {
        "keep": list(keep),
        "dimension": size,
        "entropy_bits": entropy,
        "entropy_deficit_bits": deficit,
        "rcc_main_term": deficit / g,
        "arithmetic": "binary64_logarithms",
        **spectrum,
    }


def normalize_window_request(request, *, limits=None):
    from .probes import check_probe_identity

    keys(
        request,
        {"schema", "schema_version", "kind", "states", "reference", "windows"},
        {"partition", "limits", "probe"},
        "window request",
    )
    if (
        request["schema"] != "rcc-refcert.workflow-request"
        or type(request["schema_version"]) is not int
        or request["schema_version"] != 1
        or request["kind"] != "window_analysis"
    ):
        raise InputError("window request: unsupported schema or kind")
    original = json_value(request)
    check_probe_identity(request.get("probe"))
    limits = WorkflowLimits.from_value(
        limits if limits is not None else request.get("limits")
    )
    if (
        not isinstance(request["states"], list)
        or not 1 <= len(request["states"]) <= 256
    ):
        raise InputError("states: supply one to 256 complete states")
    states, records = [], []
    for record in request["states"]:
        keys(record, {"id", "state"}, {"step", "action", "slots"}, "state record")
        name = text(record["id"], "state.id")
        for k in ("step", "slots"):
            if k in record and (type(record[k]) is not int or record[k] < 0):
                raise InputError(f"state.{k}: expected a nonnegative integer")
        if record.get("action") is not None:
            text(record["action"], "state.action")
        state = StateInput.from_dict(record["state"], limits=limits)
        if states and (state.subsystem_dims, state.subsystem_labels) != (
            states[0].subsystem_dims,
            states[0].subsystem_labels,
        ):
            raise InputError(
                "states: comparison requires the same dimensions and physical axes"
            )
        states.append(state)
        records.append({**record, "id": name, "state": state.as_dict()})
    if len({r["id"] for r in records}) != len(records):
        raise InputError("states: ids must be unique")
    windows, partition = window_configuration(
        request["windows"], request.get("partition"), states[0].subsystem_labels
    )
    scale = reference_scale(request["reference"], states[0])
    effective = {
        **original,
        "states": records,
        "reference": {
            "kind": scale["kind"],
            "gamma": scale["gamma_exact"],
            "source": scale["source"],
        },
        "windows": windows,
        "partition": partition,
        "limits": limits.as_dict(),
    }
    return original, effective, states, scale, limits


def analyze_windows(request, *, limits=None):
    from .api import producer

    original, effective, states, scale, limits = normalize_window_request(
        request, limits=limits
    )
    profiles, remaining = [], limits.max_windows
    unresolved = False
    for record, state in zip(effective["states"], states):
        labels = list(state.subsystem_labels)
        # The global quantity and partition reductions count toward the budget.
        keeps = [labels] + [w["keep"] for w in effective["windows"]]
        if effective["partition"] is not None:
            keeps += list(effective["partition"].values())
        unique = {tuple(k) for k in keeps}
        if len(profiles) >= limits.max_trajectory_states or len(unique) > remaining:
            break
        remaining -= len(unique)
        matrix, diagnostics = (
            (
                None,
                {
                    "outcome": "pass",
                    "policy": "exact_diagonal",
                    "original_digest": state.content_digest,
                },
            )
            if state.kind == "diagonal_exact"
            else prepare_numeric_state(state, limits=limits)
        )
        profile = {k: v for k, v in record.items() if k != "state"}
        profile.update(
            state_digest=state.content_digest,
            input_diagnostics=diagnostics,
            global_quantity=None,
            windows=[],
            partition=None,
        )
        if diagnostics["outcome"] != "pass":
            unresolved = True
            profiles.append(profile)
            continue
        quantities = {
            keep: _quantity(state, matrix, keep, scale["g_bits"]) for keep in unique
        }
        global_q = quantities[tuple(labels)]
        profile["global_quantity"] = global_q
        profile["windows"] = [
            {"id": w["id"], **quantities[tuple(w["keep"])]}
            for w in effective["windows"]
        ]
        partition = effective["partition"]
        if partition is not None:
            left, right = (quantities[tuple(partition[k])] for k in ("left", "right"))
            information = (
                left["entropy_bits"] + right["entropy_bits"] - global_q["entropy_bits"]
            )
            profile["partition"] = {
                "left": left,
                "right": right,
                "total_correlation_bits": information,
                "total_correlation_scaled": information / scale["g_bits"],
                "decomposition_residual": global_q["rcc_main_term"]
                - left["rcc_main_term"]
                - right["rcc_main_term"]
                - information / scale["g_bits"],
                "interpretation": "total correlation; for diagonal states this is classical mutual information",
            }
        profiles.append(profile)
    limited = len(profiles) != len(states)
    return {
        "schema": "rcc-refcert.workflow-result",
        "schema_version": 1,
        "kind": "window_analysis",
        "producer": producer(),
        "artifact_role": "author_analysis",
        "run_id": uuid.uuid4().hex,
        "original_request": original,
        "effective_request": effective,
        "digests": {"request": digest(effective)},
        "reference": scale,
        "execution": {
            "state": "partial" if limited or unresolved else "completed",
            "reason": "resource_limited"
            if limited
            else "numerical_evidence_unresolved"
            if unresolved
            else None,
        },
        "decision": "numerical_unresolved" if unresolved else "window_analysis",
        "evidence": {"windows": "numerical_entropy"},
        "profiles": profiles,
        "diagnostics": {
            "requested_states": len(states),
            "analyzed_states": len(profiles),
            "window_evaluations": limits.max_windows - remaining,
            "comparison_tolerance": 1e-10,
            "entropy_precision": "binary64; no rigorous error enclosure",
        },
    }


def attach_cost_windows(result, *, limits):
    from ..limits import ResourceLimitError
    from .core import BudgetError

    options = keys(
        result["effective_request"]["windows"],
        {"windows"},
        {"partition", "steps"},
        "cost windows",
    )
    model = result["effective_request"]["model"]
    steps = options.get("steps")
    if steps is not None and (
        not isinstance(steps, list)
        or any(type(s) is not int or s < 0 for s in steps)
        or len(set(steps)) != len(steps)
    ):
        raise InputError("windows.steps: use distinct nonnegative step numbers")
    records = []
    for candidate in result["candidates"]:
        for step in candidate["trajectory"]:
            if steps is None or step["step"] in steps:
                records.append({"id": f"{candidate['id']}:{step['step']}", **step})
    if not records:
        result["windows"] = {
            "status": "unavailable",
            "reason": "no saved legal candidate trajectory",
        }
        return
    window_request = {
        "schema": "rcc-refcert.workflow-request",
        "schema_version": 1,
        "kind": "window_analysis",
        "states": records[:256],
        "reference": model["reference"],
        "windows": options["windows"],
        "partition": options.get("partition"),
        "limits": limits.as_dict(),
    }
    try:
        result["windows"] = analyze_windows(window_request, limits=limits)
        nested = result["windows"]["execution"]
        reason = "resource_limited" if len(records) > 256 else nested["reason"]
        if reason and result["execution"]["state"] == "completed":
            result["execution"] = {
                "state": "partial",
                "reason": f"optional_windows_{reason}",
            }
    except (ResourceLimitError, BudgetError) as exc:
        result["windows"] = {"status": "resource_limited", "reason": str(exc)}
        if result["execution"]["state"] == "completed":
            result["execution"] = {
                "state": "partial",
                "reason": "optional_windows_resource_limited",
            }


def _close(a, b, tolerance=1e-10):
    if isinstance(a, float) and isinstance(b, (int, float)):
        return (
            math.isfinite(a)
            and math.isfinite(b)
            and abs(a - b) <= tolerance * max(1, abs(a), abs(b))
        )
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_close(a[k], b[k], tolerance) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_close(x, y, tolerance) for x, y in zip(a, b))
    return type(a) is type(b) and a == b


def check_window_history(history, *, limits):
    _, effective, states, scale, _ = normalize_window_request(
        history["effective_request"], limits=limits
    )
    if (
        history["digests"] != {"request": digest(history["effective_request"])}
        or history["reference"] != scale
    ):
        raise InputError("history: window request or reference binding mismatch")
    profiles = history["profiles"]
    unresolved = any(p["input_diagnostics"]["outcome"] != "pass" for p in profiles)
    if history["decision"] != (
        "numerical_unresolved" if unresolved else "window_analysis"
    ):
        raise InputError("history: window decision is inconsistent with its evidence")
    if len(profiles) > len(states) or (
        history["execution"]["state"] == "completed"
        and (len(profiles) != len(states) or unresolved)
    ):
        raise InputError("history: window completion or profile count mismatch")
    for record, state, profile in zip(effective["states"], states, profiles):
        if (
            profile["state_digest"] != state.content_digest
            or profile["id"] != record["id"]
        ):
            raise InputError("history: window state binding mismatch")
        if state.kind == "density_numeric":
            check_numeric_diagnostics(
                state, profile["input_diagnostics"], limits=limits
            )
        elif profile["input_diagnostics"] != {
            "outcome": "pass",
            "policy": "exact_diagonal",
            "original_digest": state.content_digest,
        }:
            raise InputError("history: exact window diagnostics mismatch")
        if profile["input_diagnostics"]["outcome"] != "pass":
            if (
                profile["global_quantity"] is not None
                or profile["windows"]
                or profile["partition"] is not None
                or history["decision"] != "numerical_unresolved"
            ):
                raise InputError("history: unresolved state has asserted window values")
            continue
        if len(profile["windows"]) != len(effective["windows"]):
            raise InputError("history: window count mismatch")
        if profile["global_quantity"]["keep"] != list(state.subsystem_labels):
            raise InputError("history: global quantity must retain every subsystem")
        for saved, expected in zip(profile["windows"], effective["windows"]):
            if saved["id"] != expected["id"] or saved["keep"] != expected["keep"]:
                raise InputError("history: window label or axes mismatch")
        quantities = [profile["global_quantity"], *profile["windows"]]
        partition = profile["partition"]
        if (partition is None) != (effective["partition"] is None):
            raise InputError("history: partition mismatch")
        if partition is not None:
            if any(
                partition[k]["keep"] != effective["partition"][k]
                for k in ("left", "right")
            ):
                raise InputError("history: partition axes mismatch")
            quantities += [partition["left"], partition["right"]]
            information = (
                partition["left"]["entropy_bits"]
                + partition["right"]["entropy_bits"]
                - profile["global_quantity"]["entropy_bits"]
            )
            if not _close(
                information, partition["total_correlation_bits"]
            ) or not _close(
                information / scale["g_bits"], partition["total_correlation_scaled"]
            ):
                raise InputError("history: total correlation is inconsistent")
            residual = (
                profile["global_quantity"]["rcc_main_term"]
                - partition["left"]["rcc_main_term"]
                - partition["right"]["rcc_main_term"]
                - information / scale["g_bits"]
            )
            if not _close(residual, partition["decomposition_residual"]):
                raise InputError("history: partition residual is inconsistent")
        for q in quantities:
            labels = _keep(q["keep"], state.subsystem_labels)
            dimension = math.prod(
                d
                for d, label in zip(state.subsystem_dims, state.subsystem_labels)
                if label in labels
            )
            if (
                dimension != q["dimension"]
                or not -1e-10 <= q["entropy_bits"] <= math.log2(dimension) + 1e-10
            ):
                raise InputError("history: window dimension or entropy range mismatch")
            deficit = math.log2(dimension) - q["entropy_bits"]
            if not _close(deficit, q["entropy_deficit_bits"]) or not _close(
                deficit / scale["g_bits"], q["rcc_main_term"]
            ):
                raise InputError("history: window deficit or scale is inconsistent")


def _window_number(value):
    if value == 0:
        return "0"
    return "~0" if abs(value) < 1e-12 else f"{value:.10g}"


def window_report_lines(result, *, details=False):
    from .render import _decision_label

    ref = result["reference"]
    lines = [
        "RCC state windows",
        f"Decision: {_decision_label(result['decision'])}",
        f"Reference: uniform product support; Gamma={ref['gamma_exact']}; g_R={ref['g_bits']:.10g} bits",
        f"Scale source: {ref['source']}",
        "C = entropy deficit / g_R: the state-side RCC main term.",
        "Subsystem entropy is S(rho_A) on the retained axes.",
    ]
    records = {record["id"]: record for record in result["effective_request"]["states"]}
    for profile in result["profiles"]:
        lines.append(f"State: {profile['id']}")
        record = records[profile["id"]]
        if "step" in record:
            unit = "slot" if record["slots"] == 1 else "slots"
            lines.append(
                f"  Step {record['step']}: {record['action'] or 'initial state'}; "
                f"cumulative cost {record['slots']} atomic {unit}"
            )
        if profile["global_quantity"] is None:
            lines.append(
                "  Numerical input checks unresolved: "
                + profile["input_diagnostics"].get("reason", "invalid state")
            )
            continue
        for q in [{"id": "global", **profile["global_quantity"]}, *profile["windows"]]:
            lines.append(
                f"  {q['id']}: subsystem entropy={_window_number(q['entropy_bits'])} bits; deficit={_window_number(q['entropy_deficit_bits'])} bits; C={_window_number(q['rcc_main_term'])}"
            )
        if profile["partition"] is not None:
            left = ", ".join(profile["partition"]["left"]["keep"])
            right = ", ".join(profile["partition"]["right"]["keep"])
            lines.append(
                f"  Total correlation ({left} | {right}): {_window_number(profile['partition']['total_correlation_bits'])} bits"
            )
        if details:
            lines.append(f"  State identity: {profile['state_digest']}")
    lines.append(
        "Entropies use binary64 logarithms. Values below 1e-12 in magnitude "
        "display as ~0; JSON and CSV retain the original values. "
        "Mixed-state total correlation includes classical correlation."
    )
    return lines


def export_window_files(result, *, csv_path=None, plot_path=None, overwrite=False):
    from .cli import write_atomic

    rows = [
        {
            "state": p["id"],
            "window": q["id"],
            "entropy_bits": q["entropy_bits"],
            "deficit_bits": q["entropy_deficit_bits"],
            "rcc_main_term": q["rcc_main_term"],
        }
        for p in result["profiles"]
        for q in p["windows"]
    ]
    if csv_path is not None:
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "state",
                "window",
                "entropy_bits",
                "deficit_bits",
                "rcc_main_term",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
        write_atomic(csv_path, stream.getvalue(), overwrite=overwrite)
    if plot_path is None:
        return
    destination = Path(plot_path)
    if destination.suffix.lower() not in {".svg", ".png", ".pdf"}:
        raise InputError("plot: choose .svg, .png or .pdf")
    try:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
    except ImportError:
        result["execution"] = {
            "state": "partial",
            "reason": "optional_plot_dependency_missing",
        }
        return
    if len(rows) > 128:
        result["execution"] = {"state": "partial", "reason": "optional_plot_row_limit"}
        return
    fig = Figure(figsize=(8, max(3, 0.3 * len(rows) + 1)), layout="constrained")
    FigureCanvasAgg(fig)
    ax = fig.subplots()
    ax.barh(range(len(rows)), [r["rcc_main_term"] for r in rows], color="#266c85")
    ax.set_yticks(range(len(rows)), [f"{r['state']} / {r['window']}" for r in rows])
    ax.invert_yaxis()
    ax.set_xlabel(
        f"Window RCC main term C (Gamma={result['reference']['gamma_exact']})"
    )
    ax.set_title("State organization by subsystem window")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=".rcc-plot-", suffix=destination.suffix, dir=destination.parent
    )
    os.close(fd)
    try:
        fig.savefig(temporary)
        if overwrite:
            os.replace(temporary, destination)
        else:
            os.link(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
