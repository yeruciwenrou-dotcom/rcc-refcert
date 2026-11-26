"""Fixed binary effect on target and reference, RCC V4 C.15–17 and D.46."""

from __future__ import annotations

from fractions import Fraction

from .._version import __version__
from .binomial import CP, CP_MAX_N, HOEFFDING, sampling_endpoint
from .contracts import QUALIFICATION_NAMES, Task, canonical_hash, json_ready, keys, text
from .information import fixed_effect_information
from .scalar import (
    BudgetError,
    InputError,
    ceil_fraction,
    decimal_string,
    rational,
    require_int,
)

REQUEST = "rcc-refcert.fixed-effect-counts"
PROTOCOL = "rcc-refcert.fixed-effect-protocol"
RECORD = "rcc-refcert.fixed-effect-record"
ROLES = ("target", "reference")


def probability(value, name):
    p = rational(value, name)
    if not 0 <= p <= 1:
        raise InputError(f"{name} must lie in [0,1]")
    return p


def check_version(obj, schema):
    if (
        not isinstance(obj, dict)
        or obj.get("schema") != schema
        or type(obj.get("schema_version")) is not int
        or obj["schema_version"] != 1
    ):
        raise InputError(f"expected {schema} schema version 1")


def prepare_effect_protocol(spec: dict) -> dict:
    """Freeze measurement and acquisition, independently of later preparation tolerances."""
    p = json_ready(
        keys(spec, {"schema", "schema_version", "effect", *ROLES}, "effect protocol")
    )
    check_version(p, PROTOCOL)
    effect = keys(
        p["effect"],
        {"id", "setting", "readout", "accept", "reject", "selection", "support"},
        "effect",
        {"calibration"},
    )
    for field in ("id", "setting", "readout", "accept", "reject"):
        text(effect[field], f"effect.{field}")
    if "calibration" in effect:
        cal = keys(
            effect["calibration"],
            {"kind", "false_positive", "false_negative", "source"},
            "effect.calibration",
        )
        if cal["kind"] != "known_binary":
            raise InputError("calibration requires a known binary readout matrix")
        text(cal["source"], "calibration.source")
        for field in ("false_positive", "false_negative"):
            cal[field] = str(probability(cal[field], field))
    if effect["accept"] == effect["reject"]:
        raise InputError("the two exhaustive binary outcome labels must differ")
    if effect["selection"] != "predeclared" or effect["support"] != "no_leakage":
        raise InputError(
            "the same predeclared effect on the declared support is required"
        )
    bindings, events, datasets = {}, set(), set()
    total = Fraction()
    for role in ROLES:
        arm = p[role]
        kind = arm.get("kind") if isinstance(arm, dict) else None
        if kind == "counts":
            keys(
                arm,
                {
                    "kind",
                    "state_id",
                    "event_id",
                    "dataset_id",
                    "samples",
                    "delta",
                    "sampling",
                },
                role,
                {"method"},
            )
            event, dataset = (
                text(arm[k], f"{role}.{k}") for k in ("event_id", "dataset_id")
            )
            if event in events or dataset in datasets:
                raise InputError(
                    "target and reference need distinct event_id and dataset_id for distinct observations"
                )
            events.add(event)
            datasets.add(dataset)
            method = arm.get("method", HOEFFDING)
            if method not in (CP, HOEFFDING):
                raise InputError(f"{role}: unknown binomial endpoint method")
            if arm["sampling"] != "fixed_n_iid":
                raise InputError(
                    f"{role}: binomial inference requires fixed_n_iid sampling"
                )
            if require_int(arm["samples"], f"{role}.samples", 1) > 10**12:
                raise BudgetError(f"{role}: sample count exceeds calculation budget")
            if method == CP and arm["samples"] > CP_MAX_N:
                raise BudgetError(f"Clopper-Pearson supports up to {CP_MAX_N} trials")
            failure = probability(arm["delta"], f"{role}.delta")
            if not 0 < failure < 1:
                raise InputError(f"{role}.delta must lie in (0,1)")
            arm["delta"] = str(failure)
            total += failure
        elif role == "reference" and kind in ("exact", "upper_bound"):
            keys(arm, {"kind", "state_id", "response", "source"}, role)
            arm["response"] = str(probability(arm["response"], "reference.response"))
            text(arm["source"], "reference.source")
        else:
            raise InputError(f"{role}: unsupported response source")
        text(arm["state_id"], f"{role}.state_id")
        bindings[role] = canonical_hash(
            {
                "schema": PROTOCOL,
                "schema_version": 1,
                "role": role,
                "effect": effect,
                "arm": arm,
            }
        )
    if total >= 1:
        raise InputError("total sampling failure budget must be less than one")
    return {"protocol": p, "protocol_sha256": canonical_hash(p), "arm_sha256": bindings}


