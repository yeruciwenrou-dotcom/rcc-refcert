"""Complete program witnesses, charged atom by atom and checked at the target."""

from __future__ import annotations

from fractions import Fraction

from .core import BudgetError, InputError, check_size, exact_text, keys, text
from .states import StateInput


def evaluate_candidate(
    model, target, proposal, epsilon, *, trajectory=False, trajectory_budget=None
):
    keys(proposal, {"id", "action_names", "codeword", "source"}, name="candidate")
    name = text(proposal["id"], "candidate.id")
    text(proposal["source"], "candidate.source")
    names = proposal["action_names"]
    if not isinstance(names, (list, tuple)) or any(
        not isinstance(n, str) for n in names
    ):
        raise InputError("candidate.action_names: expected a list of action names")
    check_size("candidate_steps", len(names), model.limits.max_candidate_steps)
    if (
        not isinstance(proposal["codeword"], str)
        or len(proposal["codeword"]) > model.limits.max_candidate_steps * 1022
    ):
        raise InputError("candidate.codeword: expected a bounded binary string")
    result = {
        "id": name,
        "legality": "fail",
        "slots": None,
        "output": None,
        "trace_distance_exact": None,
        "target_satisfied": False,
        "evidence": "exact_rational",
        "model_digest": model.content_digest,
        "target_digest": target.content_digest,
        "error": None,
        "trajectory": [],
    }
    syntax, values, bits = model.start, model.initial, ""
    if trajectory_budget is None:
        trajectory_budget = {
            "states": model.limits.max_trajectory_states,
            "elements": model.limits.max_matrix_elements,
        }
    states_needed = len(names) + 1
    elements_needed = states_needed * model.dimension
    record_trajectory = (
        trajectory
        and states_needed <= trajectory_budget["states"]
        and elements_needed <= trajectory_budget["elements"]
    )
    if record_trajectory:
        trajectory_budget["states"] -= states_needed
        trajectory_budget["elements"] -= elements_needed
    if trajectory and not record_trajectory:
        result["trajectory_status"] = "resource_limited"
    if record_trajectory:
        result["trajectory"].append(
            {
                "step": 0,
                "action": None,
                "slots": 0,
                "state": StateInput.diagonal(
                    values, model.dims, model.labels, source="declared initial state"
                ).as_dict(),
            }
        )
    try:
        if not names:
            raise InputError("candidate: supply a complete action word ending in halt")
        for index, name in enumerate(names):
            if syntax is None:
                raise InputError("candidate: actions follow halt")
            action = model.lookup(syntax, name)
            values = model.apply(values, action)
            bits += action["codeword"]
            syntax = action["successor"]
            if record_trajectory:
                result["trajectory"].append(
                    {
                        "step": index + 1,
                        "action": name,
                        "slots": index + 1,
                        "state": StateInput.diagonal(
                            values,
                            model.dims,
                            model.labels,
                            source=f"candidate step {index + 1}",
                        ).as_dict(),
                    }
                )
        if syntax is not None:
            raise InputError("candidate: complete program must end in halt")
        if bits != proposal["codeword"]:
            raise InputError(
                "candidate.codeword: does not match the declared action sequence"
            )
    except BudgetError:
        raise
    except InputError as exc:
        result["error"] = str(exc)
        result["trajectory"] = []
        return result
    distance = sum((abs(a - b) for a, b in zip(values, target.data)), Fraction(0)) / 2
    output = StateInput.diagonal(
        values,
        model.dims,
        model.labels,
        source="complete unconditional candidate output",
    )
    result.update(
        legality="pass",
        slots=len(names),
        output=output.as_dict(),
        trace_distance_exact=exact_text(distance),
        target_satisfied=distance <= epsilon,
    )
    return result
