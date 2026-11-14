"""Task-level cost analysis with separately identified scientific evidence."""

from __future__ import annotations

import platform
import uuid
from copy import deepcopy
from fractions import Fraction

import numpy as np

from .._version import __version__
from ..metadata import source_revision_from_environment
from .candidates import evaluate_candidate
from .core import (
    InputError,
    UnsupportedContract,
    WorkflowLimits,
    check_size,
    digest,
    exact,
    exact_text,
    json_value,
    keys,
    mapping,
    require_supported,
    text,
)
from .gain import exclude_budgets, spectral_threshold, verify_gain_certificate
from .models import ExactModel
from .presets import expand_preset
from .states import StateInput


def producer():
    return {
        "name": "rcc-refcert",
        "version": __version__,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "source_revision": source_revision_from_environment(),
    }


def normalize_cost_request(request, *, limits=None):
    request = dict(request) if isinstance(request, dict) else request
    if isinstance(request, dict) and isinstance(request.get("target"), StateInput):
        request["target"] = request["target"].as_dict()
    keys(
        request,
        {
            "schema",
            "schema_version",
            "kind",
            "mode",
            "model",
            "target",
            "epsilon",
            "candidates",
            "max_cost",
        },
        {
            "gain_certificate",
            "limits",
            "epsilon_values",
            "trajectory",
            "windows",
            "probe",
        },
        "cost request",
    )
    original = json_value(request)
    require_supported(
        request["schema"], "rcc-refcert.workflow-request", "request.schema"
    )
    if type(request["schema_version"]) is not int or request["schema_version"] != 1:
        raise InputError("request.schema_version: expected 1")
    require_supported(request["kind"], "cost_analysis", "request.kind")
    if request["mode"] != "exact":
        raise UnsupportedContract(
            "cost mode: this entry currently requires an exact recipe"
        )
    limits = WorkflowLimits.from_value(
        limits if limits is not None else request.get("limits")
    )
    default_target = default_candidates = default_gain = None
    if isinstance(request["model"], dict) and "preset" in request["model"]:
        model, default_target, default_candidates, default_gain = expand_preset(
            request["model"], limits=limits
        )
    else:
        model = ExactModel(request["model"], limits=limits)
    target_spec = request["target"]
    if target_spec == "preset_default":
        if default_target is None:
            raise InputError("target: a full state is required for a custom recipe")
        target = default_target
    else:
        target = StateInput.from_dict(target_spec, limits=limits)
    if target.kind != "diagonal_exact":
        raise UnsupportedContract("exact cost: supply a complete exact diagonal target")
    if target.subsystem_dims != model.dims or target.subsystem_labels != model.labels:
        raise InputError(
            "target: tensor dimensions and physical labels must match the model"
        )
    candidates = request["candidates"]
    if candidates == "preset_defaults":
        if default_candidates is None:
            raise InputError("candidates: declare action words for the custom recipe")
        candidates = default_candidates
    if not isinstance(candidates, list) or len(candidates) > 256:
        raise InputError("candidates: expected a list of at most 256 complete programs")
    if any(not isinstance(c, dict) for c in candidates):
        raise InputError("candidates: every program must be an object")
    if len({c.get("id") for c in candidates}) != len(candidates):
        raise InputError("candidates: ids must be unique")
    if any(not isinstance(c.get("action_names"), list) for c in candidates):
        raise InputError("candidates: provide complete action name lists")
    check_size(
        "total_candidate_steps",
        sum(len(c["action_names"]) for c in candidates),
        limits.max_candidate_steps,
    )
    check_size(
        "candidate_output_elements",
        len(candidates) * model.dimension,
        limits.max_matrix_elements,
    )
    epsilon = exact(request["epsilon"], "epsilon", limits=limits)
    if not 0 <= epsilon <= Fraction(1, 2):
        raise InputError("epsilon: supported range is [0,1/2]")
    scan = request.get("epsilon_values", [])
    if not isinstance(scan, list) or len(scan) > 256:
        raise InputError("epsilon_values: supply at most 256 exact tolerances")
    scan = [exact(v, "epsilon_values", limits=limits) for v in scan]
    if any(not 0 <= e <= Fraction(1, 2) for e in scan):
        raise InputError("epsilon_values: all tolerances must lie in [0,1/2]")
    trajectory = request.get("trajectory", False)
    if type(trajectory) is not bool:
        raise InputError("trajectory: expected true or false")
    gain = request.get("gain_certificate", default_gain)
    effective = {
        **original,
        "model": model.document,
        "target": target.as_dict(),
        "candidates": json_value(candidates),
        "epsilon": exact_text(epsilon),
        "epsilon_values": [exact_text(e) for e in scan],
        "limits": limits.as_dict(),
        "trajectory": trajectory,
    }
    if gain is not None:
        effective["gain_certificate"] = json_value(gain)
    core = {
        "model_digest": model.content_digest,
        "target_digest": target.content_digest,
        "cost_digest": digest(model.document["cost"]),
        "reference_digest": digest(model.document["reference"]),
        "error_metric": "normalized_trace_distance",
        "basis_order": "tensor_msb_first",
    }
    return original, effective, model, target, gain, core


