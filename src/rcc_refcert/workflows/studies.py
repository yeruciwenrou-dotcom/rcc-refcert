"""Finite-data research tasks linking editable acquisitions to RCC calculations."""

from decimal import ROUND_CEILING
from fractions import Fraction as F

from .._version import __version__
from ..bounds.contracts import (
    COUNT_ORIGIN_LABELS,
    canonical_hash,
    json_ready,
    keys,
    text,
)
from ..bounds.effects import probability
from ..bounds.scalar import InputError, decimal_string, require_int
from .core import WorkflowLimits, digest, json_value
from .readouts import _positions, import_readout

REQUEST = "rcc-refcert.finite-study"
RECORD = "rcc-refcert.finite-study-record"
KIND = "finite_study"
EXAMPLE_COUNT_SOURCE = "Integer allocation of the analytic example probabilities"


def apportioned(weights, n):
    """Construct an integer example histogram by largest remainders."""
    mass = {k: F(v) * n for k, v in weights.items()}
    result = {k: int(v) for k, v in mass.items()}
    for k in sorted(mass, key=lambda k: result[k] - mass[k])[
        : n - sum(result.values())
    ]:
        result[k] += 1
    return result


def acquisition(setting, state, axes, counts, n, calibration=None):
    protocol = {
        "setting": setting,
        "state_id": state,
        "preparation_id": state,
        "samples": n,
        "sampling": "fixed_n_iid",
        "selection": "predeclared",
        "support": "no_leakage",
        "readout": calibration or "ideal",
        "layout": {
            "registers": [{"name": "meas", "bits_lsb_first": list(reversed(axes))}],
            "axes": axes,
        },
    }
    return {
        "protocol": protocol,
        "data": {
            "protocol_sha256": canonical_hash(protocol),
            "dataset_id": setting,
            "source": EXAMPLE_COUNT_SOURCE,
            "origin": "synthetic_fixture",
            "outcomes": {"counts": counts},
        },
    }


def prepare_study_protocol(protocol):
    """Bind the measured wires, setting, state, fixed trials and failure budget before acquisition."""
    keys(
        protocol,
        {
            "setting",
            "state_id",
            "preparation_id",
            "dataset_id",
            "samples",
            "sampling",
            "selection",
            "support",
            "readout",
            "layout",
            "failure_per_strategy",
        },
        "study protocol",
    )
    for key in ("setting", "state_id", "preparation_id", "dataset_id"):
        text(protocol[key], key)
    if (
        protocol["sampling"] != "fixed_n_iid"
        or protocol["selection"] != "predeclared"
        or protocol["support"] != "no_leakage"
    ):
        raise InputError(
            "use fixed-N IID sampling, a predeclared measurement and the declared full support"
        )
    require_int(protocol["samples"], "fixed trial count", 1)
    if (
        not 0
        < probability(protocol["failure_per_strategy"], "failure per strategy")
        < F(1, 3)
    ):
        raise InputError(
            "failure per strategy must lie strictly between zero and one third"
        )
    if protocol["readout"] != "ideal":
        r = keys(
            protocol["readout"],
            {"event", "false_positive", "false_negative"},
            "calibrated readout",
        )
        text(r["event"], "recorded event")
        for key in ("false_positive", "false_negative"):
            probability(r[key], key)
    _positions(protocol["layout"])
    p = json_ready(protocol)
    return {"protocol": p, "protocol_sha256": canonical_hash(p)}


def read_acquisition(entry, expected, seen):
    keys(entry, {"protocol", "data"}, "study acquisition")
    p, data = entry["protocol"], entry["data"]
    prepare_study_protocol(p)
    keys(p, set(expected), "study protocol")
    for k, value in expected.items():
        if k not in ("layout", "dataset_id", "preparation_id") and p[k] != value:
            raise InputError(f"{k}: acquisition differs from the declared study design")
    if not isinstance(data, dict) or p["dataset_id"] != data.get("dataset_id"):
        raise InputError("dataset identity differs from its acquisition protocol")
    if (
        not isinstance(p["layout"], dict)
        or p["layout"].get("axes") != expected["layout"]["axes"]
    ):
        raise InputError("the output axes must match the study's measured tensor order")
    keys(
        data,
        {"protocol_sha256", "dataset_id", "source", "origin", "outcomes"},
        "study data",
    )
    if data["protocol_sha256"] != canonical_hash(p):
        raise InputError("counts differ from their frozen acquisition")
    ident = text(data["dataset_id"], "dataset identity")
    if ident in seen:
        raise InputError(
            "each distinct preparation or measurement needs a distinct dataset identity"
        )
    seen.add(ident)
    text(data["source"], "measurement source")
    if data["origin"] not in ("observed_counts", "simulation", "synthetic_fixture"):
        raise InputError("declare the acquisition origin")
    hist = import_readout(data["outcomes"], p["layout"])
    if hist["samples"] != p["samples"]:
        raise InputError("histogram must account for the fixed sample size")
    return hist["counts"]