def _read_counts(arm, role, effect, binding, data):
    keys(data, {"arm_sha256", "dataset_id", "origin", "counts"}, f"data.{role}")
    if data["arm_sha256"] != binding or data["dataset_id"] != arm["dataset_id"]:
        raise InputError(
            f"data.{role}: frozen measurement, sampling plan or dataset identity differs"
        )
    if data["origin"] not in ("observed_counts", "simulation", "synthetic_fixture"):
        raise InputError(f"data.{role}.origin must identify the data source")
    counts = keys(
        data["counts"], {effect["accept"], effect["reject"]}, f"data.{role}.counts"
    )
    hits = require_int(counts[effect["accept"]], f"{role}.accepted")
    misses = require_int(counts[effect["reject"]], f"{role}.rejected")
    if hits + misses != arm["samples"]:
        raise InputError(f"data.{role}: count total differs from frozen sample size")
    event = {
        "id": arm["event_id"],
        "role": role,
        "dataset_id": arm["dataset_id"],
        "arm_sha256": binding,
        "data_sha256": canonical_hash(data),
        "delta": arm["delta"],
        "origin": data["origin"],
        "endpoint": "lower" if role == "target" else "upper",
    }
    return hits, event


def observed_direction(effect, role):
    cal = effect.get("calibration")
    decreasing = (
        cal is not None
        and rational(cal["false_positive"]) + rational(cal["false_negative"]) > 1
    )
    return "lower" if (role == "target") != decreasing else "upper"


def binary_readout_preimage(lower, upper, false_positive, false_negative):
    """Invert a closed observed-response interval on the physical domain [0,1]."""
    lo = probability(lower, "observed lower")
    hi = probability(upper, "observed upper")
    if lo > hi:
        raise InputError("reversed observed interval")
    f = probability(false_positive, "false_positive")
    slope = 1 - f - probability(false_negative, "false_negative")
    if slope == 0:
        return (Fraction(0), Fraction(1)) if lo <= f <= hi else None
    left, right = sorted(((lo - f) / slope, (hi - f) / slope))
    left, right = max(Fraction(0), left), min(Fraction(1), right)
    return (left, right) if left <= right else None


def arm_response(arm, role, effect, binding, data, saved=None):
    hits, event = _read_counts(arm, role, effect, binding, data)
    direction = observed_direction(effect, role)
    observed = sampling_endpoint(hits, arm, direction) if saved is None else saved
    event["endpoint"] = direction
    if "method" in arm:
        event["method"] = arm["method"]
    if "calibration" not in effect:
        return observed, event
    cal = effect["calibration"]
    limits = (observed, 1) if direction == "lower" else (0, observed)
    ideal = binary_readout_preimage(
        *limits, cal["false_positive"], cal["false_negative"]
    )
    event["observed_endpoint_exact"] = str(observed)
    event["ideal_feasible_interval"] = None if ideal is None else list(map(str, ideal))
    if ideal is None:
        return None, event
    return ideal[0 if role == "target" else 1], event


def _qualified_task(raw, protocol, radius):
    if raw is None:
        return None, ["task"], None
    keys(raw, {"model", "target"}, "task")
    keys(raw["target"], {"id", "epsilon", "metric"}, "target")
    model = raw["model"]
    if not isinstance(model, dict):
        raise InputError("task.model must be an object")
    if (
        model.get("reference_id") != protocol["reference"]["state_id"]
        or raw["target"].get("id") != protocol["target"]["state_id"]
    ):
        raise InputError(
            "task target or model reference differs from the frozen preparation identity"
        )
    if radius < probability(raw["target"].get("epsilon"), "target.epsilon"):
        raise InputError("smoothing radius must cover the generation tolerance")
    supplied = model.get("qualification", {})
    keys(supplied, set(), "model.qualification", QUALIFICATION_NAMES)
    missing = sorted(QUALIFICATION_NAMES - supplied.keys())
    task = Task._parse(raw, allow_missing_qualifications=True)
    # The validated ideal support constrains state responses independently of process qualifications.
    return task, [f"model.qualification.{k}" for k in missing], model["dimension"]


