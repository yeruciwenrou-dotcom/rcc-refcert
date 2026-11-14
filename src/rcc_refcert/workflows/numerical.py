"""Data-only finite-control model adapter and diagnostic program execution."""

from __future__ import annotations

import uuid
from fractions import Fraction

import numpy as np

from ..model import Action, FiniteControlModel, require_valid_model
from ..semantics import _apply_continue_action, _apply_halt_action
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
    layout,
    require_int,
    text,
)
from .states import StateInput, prepare_numeric_state


def _encoded_matrix(matrix):
    return [
        [[float(z.real), float(z.imag)] for z in row]
        for row in np.asarray(matrix, dtype=complex)
    ]


def serialize_numeric_model(
    model,
    *,
    subsystem_dims,
    subsystem_labels,
    reference,
    cost,
    tolerance=1e-10,
    limits=None,
):
    """Copy a FiniteControlModel into an editable matrix recipe without pickle."""
    limits = WorkflowLimits.from_value(limits)
    matrices = [model.reference_state, *model.initial_blocks.values()]
    matrices += [
        matrix
        for row in model.actions_by_syntax.values()
        for action in row
        for group in (action.continue_kraus, action.halt_kraus)
        for kraus in group.values()
        for matrix in kraus
    ]
    check_size(
        "serialized_model_matrix_elements",
        sum(np.size(m) for m in matrices),
        limits.max_matrix_elements,
    )
    doc = {
        "schema": "rcc-refcert.numeric-model",
        "schema_version": 2,
        "id": model.name,
        "subsystem_dims": list(subsystem_dims),
        "subsystem_labels": list(subsystem_labels),
        "basis_order": "tensor_msb_first",
        "reference": reference,
        "cost": cost,
        "validation_tolerance": tolerance,
        "control_dims": model.control_dims,
        "start_syntax": model.start_syntax,
        "initial_blocks": {
            k: _encoded_matrix(v) for k, v in model.initial_blocks.items()
        },
        "reference_state": _encoded_matrix(model.reference_state),
        "actions": {
            s: [
                {
                    "name": a.name,
                    "codeword": a.codeword,
                    "successor": a.successor,
                    "continue_kraus": [
                        {
                            "destination": destination,
                            "source": source,
                            "matrices": [_encoded_matrix(m) for m in ks],
                        }
                        for (source, destination), ks in sorted(
                            a.continue_kraus.items()
                        )
                    ],
                    "halt_kraus": [
                        {"source": q, "matrices": [_encoded_matrix(m) for m in ks]}
                        for q, ks in sorted(a.halt_kraus.items())
                    ],
                }
                for a in row
            ]
            for s, row in sorted(model.actions_by_syntax.items())
        },
    }
    parse_numeric_model(doc, limits=limits)
    return json_value(doc)


