"""Editable recipe presets; expansion retains the complete scientific input."""

from __future__ import annotations

from fractions import Fraction

from .core import InputError, WorkflowLimits, exact, exact_text, keys, require_int
from .models import ExactModel, basis_index, coordinates
from .states import StateInput, tensor_probabilities


def _cost(initial, auxiliary):
    return {
        "kind": "integer_atomic_slots",
        "action_slots": 1,
        "halt_slots": 1,
        "initial_preparation": initial,
        "auxiliary_systems": auxiliary,
        "output_rule": "complete_unconditional_output",
    }


def _action(name, code, successor, operations, description):
    return {
        "name": name,
        "codeword": code,
        "successor": successor,
        "operations": operations,
        "description": description,
    }


def program(model, names, *, name="candidate"):
    syntax, bits = model.start, ""
    for index, action_name in enumerate(names):
        action = model.lookup(syntax, action_name)
        bits += action["codeword"]
        syntax = action["successor"]
        if syntax is None and index != len(names) - 1:
            raise InputError("candidate: actions follow halt")
    if syntax is not None:
        raise InputError("candidate: a complete program must halt")
    return {
        "id": name,
        "action_names": list(names),
        "codeword": bits,
        "source": "declared preset program",
    }


def expand_preset(spec, *, limits=None):
    limits = WorkflowLimits.from_value(limits)
    keys(spec, {"preset", "parameters"}, name="model preset")
    name, params = spec["preset"], spec["parameters"]
    if name == "cyclic_reset":
        keys(params, {"qubits", "p"}, name="cyclic_reset.parameters")
        n = require_int(params["qubits"], "cyclic_reset.qubits", 1)
        if n > 12:
            raise InputError("cyclic_reset.qubits: supported preset range is 1 to 12")
    elif name == "algorithmic_cooling":
        keys(params, {"p", "cycles"}, name="algorithmic_cooling.parameters")
        n = 3
        cycles = require_int(params["cycles"], "algorithmic_cooling.cycles", 0)
        if 2 * cycles + 2 > limits.max_candidate_steps:
            from .core import check_size

            check_size("candidate_steps", 2 * cycles + 2, limits.max_candidate_steps)
    else:
        raise InputError("model.preset: use cyclic_reset or algorithmic_cooling")
    p = exact(params["p"], "preset.p", limits=limits)
    if not Fraction(1, 2) < p < 1:
        raise InputError(
            "preset.p: require 1/2 < p < 1; degenerate boundaries need a separate recipe"
        )
    d, dims, labels = 2**n, [2] * n, [f"q{i + 1}" for i in range(n)]
    uniform = [exact_text(Fraction(1, d))] * d
    tau = [exact_text(p), exact_text(1 - p)]
    base = {
        "schema": "rcc-refcert.exact-model",
        "schema_version": 1,
        "id": name,
        "subsystem_dims": dims,
        "subsystem_labels": labels,
        "basis_order": "tensor_msb_first",
        "initial": uniform,
    }
    if name == "cyclic_reset":
        permutation = [
            basis_index(coordinates(i, dims)[1:] + coordinates(i, dims)[:1], dims)
            for i in range(d)
        ]
        actions = [
            _action(
                "reset-0",
                "00",
                "s",
                [
                    {
                        "kind": "reset_product",
                        "systems": [labels[0]],
                        "probabilities": [tau],
                    },
                    {"kind": "basis_permutation", "permutation": permutation},
                ],
                "Replace the first qubit, then rotate it to the final tensor axis; one atomic slot.",
            ),
            _action(
                "reset-1",
                "01",
                "s",
                [
                    {
                        "kind": "reset_product",
                        "systems": [labels[0]],
                        "probabilities": [tau[::-1]],
                    },
                    {"kind": "basis_permutation", "permutation": permutation},
                ],
                "Replace the first qubit with the opposite polarization, then rotate; one atomic slot.",
            ),
            _action(
                "phase",
                "10",
                "s",
                [{"kind": "phase_z", "system": labels[0]}],
                "Apply Z to the first qubit; one atomic slot.",
            ),
            _action(
                "halt",
                "11",
                None,
                [{"kind": "halt"}],
                "Return the full register; one atomic slot.",
            ),
        ]
        doc = {
            **base,
            "reference": {
                "kind": "uniform_product_support",
                "gamma": 4,
                "source": "four declared physical action classes per atomic slot",
            },
            "cost": _cost(
                "The maximally mixed register is the supplied reference input.",
                "Each replacement uses the declared polarization; its refresh is charged in its atom.",
            ),
            "start_syntax": "s",
            "actions": {"s": actions},
        }
        model = ExactModel(doc, limits=limits)
        target = StateInput.diagonal(
            tensor_probabilities([[p, 1 - p]] * n),
            dims,
            labels,
            source="declared polarized product target",
        )
        candidates = [program(model, ["reset-0"] * n + ["halt"], name="full-reset")]
        if n > 1:
            candidates.insert(
                0,
                program(model, ["reset-0"] * (n - 1) + ["halt"], name="shorter-reset"),
            )
        envelopes = {"s": uniform}
    else:
        permutation = list(range(8))
        permutation[3], permutation[4] = permutation[4], permutation[3]
        actions = {}
        for syntax, successor in (("s0", "s0"), ("sR", "sC"), ("sC", "sR")):
            actions[syntax] = [
                _action(
                    "R",
                    "00",
                    "sR",
                    [
                        {
                            "kind": "reset_product",
                            "systems": ["q2", "q3"],
                            "probabilities": [tau, tau],
                        }
                    ],
                    "Replace both bath qubits with the declared product bath; one charged refresh slot.",
                ),
                _action(
                    "C",
                    "01",
                    successor,
                    [{"kind": "basis_permutation", "permutation": permutation}],
                    "Swap basis states 011 and 100; one compression slot.",
                ),
                _action(
                    "H",
                    "10",
                    None,
                    [{"kind": "halt"}],
                    "Return all three qubits; one halt slot.",
                ),
            ]
        doc = {
            **base,
            "reference": {
                "kind": "uniform_product_support",
                "gamma": 3,
                "source": "refresh, compression and halt are three physical action classes",
            },
            "cost": _cost(
                "The maximally mixed three-qubit register is supplied.",
                "Both bath qubits remain in the output; each refresh is charged.",
            ),
            "start_syntax": "s0",
            "actions": actions,
        }
        model = ExactModel(doc, limits=limits)
        names = ["R"] + ["C", "R"] * cycles + ["H"]
        output, syntax = model.initial, model.start
        for action_name in names:
            action = model.lookup(syntax, action_name)
            output = model.apply(output, action)
            syntax = action["successor"]
        target = StateInput.diagonal(
            output,
            dims,
            labels,
            source="complete output of the declared compression-refresh target program",
        )
        candidates = [program(model, names, name="target-program")]
        if cycles:
            candidates.insert(
                0,
                program(
                    model,
                    ["R"] + ["C", "R"] * (cycles - 1) + ["H"],
                    name="shorter-program",
                ),
            )
        theta_r = tensor_probabilities([[Fraction(1, 2)] * 2, [p, 1 - p], [p, 1 - p]])
        theta_c = model.apply(theta_r, model.lookup("sR", "C"))
        envelopes = {
            "s0": uniform,
            "sR": [exact_text(v) for v in theta_r],
            "sC": [exact_text(v) for v in theta_c],
        }
    return model, target, candidates, {"envelopes": envelopes}
