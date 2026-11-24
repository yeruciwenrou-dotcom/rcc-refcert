"""Predeclared complete projective measurements of finite-sample RCC windows."""

from __future__ import annotations

from fractions import Fraction as F

from .._version import __version__
from ..bounds.api import _cost_terms
from ..bounds.binomial import CP, CP_MAX_N, HOEFFDING, sampling_endpoint
from ..bounds.contracts import Task, canonical_hash, json_ready, keys, text
from ..bounds.effects import probability
from ..bounds.multinomial import HistogramRegion, tv_radius
from ..bounds.scalar import (
    BudgetError,
    InputError,
    Interval,
    ceil_fraction,
    decimal_string,
    log2_interval,
    require_int,
)
from .core import WorkflowLimits, check_size

REQUEST = "rcc-refcert.pvm-windows"
RECORD = "rcc-refcert.pvm-window-record"
KIND = "pvm_windows"


def _items(x, name, maximum, minimum=1):
    if not isinstance(x, list) or len(x) < minimum:
        raise InputError(f"{name}: expected a list with at least {minimum} entries")
    if len(x) > maximum:
        raise BudgetError(f"{name}: at most {maximum} entries")
    return x


def _ranks(x, name):
    if not isinstance(x, dict) or not x:
        raise InputError(f"{name}: declare nonempty block ranks")
    if len(x) > 256:
        raise BudgetError("at most 256 PVM outcomes are supported")
    for label, r in x.items():
        text(label, name)
        if require_int(r, "block rank", 1).bit_length() > 256:
            raise BudgetError("block rank exceeds the 256-bit dimension budget")
    return x


def _product_axes(measurement):
    prod = keys(measurement["product"], {"axes", "coordinates", "source"}, "product")
    text(prod["source"], "tensor factorization and local projector source")
    axes = _items(prod["axes"], "product axes", 2, 2)
    for axis in axes:
        keys(axis, {"label", "ranks"}, "axis")
        text(axis["label"], "tensor label")
        _ranks(axis["ranks"], "local block ranks")
    a, b = axes
    if a["label"] == b["label"]:
        raise InputError("tensor axes must be distinct")
    ranks = measurement["ranks"]
    coords = keys(prod["coordinates"], set(ranks), "product coordinates")
    if len(a["ranks"]) * len(b["ranks"]) != len(ranks):
        raise InputError("product alphabet differs from the joint readout")
    seen = set()
    for outcome, coord in coords.items():
        _items(coord, "product coordinate", 2, 2)
        i, j = (text(v, "local outcome label") for v in coord)
        if (
            i not in a["ranks"]
            or j not in b["ranks"]
            or (i, j) in seen
            or ranks[outcome] != a["ranks"][i] * b["ranks"][j]
        ):
            raise InputError(
                "product coordinates or joint block rank disagree with local projectors"
            )
        seen.add((i, j))