def parse_numeric_model(document, *, limits=None):
    limits = WorkflowLimits.from_value(limits)
    keys(
        document,
        {
            "schema",
            "schema_version",
            "id",
            "subsystem_dims",
            "subsystem_labels",
            "basis_order",
            "reference",
            "cost",
            "validation_tolerance",
            "control_dims",
            "start_syntax",
            "initial_blocks",
            "reference_state",
            "actions",
        },
        name="numeric model",
    )
    doc = json_value(document)
    if (
        doc["schema"] != "rcc-refcert.numeric-model"
        or type(doc["schema_version"]) is not int
        or doc["schema_version"] not in (1, 2)
        or doc["basis_order"] != "tensor_msb_first"
    ):
        raise InputError("numeric model: unsupported schema or tensor order")
    dims, labels, output_dim = layout(
        doc["subsystem_dims"], doc["subsystem_labels"], limits=limits
    )
    tol = doc["validation_tolerance"]
    if (
        isinstance(tol, bool)
        or not isinstance(tol, (int, float))
        or not 0 < tol <= 1e-3
    ):
        raise InputError(
            "validation_tolerance: require a finite positive number <= 0.001"
        )
    controls = doc["control_dims"]
    if not isinstance(controls, dict) or not controls or len(controls) > 256:
        raise InputError("control_dims: supply one to 256 control blocks")
    for name, size in controls.items():
        text(name, "control label")
        require_int(size, "control dimension", 1)
    check_size(
        "model_state_working_elements",
        6 * (output_dim**2 + sum(d * d for d in controls.values())),
        limits.max_matrix_elements,
    )
    budget = [0]

    def matrix(value, shape):
        count = shape[0] * shape[1]
        budget[0] += count
        check_size(
            "numeric_model_matrix_elements", budget[0], limits.max_matrix_elements
        )
        if (
            not isinstance(value, list)
            or len(value) != shape[0]
            or any(not isinstance(row, list) or len(row) != shape[1] for row in value)
        ):
            raise InputError("model matrix: shape mismatch")
        result = np.empty(shape, dtype=complex)
        for i, row in enumerate(value):
            for j, z in enumerate(row):
                if (
                    not isinstance(z, list)
                    or len(z) != 2
                    or any(
                        isinstance(v, bool)
                        or not isinstance(v, (int, float))
                        or not np.isfinite(v)
                        for v in z
                    )
                ):
                    raise InputError(
                        "model matrix: use finite [real, imaginary] entries"
                    )
                result[i, j] = complex(*z)
        return result

    if not isinstance(doc["initial_blocks"], dict) or set(doc["initial_blocks"]) - set(
        controls
    ):
        raise InputError("initial_blocks: unknown controls")
    initial = {
        q: matrix(v, (controls[q], controls[q]))
        for q, v in doc["initial_blocks"].items()
    }
    reference = matrix(doc["reference_state"], (output_dim, output_dim))
    actions = {}
    if not isinstance(doc["actions"], dict) or not 1 <= len(doc["actions"]) <= 1024:
        raise InputError("actions: supply one to 1024 syntax states")
    edge_count = 0
    for syntax, row in sorted(doc["actions"].items()):
        text(syntax, "syntax")
        if not isinstance(row, list) or not 1 <= len(row) <= 1024:
            raise InputError("actions: each syntax needs one to 1024 actions")
        edge_count += len(row)
        check_size("model_edges", edge_count, limits.max_dp_cells)
        entries = []
        for action in row:
            keys(
                action,
                {"name", "codeword", "successor", "continue_kraus", "halt_kraus"},
                name="action",
            )
            continuing, halting = {}, {}
            for field, target, continuation in (
                ("continue_kraus", continuing, True),
                ("halt_kraus", halting, False),
            ):
                if not isinstance(action[field], list):
                    raise InputError("Kraus groups: expected a list")
                for group in action[field]:
                    keys(
                        group,
                        {"source", "matrices", "destination"}
                        if continuation
                        else {"source", "matrices"},
                        name="Kraus group",
                    )
                    source = group["source"]
                    dest = group.get("destination")
                    if source not in controls or (
                        continuation and dest not in controls
                    ):
                        raise InputError("Kraus group: unknown control")
                    if continuation and source != dest and doc["schema_version"] == 1:
                        raise UnsupportedContract(
                            "numeric model schema 1: cross-control edge directions are "
                            "ambiguous; re-export the original FiniteControlModel with "
                            "the current serializer (schema 2), then rerun the task"
                        )
                    key = (source, dest) if continuation else source
                    if (
                        key in target
                        or not isinstance(group["matrices"], list)
                        or not group["matrices"]
                    ):
                        raise InputError(
                            "Kraus group: duplicate group or empty channel"
                        )
                    target[key] = tuple(
                        matrix(
                            m,
                            (
                                controls[dest] if continuation else output_dim,
                                controls[source],
                            ),
                        )
                        for m in group["matrices"]
                    )
            entries.append(
                Action(
                    action["name"],
                    action["codeword"],
                    action["successor"],
                    continuing,
                    halting,
                )
            )
        actions[syntax] = tuple(entries)
    cost = keys(
        doc["cost"],
        {
            "kind",
            "action_slots",
            "halt_slots",
            "initial_preparation",
            "auxiliary_systems",
            "output_rule",
        },
        name="cost",
    )
    if (
        cost["kind"] != "integer_atomic_slots"
        or type(cost["action_slots"]) is not int
        or cost["action_slots"] != 1
        or type(cost["halt_slots"]) is not int
        or cost["halt_slots"] != 1
        or cost["output_rule"] != "complete_unconditional_output"
    ):
        raise UnsupportedContract(
            "numeric cost: supported contract is one slot per action including halt, with complete unconditional output"
        )
    for field in ("initial_preparation", "auxiliary_systems", "output_rule"):
        text(cost[field], "cost." + field)
    ref = keys(doc["reference"], {"kind", "gamma", "source"}, name="reference")
    if ref["kind"] != "uniform_product_support" or exact(ref["gamma"]) < 2:
        raise UnsupportedContract(
            "numeric cost: declare a uniform product reference and Gamma >= 2"
        )
    text(ref["source"], "reference.source")
    if not np.allclose(reference, np.eye(output_dim) / output_dim, rtol=0, atol=tol):
        raise InputError(
            "reference_state differs from the declared uniform product reference"
        )
    model = FiniteControlModel(
        tuple(actions),
        controls,
        actions,
        doc["start_syntax"],
        initial,
        output_dim,
        reference,
        text(doc["id"], "model.id"),
    )
    require_valid_model(model, tol=tol)
    return doc, model, dims, labels


