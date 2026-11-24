"""Plan a fixed target acquisition before observing target counts."""

from fractions import Fraction

from .api import _cost_terms
from .binomial import CP, GRID, _tail_at_most, _upper_tail_parts
from .contracts import json_ready, keys
from .effects import (
    REQUEST,
    _qualified_task,
    arm_response,
    check_version,
    prepare_effect_protocol,
    probability,
)
from .information import fixed_effect_information, hoeffding_lower
from .scalar import BudgetError, InputError, decimal_string, rational, require_int

PLAN = "rcc-refcert.fixed-effect-plan"
MAX_PLAN_N = 1024


def _critical_hits(n, threshold, alpha, method, previous=None):
    """First k whose implemented conservative lower endpoint strictly exceeds p0."""
    if threshold >= 1:
        return n + 1
    if method != CP:
        radius = 1 - hoeffding_lower(n, n, alpha).lower
        return min(n + 1, int(n * (threshold + radius)) + 1)
    next_grid_point = Fraction(int(threshold * GRID) + 1, GRID)
    if previous is not None:
        # Adding one Bernoulli trial moves the critical count by zero or one.
        return (
            previous
            if _tail_at_most(n, previous, next_grid_point, alpha)
            else previous + 1
        )
    lo, hi = 0, n + 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if _tail_at_most(n, mid, next_grid_point, alpha):
            hi = mid
        else:
            lo = mid
    return hi


def _first_passing_grid(passes):
    """Return the smallest grid index accepted by a monotone predicate."""
    low, high = 0, GRID
    while high - low > 1:
        mid = (low + high) // 2
        if passes(Fraction(mid, GRID)):
            high = mid
        else:
            low = mid
    return high


def _power(n, minimum, maximum, p):
    if minimum > maximum:
        return Fraction(0)
    lo = Fraction(*_upper_tail_parts(n, minimum, p))
    hi = Fraction(*_upper_tail_parts(n, maximum + 1, p))
    return lo - hi


