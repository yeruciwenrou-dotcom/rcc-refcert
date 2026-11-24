"""A two-color graph-state witness from the same target in two local bases."""

from fractions import Fraction as F

from ..bounds.api import _cost_terms
from ..bounds.contracts import Task, keys
from ..bounds.effects import probability
from ..bounds.information import fixed_effect_information, hoeffding_lower
from ..bounds.scalar import InputError, ceil_fraction, decimal_string, require_int
from .studies import acquisition, apportioned, window_batch, windows

EDGES = ((0, 1), (1, 2), (3, 4), (4, 5), (0, 3), (1, 4), (2, 5))
COLORS = {"A": (0, 2, 4), "B": (1, 3, 5)}
AXES = [f"q{i}" for i in range(6)]


def syndrome(bits, color):
    return tuple(
        (
            int(bits[i])
            + sum(int(bits[b if a == i else a]) for a, b in EDGES if i in (a, b))
        )
        % 2
        for i in COLORS[color]
    )


def design(params, limits):
    keys(params, set(), "cluster parameters", {"noise", "shots"})
    q = probability(params.get("noise", "1/20"), "local phase-flip probability")
    n = require_int(params.get("shots", 10000), "shots per color", 1)
    if q > F(1, 2) or 2 * n > 10**12:
        raise InputError(
            "use noise in [0,1/2] and at most 10^12 total shots per strategy"
        )
    state = f"cluster-2x3-phase-{q}"
    bits = [format(x, "06b") for x in range(64)]
    entries = {}
    for color, sites in COLORS.items():
        groups = {}
        for label in bits:
            groups.setdefault(syndrome(label, color), []).append(label)
        weights = {s: q ** sum(s) * (1 - q) ** (3 - sum(s)) for s in groups}
        syndromes = apportioned(weights, n)
        counts = {}
        for s, labels in groups.items():
            counts.update(
                apportioned(dict.fromkeys(labels, F(1, len(labels))), syndromes[s])
            )
        setting = "".join("X" if i in sites else "Z" for i in range(6))
        entries[color] = acquisition(setting, state, AXES, counts, n)
    entries["Z"] = acquisition(
        "ZZZZZZ", state, AXES, apportioned(dict.fromkeys(bits, F(1, 64)), 2 * n), 2 * n
    )
    return (
        {"noise": str(q), "shots": n},
        entries,
        {
            "ideal_color_probability": str((1 - q) ** 3),
            "ideal_graph_probability": str((1 - q) ** 6),
            "ideal_z_probability_per_outcome": "1/64",
        },
    )


def model_for(q):
    source = "docs/FINITE_DATA_STUDIES.md#cluster-model: balanced addressed resets, unital gates and first halt"
    return {
        "id": f"cluster-addressed-phase-{q}",
        "reference_id": "uniform-C64",
        "dimension": 64,
        "atomic_action_classes": 32,
        "transcription": {"mode": "exact", "a": "0", "gamma_bits": "0"},
        "reference_domination": {
            "upper_constant": "1",
            "source": source,
            "source_kind": "analytic_argument",
        },
        "reference_treatment": "ideal_support",
        "cost_domain": "integer_atomic_slots",
        "qualification": {
            name: {"basis": "analytic_argument_supplied", "source": source}
            for name in ("TC", "RA", "RCon")
        },
    }


def strongest_bounds(result):
    """Compare witnesses for the same task on explicitly simultaneous events."""
    routes = {
        name: (w["one_shot_bits_lower"], w["lower_slots"], w["integer_slots"])
        for name, w in result["witnesses"].items()
    }
    events = [e["id"] for e in result["color_events"]]

    def select(coverage):
        maximum = max(F(point[0]) for point in routes.values())
        winners = [name for name, point in routes.items() if F(point[0]) == maximum]
        bits, lower, slots = routes[winners[0]]
        return {
            "witnesses": winners,
            "one_shot_bits_lower": bits,
            "lower_slots": lower,
            "integer_slots": slots,
            "coverage_at_least": coverage,
            "events": list(events),
        }

    binary = select(result["strategy_coverage"])
    for name, profile in (
        ("color", result["color_windows"]),
        ("Z", result["z_windows"]),
    ):
        events.extend(e["event_id"] for e in profile["coverage"]["events"])
        for batch in profile["batches"]:
            point = batch["process"][0]
            cost = point["cost"]
            routes[f"{name} histogram ({batch['dataset_id']})"] = (
                point["one_shot_lower_bits"],
                cost["lower_bound_slots"] if cost is not None else None,
                cost["integer_lower_bound_slots"] if cost is not None else None,
            )
    return {
        "binary_colors": binary,
        "all_measurements": select(result["joint_coverage"]),
    }