def window_batch(entry, counts, axes, delta, product=False):
    from .pvm import prepare_pvm_protocol

    design, data = entry["protocol"], entry["data"]
    n = len(axes)
    labels = [format(i, f"0{n}b") for i in range(2**n)]
    m = {
        "id": design["setting"],
        "setting": design["setting"],
        "ranks": dict.fromkeys(labels, 1),
        "readout": "ideal",
        "window": design["setting"],
        "window_scope": "classical_blocks",
        "source": "Complete product projectors with the archived measurement and tensor order",
    }
    if product:
        bath = sorted({s[1:] for s in labels})
        m["product"] = {
            "axes": [
                {"label": axes[0], "ranks": {"0": 1, "1": 1}},
                {"label": "bath", "ranks": dict.fromkeys(bath, 1)},
            ],
            "coordinates": {s: [s[0], s[1:]] for s in labels},
            "source": "Declared target qubit and joint two-qubit bath in tensor order",
        }
    p = {
        "event_id": data["dataset_id"] + "/TV",
        "dataset_id": data["dataset_id"],
        "state_id": design["state_id"],
        "reference_id": f"uniform-C{2**n}",
        "dimension": 2**n,
        "reference_treatment": "uniform_on_support",
        "support": "no_leakage",
        "measurement": m,
        "samples": design["samples"],
        "delta": str(delta),
        "sampling": "fixed_n_iid",
        "selection": "predeclared",
    }
    f = prepare_pvm_protocol(p)
    return {
        "protocol": f["protocol"],
        "data": {
            "protocol_sha256": f["protocol_sha256"],
            "dataset_id": data["dataset_id"],
            "origin": data["origin"],
            "counts": counts,
        },
    }


def windows(entries, classes, eps, limits, models=None):
    from .pvm import REQUEST as PVM
    from .pvm import analyze_pvm_windows

    req = {
        "schema": PVM,
        "schema_version": 1,
        "atomic_action_classes": classes,
        "batches": entries,
        "tolerances": [str(eps)],
        "models": models or {},
    }
    record = analyze_pvm_windows(req, limits=limits)
    return {
        k: record[k]
        for k in ("analysis_state", "coverage", "batches", "strongest_process_bounds")
    }


def _design(name, params, *, limits=None):
    if name == "cluster":
        from .study_cluster import analyze, design
    elif name == "cooling":
        from .study_cooling import analyze, design
    else:
        raise InputError("choose the cluster or cooling study")
    return design(params, limits), analyze


def study_template(name, *, failure="1/100", **parameters):
    """Generate editable synthetic acquisitions at a chosen noise, bath or shot budget."""
    (params, entries, _), _analyze = _design(name, parameters)
    failure = str(probability(failure, "failure per strategy"))
    for entry in entries.values():
        entry["protocol"]["dataset_id"] = entry["data"]["dataset_id"]
        entry["protocol"]["failure_per_strategy"] = failure
        entry["data"]["protocol_sha256"] = prepare_study_protocol(entry["protocol"])[
            "protocol_sha256"
        ]
    model = {}
    if name == "cluster":
        from .study_cluster import model_for

        model["process_model"] = (
            model_for(F(params["noise"])) if F(params["noise"]) else None
        )
    return {
        **model,
        "schema": REQUEST,
        "schema_version": 1,
        "study": name,
        "parameters": params,
        "epsilon": "1/20" if name == "cluster" else "1/50",
        "failure": failure,
        "acquisitions": entries,
    }


def source_bindings(entries):
    for entry in entries.values():
        if canonical_hash(entry["protocol"]) != entry["data"]["protocol_sha256"]:
            raise InputError(
                "archived raw counts differ from the specified acquisition"
            )
    return {
        k: {
            "preparation_id": e["protocol"]["preparation_id"],
            **{
                key: e["data"][key]
                for key in ("dataset_id", "origin", "source", "protocol_sha256")
            },
            "readout_sha256": digest(e["data"]["outcomes"]),
        }
        for k, e in entries.items()
    }


def analyze_study(request, *, limits=None):
    """Analyze raw acquisitions under the current finite-study result format."""
    return _analyze_study(request, limits=limits, record_version=2)