def plan_counts(request):
    """Design a fixed-N acquisition for a response or cost threshold."""
    keys(
        request,
        {
            "schema",
            "schema_version",
            "protocol",
            "goal",
            "expected_response",
            "power",
            "derivation",
        },
        "plan",
        {"task", "reference_data", "max_samples", "fixed_samples"},
    )
    check_version(request, PLAN)
    if ("fixed_samples" in request) == ("max_samples" in request):
        raise InputError("specify either fixed_samples or max_samples")
    fixed = "fixed_samples" in request
    n_limit = require_int(
        request["fixed_samples" if fixed else "max_samples"], "samples", 1
    )
    if n_limit > MAX_PLAN_N:
        raise BudgetError(f"exact power planning supports up to {MAX_PLAN_N} trials")
    if not isinstance(request["protocol"], dict) or not isinstance(
        request["protocol"].get("target"), dict
    ):
        raise InputError("plan requires a target sampling protocol")
    raw = json_ready(request["protocol"])
    if "samples" in raw["target"]:
        raise InputError(
            "supply target sample size through fixed_samples or max_samples"
        )
    raw["target"]["samples"] = 1
    frozen = prepare_effect_protocol(raw)
    p = frozen["protocol"]
    arm = p["target"]
    ref = p["reference"]
    if (ref["kind"] == "counts") != ("reference_data" in request):
        raise InputError(
            "supply the prior reference data exactly for a sampled reference"
        )
    ref_event = None
    if ref["kind"] == "counts":
        reference, ref_event = arm_response(
            ref,
            "reference",
            p["effect"],
            frozen["arm_sha256"]["reference"],
            request["reference_data"],
        )
    else:
        reference = rational(ref["response"])
    spec = keys(request["derivation"], {"smoothing_radius"}, "derivation", {"eta"})
    radius = probability(spec["smoothing_radius"], "smoothing radius")
    if "eta" in spec:
        probability(spec["eta"], "eta")
    task, missing, dimension = _qualified_task(request.get("task"), p, radius)
    target_power = probability(request["power"], "power")
    if target_power == 0:
        raise InputError("design power must be positive")
    expected = request["expected_response"]
    if not isinstance(expected, list):
        expected = [expected]
    if not 1 <= len(expected) <= 2:
        raise InputError(
            "expected_response requires a probability or a range of two endpoints"
        )
    alternatives = [probability(v, "expected response") for v in expected]
    if alternatives != sorted(alternatives):
        raise InputError("reversed expected-response range")
    goal = keys(request["goal"], set(), "goal", {"response_above", "cost_above_slots"})
    if len(goal) != 1:
        raise InputError("choose one response or cost goal")
    alpha = rational(arm["delta"])
    failure = alpha + (rational(ref["delta"]) if ref_event else 0)
    result = {
        "schema": "rcc-refcert.sampling-plan",
        "schema_version": 1,
        "goal": json_ready(goal),
        "design_request": json_ready(request),
        "target_power": str(target_power),
        "method": arm.get("method", "hoeffding"),
        "reference_upper_exact": str(reference) if reference is not None else None,
        "reference_event": ref_event,
        "joint_coverage_at_least_exact": str(1 - failure),
        "planned_protocol": None,
        "counts_request": None,
    }
    if reference is None:
        return {**result, "status": "empty_reference_readout_preimage"}
    ceiling = (
        min(Fraction(1), dimension * reference)
        if dimension is not None
        else Fraction(1)
    )
    if "response_above" in goal:
        threshold = probability(goal["response_above"], "response threshold")

        def passes(value):
            return value > threshold

        result["ideal_threshold_strict"] = str(threshold)
    else:
        if missing:
            raise InputError("cost planning requires a qualified process task")
        if reference == 0:
            return {**result, "status": "zero_reference_requires_support_assessment"}
        budget = rational(goal["cost_above_slots"], "cost budget")
        if budget < 0:
            raise InputError("cost budget must be nonnegative")

        def passes(value):
            info = fixed_effect_information(value, reference, radius)
            bound = _cost_terms(task, info, {}, "fixed_effect")[2].lower
            return Fraction(decimal_string(bound)) > budget

    if not passes(ceiling):
        return {**result, "status": "threshold_unreachable"}
    exact_trace = dimension is not None and ref["kind"] == "exact"
    # Applied to I-Q, the same uniform-support inequality also bounds its minimum response.
    floor = (
        max(Fraction(0), 1 - dimension * (1 - reference))
        if exact_trace
        else Fraction(0)
    )
    identity_effect = exact_trace and reference == 1
    if max(alternatives) > ceiling or min(alternatives) < floor:
        raise InputError(
            "expected response conflicts with the declared reference on ideal support"
        )
    cal = p["effect"].get("calibration", {})
    f, h = (
        rational(cal.get("false_positive", 0)),
        rational(cal.get("false_negative", 0)),
    )
    slope = 1 - f - h
    if slope == 0:
        return {**result, "status": "uninformative_readout"}
    offset = f if slope > 0 else 1 - f
    favourable = p["effect"]["accept" if slope > 0 else "reject"]
    if "response_above" in goal:
        threshold_obs = offset + abs(slope) * threshold
    else:

        def observed_passes(value):
            ideal = min(Fraction(1), max(Fraction(0), (value - offset) / abs(slope)))
            return passes(ideal)

        # CP uses this exact grid. For Hoeffding the grid locates the crossing;
        # we check the adjacent integer hit counts against the published cost.
        crossing = _first_passing_grid(observed_passes)
        threshold_obs = Fraction(crossing - 1, GRID)
        result["observed_cost_crossing_enclosure"] = [
            str(threshold_obs),
            str(Fraction(crossing, GRID)),
        ]
    cap_obs = offset + abs(slope) * ceiling
    probabilities = [offset + abs(slope) * v for v in alternatives]
    if any(v.denominator.bit_length() > 128 for v in probabilities):
        raise BudgetError(
            "exact power alternatives exceed the 128-bit denominator budget"
        )
    result["counted_outcome"] = favourable
    first = beyond = None
    for n in range(n_limit if fixed else 1, n_limit + 1):
        first = _critical_hits(n, threshold_obs, alpha, result["method"], first)
        if (
            "cost_above_slots" in goal
            and result["method"] != CP
            and first <= n
            and not observed_passes(hoeffding_lower(first, n, alpha).lower)
        ):
            first += 1
        beyond = _critical_hits(n, cap_obs, alpha, result["method"], beyond)
        # Binomial mass on a fixed consecutive set is unimodal in p;
        # the worst power over a closed interval is attained at an endpoint.
        passing_min = (
            max(first, n) if identity_effect and offset + abs(slope) == 1 else first
        )
        powers = [_power(n, passing_min, beyond - 1, v) for v in probabilities]
        if fixed or min(powers) >= target_power:
            break
    result.update(
        samples_evaluated_through=n,
        minimum_hits=passing_min,
        maximum_hits=beyond - 1,
        design_power_lower=decimal_string(min(powers), 16),
        sensitivity=[
            {"ideal_response": str(v), "power_lower": decimal_string(power, 16)}
            for v, power in zip(alternatives, powers)
        ],
    )
    if not fixed and min(powers) < target_power:
        return {**result, "status": "search_limit_reached"}
    arm["samples"] = n
    frozen = prepare_effect_protocol(p)
    # Counts and origin are deliberately blank until the target acquisition is complete.
    data = {
        "target": {
            "dataset_id": arm["dataset_id"],
            "arm_sha256": frozen["arm_sha256"]["target"],
            "origin": None,
            "counts": {p["effect"]["accept"]: None, p["effect"]["reject"]: None},
        }
    }
    if ref_event:
        data["reference"] = json_ready(request["reference_data"])

    follow = {
        "schema": REQUEST,
        "schema_version": 1,
        "protocol": p,
        "derivation": json_ready(spec),
        "data": data,
    }
    if "task" in request:
        follow["task"] = json_ready(request["task"])
    return {
        **result,
        "status": "power_met" if min(powers) >= target_power else "fixed_n_below_power",
        "samples": n,
        "minimum_over_all_smaller_n": not fixed,
        "planned_protocol": frozen,
        "counts_request": follow,
    }