def normalize_numerical_request(request, *, limits=None):
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
        {"limits", "epsilon_values", "trajectory", "windows", "probe"},
        "numerical cost request",
    )
    original = json_value(request)
    if (
        request["schema"] != "rcc-refcert.workflow-request"
        or type(request["schema_version"]) is not int
        or request["schema_version"] != 1
        or request["kind"] != "cost_analysis"
        or request["mode"] != "numerical"
    ):
        raise InputError("numerical cost request: unsupported schema or mode")
    limits = WorkflowLimits.from_value(
        limits if limits is not None else request.get("limits")
    )
    doc, model, dims, labels = parse_numeric_model(request["model"], limits=limits)
    target = StateInput.from_dict(request["target"], limits=limits)
    if target.subsystem_dims != dims or target.subsystem_labels != labels:
        raise InputError("target: tensor dimensions and labels must match the model")
    epsilon = exact(request["epsilon"], "epsilon", limits=limits)
    if not 0 <= epsilon <= Fraction(1, 2):
        raise InputError("epsilon: require [0,1/2]")
    if not isinstance(request["candidates"], list) or len(request["candidates"]) > 256:
        raise InputError("candidates: supply at most 256 programs")
    if any(
        not isinstance(c, dict) or not isinstance(c.get("action_names"), list)
        for c in request["candidates"]
    ):
        raise InputError("candidates: provide complete action name lists")
    check_size(
        "total_candidate_steps",
        sum(len(c["action_names"]) for c in request["candidates"]),
        limits.max_candidate_steps,
    )
    check_size(
        "candidate_output_working_elements",
        6 * len(request["candidates"]) * model.output_dim**2,
        limits.max_matrix_elements,
    )
    if request.get("epsilon_values"):
        raise UnsupportedContract(
            "numerical cost: use separately identified requests for tolerance comparisons"
        )
    if type(request.get("trajectory", False)) is not bool:
        raise InputError("trajectory: expected true or false")
    require_int(request["max_cost"], "max_cost", 0)
    effective = {
        **original,
        "model": doc,
        "target": target.as_dict(),
        "epsilon": exact_text(epsilon),
        "limits": limits.as_dict(),
        "epsilon_values": [],
        "trajectory": request.get("trajectory", False),
    }
    core = {
        "model_digest": digest(doc),
        "target_digest": target.content_digest,
        "cost_digest": digest(doc["cost"]),
        "reference_digest": digest(doc["reference"]),
        "error_metric": "normalized_trace_distance",
        "basis_order": "tensor_msb_first",
    }
    return original, effective, model, target, limits, core


