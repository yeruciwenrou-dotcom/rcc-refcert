"""Terminal-state RCC lower bounds for the declared model, with D.6 audit records."""

from __future__ import annotations

from fractions import Fraction

from .._version import __version__
from .contracts import (
    COUNT_ORIGIN_LABELS,
    Task,
    canonical_hash,
    json_ready,
    keys,
    text,
    validate_projector_hits,
    validate_protocol,
)
from .effects import RECORD, REQUEST, analyze_effect_counts, render_effect_record
from .information import hoeffding_lower, projection_information, spectral_information
from .scalar import (
    InputError,
    Interval,
    bit_text,
    ceil_fraction,
    decimal_string,
    invert_canonical,
    log2_interval,
    probability_text,
    rational,
    require_int,
)


def _cost_terms(task: Task, information: Interval, details: dict, path: str):
    """Shared conservative cost inversion for original and derived records."""
    g = log2_interval(Fraction(task.gamma_classes))
    beta = Interval.point(task.gamma_bits) + log2_interval(task.reference_constant)
    y = information - beta
    inverse, numerical_status = invert_canonical(y, g, task.a)
    if inverse.lower > 0:
        zero_reason = None
    elif path == "spectrum" and information.upper == 0:
        zero_reason = "smoothing_saturated"
    elif details.get("acceptance_margin_exhausted"):
        zero_reason = "sampling_margin_exhausted"
    elif information.upper <= 0:
        zero_reason = "reference_contrast_not_resolved"
    elif y.upper <= 0:
        zero_reason = "model_overhead_exhausted"
    else:
        zero_reason = "numerical_resolution_limited"
    return g, beta, inverse, numerical_status, zero_reason


def _record(
    task: Task,
    information: Interval,
    details: dict,
    path: str,
    inputs: dict,
    statistics: dict | None = None,
) -> dict:
    g, beta, inverse, numerical_status, zero_reason = _cost_terms(
        task, information, details, path
    )
    details = {**details, "one_shot_readout_st_R": (information / g).strings()}
    decl = task.declaration
    record = {
        "schema": "rcc-refcert.bound-record",
        "schema_version": 2,
        "producer": {"name": "rcc-refcert", "version": __version__},
        "artifact_role": "fresh-run-bound",
        "analysis_state": "complete" if numerical_status == "complete" else "partial",
        "record_role": "conditional_cost_lower_bound",
        "task": {"fingerprint": task.fingerprint, **decl["target"]},
        "model": decl["model"],
        "qualification": decl["model"]["qualification"],
        "path": {
            "name": path,
            "cost_formula": "C.4",
            "information_formula": "C.10" if path == "spectrum" else "D.17/C.18",
        },
        "parameters": {
            "dimension": task.dimension,
            "generation_epsilon": str(task.epsilon),
            "program_radius": str(task.epsilon),
            "smoothing_radius": str(task.epsilon),
            "bandwidth_bits_per_slot": g.strings(),
            "beta_bits": beta.strings(),
            "reporting_unit": {
                "symbol": "st_R",
                "bits_per_unit": g.strings(),
                "meaning": "calibrated information unit; full process bound additionally uses beta and cost inversion",
            },
        },
        "calibration": {
            "statistical": statistics,
            "deterministic": {
                "arithmetic": "fraction-endpoints-and-decimal-ln-enclosures",
                "decimal_precision": 64,
                "input_semantics": "exact_as_declared",
                "matrix_eigensolver_certified": False,
            },
        },
        "reference_treatment": {
            "mode": "ideal_support",
            "reference_id": decl["model"]["reference_id"],
        },
        "confidence": None
        if statistics is None
        else {
            "coverage_at_least_exact": str(1 - rational(statistics["delta_stat"])),
            "scope": "sampling_event_under_declared_fixed_n_iid_model; not probability that model premises are true",
        },
        "information": details,
        "cost": {
            "lower_bound_slots": decimal_string(inverse.lower),
            "calculator_enclosure_slots": inverse.strings(),
            "integer_lower_bound_slots": ceil_fraction(inverse.lower)
            if task.integer_cost
            else None,
            "enclosure_upper_is_process_upper_bound": False,
            "numerical_status": numerical_status,
            "zero_reason": zero_reason,
        },
        "flags": [
            "model_premises_external_not_machine_verified",
            "no_general_reachability_or_optimality_inference",
        ],
        "display": {
            "lower_bound_slots": decimal_string(inverse.lower, 8),
            "information_lower_bits": decimal_string(information.lower, 8),
            "rounding": "toward_negative_infinity",
        },
        "provenance": {
            "input_sha256": canonical_hash(inputs),
            "input_snapshot": json_ready(inputs),
            "input_hash_semantics": "submitted-exact-values; spellings may differ",
            "method_reference": "RCC manuscript: Appendices A, C and D; docs/TERMINAL_BOUNDS.md",
        },
    }
    # Check serialization relationships, not the truth of external premises.
    from .records import validate_record

    validate_record(record)
    return record