def _analyze_study(request, *, limits, record_version):
    keys(
        request,
        {
            "schema",
            "schema_version",
            "study",
            "parameters",
            "epsilon",
            "failure",
            "acquisitions",
        },
        "study request",
        {"process_model"},
    )
    if (
        request["schema"] != REQUEST
        or require_int(request["schema_version"], "schema version") != 1
    ):
        raise InputError("unsupported study request")
    eps = probability(request["epsilon"], "generation tolerance")
    alpha = probability(request["failure"], "failure per measurement strategy")
    if not 0 < alpha < F(1, 3):
        raise InputError(
            "failure per strategy must lie strictly between zero and one third"
        )
    limits = WorkflowLimits.from_value(limits)
    raw = json_value(request)
    (params, expected, control), analyze = _design(
        raw["study"], raw["parameters"], limits=limits
    )
    if raw["study"] == "cluster":
        from .study_cluster import model_for

        model = raw.get("process_model")
        if model is not None and (
            F(params["noise"]) == 0
            or canonical_hash(model) != canonical_hash(model_for(F(params["noise"])))
        ):
            raise InputError(
                "the cluster process model must match the declared noise and action classes"
            )
        control["process_model"] = model
    elif "process_model" in raw:
        raise InputError("cooling uses the declared exact refresh/compression model")
    entries = keys(raw["acquisitions"], set(expected), "measurement settings")
    for entry in expected.values():
        entry["protocol"]["dataset_id"] = entry["data"]["dataset_id"]
        entry["protocol"]["failure_per_strategy"] = str(alpha)
    seen = set()
    counts = {
        k: read_acquisition(entries[k], v["protocol"], seen)
        for k, v in expected.items()
    }
    shared = (
        ("A", "B", "Z")
        if raw["study"] == "cluster"
        else ("target-program", "calibrated")
    )
    for k in shared[1:]:
        first, other = entries[shared[0]], entries[k]
        if (first["protocol"]["preparation_id"], first["data"]["origin"]) != (
            other["protocol"]["preparation_id"],
            other["data"]["origin"],
        ):
            raise InputError(
                "measurements of one physical preparation require the same preparation identity and data origin"
            )
    if raw["study"] == "cooling":
        result = analyze(
            params,
            entries,
            counts,
            control,
            eps,
            alpha,
            limits,
            record_version=record_version,
        )
    else:
        result = analyze(params, entries, counts, control, eps, alpha, limits)
        if record_version == 2:
            from .study_cluster import strongest_bounds

            result["strongest_bounds"] = strongest_bounds(result)
    return {
        "schema": RECORD,
        "schema_version": record_version,
        "kind": KIND,
        "run_id": digest(raw),
        "producer": {"name": "rcc-refcert", "version": __version__},
        "decision": raw["study"],
        "analysis_state": result.pop("analysis_state"),
        "parameters": params,
        "epsilon": str(eps),
        "sources": source_bindings(entries),
        **(
            {"computation_limits": limits.as_dict()}
            if limits != WorkflowLimits()
            else {}
        ),
        **result,
    }


_STUDY_LABELS = {
    "A": "Color A",
    "B": "Color B",
    "Z": "Z-basis control",
    "target-program": "Full target program",
    "after-compression": "After the last compression",
    "calibrated": "Calibrated final readout",
}


def _percent(value):
    return decimal_string(100 * F(value), 6) + "%"


def _slots(value):
    return f"{value} slot" if value == 1 else f"{value} slots"