def _route(name, acceptance, reference, radius, reason, task, events):
    from .api import _cost_terms

    result = {
        "route": name,
        "event_ids": events,
        "eligible": reason is None,
        "reason": reason,
        "information_floor_bits": None,
        "cost": None,
    }
    if reason:
        return result
    info = fixed_effect_information(acceptance, reference, radius)
    result["information_floor_bits"] = info.strings()
    if task is not None:
        _, _, inv, status, zero = _cost_terms(
            task,
            info,
            {"acceptance_margin_exhausted": acceptance <= radius},
            "fixed_effect",
        )
        result["cost"] = {
            "lower_bound_slots": decimal_string(inv.lower),
            "calculator_enclosure_slots": inv.strings(),
            "integer_lower_bound_slots": ceil_fraction(inv.lower)
            if task.integer_cost
            else None,
            "numerical_status": status,
            "zero_reason": zero,
        }
    return result


def analyze_effect_counts(request):
    """Compute both one-sided endpoints from the raw sampling records."""
    return _derive_effect_record(request)


def _derive_effect_record(request, saved_endpoints=None):
    keys(
        request,
        {"schema", "schema_version", "protocol", "data", "derivation"},
        "fixed-effect request",
        {"task"},
    )
    check_version(request, REQUEST)
    frozen = prepare_effect_protocol(request["protocol"])
    p = frozen["protocol"]
    data = keys(
        request["data"],
        {role for role in ROLES if p[role]["kind"] == "counts"},
        "fixed-effect data",
    )
    spec = keys(request["derivation"], {"smoothing_radius"}, "derivation", {"eta"})
    radius = probability(spec["smoothing_radius"], "smoothing_radius")
    eta = probability(spec["eta"], "eta") if "eta" in spec else None
    task, missing, dimension = _qualified_task(request.get("task"), p, radius)
    endpoints, events = {}, []
    for role in ROLES:
        arm = p[role]
        if arm["kind"] == "counts":
            endpoints[role], event = arm_response(
                arm,
                role,
                p["effect"],
                frozen["arm_sha256"][role],
                data[role],
                None if saved_endpoints is None else saved_endpoints[role],
            )
            events.append(event)
        else:
            endpoints[role] = rational(arm["response"])
    a, b = endpoints["target"], endpoints["reference"]
    ids = [e["id"] for e in events]
    support = None
    cal = p["effect"].get("calibration", {})
    hits = data["target"]["counts"][p["effect"]["accept"]]
    misses = p["target"]["samples"] - hits

    def impossible_observation(response):
        return (hits > 0 and response == 0) or (misses > 0 and response == 1)

    if a is None or b is None:
        support = "empty_readout_preimage"
    elif b == 0:
        support = "zero_reference_requires_support_assessment"
        if dimension is not None:
            support = "zero_effect_on_ideal_support"
            if a > 0 or impossible_observation(rational(cal.get("false_positive", 0))):
                support = "target_hits_incompatible_with_zero_effect"
    elif dimension is not None and a > dimension * b:
        support = "response_incompatible_with_uniform_reference_on_support"
    elif (
        dimension is not None
        and p["reference"]["kind"] == "exact"
        and b == 1
        and impossible_observation(1 - rational(cal.get("false_negative", 0)))
    ):
        support = "target_misses_incompatible_with_identity_effect"
    direct_reason = support or ("sampling_margin_exhausted" if a <= radius else None)
    routes = [_route("fixed_effect_C15", a, b, radius, direct_reason, task, ids)]
    if eta is not None:
        threshold = 1 - eta
        reason = support
        if not reason and a < threshold:
            reason = "target_lower_below_one_minus_eta"
        if not reason and eta + radius >= 1:
            reason = "eta_plus_radius_must_be_less_than_one"
        routes.append(
            _route("hypothesis_test_C16_C17", threshold, b, radius, reason, task, ids)
        )
    costs = [r for r in routes if r["cost"] is not None]
    cost = None
    if costs:
        best = max(costs, key=lambda r: Fraction(r["cost"]["lower_bound_slots"]))
        cost = {**best["cost"], "selected_route": best["route"]}
    elif task and support in (None, "zero_effect_on_ideal_support"):
        cost = {
            "lower_bound_slots": "0",
            "integer_lower_bound_slots": 0 if task.integer_cost else None,
            "selected_route": None,
            "zero_reason": direct_reason,
            "numerical_status": "complete",
            "calculator_enclosure_slots": {"lower": "0", "upper": "0"},
        }
    identity = {
        "task": task.declaration if task else json_ready(request.get("task")),
        "smoothing_radius": str(radius),
        "eta": str(eta) if eta is not None else None,
        "protocol_sha256": frozen["protocol_sha256"],
        "data_sha256": canonical_hash(data),
    }
    total = sum((rational(e["delta"]) for e in events), Fraction())
    if support == "empty_readout_preimage":
        decision = "readout_conflict"
    elif support and "incompatible" in support:
        decision = "support_conflict"
    elif support == "zero_reference_requires_support_assessment":
        decision = "support_assessment_required"
    elif task is None:
        decision = "information_only"
    else:
        decision = "cost_lower_bound"
    information = max(
        (
            Fraction(r["information_floor_bits"]["lower"])
            for r in routes
            if r["eligible"]
        ),
        default=Fraction(0),
    )
    return {
        "schema": RECORD,
        "schema_version": 1,
        "producer": {"name": "rcc-refcert", "version": __version__},
        "analysis_state": "partial"
        if cost and cost["numerical_status"] != "complete"
        else "complete",
        "decision": decision,
        "information_lower_bits": None
        if decision
        in ("readout_conflict", "support_conflict", "support_assessment_required")
        else decimal_string(information),
        "protocol_sha256": frozen["protocol_sha256"],
        "derivation_sha256": canonical_hash(identity),
        "task_fingerprint": task.fingerprint if task else None,
        "missing_process_premises": missing,
        "support_diagnostic": support,
        "target_response_lower_exact": None if a is None else str(a),
        "reference_response_upper_exact": None if b is None else str(b),
        "external_premises_verified": False,
        "reference_source": p["reference"]["kind"],
        "coverage": {
            "events": events,
            "delta_total": str(total),
            "coverage_at_least_exact": str(1 - total),
            "method": "one_sided_binomial_union_bound"
            if any(e.get("method") == CP for e in events)
            else "one_sided_hoeffding_union_bound",
        },
        "routes": routes,
        "cost": cost,
        "provenance": {
            "input_snapshot": json_ready(request),
            "input_sha256": canonical_hash(request),
        },
    }