def bound_from_spectrum(request: dict) -> dict:
    """Compute a terminal lower-bound record from an exact target spectrum and declared task."""
    keys(request, {"task", "spectrum"}, "spectrum request")
    task = Task.from_dict(request["task"])
    info = spectral_information(request["spectrum"], task.dimension, task.epsilon)
    return _record(task, info.information, info.as_dict(), "spectrum", request)


def bound_from_counts(request: dict) -> dict:
    """Compute a terminal lower-bound record from a frozen measurement protocol and observed counts."""
    if isinstance(request, dict) and request.get("schema") == REQUEST:
        return analyze_effect_counts(request)
    keys(request, {"task", "protocol", "data"}, "counts request")
    task = Task.from_dict(request["task"])
    p = validate_protocol(task, request["protocol"])
    n, rank = p["samples"], p["rank"]
    delta = rational(p["delta_stat"], "protocol.delta_stat")
    data = keys(
        request["data"],
        {"protocol_id", "protocol_sha256", "samples", "hits", "origin", "dataset_id"},
        "data",
    )
    if data["protocol_sha256"] != canonical_hash(p):
        raise InputError(
            "data protocol digest differs or is missing; reuse the protocol frozen before acquisition, not a revised witness or confidence budget"
        )
    if data["protocol_id"] != p["id"] or data["samples"] != n:
        raise InputError(
            "counts must match the declared protocol and fixed sample size"
        )
    require_int(data["samples"], "data.samples", 1)
    text(data["dataset_id"], "data.dataset_id")
    if not isinstance(data["origin"], str) or data["origin"] not in {
        "synthetic_fixture",
        "observed_counts",
        "simulation",
    }:
        raise InputError("data origin must be explicit")
    hits = validate_projector_hits(data["hits"], p, task.dimension)
    occupancy = hoeffding_lower(hits, n, delta)
    info = projection_information(occupancy.lower, rank, task.dimension, task.epsilon)
    details = {
        "kind": "fixed_projector_counts",
        "information_semantics": "enclosure_of_witness_lower_bound_only; not upper bound on true Dmax",
        "information_bits": info.strings(),
        "occupancy_endpoint_enclosure": occupancy.strings(),
        "occupancy_lower_used": decimal_string(occupancy.lower),
        "rank": rank,
        "reference_response_exact": str(Fraction(rank, task.dimension)),
        "samples": n,
        "hits": data["hits"],
        "witness_id": p["witness_id"],
        "dataset_id": data["dataset_id"],
        "data_origin": data["origin"],
        "acquisition_protocol_sha256": data["protocol_sha256"],
        "acceptance_margin_exhausted": occupancy.lower <= task.epsilon,
    }
    stat = {
        "event_id": p["id"] + ":occupancy-lower",
        "delta_stat": str(delta),
        "method": "one-sided Hoeffding, D.5",
        "protocol": p,
        "protocol_sha256": canonical_hash(p),
        "chronology_or_iid_independently_verified": False,
    }
    return _record(task, info, details, "fixed_projector_counts", request, stat)


ZERO_EXPLANATIONS = {
    "smoothing_saturated": "The declared tolerance already includes the reference state.",
    "sampling_margin_exhausted": "The occupancy lower endpoint does not exceed the generation tolerance.",
    "reference_contrast_not_resolved": "The remaining occupancy does not exceed the reference response.",
    "model_overhead_exhausted": "The one-shot input is fully absorbed by the model overhead.",
    "numerical_resolution_limited": "Only zero is resolved with the current numerical allowance.",
}