def prepare_pvm_protocol(value):
    p = json_ready(
        keys(
            value,
            {
                "event_id",
                "dataset_id",
                "state_id",
                "reference_id",
                "reference_treatment",
                "support",
                "dimension",
                "measurement",
                "samples",
                "delta",
                "sampling",
                "selection",
            },
            "PVM acquisition",
            {"retention"},
        )
    )
    for k in ("event_id", "dataset_id", "state_id", "reference_id"):
        text(p[k], k)
    n = require_int(p["samples"], "fixed trial count", 1)
    if n > 10**12:
        raise BudgetError("trial budget exceeded")
    if p["sampling"] != "fixed_n_iid" or p["selection"] != "predeclared":
        raise InputError("certification requires a predeclared fixed-N IID measurement")
    delta = probability(p["delta"], "TV failure budget")
    if p["reference_treatment"] != "uniform_on_support" or p["support"] != (
        "projected_branch" if "retention" in p else "no_leakage"
    ):
        raise InputError(
            "declare a uniform reference and support consistent with the recorded acquisition"
        )
    p["delta"] = str(delta)
    m = keys(
        p["measurement"],
        {"id", "setting", "ranks", "readout", "window", "window_scope", "source"},
        "measurement",
        {"product"},
    )
    for k in ("id", "setting", "window", "source"):
        text(m[k], k)
    if m["readout"] != "ideal" or m["window_scope"] not in (
        "classical_blocks",
        "containing_quantum",
    ):
        raise InputError(
            "declare an ideal PVM and its classical or containing quantum window"
        )
    ranks = _ranks(m["ranks"], "PVM ranks")
    if delta >= 1 or (len(ranks) > 1 and delta == 0):
        raise InputError("multi-outcome TV failure budget must lie in (0,1)")
    tv_failure = delta if len(ranks) > 1 else F(0)
    d = require_int(p["dimension"], "reference dimension", 1)
    if sum(ranks.values()) != d or d.bit_length() > 256:
        raise InputError(
            "complete PVM ranks must sum to the declared reference dimension within 256 bits"
        )
    if "product" in m:
        _product_axes(m)
    if "retention" in p:
        r = p["retention"]
        known = isinstance(r, dict) and r.get("method") == "known"
        keys(
            r,
            {"source", "state", "method"}
            | ({"probability"} if known else {"event_id", "delta"}),
            "retention",
        )
        text(r["source"], "projected-state measurement source")
        if r["state"] != "normalized_projected" or r["method"] not in (
            CP,
            HOEFFDING,
            "known",
        ):
            raise InputError(
                "retention requires a declared normalized projected branch and supported probability evidence"
            )
        if known:
            r["probability"] = str(probability(r["probability"], "known retention"))
        else:
            text(r["event_id"], "retention event id")
            if r["method"] == CP and n > CP_MAX_N:
                raise BudgetError("Clopper-Pearson retention exceeds its trial limit")
            rd = probability(r["delta"], "retention failure budget")
            if rd <= 0 or rd + tv_failure >= 1 or r["event_id"] == p["event_id"]:
                raise InputError(
                    "retention needs a distinct event and joint failure budget below one"
                )
            r["delta"] = str(rd)
    return {"protocol": p, "protocol_sha256": canonical_hash(p)}


def _histogram(p, sha, data):
    conditional = "retention" in p
    data = keys(
        data,
        {"dataset_id", "protocol_sha256", "origin", "counts"}
        | ({"discarded"} if conditional else set()),
        "PVM data",
    )
    if data["dataset_id"] != p["dataset_id"] or data["protocol_sha256"] != sha:
        raise InputError(
            "data differ from their frozen PVM, sampling plan or dataset identity"
        )
    if data["origin"] not in ("observed_counts", "simulation", "synthetic_fixture"):
        raise InputError("declare the data origin")
    ranks = p["measurement"]["ranks"]
    counts = data["counts"]
    if not isinstance(counts, dict) or not counts.keys() <= ranks.keys():
        raise InputError(
            "histogram contains outcomes outside the declared complete alphabet"
        )
    h = {
        label: require_int(counts.get(label, 0), "outcome count")
        for label in sorted(ranks)
    }
    discarded = require_int(data.get("discarded", 0), "discarded trials")
    if sum(h.values()) + discarded != p["samples"]:
        raise InputError(
            "counts and discarded trials must account for the fixed sample size"
        )
    return h


def _window(counts, ranks, radius, g, scope):
    labels = sorted(ranks)
    region = HistogramRegion(
        [counts[i] for i in labels], [ranks[i] for i in labels], radius
    )
    interval, q = region.classical(g)
    classical = interval.strings()
    return (
        region,
        interval,
        {
            "scope": scope,
            "classical_st_R": classical,
            "window_st_R": {
                "lower": classical["lower"],
                "upper": classical["upper"] if scope == "classical_blocks" else None,
            },
            "least_kl_distribution": dict(zip(labels, map(str, q))),
        },
    )