def validate_effect_record(record, request=None):
    """Check identities and internal relationships without rerunning the endpoints."""
    check_version(record, RECORD)
    source = keys(
        record.get("provenance"),
        {"input_snapshot", "input_sha256"},
        "record.provenance",
    )
    raw = source["input_snapshot"]
    if (
        canonical_hash(raw) != source["input_sha256"]
        or request is not None
        and canonical_hash(request) != source["input_sha256"]
    ):
        raise InputError("record input binding differs from supplied request")
    producer = keys(record.get("producer"), {"name", "version"}, "record.producer")
    if producer["name"] != "rcc-refcert":
        raise InputError("unsupported record producer")
    text(producer["version"], "record producer version")
    if "calibration" in raw["protocol"]["effect"]:
        endpoints = {
            e["role"]: probability(
                e["observed_endpoint_exact"], "saved observed endpoint"
            )
            for e in record["coverage"]["events"]
        }
    else:
        endpoints = {
            "target": probability(
                record.get("target_response_lower_exact"), "saved target lower"
            ),
            "reference": probability(
                record.get("reference_response_upper_exact"), "saved reference upper"
            ),
        }
    expected = _derive_effect_record(raw, saved_endpoints=endpoints)
    expected["producer"] = producer
    if canonical_hash(expected) != canonical_hash(record):
        raise InputError(
            "stored conclusions or evidence bindings differ from the saved response endpoints"
        )