def _cluster_lines(r):
    from .study_cluster import strongest_bounds

    summary = r.get("strongest_bounds") or strongest_bounds(r)
    binary = summary["binary_colors"]
    combined = summary["all_measurements"]

    def names(point):
        return ", ".join(_STUDY_LABELS.get(k, k) for k in point["witnesses"])

    bits = decimal_string(F(binary["one_shot_bits_lower"]), 9)
    slots = binary["integer_slots"]
    coverage = _percent(binary["coverage_at_least"])
    evidence = (
        f"The strongest one-shot information lower bound is {bits} bits ({names(binary)}), "
        f"with at least {coverage} joint coverage under fixed-size IID sampling."
    )
    if slots is None:
        lead = f"The binary color tests bound the measured state's information at smoothing radius {r['epsilon']}."
    elif slots == 0:
        lead = f"The binary color tests leave the preparation-cost lower bound at zero in model {r['reference_model']['id']} at tolerance {r['epsilon']}."
    else:
        lead = (
            f"The binary color tests certify a preparation cost of at least {_slots(slots)} "
            f"in model {r['reference_model']['id']} at trace-distance tolerance {r['epsilon']}."
        )
    lines = [f"{lead} {evidence}"]
    if slots is None:
        lines.append(
            "To translate this state bound into a preparation cost, supply a model in the fixed-effect or window workflow."
        )
    else:
        lines.append(
            f"The model counts {r['reference_model']['atomic_action_classes']} atomic action classes, including halt."
        )
    for name, witness in r["witnesses"].items():
        value = decimal_string(F(witness["one_shot_bits_lower"]), 9)
        label = _STUDY_LABELS.get(name, "The graph intersection")
        line = f"{label} gives a one-shot information lower bound of {value} bits"
        if witness["integer_slots"] is not None:
            line += f" and a cost lower bound of {_slots(witness['integer_slots'])}"
        lines.append(line + ".")
    if F(binary["one_shot_bits_lower"]) == 0:
        a, b = (r["witnesses"][k] for k in ("A", "B"))
        lines.append(
            f"The color acceptance lower endpoints are {decimal_string(F(a['target_response_lower']), 6)} and "
            f"{decimal_string(F(b['target_response_lower']), 6)}. After smoothing at radius {r['epsilon']}, "
            "these measurements do not resolve a positive excess over the reference responses of 1/8 for each color and 1/64 for the intersection."
        )
    z = F(r["z_control"]["bits_lower"])
    lines.append(
        "The color settings test stabilizer parities. From the computational-basis populations, "
        f"the Z-basis control gives a one-shot information lower bound of {decimal_string(z, 9)} bits at this tolerance."
    )
    all_bits = decimal_string(F(combined["one_shot_bits_lower"]), 9)
    all_cost = combined["integer_slots"]
    cost_text = (
        f", corresponding to a preparation-cost lower bound of {_slots(all_cost)}"
        if all_cost is not None
        else ""
    )
    lines.append(
        f"Including the full color and Z histograms, the strongest information lower bound is {all_bits} bits "
        f"({names(combined)}){cost_text}. Joint coverage across these measurements is at least {_percent(combined['coverage_at_least'])}."
    )
    return lines


def _cooling_interval(lower, upper):
    # Round outward so that the printed interval still contains the certified one.
    return (
        f"[{decimal_string(F(lower), 6)}, {decimal_string(F(upper), 6, ROUND_CEILING)}]"
    )


def _cooling_lines(r, *, details):
    cost = r["model_cost"]
    if cost["decision"] == "certified_optimal":
        lead = f"The optimal cost of the complete model target is {_slots(cost['lower_bound_slots'])}"
    elif cost["interval_slots"] is not None:
        low, high = cost["interval_slots"]
        lead = f"The complete model target costs between {low} and {high} slots"
    else:
        lead = f"The cost of the complete model target is unresolved ({cost['decision'].replace('_', ' ')})"
    lines = [
        f"{lead} within trace-distance tolerance {r['epsilon']}. Each program includes one halt slot."
    ]
    winners = cost["upper_witness_ids"]
    for name in sorted(r["candidates"], key=lambda key: (key not in winners, key)):
        program = r["candidates"][name]
        if name.startswith("cycle-prefix-"):
            if name not in winners:
                continue
            subject = f"The {name.removeprefix('cycle-prefix-')}-cycle program"
        elif name == "shorter-program":
            subject = f"The {r['parameters']['cycles'] - 1}-cycle program"
        else:
            subject = "The full target program"
        distance = program["trace_distance_exact"]
        if F(distance) == 0:
            lines.append(
                f"{subject} prepares the target exactly in {_slots(program['slots'])}."
            )
        else:
            verdict = "within" if program["target_satisfied"] else "outside"
            approx = decimal_string(F(distance), 6)
            reading = approx if F(approx) == F(distance) else f"about {approx}"
            if details:
                reading += f", exact value {distance}"
            lines.append(
                f"{subject} costs {_slots(program['slots'])} and finishes {verdict} tolerance (trace distance {reading})."
            )
    from .pvm_render import window_scale_line
    from .study_cooling import WINDOW_ACTION_CLASSES

    first_batch = r["finite_windows"]["batches"][0]
    lines.append(
        f"Classical joint Z window on the target and bath, uniform reference "
        f"{first_batch['reference_id']} (support dimension {first_batch['dimension']})."
    )
    lines.append(window_scale_line(WINDOW_ACTION_CLASSES))
    batches = {b["dataset_id"]: b for b in r["finite_windows"]["batches"]}
    stages = {
        "shorter-program": f"After the {r['parameters']['cycles'] - 1}-cycle program",
        "after-compression": "After the last compression",
        "target-program": "After the full target program",
    }
    lines.append(
        "In the model the final refresh preserves target-qubit polarization. "
        "It replaces the bath and removes its correlations with the target."
    )
    for name, stage in stages.items():
        point = r["observed_polarizations"][name]
        batch = batches[r["sources"][name]["dataset_id"]]
        product = batch["product"]
        correlation = product["classical_correlation_st_R"]
        lines.append(
            f"{stage}, target-qubit polarization lies in {_cooling_interval(point['lower'], point['upper'])} "
            f"and classical target-bath correlations contribute {_cooling_interval(correlation['lower'], correlation['upper'])} st_R to the measured window."
        )
        windows = {
            "target q1": product["marginals"]["q1"]["window_st_R"],
            "bath": product["marginals"]["bath"]["window_st_R"],
            "joint": batch["window"]["window_st_R"],
        }
        lines.append(
            "  Measured RCC (st_R): "
            + ", ".join(
                f"{label} {_cooling_interval(v['lower'], v['upper'])}"
                for label, v in windows.items()
            )
            + "."
        )
    calibrated = r["calibrated"]["polarization_lower"]
    if calibrated is None:
        lines.append(
            "The declared detector errors are incompatible with the observed interval for the calibrated readout."
        )
    else:
        lines.append(
            f"The calibrated readout bounds final target-qubit polarization from below by {decimal_string(F(calibrated), 6)}."
        )
    lines.append(
        f"The recorded measurements have joint sampling coverage of at least {_percent(r['joint_coverage'])} under fixed-size IID sampling."
    )
    plan = r["sampling_plan"]
    goal = plan["goal"]["response_above"]
    power = _percent(plan["target_power"])
    forecast = plan["design_request"]["expected_response"]
    if plan["status"] == "power_met":
        lines.append(
            f"For a new ideal target-qubit measurement, at least {plan['minimum_hits']} ground-state outcomes in {plan['samples']} shots "
            f"certify a ground-state probability above {goal} with {_percent(plan['joint_coverage_at_least_exact'])} confidence."
        )
        lines.append(
            f"The design reaches the requested power of {power} at the forecast ground-state probability {forecast}."
        )
    else:
        lines.append(
            f"For a new ideal target-qubit measurement, no sample size through {plan['samples_evaluated_through']} shots "
            f"reaches power {power} to certify a ground-state probability above {goal} at the forecast {forecast}."
        )
    return lines