def _candidate_actions(model, raw):
    """Validate the declared word without executing its physical channels."""
    keys(raw, {"id", "action_names", "codeword", "source"}, name="candidate")
    text(raw["id"], "candidate.id")
    text(raw["source"], "candidate.source")
    names = raw["action_names"]
    if (
        not isinstance(names, list)
        or any(not isinstance(n, str) for n in names)
        or not isinstance(raw["codeword"], str)
    ):
        raise InputError("candidate: expected action name list and codeword string")
    syntax, bits, actions = model.start_syntax, "", []
    for name in names:
        if syntax is None:
            raise InputError("candidate: actions follow halt")
        lookup = {a.name: a for a in model.actions_by_syntax[syntax]}
        if name not in lookup:
            raise InputError("candidate: unknown action")
        action = lookup[name]
        actions.append(action)
        bits += action.codeword
        syntax = action.successor
    if not actions or syntax is not None or bits != raw["codeword"]:
        raise InputError(
            "candidate: complete matching codeword ending in halt required"
        )
    return actions


def _target_status(distance, epsilon, tolerance, target_check, output_check):
    margin = float(exact(epsilon)) - distance
    if (
        target_check["outcome"] != "pass"
        or output_check["outcome"] != "pass"
        or abs(margin) <= tolerance
    ):
        return "unresolved"
    return "within_tolerance" if margin > 0 else "outside_tolerance"


def _numerical_decision(target_check, candidates):
    unresolved = target_check["outcome"] != "pass" or any(
        c["legality"] == "pass" and c["numerical_target_status"] == "unresolved"
        for c in candidates
    )
    return "numerical_unresolved" if unresolved else "numerical_analysis"


