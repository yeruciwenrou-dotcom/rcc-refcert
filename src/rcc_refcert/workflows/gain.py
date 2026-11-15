"""Exact reference-envelope verification and finite-syntax budget exclusion."""

from __future__ import annotations

from fractions import Fraction

from .core import (
    BudgetError,
    InputError,
    check_fraction,
    check_size,
    exact,
    exact_text,
    keys,
    probabilities,
    require_int,
)


def domination(values, envelope):
    ratios = []
    for numerator, denominator in zip(values, envelope):
        if not denominator:
            if numerator:
                raise InputError(
                    "gain envelope: positive output lies outside the declared support"
                )
        else:
            ratios.append(numerator / denominator)
    return max(ratios, default=Fraction(0))


def verify_gain_certificate(model, proposal=None):
    """Recompute local inequalities from the recipe, independently of a preset."""
    proposal = proposal or {
        "envelopes": {
            s: [exact_text(v) for v in model.reference] for s in model.actions
        }
    }
    keys(
        proposal,
        {"envelopes"},
        {"initial_coefficient", "coefficients", "model_digest"},
        "gain certificate",
    )
    if proposal.get("model_digest", model.content_digest) != model.content_digest:
        raise InputError("gain certificate: model digest mismatch")
    raw = proposal["envelopes"]
    if not isinstance(raw, dict) or set(raw) != set(model.actions):
        raise InputError("gain certificate: provide an envelope for every syntax state")
    envelopes = {
        s: probabilities(v, model.dimension, name=f"envelope {s}", limits=model.limits)
        for s, v in raw.items()
    }
    initial_min = domination(model.initial, envelopes[model.start])
    initial = exact(
        proposal.get("initial_coefficient", initial_min),
        "initial coefficient",
        limits=model.limits,
    )
    if initial < initial_min:
        raise InputError("gain certificate: initial domination inequality fails")
    proposed = proposal.get("coefficients")
    if proposed is not None and (
        not isinstance(proposed, dict) or set(proposed) != set(model.actions)
    ):
        raise InputError("gain certificate: coefficient syntax states mismatch")
    coefficients, checks = {}, []
    for syntax, actions in model.actions.items():
        if proposed is not None and (
            not isinstance(proposed[syntax], dict)
            or set(proposed[syntax]) != {a["name"] for a in actions}
        ):
            raise InputError("gain certificate: coefficient action names mismatch")
        row = {}
        for action in actions:
            output = model.apply(envelopes[syntax], action)
            reference = (
                model.reference
                if action["successor"] is None
                else envelopes[action["successor"]]
            )
            minimum = check_fraction(
                domination(output, reference), "gain coefficient", model.limits
            )
            value = (
                minimum
                if proposed is None
                else exact(
                    proposed[syntax][action["name"]],
                    "gain coefficient",
                    limits=model.limits,
                )
            )
            if value < minimum:
                raise InputError(
                    f"gain certificate: domination inequality fails for {syntax}/{action['name']}"
                )
            row[action["name"]] = exact_text(value)
            checks.append(
                {
                    "syntax": syntax,
                    "action": action["name"],
                    "outcome": "pass",
                    "minimum_exact": exact_text(minimum),
                    "supplied_exact": exact_text(value),
                    "role": "halt" if action["successor"] is None else "continue",
                }
            )
        coefficients[syntax] = row
    return {
        "model_digest": model.content_digest,
        "envelopes": {s: [exact_text(v) for v in p] for s, p in envelopes.items()},
        "initial_coefficient": exact_text(initial),
        "coefficients": coefficients,
        "verification": {
            "outcome": "pass",
            "evidence": "exact_rational",
            "initial_minimum_exact": exact_text(initial_min),
            "checks": checks,
        },
        "scope": "unweighted physical action domination in this declared finite recipe",
    }


def spectral_threshold(values, epsilon, limits):
    """Exact normalized trace-distance spectral cap, with no entropy rounding."""
    epsilon = exact(epsilon, "epsilon", limits=limits)
    if not 0 <= epsilon <= Fraction(1, 2):
        raise InputError("epsilon: supported workflow range is [0,1/2]")
    d, cap, total = len(values), Fraction(1, len(values)), Fraction(0)
    for k, value in enumerate(sorted(values, reverse=True), 1):
        total = check_fraction(total + value, "spectral prefix", limits)
        cap = max(cap, (total - epsilon) / k)
    return check_fraction(d * cap, "spectral threshold", limits)


def exclude_budgets(model, certificate, threshold, max_cost):
    """Max-product DP over syntax states, including the charged halt edge."""
    limits = model.limits
    require_int(max_cost, "max_cost", 0)
    states = len(model.actions)
    check_size("dp_cells", (max_cost + 1) * states, limits.max_dp_cells)
    current = {model.start: exact(certificate["initial_coefficient"])}
    coefficients = {
        s: {a: exact(v) for a, v in row.items()}
        for s, row in certificate["coefficients"].items()
    }
    best, lower, updates = Fraction(0), 0, 0
    rows = [
        {
            "cost": 0,
            "terminated_max_exact": "0",
            "budget_max_exact": "0",
            "excluded": 0 < threshold,
        }
    ]
    if threshold > 0:
        lower = 1
    reason, complete = "requested_budget", True
    for cost in range(1, max_cost + 1):
        nxt, terminated = {}, Fraction(0)
        try:
            for syntax, value in current.items():
                for action in model.actions[syntax]:
                    if updates >= limits.max_dp_updates:
                        reason = "update_budget"
                        raise BudgetError("dynamic-program update budget reached")
                    updates += 1
                    product = check_fraction(
                        value * coefficients[syntax][action["name"]],
                        "dynamic-program product",
                        limits,
                    )
                    if action["successor"] is None:
                        terminated = max(terminated, product)
                    else:
                        successor = action["successor"]
                        nxt[successor] = max(nxt.get(successor, Fraction(0)), product)
        except BudgetError:
            reason = (
                "update_budget" if reason == "update_budget" else "arithmetic_budget"
            )
            complete = False
            break
        current = nxt
        best = max(best, terminated)
        excluded = best < threshold
        rows.append(
            {
                "cost": cost,
                "terminated_max_exact": exact_text(terminated),
                "budget_max_exact": exact_text(best),
                "excluded": excluded,
            }
        )
        if excluded:
            lower = cost + 1
        else:
            reason = "threshold_reached"
            break
        if not current:
            reason = "no_longer_programs"
            break
    return {
        "method": "exact_gain_budget",
        "evidence": "exact_rational",
        "threshold_exact": exact_text(threshold),
        "integer_lower_bound_slots": lower,
        "rows": rows,
        "updates": updates,
        "stop_reason": reason,
        "completed": complete,
        "interpretation": "Only budgets with maximum terminating gain strictly below the threshold are excluded.",
    }
