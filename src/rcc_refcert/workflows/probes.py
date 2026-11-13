"""Versioned, editable research questions backed by runnable state inputs."""

from __future__ import annotations

import json
import math
from importlib.resources import files

import numpy as np

from .core import (
    InputError,
    WorkflowLimits,
    digest,
    exact,
    exact_text,
    keys,
    require_int,
)
from .states import StateInput
from .templates import load_workflow_template

POLICY = {"mode": "roundoff_only", "tolerance": 1e-10, "repair_budget": 1e-10}


def list_probes():
    catalog = json.loads(
        files(__package__).joinpath("data/probes.json").read_text(encoding="utf-8")
    )
    return [
        {k: entry[k] for k in ("probe_id", "revision", "title", "research_question")}
        for entry in catalog
    ]


def load_probe(probe_id):
    catalog = json.loads(
        files(__package__).joinpath("data/probes.json").read_text(encoding="utf-8")
    )
    for entry in catalog:
        if entry["probe_id"] == probe_id:
            return entry
    raise InputError("probe_id: choose an installed probe from probe list")


def _binary_entropy(p):
    return -sum(v * math.log2(v) for v in (p, 1 - p) if v > 0)


def _dephase(rho, axis, probability):
    signs = np.array([(-1) ** ((i >> (3 - axis)) & 1) for i in range(16)])
    return (1 - probability) * rho + probability * signs[:, None] * rho * signs[None, :]


def export_probe(probe_id, *, parameters=None):
    entry = load_probe(probe_id)
    params = {**entry["parameter_defaults"], **(parameters or {})}
    keys(params, entry["parameter_defaults"], name="probe parameters")
    if probe_id == "w3-cooling-trajectory":
        request = load_workflow_template("algorithmic-cooling")
        request["model"]["parameters"] = params
        request["trajectory"] = True
        request["windows"] = {
            "windows": [
                {"id": "target", "keep": ["q1"]},
                {"id": "bath", "keep": ["q2", "q3"]},
            ],
            "partition": {"left": ["q1"], "right": ["q2", "q3"]},
        }
        from .api import normalize_cost_request

        _, request, _, _, _, _ = normalize_cost_request(request)
    else:
        gamma = require_int(params["gamma"], "gamma", 2)
        bell = np.array([1, 0, 0, 1], dtype=complex) / math.sqrt(2)
        vector = np.kron(bell, bell)
        paired = np.outer(vector, vector.conj())
        origin = {"source": entry["data_origin"]}
        if probe_id == "w1-quantum-organization":
            mixing = exact(params["mixing"], "mixing")
            if not 0 <= mixing <= 1:
                raise InputError("mixing: require a value in [0,1]")
            vector = np.zeros(16, dtype=complex)
            vector[0] = vector[-1] = 1 / math.sqrt(2)
            ghz = np.outer(vector, vector.conj())
            states = [("paired-bell", paired), ("ghz", ghz)]
            states = [
                (name, (1 - float(mixing)) * rho + float(mixing) * np.eye(16) / 16)
                for name, rho in states
            ]
            params["mixing"] = exact_text(mixing)
        else:
            alpha = exact(
                params["concentrated_probability"], "concentrated_probability"
            )
            if not 0 <= alpha <= 0.5:
                raise InputError("concentrated_probability: require a value in [0,1/2]")
            target = _binary_entropy(float(alpha)) / 2
            low, high = 0.0, 0.5
            for _ in range(60):
                middle = (low + high) / 2
                if _binary_entropy(middle) < target:
                    low = middle
                else:
                    high = middle
            q = (low + high) / 2
            origin.update(
                distributed_probability=q,
                root_entropy_residual=_binary_entropy(q) - target,
                root_method="60-step bisection on [0,1/2] in binary64",
            )
            states = [
                ("concentrated", _dephase(paired, 0, float(alpha))),
                ("distributed", _dephase(_dephase(paired, 0, q), 2, q)),
            ]
            params["concentrated_probability"] = exact_text(alpha)
        records = []
        for name, matrix in states:
            state = StateInput.numeric(
                matrix, (2, 2, 2, 2), ("q1", "q2", "q3", "q4"), policy=POLICY
            )
            body = state.as_dict()
            body["provenance"] = {**origin, "parameters": params}
            records.append({"id": name, "state": body})
        request = {
            "schema": "rcc-refcert.workflow-request",
            "schema_version": 1,
            "kind": "window_analysis",
            "states": records,
            "reference": {
                "kind": "uniform_product_support",
                "gamma": gamma,
                "source": "declared observation scale for comparison",
            },
            "windows": [
                {"id": "pair-12", "keep": ["q1", "q2"]},
                {"id": "cross-13", "keep": ["q1", "q3"]},
                {"id": "pair-34", "keep": ["q3", "q4"]},
            ],
            "partition": {"left": ["q1", "q2"], "right": ["q3", "q4"]},
            "limits": WorkflowLimits().as_dict(),
        }
    instance = {
        "probe_id": probe_id,
        "revision": entry["revision"],
        "parameters": params,
    }
    request["probe"] = {**instance, "instance_digest": digest(instance)}
    return request


def check_probe_identity(value):
    if value is None:
        return
    keys(
        value,
        {"probe_id", "revision", "parameters", "instance_digest"},
        name="probe identity",
    )
    if value["instance_digest"] != digest(
        {k: v for k, v in value.items() if k != "instance_digest"}
    ):
        raise InputError(
            "probe: declared instance identity does not match its parameters"
        )