def analyze_numerical_cost(request, *, limits=None):
    from .api import compose_interval, producer
    from .probes import check_probe_identity

    original, effective, model, target, limits, core = normalize_numerical_request(
        request, limits=limits
    )
    check_probe_identity(request.get("probe"))
    _, target_check = prepare_numeric_state(target, limits=limits)
    tol = effective["model"]["validation_tolerance"]
    policy = {"mode": "roundoff_only", "tolerance": tol, "repair_budget": tol}
    candidates = []
    partial = False
    remaining_states = limits.max_trajectory_states
    remaining_elements = limits.max_matrix_elements
    for raw in effective["candidates"]:
        keys(raw, {"id", "action_names", "codeword", "source"}, name="candidate")
        text(raw["id"], "candidate.id")
        text(raw["source"], "candidate.source")
        names = raw["action_names"]
        if (
            not isinstance(names, list)
            or any(not isinstance(n, str) for n in names)
            or not isinstance(raw["codeword"], str)
        ):
            raise InputError("candidate: expected action name list and codeword string")
        check_size("candidate_steps", len(names), limits.max_candidate_steps)
        result = {
            "id": raw["id"],
            "legality": "fail",
            "slots": None,
            "output": None,
            "trace_distance_exact": None,
            "trace_distance_numeric": None,
            "target_satisfied": None,
            "numerical_target_status": "unresolved",
            "evidence": "numerical",
            "model_digest": core["model_digest"],
            "target_digest": core["target_digest"],
            "error": None,
            "trajectory": [],
        }
        try:
            actions = _candidate_actions(model, raw)
        except InputError as exc:
            result["error"] = str(exc)
            candidates.append(result)
            continue
        blocks = {
            q: np.array(model.initial_blocks.get(q, np.zeros((d, d))), dtype=complex)
            for q, d in model.control_dims.items()
        }
        wants = effective["trajectory"] or bool(effective.get("windows"))
        can_record = (
            wants
            and len(names) + 1 <= remaining_states
            and 6 * (len(names) + 1) * model.output_dim**2 <= remaining_elements
            and len(blocks) == 1
            and next(iter(blocks.values())).shape
            == (model.output_dim, model.output_dim)
        )
        if can_record:
            remaining_states -= len(names) + 1
            remaining_elements -= 6 * (len(names) + 1) * model.output_dim**2
        if wants and not can_record:
            partial = True
            result["trajectory_status"] = (
                "resource_limited_or_incompatible_control_layout"
            )

        def state(matrix, source):
            return StateInput.numeric(
                matrix,
                target.subsystem_dims,
                target.subsystem_labels,
                policy=policy,
                source=source,
            ).as_dict()

        if can_record:
            result["trajectory"].append(
                {
                    "step": 0,
                    "action": None,
                    "slots": 0,
                    "state": state(
                        next(iter(blocks.values())), "numerical model initial state"
                    ),
                }
            )
        output = None
        for step, action in enumerate(actions, 1):
            if action.is_halt:
                output = _apply_halt_action(model, action, blocks)
            else:
                blocks = _apply_continue_action(model, action, blocks)
            if can_record:
                result["trajectory"].append(
                    {
                        "step": step,
                        "action": action.name,
                        "slots": step,
                        "state": state(
                            output if action.is_halt else next(iter(blocks.values())),
                            f"numerical candidate step {step}",
                        ),
                    }
                )
        output_state = StateInput.from_dict(
            state(output, "unweighted unconditional numerical output"), limits=limits
        )
        _, output_check = prepare_numeric_state(output_state, limits=limits)
        singular = np.linalg.svd(
            output - target.matrix(limits=limits), compute_uv=False
        )
        distance = float(singular.sum() / 2)
        numerical_status = _target_status(
            distance, effective["epsilon"], tol, target_check, output_check
        )
        result.update(
            legality="pass",
            slots=len(names),
            output=output_state.as_dict(),
            trace_distance_numeric=distance,
            distance_singular_values=singular.tolist(),
            numerical_target_status=numerical_status,
            output_diagnostics=output_check,
            comparison_tolerance=tol,
        )
        candidates.append(result)
    if len({c["id"] for c in candidates}) != len(candidates):
        raise InputError("candidate ids must be unique")
    cost = compose_interval(
        None, None, core_digest=digest(core), epsilon=effective["epsilon"]
    )
    decision = _numerical_decision(target_check, candidates)
    unresolved = decision == "numerical_unresolved"
    result = {
        "schema": "rcc-refcert.workflow-result",
        "schema_version": 1,
        "kind": "cost_analysis",
        "producer": producer(),
        "artifact_role": "author_analysis",
        "run_id": uuid.uuid4().hex,
        "original_request": original,
        "effective_request": effective,
        "digests": {"request": digest(effective), "task_core": digest(core), **core},
        "execution": {
            "state": "partial" if partial or unresolved else "completed",
            "reason": "numerical_evidence_unresolved"
            if unresolved
            else "optional_trajectory_unavailable"
            if partial
            else None,
        },
        "decision": decision,
        "evidence": {"candidates": "numerical", "model": "numerical_CPTP_checks"},
        "cost": cost,
        "gain_certificate": None,
        "gain_bound": None,
        "candidates": candidates,
        "epsilon_scan": [],
        "windows": None,
        "diagnostics": {
            "target": target_check,
            "strict_interval": "unavailable from numerical evidence",
        },
    }
    if effective.get("windows"):
        from .windows import attach_cost_windows

        attach_cost_windows(result, limits=limits)
    return result


