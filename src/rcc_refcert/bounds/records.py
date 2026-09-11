"""Cross-field record checks, not a proof checker or an external certificate API.

A conforming record can still contain false external premises. This validator
checks identities, roles and basic numeric relationships. It does not re-run a
scientific computation or accept stored JSON as a proof of the RCC theorem.
"""

from __future__ import annotations

from fractions import Fraction

from .contracts import Task, canonical_hash, validate_protocol
from .scalar import InputError, ceil_fraction, rational, require_int


def _fail(message: str) -> None:
    raise InputError("record: " + message)


def _interval(raw: dict, name: str) -> tuple[Fraction, Fraction]:
    if not isinstance(raw, dict) or set(raw) != {"lower", "upper"}:
        _fail(name + " must contain exactly lower and upper")
    if any(not isinstance(raw[k], str) for k in raw):
        _fail(name + " endpoints must be decimal strings")
    lo, hi = rational(raw["lower"], name), rational(raw["upper"], name)
    if lo > hi:
        _fail(name + " is reversed")
    return lo, hi


def validate_record(record: dict) -> None:
    """Check D.47 relationships without certifying the supplied physics."""
    try:
        if (
            canonical_hash(record["provenance"]["input_snapshot"])
            != record["provenance"]["input_sha256"]
        ):
            _fail("input snapshot and hash differ")
        if (
            record["schema"] != "rcc-refcert.bound-record"
            or record["schema_version"] != 2
        ):
            _fail("unsupported bound-record schema or version")
        t = record["task"]
        target = {k: t[k] for k in ("id", "epsilon", "metric")}
        task = Task.from_dict({"model": record["model"], "target": target})
        if t["fingerprint"] != task.fingerprint:
            _fail("task fingerprint differs from its model/target declaration")
        if record["qualification"] != task.declaration["model"]["qualification"]:
            _fail("qualification copies differ")
        if record["reference_treatment"] != {
            "mode": "ideal_support",
            "reference_id": record["model"]["reference_id"],
        }:
            _fail("reference treatment differs from the model")
        p = record["parameters"]
        if p["dimension"] != task.dimension:
            _fail("dimension differs from model")
        for field in ("generation_epsilon", "program_radius", "smoothing_radius"):
            if rational(p[field], field) != task.epsilon:
                _fail("exact-transcription radii differ")
        information = record["information"]
        ilo, _ihi = _interval(information["information_bits"], "information")
        if ilo < 0:
            _fail("implemented spectrum/projector paths must have nonnegative input")
        g, _ = _interval(p["bandwidth_bits_per_slot"], "bandwidth")
        beta, _ = _interval(p["beta_bits"], "beta")
        if g <= 0 or beta < 0:
            _fail("invalid model scale or overhead")
        cost = record["cost"]
        clo, chi = _interval(cost["calculator_enclosure_slots"], "cost calculator")
        lower = rational(cost["lower_bound_slots"], "cost lower")
        if (
            not isinstance(cost["lower_bound_slots"], str)
            or not 0 <= lower == clo <= chi
        ):
            _fail("cost lower differs from the reported conservative endpoint")
        if cost["enclosure_upper_is_process_upper_bound"] is not False:
            _fail("calculator upper cannot be a process upper")
        integer = cost["integer_lower_bound_slots"]
        if task.integer_cost:
            require_int(integer, "integer lower bound")
            # A rounded-down decimal lower may cross an integer from above.
            # Do not demand ceil(display) == ceil(exact endpoint); retain this
            # conservative relationship and test exact rounding at generation.
            if integer < ceil_fraction(lower) or integer > ceil_fraction(chi):
                _fail("integer lower is inconsistent with calculator enclosure")
        elif integer is not None:
            _fail("integer rounding has no declared legal-cost basis")
        status = cost["numerical_status"]
        if status not in ("complete", "precision_limited", "iteration_budget_reached"):
            _fail("unknown numerical status")
        expected_state = "complete" if status == "complete" else "partial"
        if record["analysis_state"] != expected_state:
            _fail("analysis state differs from numerical status")
        if record["record_role"] != "conditional_cost_lower_bound":
            _fail("external model premises must remain conditional")
        flags = record["flags"]
        if "model_premises_external_not_machine_verified" not in flags:
            _fail("missing external-premise flag")
        if not 0 <= rational(record["display"]["lower_bound_slots"]) <= lower:
            _fail("display raises the lower bound")
        if not 0 <= rational(record["display"]["information_lower_bits"]) <= ilo:
            _fail("display raises information input")
        path = record["path"]["name"]
        stat = record["calibration"]["statistical"]
        confidence = record["confidence"]
        if path == "spectrum":
            if stat is not None or confidence is not None:
                _fail("deterministic spectrum path cannot invent sampling confidence")
            if information["kind"] != "declared_exact_spectrum":
                _fail("spectrum result has incorrect role")
        elif path == "fixed_projector_counts":
            if not isinstance(stat, dict) or not isinstance(confidence, dict):
                _fail("counts path requires a statistical event and confidence")
            if information["kind"] != "fixed_projector_counts":
                _fail("counts result has incorrect role")
            protocol = validate_protocol(task, stat["protocol"])
            digest = canonical_hash(protocol)
            if (
                stat["protocol_sha256"] != digest
                or information["acquisition_protocol_sha256"] != digest
            ):
                _fail("protocol digest differs from acquisition identity")
            for a, b in [
                ("rank", "rank"),
                ("samples", "samples"),
                ("witness_id", "witness_id"),
            ]:
                if information[a] != protocol[b]:
                    _fail("projector/count metadata differs from protocol")
            delta = rational(stat["delta_stat"])
            if delta != rational(protocol["delta_stat"]):
                _fail("statistical budgets differ")
            if rational(confidence["coverage_at_least_exact"]) != 1 - delta:
                _fail("confidence is not the complement of the declared failure budget")
            if stat["chronology_or_iid_independently_verified"] is not False:
                _fail("input identity cannot prove chronology or iid")
            require_int(information["hits"], "hits")
            if information["hits"] > protocol["samples"]:
                _fail("hits exceed sample count")
            if rational(information["reference_response_exact"]) != Fraction(
                protocol["rank"], task.dimension
            ):
                _fail("projector reference response differs from rank/dimension")
        else:
            _fail("unimplemented information path")
    except (KeyError, TypeError, AttributeError) as exc:
        raise InputError("record is incomplete or has invalid field types") from exc