def _decomposition(p, counts, radius, g, joint):
    product = p["measurement"]["product"]
    marginals = {}
    bounds = []
    for idx, axis in enumerate(product["axes"]):
        ranks = axis["ranks"]
        bins = {label: 0 for label in ranks}
        for label, n in counts.items():
            bins[product["coordinates"][label][idx]] += n
        _, interval, window = _window(bins, ranks, radius, g, "classical_blocks")
        marginals[axis["label"]] = {"counts": bins, **window}
        bounds.append(interval)
    a, b = bounds
    difference = joint - a - b
    cap = log2_interval(F(min(len(x["ranks"]) for x in product["axes"]))) / g
    corr = Interval(max(F(0), difference.lower), min(difference.upper, cap.upper))
    return {
        "marginals": marginals,
        "classical_correlation_st_R": corr.strings(),
        "quantum_mutual_information_lower_st_R": decimal_string(corr.lower),
    }


def _task_for(p, classes, model, eps):
    if model is None:
        return None, ["model"]
    if not isinstance(model, dict) or (
        model.get("dimension"),
        model.get("reference_id"),
        model.get("atomic_action_classes"),
    ) != (p["dimension"], p["reference_id"], classes):
        raise InputError(
            "process model reference, dimension or action classes differ from the acquisition"
        )
    raw = {
        "model": model,
        "target": {
            "id": p["state_id"],
            "epsilon": str(eps),
            "metric": "normalized_trace_distance",
        },
    }
    task = Task._parse(raw, allow_missing_qualifications=True)
    return task, sorted({"TC", "RA", "RCon"} - model.get("qualification", {}).keys())


def _process_points(p, classes, model, eps_values, region):
    points = []
    labels = sorted(p["measurement"]["ranks"])
    for eps in eps_values:
        task, missing = _task_for(p, classes, model, eps)
        info, z, indices = region.smooth_floor(eps)
        cost = None
        if "retention" in p:
            missing = ["process contract for leakage"]
        elif task is not None:
            _, _, inv, status, reason = _cost_terms(task, info, {}, "pvm")
            cost = {
                "lower_bound_slots": decimal_string(inv.lower),
                "integer_lower_bound_slots": ceil_fraction(inv.lower)
                if task.integer_cost
                else None,
                "numerical_status": status,
                "zero_reason": reason,
            }
        points.append(
            {
                "epsilon": str(eps),
                "smoothing_with_sampling": str(min(F(1), region.radius + eps)),
                "one_shot_lower_bits": decimal_string(info.lower),
                "cap_ratio_exact": str(z),
                "pooled_outcomes": [labels[i] for i in indices],
                "cost": cost,
                "task_fingerprint": task.fingerprint if cost is not None else None,
                "missing_process_premises": missing,
            }
        )
    return points