def check_numerical_history(history, *, limits):
    from .api import compose_interval
    from .states import check_numeric_diagnostics
    from .windows import _close

    _, effective, model, target, limits, core = normalize_numerical_request(
        history["effective_request"], limits=limits
    )
    if history["digests"] != {
        "request": digest(history["effective_request"]),
        "task_core": digest(core),
        **core,
    }:
        raise InputError("history: numerical task binding mismatch")
    if history["cost"] != compose_interval(
        None, None, core_digest=digest(core), epsilon=effective["epsilon"]
    ):
        raise InputError("history: numerical evidence cannot assert strict endpoints")
    if len(history["candidates"]) != len(effective["candidates"]):
        raise InputError("history: numerical candidate count mismatch")
    target_check = check_numeric_diagnostics(
        target, history["diagnostics"]["target"], limits=limits
    )
    tol = effective["model"]["validation_tolerance"]
    if (
        history["gain_certificate"] is not None
        or history["gain_bound"] is not None
        or history["epsilon_scan"] != []
        or history["evidence"]
        != {"candidates": "numerical", "model": "numerical_CPTP_checks"}
    ):
        raise InputError("history: numerical evidence cannot assert exact proofs")
    for saved, raw in zip(history["candidates"], effective["candidates"]):
        if (
            saved["id"] != raw["id"]
            or saved["model_digest"] != core["model_digest"]
            or saved["target_digest"] != target.content_digest
            or saved["target_satisfied"] is not None
            or saved["trace_distance_exact"] is not None
            or saved["evidence"] != "numerical"
            or saved["legality"] not in {"pass", "fail"}
        ):
            raise InputError(
                "history: numerical candidate binding or evidence mismatch"
            )
        try:
            _candidate_actions(model, raw)
            error = None
        except InputError as exc:
            error = str(exc)
        if (
            saved["legality"] != ("pass" if error is None else "fail")
            or saved["error"] != error
        ):
            raise InputError("history: numerical candidate legality mismatch")
        if error is not None:
            if (
                any(
                    saved[k] is not None
                    for k in ("slots", "output", "trace_distance_numeric")
                )
                or saved["numerical_target_status"] != "unresolved"
                or saved["trajectory"] != []
            ):
                raise InputError("history: invalid candidate asserts an output")
        else:
            output = StateInput.from_dict(saved["output"], limits=limits)
            if (output.subsystem_dims, output.subsystem_labels) != (
                target.subsystem_dims,
                target.subsystem_labels,
            ):
                raise InputError("history: numerical output layout mismatch")
            if output.numeric_policy != {
                "mode": "roundoff_only",
                "tolerance": tol,
                "repair_budget": tol,
            }:
                raise InputError("history: numerical output policy mismatch")
            output_check = check_numeric_diagnostics(
                output, saved["output_diagnostics"], limits=limits
            )
            singular = np.linalg.svd(
                output.matrix(limits=limits) - target.matrix(limits=limits),
                compute_uv=False,
            )
            distance = float(singular.sum() / 2)
            if not _close(distance, saved["trace_distance_numeric"]) or saved[
                "slots"
            ] != len(raw["action_names"]):
                raise InputError("history: numerical distance or charged cost mismatch")
            if (
                saved["comparison_tolerance"] != tol
                or not _close(saved["distance_singular_values"], singular.tolist())
                or saved["numerical_target_status"]
                != _target_status(
                    distance, effective["epsilon"], tol, target_check, output_check
                )
            ):
                raise InputError(
                    "history: numerical target status or diagnostics mismatch"
                )
    decision = _numerical_decision(target_check, history["candidates"])
    if history["decision"] != decision:
        raise InputError(
            "history: numerical decision is inconsistent with its evidence"
        )
    if history["execution"]["state"] == "completed" and (
        decision == "numerical_unresolved"
        or any(c.get("trajectory_status") for c in history["candidates"])
    ):
        raise InputError("history: unresolved numerical analysis claims completion")
