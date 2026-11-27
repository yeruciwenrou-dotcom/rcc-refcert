"""Three-qubit refresh/compression costs, measured polarization and correlations."""

from fractions import Fraction as F

from ..bounds.cli import load_template
from ..bounds.contracts import keys
from ..bounds.effects import binary_readout_preimage, probability
from ..bounds.information import hoeffding_lower, hoeffding_upper
from ..bounds.planning import plan_counts
from ..bounds.scalar import InputError, require_int
from .api import analyze_cost
from .presets import expand_preset, program
from .studies import acquisition, apportioned, window_batch, windows
from .templates import load_workflow_template

AXES = ["q1", "q2", "q3"]
WINDOW_ACTION_CLASSES = 3


def design(params, limits):
    keys(
        params,
        set(),
        "cooling parameters",
        {"bath", "cycles", "shots", "false_positive", "false_negative"},
    )
    p = probability(params.get("bath", "9/10"), "bath ground-state probability")
    cycles = require_int(params.get("cycles", 3), "cycles", 1)
    n = require_int(params.get("shots", 10000), "shots per acquisition", 1)
    fp = probability(params.get("false_positive", "1/50"), "false positive")
    fn = probability(params.get("false_negative", "1/25"), "false negative")
    if (
        not F(1, 2) < p < 1
        or cycles > 12
        or n > 10**12
        or p.denominator.bit_length() > 32
    ):
        raise InputError(
            "use 1 to 12 cycles, a bath probability in (1/2,1) with a 32-bit denominator and up to 10^12 shots"
        )
    params = {
        "bath": str(p),
        "cycles": cycles,
        "shots": n,
        "false_positive": str(fp),
        "false_negative": str(fn),
    }
    spec = {
        "preset": "algorithmic_cooling",
        "parameters": {"p": str(p), "cycles": cycles},
    }
    model, _, candidates, _ = expand_preset(spec, limits=limits)
    # The final refresh erases target-bath correlations. Keep the preceding compression as a separate preparation.
    stages = {item["id"]: item["action_names"] for item in candidates}
    stages["after-compression"] = stages["target-program"][:-2]
    entries, truth = {}, {}
    for name, actions in stages.items():
        state, syntax = model.initial, model.start
        for op in actions:
            action = model.lookup(syntax, op)
            state, syntax = model.apply(state, action), action["successor"]
        dist = {format(i, "03b"): x for i, x in enumerate(state)}
        truth[name] = {
            "complete_distribution": {k: str(v) for k, v in dist.items()},
            "polarization": str(2 * sum(state[:4]) - 1),
        }
        ident = f"bath-{p}/cycles-{cycles}/{name}"
        entries[name] = acquisition("ZZZ", ident, AXES, apportioned(dist, n), n)
        entries[name]["data"]["dataset_id"] = ident + "/ZZZ"
    target = entries["target-program"]["protocol"]["state_id"]
    ground = (F(truth["target-program"]["polarization"]) + 1) / 2
    obs = fp + (1 - fp - fn) * ground
    entries["calibrated"] = acquisition(
        "target ground-state flag",
        target,
        ["q1"],
        apportioned({"0": obs, "1": 1 - obs}, n),
        n,
        {"false_positive": str(fp), "false_negative": str(fn), "event": "recorded 0"},
    )
    return params, entries, {"model": spec, "stages": truth}


def cycle_prefixes(cycles, base_programs, limits):
    """Earlier complete cycles affordable alongside the two preset programs."""
    steps = sum(len(p["action_names"]) for p in base_programs)
    for count in range(cycles - 1):
        names = ["R"] + ["C", "R"] * count + ["H"]
        steps += len(names)
        elements = (len(base_programs) + count + 1) * (2 ** len(AXES))
        if steps > limits.max_candidate_steps or elements > limits.max_matrix_elements:
            break
        yield names