_DIAGNOSTICS = {
    "empty_readout_preimage": "the observed confidence region has no preimage under the declared readout",
    "target_lower_below_one_minus_eta": "the certified target acceptance is below 1 - eta",
    "eta_plus_radius_must_be_less_than_one": "eta plus the smoothing radius must be below one",
    "sampling_margin_exhausted": "the target lower endpoint does not exceed the smoothing radius",
    "zero_reference_requires_support_assessment": "a deterministic zero reference requires a support assessment",
    "zero_effect_on_ideal_support": "the effect vanishes on the declared ideal support",
    "target_hits_incompatible_with_zero_effect": "target hits conflict with a zero effect on the declared ideal support",
    "target_misses_incompatible_with_identity_effect": "target misses conflict with an identity effect on the declared ideal support",
    "response_incompatible_with_uniform_reference_on_support": "the joint endpoints conflict with the declared uniform reference on this support",
}


def render_effect_record(record, *, details=False):
    from decimal import ROUND_CEILING

    request = record["provenance"]["input_snapshot"]
    p = request["protocol"]
    a = record["target_response_lower_exact"]
    b = record["reference_response_upper_exact"]
    lines = []
    cost = record["cost"]
    if cost is not None:
        lines.append(
            f"Continuous lower bound: {decimal_string(Fraction(cost['lower_bound_slots']), 8)} atomic slots"
        )
        if cost["integer_lower_bound_slots"] is not None:
            lines.append(
                f"Integer-slot lower bound: {cost['integer_lower_bound_slots']}"
            )
        if cost["zero_reason"]:
            from .api import ZERO_EXPLANATIONS

            reason = cost["zero_reason"]

            lines.append(
                "Zero-bound explanation: "
                + _DIAGNOSTICS.get(reason, ZERO_EXPLANATIONS.get(reason, reason))
            )
    elif (
        record["missing_process_premises"] == ["task"]
        and not record["support_diagnostic"]
    ):
        lines.append(
            "To bound the preparation cost, supply the preparation model and target tolerance."
        )
    else:
        lines.append(
            "Process cost unavailable: "
            + (
                _DIAGNOSTICS.get(record["support_diagnostic"])
                or ", ".join(record["missing_process_premises"])
            )
        )
    lines += [
        f"Fixed effect {p['effect']['id']} | target {p['target']['state_id']} | reference {p['reference']['state_id']}",
        f"Target response >= {decimal_string(Fraction(a), 8) if a is not None else 'unavailable'}; reference response <= {decimal_string(Fraction(b), 8, ROUND_CEILING) if b is not None else 'unavailable'} ({record['reference_source']})",
        f"Joint sampling coverage >= {record['coverage']['coverage_at_least_exact']}",
    ]
    if request.get("task"):
        task = request["task"]
        lines.append(
            f"Model {task['model']['id']}, generation tolerance {task['target']['epsilon']} (trace distance)"
        )
        from .api import _scale_line
        from .scalar import log2_interval

        classes = task["model"]["atomic_action_classes"]
        bandwidth = log2_interval(Fraction(classes))
        floor = record["information_lower_bits"]
        if floor is not None:
            scaled = decimal_string(Fraction(floor) / bandwidth.upper, 8)
            lines.append(f"One-shot RCC readout >= {scaled} st_R.")
        lines.append(_scale_line(classes, bandwidth.strings()))
    lines.append(f"Smoothing radius: {request['derivation']['smoothing_radius']}")
    for event in record["coverage"]["events"]:
        lines.append(
            f"  {event['role']}: {event['origin']}, dataset {event['dataset_id']}, failure budget {event['delta']}"
        )
        if "observed_endpoint_exact" in event:
            direction = event["endpoint"]
            lines.append(
                f"    Observed {direction} endpoint: {event['observed_endpoint_exact']} | compatible ideal interval: {event['ideal_feasible_interval']}"
            )
        if "method" in event:
            lines.append(f"    Endpoint method: {event['method']}")
    for route in record["routes"]:
        info = route["information_floor_bits"]
        result = (
            f">= {decimal_string(Fraction(info['lower']), 8)} bits"
            if info
            else _DIAGNOSTICS.get(route["reason"], route["reason"])
        )
        lines.append(f"{route['route']}: {result}")
    if details:
        lines.extend(
            [
                f"Acquisition SHA-256: {record['protocol_sha256']}",
                f"Derivation SHA-256: {record['derivation_sha256']}",
            ]
        )
    return "\n".join(lines) + "\n"