def compose_interval(
    lower,
    upper,
    *,
    core_digest,
    epsilon,
    epsilon_lower=None,
    epsilon_upper=None,
    lower_core=None,
    upper_core=None,
):
    """Combine strict endpoints only when task identities and tolerances agree."""
    e = exact(epsilon, "epsilon")
    el = e if epsilon_lower is None else exact(epsilon_lower, "epsilon_lower")
    eu = e if epsilon_upper is None else exact(epsilon_upper, "epsilon_upper")
    if not 0 <= eu <= e <= el <= Fraction(1, 2):
        raise InputError(
            "interval: require epsilon_upper <= epsilon <= epsilon_lower in [0,1/2]"
        )
    if lower_core not in (None, core_digest) or upper_core not in (None, core_digest):
        raise InputError("interval: endpoints refer to different complete tasks")
    for name, value in (("lower", lower), ("upper", upper)):
        if value is not None and (type(value) is not int or value < 0):
            raise InputError(f"interval.{name}: expected a nonnegative integer or null")
    if lower is None:
        decision = "numerical_analysis"
    elif upper is None:
        decision = "lower_bound_only"
    elif lower > upper:
        decision = "evidence_conflict"
    elif lower == upper:
        decision = "certified_optimal"
    else:
        decision = "certified_interval"
    valid = lower is not None and upper is not None and lower <= upper
    return {
        "decision": decision,
        "lower_bound_slots": lower,
        "upper_bound_slots": upper,
        "interval_slots": [lower, upper] if valid else None,
        "additive_overhead_upper": upper - lower if valid else None,
        "multiplicative_overhead_upper_exact": exact_text(Fraction(upper, lower))
        if valid and lower > 0
        else None,
        "epsilon_exact": exact_text(e),
        "task_core_digest": core_digest,
    }


def _point(
    model,
    target,
    certificate,
    candidates,
    epsilon,
    max_cost,
    core_digest,
    *,
    compact=False,
):
    q = spectral_threshold(target.data, epsilon, model.limits)
    bound = exclude_budgets(model, certificate, q, max_cost)
    witnesses = deepcopy(
        [
            {k: v for k, v in c.items() if k not in {"trajectory", "output"}}
            for c in candidates
        ]
        if compact
        else candidates
    )
    for result in witnesses:
        result["target_satisfied"] = (
            result["legality"] == "pass"
            and exact(result["trace_distance_exact"]) <= epsilon
        )
    upper = min((r["slots"] for r in witnesses if r["target_satisfied"]), default=None)
    cost = compose_interval(
        bound["integer_lower_bound_slots"],
        upper,
        core_digest=core_digest,
        epsilon=epsilon,
    )
    cost["lower_route"] = "exact_gain_budget"
    cost["upper_witness_ids"] = [
        r["id"] for r in witnesses if r["target_satisfied"] and r["slots"] == upper
    ]
    return cost, bound, witnesses