def render_study(r, *, markdown=False, details=False):
    cluster = r["decision"] == "cluster"
    title = "Six-qubit cluster state" if cluster else "Three-qubit algorithmic cooling"
    findings = _cluster_lines(r) if cluster else _cooling_lines(r, details=details)
    lines = [("# " if markdown else "") + title, findings[0]]
    labels = _STUDY_LABELS.copy()
    if not cluster:
        labels["shorter-program"] = f"The {r['parameters']['cycles'] - 1}-cycle program"
    origins = {}
    for key, source in r["sources"].items():
        origins.setdefault(source["origin"], []).append(labels[key])
    for origin, settings in origins.items():
        label = COUNT_ORIGIN_LABELS[origin]
        if origin == "synthetic_fixture" and all(
            source["source"] == EXAMPLE_COUNT_SOURCE
            for source in r["sources"].values()
            if source["origin"] == origin
        ):
            label += " generated from the analytic probabilities"
        if len(origins) == 1:
            lines.append(f"This analysis uses {label}.")
        else:
            lines.append(f"{', '.join(settings)}: {label}.")
    lines.extend(findings[1:])
    if r["analysis_state"] == "partial":
        stop = r.get("cost_search_stop")
        if stop and stop["reason"] == "update_budget":
            lines.append(
                f"Partial analysis. The cost lower-bound search reached its limit of {stop['max_dp_updates']} updates. "
                "Rerun study analyze on the original request with a larger --max-dp-updates value."
            )
        elif stop and stop["reason"] == "arithmetic_budget":
            lines.append(
                f"Partial analysis. The cost lower-bound search reached the {stop['max_fraction_bits']}-bit arithmetic limit. "
                "Rerun analyze_study on the original request with a larger max_fraction_bits limit."
            )
        else:
            lines.append("Partial analysis. The computation budget was reached.")
    if details:
        for key, source in r["sources"].items():
            lines.extend(
                [
                    f"{labels[key]} used dataset {source['dataset_id']} from preparation {source['preparation_id']}.",
                    f"Source: {source['source']}",
                    f"Protocol SHA-256: {source['protocol_sha256']}",
                    f"Raw readout SHA-256: {source['readout_sha256']}",
                ]
            )
        lines.append(f"Run: {r['run_id']}")
    return ("\n\n" if markdown else "\n").join(lines) + "\n"