def _enclosure_text(enclosure):
    from decimal import ROUND_CEILING

    lower = decimal_string(Fraction(enclosure["lower"]), 8)
    upper = decimal_string(Fraction(enclosure["upper"]), 8, ROUND_CEILING)
    return lower if lower == upper else f"[{lower}, {upper}]"


def _scale_line(classes, bandwidth):
    return (
        f"Calibration: Gamma_R = {classes} atomic action classes, "
        f"g_R = log2(Gamma_R) = {bit_text(_enclosure_text(bandwidth))} per atomic slot. "
        "One R-structon (st_R) represents g_R bits."
    )


def render_record(result: dict, *, details: bool = False) -> str:
    """Render one result; short display values were rounded down at construction."""
    if result.get("schema") == RECORD:
        return render_effect_record(result, details=details)
    c = result["cost"]
    display = result["display"]
    lines = [
        "RCC quantum circuit complexity lower bound",
        f"Task: {result['task']['id']} | model: {result['model']['id']}",
        f"Continuous lower bound: {display['lower_bound_slots']} atomic slots (rounded down)",
    ]
    if c["integer_lower_bound_slots"] is not None:
        lines.append(f"Integer-slot lower bound: {c['integer_lower_bound_slots']}")
    lines.append(
        f"One-shot information input: {bit_text(display['information_lower_bits'])} (rounded down)"
    )
    info = result["information"]
    params = result["parameters"]
    lines.append(
        "One-shot RCC readout >= "
        + decimal_string(Fraction(info["one_shot_readout_st_R"]["lower"]), 8)
        + " st_R."
    )
    lines.append(
        _scale_line(
            result["model"]["atomic_action_classes"], params["bandwidth_bits_per_slot"]
        )
    )
    if result["path"]["name"] == "spectrum":
        lines.append(
            f"Mean relative information D = {bit_text(_enclosure_text(info['relative_entropy_bits']))}, "
            f"plus spectral skew = {bit_text(_enclosure_text(info['spectral_skew_bits']))}, "
            f"minus smoothing loss = {bit_text(_enclosure_text(info['smoothing_loss_bits']))}."
        )
        d = info["relative_entropy_bits"]
        g = params["bandwidth_bits_per_slot"]
        main = Interval(Fraction(d["lower"]), Fraction(d["upper"])) / Interval(
            Fraction(g["lower"]), Fraction(g["upper"])
        )
        lines.append(
            f"State-side main term C_R = D/g_R = {_enclosure_text(main.strings())} st_R."
        )
    lines.append(
        f"Generation tolerance: {result['parameters']['generation_epsilon']} (trace distance)"
    )
    if result["confidence"]:
        lines.append(
            "Sampling coverage is at least "
            + probability_text(result["confidence"]["coverage_at_least_exact"])
            + "."
        )
        lines.append("Data source: " + COUNT_ORIGIN_LABELS[info["data_origin"]])
    lines.append(f"Calculation: {result['analysis_state']}")
    if c["zero_reason"]:
        lines.append("Zero-bound explanation: " + ZERO_EXPLANATIONS[c["zero_reason"]])
    if details:
        import json

        lines.extend(
            [
                "",
                "Detailed record:",
                json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False),
            ]
        )
    return "\n".join(lines) + "\n"


def replay_record(record: dict) -> dict:
    """Recompute a current-version saved record from its exact input snapshot.

    Matching confirms reproducibility of this calculator, not the truth of
    model declarations, measurements or physical preparation claims.
    """
    from .records import validate_record

    validate_record(record)
    if record["schema"] == RECORD:
        fresh = analyze_effect_counts(record["provenance"]["input_snapshot"])
        if canonical_hash(fresh) != canonical_hash(record):
            raise InputError(
                "saved record differs from a fresh fixed-effect computation"
            )
        return {
            "schema": "rcc-refcert.replay",
            "schema_version": 3,
            "matches": True,
            "input_sha256": record["provenance"]["input_sha256"],
        }
    compute = (
        bound_from_spectrum
        if record["path"]["name"] == "spectrum"
        else bound_from_counts
    )
    expected = compute(record["provenance"]["input_snapshot"])
    if expected != record:
        raise InputError(
            "saved record differs from a fresh computation; original record was not changed"
        )
    return {
        "schema": "rcc-refcert.replay",
        "schema_version": 2,
        "matches": True,
        "input_sha256": record["provenance"]["input_sha256"],
        "scope": "same-version computation replay; external premises not verified",
    }