def analyze(params, entries, counts, control, eps, alpha, limits, *, record_version):
    cost_req = load_workflow_template("algorithmic-cooling")
    cost_req.update(
        model=control["model"],
        epsilon=str(eps),
        max_cost=max(32, 2 * params["cycles"] + 2),
    )
    if record_version == 2 and params["cycles"] >= 2:
        # Compare previously completed cycles of the same physical program.
        # These are model predictions; no extra measurement batch is needed.
        model, _, proposals, _ = expand_preset(control["model"], limits=limits)
        for count, names in enumerate(
            cycle_prefixes(params["cycles"], tuple(proposals), limits)
        ):
            proposals.append(program(model, names, name=f"cycle-prefix-{count}"))
        cost_req["candidates"] = proposals
    cost = analyze_cost(cost_req, limits=limits)
    candidates = {
        x["id"]: {
            k: x[k] for k in ("slots", "trace_distance_exact", "target_satisfied")
        }
        for x in cost["candidates"]
    }
    stage_names = list(control["stages"])
    delta = alpha / (1 + len(stage_names))
    pvm = windows(
        [
            window_batch(entries[k], counts[k], AXES, delta, product=True)
            for k in stage_names
        ],
        WINDOW_ACTION_CLASSES,
        eps,
        limits,
    )
    polar = {}
    for k, b in zip(stage_names, pvm["batches"]):
        n = b["analyzed_samples"]
        p0 = F(sum(v for s, v in counts[k].items() if s[0] == "0"), n)
        t = F(b["tv_radius_upper"])
        polar[k] = {
            "lower": str(2 * max(F(0), p0 - t) - 1),
            "upper": str(2 * min(F(1), p0 + t) - 1),
        }
    fp, fn = F(params["false_positive"]), F(params["false_negative"])
    k = counts["calibrated"].get("0", 0)
    n = params["shots"]
    # Two one-sided endpoints share the separate calibrated-readout allocation.
    lo = hoeffding_lower(k, n, delta / 2).lower
    hi = hoeffding_upper(k, n, delta / 2).upper
    interval = binary_readout_preimage(lo, hi, fp, fn)
    calibrated = {
        "event": entries["calibrated"]["data"]["dataset_id"],
        "delta": str(delta),
        "hits": k,
        "observed_interval": [str(lo), str(hi)],
        "status": "readout_conflict" if interval is None else "complete",
        "polarization_lower": None if interval is None else str(2 * interval[0] - 1),
        "polarization_upper": None if interval is None else str(2 * interval[1] - 1),
    }
    # A new, ideal target-qubit measurement. The rounded forecast is a design input.
    plan = load_template("sample-plan")
    plan["derivation"] = {"smoothing_radius": "0"}
    arm = plan["protocol"]["target"]
    arm.update(
        state_id=entries["target-program"]["protocol"]["state_id"],
        event_id="future-q1-lower",
        dataset_id="future-q1-shots",
        delta=str(alpha),
    )
    plan["protocol"]["reference"].update(
        state_id="uniform-C8",
        response="1/2",
        source="rank-four target-qubit event on I/8",
    )
    plan["protocol"]["effect"].update(
        id="q1-ground",
        setting="Ideal Z readout on q1 after the final refresh",
        readout="yes exactly for q1=0",
    )
    p0 = (F(control["stages"]["target-program"]["polarization"]) + 1) / 2
    plan["expected_response"] = str(F(int(100 * p0), 100))
    forecast = plan_counts(plan)
    return {
        "analysis_state": "partial"
        if cost["execution"]["state"] != "completed"
        else "complete",
        "analytic_control": control,
        "model_cost": cost["cost"],
        **(
            {
                "cost_search_stop": {
                    "stage": "cost_lower_bound",
                    "reason": cost["gain_bound"]["stop_reason"],
                    "updates": cost["gain_bound"]["updates"],
                    "max_dp_updates": limits.max_dp_updates,
                    "max_fraction_bits": limits.max_fraction_bits,
                }
            }
            if record_version == 2
            and cost.get("gain_bound")
            and not cost["gain_bound"]["completed"]
            else {}
        ),
        "candidates": candidates,
        "model_request": cost_req,
        "finite_windows": pvm,
        "observed_polarizations": polar,
        "calibrated": calibrated,
        "sampling_plan": forecast,
        "joint_coverage": str(1 - alpha),
    }