def analyze_cost(request, *, limits=None):
    """Analyze a complete task; a failed candidate is a valid scientific result."""
    mapping(request, "cost request")
    if isinstance(request, dict) and request.get("mode") == "numerical":
        from .numerical import analyze_numerical_cost

        return analyze_numerical_cost(request, limits=limits)
    from .probes import check_probe_identity

    check_probe_identity(request.get("probe"))
    original, effective, model, target, proposal, core = normalize_cost_request(
        request, limits=limits
    )
    certificate = verify_gain_certificate(model, proposal)
    effective["gain_certificate"] = {
        k: certificate[k]
        for k in ("model_digest", "envelopes", "initial_coefficient", "coefficients")
    }
    core_digest = digest(core)
    epsilon = exact(effective["epsilon"])
    trajectory_budget = {
        "states": model.limits.max_trajectory_states,
        "elements": model.limits.max_matrix_elements,
    }
    candidates = [
        evaluate_candidate(
            model,
            target,
            p,
            epsilon,
            trajectory=effective["trajectory"] or bool(effective.get("windows")),
            trajectory_budget=trajectory_budget,
        )
        for p in effective["candidates"]
    ]
    cost, bound, candidates = _point(
        model,
        target,
        certificate,
        candidates,
        epsilon,
        effective["max_cost"],
        core_digest,
    )
    partial = not bound["completed"] or any(
        r.get("trajectory_status") == "resource_limited" for r in candidates
    )
    result = {
        "schema": "rcc-refcert.workflow-result",
        "schema_version": 1,
        "kind": "cost_analysis",
        "producer": producer(),
        "source_revision": source_revision_from_environment(),
        "artifact_role": "author_analysis",
        "run_id": uuid.uuid4().hex,
        "original_request": original,
        "effective_request": effective,
        "digests": {"request": digest(effective), "task_core": core_digest, **core},
        "execution": {
            "state": "partial" if partial else "completed",
            "reason": "resource_limited" if partial else None,
        },
        "decision": cost["decision"],
        "evidence": {
            "gain": "exact_rational",
            "recipe": "analytic_recipe",
            "candidates": "exact_rational",
        },
        "cost": cost,
        "gain_certificate": certificate,
        "gain_bound": bound,
        "candidates": candidates,
        "epsilon_scan": [],
        "diagnostics": [],
        "windows": None,
    }
    for e in effective["epsilon_values"]:
        ecost, ebound, ewitnesses = _point(
            model,
            target,
            certificate,
            candidates,
            exact(e),
            effective["max_cost"],
            core_digest,
            compact=True,
        )
        point_request = {**effective, "epsilon": e, "epsilon_values": []}
        result["epsilon_scan"].append(
            {
                "request_digest": digest(point_request),
                "epsilon_exact": e,
                "cost": ecost,
                "gain_bound": ebound,
                "candidates": ewitnesses,
            }
        )
        if not ebound["completed"]:
            result["execution"] = {"state": "partial", "reason": "resource_limited"}
    if cost["decision"] == "evidence_conflict":
        result["execution"] = {"state": "partial", "reason": "evidence_conflict"}
    if effective.get("windows"):
        from .windows import attach_cost_windows

        attach_cost_windows(result, limits=model.limits)
    return result


def compare_cost_results(results, *, criterion=None):
    if not isinstance(results, (list, tuple)) or not results or len(results) > 256:
        raise InputError("comparison: supply one to 256 cost results")
    rows, groups = [], {}
    for result in results:
        mapping(result, "comparison result")
        if (
            result.get("schema") != "rcc-refcert.workflow-result"
            or result.get("kind") != "cost_analysis"
            or type(result.get("schema_version")) is not int
            or result["schema_version"] != 1
        ):
            raise InputError("comparison: expected cost workflow results")
        cost = mapping(result.get("cost"), "comparison cost")
        identity = mapping(result.get("digests"), "comparison digests")
        core = text(identity.get("task_core"), "comparison task identity")
        text(result.get("run_id"), "comparison run_id")
        required = {
            "lower_bound_slots",
            "upper_bound_slots",
            "epsilon_exact",
        }
        if not required <= cost.keys():
            raise InputError("comparison: cost endpoints or tolerance are missing")
        expected = compose_interval(
            cost["lower_bound_slots"],
            cost["upper_bound_slots"],
            core_digest=core,
            epsilon=cost["epsilon_exact"],
        )
        if any(k not in cost or cost[k] != v for k, v in expected.items()):
            raise InputError(
                "comparison: cost interval or task identity is inconsistent"
            )
        key = (core, cost["epsilon_exact"])
        groups.setdefault(key, []).append(result)
        rows.append({"run_id": result["run_id"], "task_core_digest": key[0], **cost})
    comparable = len(groups) == 1
    savings = []
    if comparable:
        feasible = [
            r
            for r in rows
            if r["upper_bound_slots"] is not None
            and r["decision"] in {"certified_interval", "certified_optimal"}
        ]
        if feasible:
            best = min(r["upper_bound_slots"] for r in feasible)
            savings = [
                {
                    "run_id": r["run_id"],
                    "slots_saved_by_best_candidate": r["upper_bound_slots"] - best,
                }
                for r in feasible
            ]
    if criterion is not None:
        keys(criterion, (), {"additive_gap", "multiplicative_factor"}, "criterion")
        if len(criterion) != 1:
            raise InputError(
                "criterion: select one additive_gap or multiplicative_factor"
            )
        name, raw = next(iter(criterion.items()))
        value = exact(raw, name)
        if value < (1 if name == "multiplicative_factor" else 0):
            raise InputError("criterion: threshold is below its meaningful minimum")
        for row in rows:
            measure = (
                row["additive_overhead_upper"]
                if name == "additive_gap"
                else row["multiplicative_overhead_upper_exact"]
            )
            row["meets_criterion"] = (
                None if measure is None else exact(measure) <= value
            )
    return {
        "schema": "rcc-refcert.cost-comparison",
        "schema_version": 1,
        "comparable_task": comparable,
        "rows": rows,
        "candidate_savings": savings,
        "criterion": json_value(criterion),
        "scope": "Comparison of the supplied result records; reverify shared bundles before relying on their evidence.",
    }