def _batch(entry, classes, g, models, eps_values):
    keys(entry, {"protocol", "data"}, "acquisition", {"coarse_windows"})
    frozen = prepare_pvm_protocol(entry["protocol"])
    p = frozen["protocol"]
    h = _histogram(p, frozen["protocol_sha256"], entry["data"])
    coarse = entry.get("coarse_windows", {})
    if not isinstance(coarse, dict) or len(coarse) > 256:
        raise InputError(
            "coarse_windows must map at most 256 named windows to partitions"
        )
    for name, partition in coarse.items():
        text(name, "coarse window")
        if name == p["measurement"]["window"]:
            raise InputError("coarse window duplicates the parent name")
        keys(partition, set(h), "complete coarse-graining map")
        for group in partition.values():
            text(group, "coarse label")
    n = sum(h.values())
    m = p["measurement"]
    identity = {
        "reference": p["reference_id"],
        "dimension": p["dimension"],
        "measurement": m,
        "atomic_action_classes": classes,
        "retained_branch": "retention" in p,
    }
    if "retention" in p:
        identity["projection_source"] = p["retention"]["source"]
    base = {
        "state_object": "normalized_projected_state"
        if "retention" in p
        else "target_state",
        "event_id": p["event_id"],
        "dataset_id": p["dataset_id"],
        "state_id": p["state_id"],
        "window_id": m["window"],
        "measurement_id": m["id"],
        "window_scope": m["window_scope"],
        "reference_id": p["reference_id"],
        "dimension": p["dimension"],
        "reference_weights_exact": {
            k: str(F(rank, p["dimension"])) for k, rank in m["ranks"].items()
        },
        "window_fingerprint": canonical_hash(identity),
        "protocol_sha256": frozen["protocol_sha256"],
        "origin": entry["data"]["origin"],
        "data_sha256": canonical_hash(entry["data"]),
        "counts": h,
        "analyzed_samples": n,
        "window": None,
        "coarse_windows": {},
        "product": None,
        "process": [],
        "retention": None,
    }
    events = [
        {
            "event_id": p["event_id"],
            "dataset_id": p["dataset_id"],
            "delta": p["delta"] if len(h) > 1 else "0",
            "method": "joint_tv_D32" if len(h) > 1 else "complete_single_outcome",
        }
    ]
    if "retention" in p:
        r = p["retention"]
        if r["method"] == "known":
            q = F(r["probability"])
            if (q == 0 and n > 0) or (q == 1 and n != p["samples"]):
                raise InputError(
                    "retained counts conflict with the deterministic retention probability"
                )
        else:
            limb = {**r, "samples": p["samples"]}
            q = sampling_endpoint(n, limb, "lower")
            events.append(
                {
                    "event_id": r["event_id"],
                    "dataset_id": p["dataset_id"],
                    "delta": r["delta"],
                    "method": r["method"],
                }
            )
        base["retention"] = {
            "retained": n,
            "discarded": p["samples"] - n,
            "probability_lower": str(q),
            "leakage_upper": str(1 - q),
            "discounted_state_lower_st_R": "0",
        }
    if n == 0:
        _task_for(p, classes, models.get(p["state_id"]), eps_values[0])
        if r["method"] == "known" and q == 0:
            base["retention"]["discounted_state_exact_st_R"] = "0"
        base["status"] = (
            "conditional_state_undefined"
            if r["method"] == "known" and q == 0
            else "no_retained_observations"
        )
        return base, events
    t = tv_radius(len(h), n, F(p["delta"]))
    region, interval, window = _window(h, m["ranks"], t, g, m["window_scope"])
    base.update(
        status="complete",
        tv_radius_upper=str(t),
        window=window,
        process=_process_points(
            p, classes, models.get(p["state_id"]), eps_values, region
        ),
    )
    for name, partition in coarse.items():
        bins = {}
        ranks = {}
        for label, group in partition.items():
            bins[group] = bins.get(group, 0) + h[label]
            ranks[group] = ranks.get(group, 0) + m["ranks"][label]
        _, _, w = _window(bins, ranks, t, g, "classical_blocks")
        base["coarse_windows"][name] = {"counts": bins, "ranks": ranks, **w}
    if "product" in m:
        base["product"] = _decomposition(p, h, t, g, interval)
    if base["retention"]:
        base["retention"]["discounted_state_lower_st_R"] = decimal_string(
            q * interval.lower
        )
    return base, events


def _window_difference_lower(left, right):
    """Lower bound on left minus right from the simultaneous window intervals."""
    if not left["window"] or not right["window"]:
        return None
    upper = right["window"]["window_st_R"]["upper"]
    if upper is None:
        return None
    return decimal_string(F(left["window"]["window_st_R"]["lower"]) - F(upper))