def analyze(params, entries, counts, control, eps, alpha, limits):
    model = control.pop("process_model")
    state = entries["A"]["protocol"]["state_id"]
    task = (
        Task.from_dict(
            {
                "model": model,
                "target": {
                    "id": state,
                    "epsilon": str(eps),
                    "metric": "normalized_trace_distance",
                },
            }
        )
        if model
        else None
    )
    ledger, witnesses, endpoints = [], {}, {}

    def witness(p, rank, events):
        info = fixed_effect_information(p, F(rank, 64), eps)
        cost = _cost_terms(task, info, {}, "cluster")[2] if task else None
        return {
            "target_response_lower": str(p),
            "reference_response": str(F(rank, 64)),
            "one_shot_bits_lower": decimal_string(info.lower),
            "integer_slots": ceil_fraction(cost.lower) if cost else None,
            "lower_slots": decimal_string(cost.lower) if cost else None,
            "events": events,
        }

    for color in COLORS:
        n = params["shots"]
        hits = sum(v for b, v in counts[color].items() if not any(syndrome(b, color)))
        p = hoeffding_lower(hits, n, alpha / 2).lower
        event = entries[color]["data"]["dataset_id"] + "/color-Hoeffding"
        ledger.append(
            {
                "id": event,
                "delta": str(alpha / 2),
                "samples": n,
                "hits": hits,
                "color": color,
            }
        )
        endpoints[color] = p
        witnesses[color] = witness(p, 8, [event])
    witnesses["graph intersection"] = witness(
        max(F(0), sum(endpoints.values()) - 1), 1, [e["id"] for e in ledger]
    )
    pvm = [window_batch(entries[k], counts[k], AXES, alpha / 2) for k in COLORS]
    models = {state: model} if model else None
    # The q=0 readout has the same five-bit comparison scale; no process model is declared.
    color_windows = windows(pvm, 32, eps, limits, models)
    z = windows(
        [window_batch(entries["Z"], counts["Z"], AXES, alpha)], 32, eps, limits, models
    )
    return {
        "analysis_state": "complete",
        "reference_model": model,
        "model_evidence": {
            "initial_state": "I/64",
            "actions": {
                "addressed_resets_to_0_or_1": 12,
                "addressed_H": 6,
                "grid_CZ": 7,
                "addressed_phase_channels": 6,
                "first_halt": 1,
            },
            "phase_flip_probability": params["noise"],
            "slot_cost_per_action": 1,
            "code_bits_per_slot": 5,
            "reference_balance": "The two reset directions at each site sum to twice the uniform reference. All other continuing maps are unital.",
            "continuation_weight_on_reference": "31/32",
            "halt_weight_on_reference": "1/32",
            "program_semidensity": "sum from n=0 to infinity of (31/32)^n * (1/32) * I/64 = I/64",
        }
        if model
        else None,
        "analytic_control": control,
        "derived_effect": {
            "grid_edges": [list(e) for e in EDGES],
            "x_sites": {k: list(v) for k, v in COLORS.items()},
            "relation": "P_G = P_A P_B >= P_A + P_B - I",
            "ranks": [8, 8, 1],
        },
        "witnesses": witnesses,
        "color_events": ledger,
        "color_windows": color_windows,
        "z_windows": z,
        "z_control": {
            "bits_lower": z["batches"][0]["process"][0]["one_shot_lower_bits"]
        },
        "strategy_coverage": str(1 - alpha),
        "joint_coverage": str(1 - 3 * alpha),
        "budget_per_strategy": 2 * params["shots"],
        "target_scope": "same measured six-qubit preparation; model qualification applies as declared",
    }
