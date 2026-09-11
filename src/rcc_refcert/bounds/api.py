"""Reference end-to-end records following C.1/C.2 and D.47.

All process conclusions remain conditional on the supplied model premises.
The scalar calculations share a single implementation across API and CLI.
"""

from __future__ import annotations

from fractions import Fraction

from .._version import __version__
from .contracts import Task, canonical_hash, json_ready, keys, text, validate_protocol
from .information import hoeffding_lower, projection_information, spectral_information
from .scalar import (
    InputError,
    Interval,
    ceil_fraction,
    decimal_string,
    invert_canonical,
    log2_interval,
    rational,
    require_int,
)


def _record(
    task: Task,
    information: Interval,
    details: dict,
    path: str,
    inputs: dict,
    statistics: dict | None = None,
) -> dict:
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
    keys(request, {"task", "spectrum"}, "spectrum request")
    task = Task.from_dict(request["task"])
    info = spectral_information(request["spectrum"], task.dimension, task.epsilon)
    return _record(task, info.information, info.as_dict(), "spectrum", request)


def bound_from_counts(request: dict) -> dict:
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
    occupancy = hoeffding_lower(data["hits"], n, delta)
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


def render_record(result: dict, *, details: bool = False) -> str:
    """Render one result; short display values were rounded down at construction."""
    c = result["cost"]
    display = result["display"]
    lines = [
        "RCC lower bound (conditional on the declared model)",
        f"Task: {result['task']['id']} | model: {result['model']['id']}",
        f"Continuous lower bound: {display['lower_bound_slots']} atomic slots (rounded down)",
    ]
    if c["integer_lower_bound_slots"] is not None:
        lines.append(f"Integer-slot lower bound: {c['integer_lower_bound_slots']}")
    lines.append(
        f"One-shot information input: {display['information_lower_bits']} bits (rounded down)"
    )
    lines.append(
        f"Generation tolerance: {result['parameters']['generation_epsilon']} (trace distance)"
    )
    if result["confidence"]:
        lines.append(
            "Sampling coverage at least: "
            + result["confidence"]["coverage_at_least_exact"]
        )
        lines.append("Data source: " + result["information"]["data_origin"])
    lines.append(
        "Model premises: supplied externally; not verified by this calculator."
    )
    lines.append(f"Calculation: {result['analysis_state']}")
    if c["zero_reason"]:
        lines.append("Zero-bound explanation: " + ZERO_EXPLANATIONS[c["zero_reason"]])
        lines.append("Zero is not a claim of zero preparation cost.")
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