def analyze_pvm_windows(request, *, limits=None):
    limits = WorkflowLimits.from_value(limits)
    keys(
        request,
        {"schema", "schema_version", "atomic_action_classes", "batches", "tolerances"},
        "PVM window request",
        {"models", "comparisons"},
    )
    if (
        request["schema"] != REQUEST
        or type(request["schema_version"]) is not int
        or request["schema_version"] != 1
    ):
        raise InputError("unsupported PVM window schema")
    classes = require_int(request["atomic_action_classes"], "atomic action classes", 2)
    if classes.bit_length() > 256:
        raise BudgetError("atomic action class budget exceeded")
    g = log2_interval(F(classes))
    entries = _items(request["batches"], "PVM acquisitions", 64)
    eps = [
        probability(v, "trace-distance tolerance")
        for v in _items(request["tolerances"], "tolerances", 64)
    ]
    if len(set(eps)) != len(eps):
        raise InputError("tolerances must be distinct")
    models = request.get("models", {})
    if not isinstance(models, dict) or any(
        not isinstance(v, dict) for v in models.values()
    ):
        raise InputError("models must map target states to declarations")
    batches, ledger, combined = {}, {}, {}
    datasets = set()
    count = 0
    for entry in entries:
        # Each acquisition contributes one joint event to every derived window and tolerance.
        p = entry.get("protocol", {}) if isinstance(entry, dict) else {}
        extra = (
            3
            if isinstance(p, dict)
            and isinstance(p.get("measurement"), dict)
            and "product" in p["measurement"]
            else 0
        )
        if isinstance(entry, dict) and isinstance(entry.get("coarse_windows"), dict):
            extra += len(entry["coarse_windows"])
        count += 1 + extra
        check_size("windows", count, limits.max_windows)
        batch, events = _batch(entry, classes, g, models, eps)
        for e in events:
            if e["event_id"] in ledger:
                raise InputError(
                    "repeated acquisition event; reuse its batch for derived windows"
                )
            ledger[e["event_id"]] = e
        if batch["dataset_id"] in datasets:
            raise InputError(
                "distinct acquisitions require distinct dataset identities"
            )
        datasets.add(batch["dataset_id"])
        batches[batch["event_id"]] = batch
        for point in batch["process"]:
            if point["cost"] is not None:
                fingerprint = point["task_fingerprint"]
                old = combined.get(fingerprint)
                if old is None or F(point["cost"]["lower_bound_slots"]) > F(
                    old["cost"]["lower_bound_slots"]
                ):
                    combined[fingerprint] = {
                        "state_id": batch["state_id"],
                        "epsilon": point["epsilon"],
                        "cost": point["cost"],
                        "event_id": batch["event_id"],
                    }
    if not models.keys() <= {b["state_id"] for b in batches.values()}:
        raise InputError("model supplied for an unknown target")
    failure = sum((F(e["delta"]) for e in ledger.values()), F(0))
    if failure >= 1:
        raise InputError("combined failure budget must be below one")
    comparisons = []
    for pair in _items(request.get("comparisons", []), "comparisons", 256, 0):
        _items(pair, "comparison pair", 2, 2)
        if pair[0] == pair[1] or any(
            not isinstance(k, str) or k not in batches for k in pair
        ):
            raise InputError(
                "comparison requires two distinct declared acquisition events"
            )
        a, b = (batches[k] for k in pair)
        if a["window_fingerprint"] != b["window_fingerprint"]:
            raise InputError(
                "comparison requires a common window, measurement, reference and scale"
            )
        diff = _window_difference_lower(a, b)
        comparisons.append({"events": pair, "difference_lower_st_R": diff})
    return {
        "schema": RECORD,
        "schema_version": 1,
        "kind": KIND,
        "producer": {"name": "rcc-refcert", "version": __version__},
        "run_id": canonical_hash(request),
        "decision": "finite_sample_windows",
        **(
            {"computation_limits": limits.as_dict()}
            if limits != WorkflowLimits()
            else {}
        ),
        "atomic_action_classes": classes,
        "bandwidth_bits_per_slot": g.strings(),
        "analysis_state": "partial"
        if any(
            v["cost"]["numerical_status"] != "complete"
            for b in batches.values()
            for v in b["process"]
            if v["cost"] is not None
        )
        else "complete",
        "coverage": {"at_least": str(1 - failure), "events": list(ledger.values())},
        "batches": list(batches.values()),
        "comparisons": comparisons,
        "strongest_process_bounds": combined,
        "external_premises_verified": False,
    }
