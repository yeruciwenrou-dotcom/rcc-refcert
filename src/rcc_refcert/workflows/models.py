"""Finite exact recipes and their unweighted quantum-channel realizations."""

from __future__ import annotations

from fractions import Fraction
from itertools import product
from math import prod

import numpy as np

from ..model import Action, FiniteControlModel, require_valid_model
from ..prefix import is_binary_word, prefix_conflicts
from ..weights import MAX_CODE_LENGTH
from .core import (
    InputError,
    WorkflowLimits,
    check_fraction,
    check_size,
    digest,
    exact,
    exact_text,
    json_value,
    keys,
    layout,
    probabilities,
    require_int,
    require_supported,
    text,
)


def coordinates(index, dims):
    out = []
    for dim in reversed(dims):
        index, digit = divmod(index, dim)
        out.append(digit)
    return tuple(reversed(out))


def basis_index(values, dims):
    out = 0
    for value, dim in zip(values, dims):
        out = out * dim + value
    return out


class ExactModel:
    """A validated single-control-block recipe, copied from its public data."""

    def __init__(self, document, *, limits=None):
        self.limits = WorkflowLimits.from_value(limits)
        doc = keys(
            document,
            {
                "schema",
                "schema_version",
                "id",
                "subsystem_dims",
                "subsystem_labels",
                "basis_order",
                "initial",
                "reference",
                "cost",
                "start_syntax",
                "actions",
            },
            name="exact model",
        )
        require_supported(doc["schema"], "rcc-refcert.exact-model", "model.schema")
        if type(doc["schema_version"]) is not int or doc["schema_version"] != 1:
            raise InputError("model.schema_version: expected 1")
        self.dims, self.labels, self.dimension = layout(
            doc["subsystem_dims"], doc["subsystem_labels"], limits=self.limits
        )
        require_supported(doc["basis_order"], "tensor_msb_first", "model.basis_order")
        text(doc["id"], "model.id")
        self.initial = probabilities(
            doc["initial"], self.dimension, name="model.initial", limits=self.limits
        )
        ref = keys(doc["reference"], {"kind", "gamma", "source"}, name="reference")
        require_supported(ref["kind"], "uniform_product_support", "reference.kind")
        require_int(ref["gamma"], "reference.gamma", 2)
        if ref["gamma"].bit_length() > 256:
            raise InputError("reference.gamma: exceeds supported integer size")
        text(ref["source"], "reference.source")
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
        require_supported(cost["kind"], "integer_atomic_slots", "cost.kind")
        if type(cost["action_slots"]) is not int or type(cost["halt_slots"]) is not int:
            raise InputError("cost: action and halt slots must be integers")
        require_supported(cost["action_slots"], 1, "cost.action_slots")
        require_supported(cost["halt_slots"], 1, "cost.halt_slots")
        for k in ("initial_preparation", "auxiliary_systems", "output_rule"):
            text(cost[k], f"cost.{k}")
        require_supported(
            cost["output_rule"], "complete_unconditional_output", "cost.output_rule"
        )
        actions = doc["actions"]
        if not isinstance(actions, dict) or not actions or len(actions) > 1024:
            raise InputError("model.actions: expected one to 1024 syntax states")
        if doc["start_syntax"] not in actions:
            raise InputError("model.start_syntax: must name a declared syntax state")
        clean = {}
        edge_count = 0
        for syntax, entries in sorted(actions.items()):
            text(syntax, "syntax state")
            if (
                not isinstance(entries, (list, tuple))
                or not entries
                or len(entries) > 1024
            ):
                raise InputError("model.actions: each syntax needs one to 1024 actions")
            edge_count += len(entries)
            check_size("recipe_edges", edge_count, self.limits.max_dp_cells)
            row = []
            for raw in entries:
                action = keys(
                    raw,
                    {"name", "codeword", "successor", "operations", "description"},
                    name="action",
                )
                text(action["name"], "action.name")
                text(action["description"], "action.description")
                code = action["codeword"]
                if not is_binary_word(code) or len(code) > MAX_CODE_LENGTH:
                    raise InputError(
                        "action.codeword: supply a supported nonempty binary word"
                    )
                successor = action["successor"]
                if successor is not None and successor not in actions:
                    raise InputError("action.successor: syntax state is not declared")
                ops = action["operations"]
                if not isinstance(ops, (list, tuple)) or not 1 <= len(ops) <= 64:
                    raise InputError(
                        "action.operations: supply one to 64 declared primitives"
                    )
                normalized = [self._primitive(op) for op in ops]
                halts = [op["kind"] == "halt" for op in normalized]
                if successor is None:
                    if halts != [True]:
                        raise InputError(
                            "halt action: exactly one identity halt primitive is required"
                        )
                elif any(halts):
                    raise InputError(
                        "continuing action: halt cannot be embedded in an atom"
                    )
                row.append({**action, "operations": normalized})
            if len({a["name"] for a in row}) != len(row):
                raise InputError("action names must be unique within a syntax state")
            if prefix_conflicts([a["codeword"] for a in row]):
                raise InputError(
                    "action codewords must be prefix-free at each syntax state"
                )
            clean[syntax] = row
        self.document = json_value(
            {**doc, "initial": [exact_text(v) for v in self.initial], "actions": clean}
        )
        self.actions = self.document["actions"]
        self.start = self.document["start_syntax"]
        self.reference = tuple(
            Fraction(1, self.dimension) for _ in range(self.dimension)
        )
        self.content_digest = digest(self.document)

    def _primitive(self, op):
        if not isinstance(op, dict):
            raise InputError("primitive: expected an object")
        kind = op.get("kind")
        d = self.dimension
        if kind == "reset_product":
            keys(op, {"kind", "systems", "probabilities"}, name="reset_product")
            systems = op["systems"]
            if (
                not isinstance(systems, (list, tuple))
                or not systems
                or any(s not in self.labels for s in systems)
                or len(set(systems)) != len(systems)
            ):
                raise InputError("reset_product.systems: use distinct declared labels")
            if not isinstance(op["probabilities"], (list, tuple)) or len(
                op["probabilities"]
            ) != len(systems):
                raise InputError(
                    "reset_product.probabilities: supply one marginal per reset system"
                )
            factors = [
                probabilities(
                    p,
                    self.dims[self.labels.index(s)],
                    name=f"reset_product.{s}",
                    limits=self.limits,
                )
                for s, p in zip(systems, op["probabilities"])
            ]
            return {
                "kind": kind,
                "systems": list(systems),
                "probabilities": [[exact_text(v) for v in p] for p in factors],
            }
        if kind == "basis_permutation":
            keys(op, {"kind", "permutation"}, name=kind)
            perm = op["permutation"]
            if (
                not isinstance(perm, (list, tuple))
                or len(perm) != d
                or any(type(v) is not int for v in perm)
                or set(perm) != set(range(d))
            ):
                raise InputError(
                    "basis_permutation: supply each output index exactly once, in input-index order"
                )
            return {"kind": kind, "permutation": list(perm)}
        if kind == "phase_z":
            keys(op, {"kind", "system"}, name=kind)
            if (
                op["system"] not in self.labels
                or self.dims[self.labels.index(op["system"])] != 2
            ):
                raise InputError("phase_z.system: select one qubit label")
            return dict(op)
        if kind == "classical_channel":
            keys(op, {"kind", "matrix"}, name=kind)
            check_size(
                "classical_channel_elements", d * d, self.limits.max_matrix_elements
            )
            matrix = op["matrix"]
            if (
                not isinstance(matrix, (list, tuple))
                or len(matrix) != d
                or any(
                    not isinstance(row, (list, tuple)) or len(row) != d
                    for row in matrix
                )
            ):
                raise InputError(
                    "classical_channel.matrix: expected a dimension by dimension matrix"
                )
            columns = [
                probabilities(
                    [matrix[i][j] for i in range(d)],
                    d,
                    name="classical_channel column",
                    limits=self.limits,
                )
                for j in range(d)
            ]
            return {
                "kind": kind,
                "matrix": [
                    [exact_text(columns[j][i]) for j in range(d)] for i in range(d)
                ],
            }
        if kind == "halt":
            keys(op, {"kind"}, name=kind)
            return {"kind": "halt"}
        raise InputError("primitive.kind: unsupported exact recipe primitive")

    def lookup(self, syntax, name):
        for action in self.actions[syntax]:
            if action["name"] == name:
                return action
        raise InputError(f"candidate action {name!r}: unknown at syntax {syntax!r}")

    def apply(self, values, action):
        """Apply a declared total atom without multiplying its program prior."""
        out = tuple(values)
        for op in action["operations"]:
            kind = op["kind"]
            if kind in {"phase_z", "halt"}:
                continue
            if kind == "basis_permutation":
                result = [Fraction(0)] * self.dimension
                for old, new in enumerate(op["permutation"]):
                    result[new] = out[old]
            elif kind == "classical_channel":
                result = []
                for row in op["matrix"]:
                    total = Fraction(0)
                    for a, b in zip(row, out):
                        total = check_fraction(
                            total + exact(a) * b,
                            "classical channel output",
                            self.limits,
                        )
                    result.append(total)
            else:
                axes = [self.labels.index(s) for s in op["systems"]]
                rest = [i for i in range(len(self.dims)) if i not in axes]
                marginal = {}
                for index, value in enumerate(out):
                    digits = coordinates(index, self.dims)
                    key = tuple(digits[i] for i in rest)
                    marginal[key] = check_fraction(
                        marginal.get(key, Fraction(0)) + value,
                        "reset marginal",
                        self.limits,
                    )
                factors = [[exact(v) for v in p] for p in op["probabilities"]]
                result = []
                for index in range(self.dimension):
                    digits = coordinates(index, self.dims)
                    value = marginal[tuple(digits[i] for i in rest)]
                    for axis, factor in zip(axes, factors):
                        value = check_fraction(
                            value * factor[digits[axis]], "reset output", self.limits
                        )
                    result.append(value)
            out = tuple(result)
        return out

    def _kraus(self, op):
        d = self.dimension
        kind = op["kind"]
        count = 1
        if kind == "reset_product":
            axes = [self.labels.index(s) for s in op["systems"]]
            count = prod(self.dims[i] for i in axes) ** 2
        elif kind == "classical_channel":
            count = sum(exact(v) > 0 for row in op["matrix"] for v in row)
        check_size(
            "recipe_kraus_elements", count * d * d, self.limits.max_matrix_elements
        )
        if kind == "halt":
            return (np.eye(d, dtype=complex),)
        if kind == "basis_permutation":
            matrix = np.zeros((d, d), dtype=complex)
            matrix[op["permutation"], np.arange(d)] = 1
            return (matrix,)
        if kind == "phase_z":
            axis = self.labels.index(op["system"])
            return (
                np.diag(
                    [(-1) ** coordinates(i, self.dims)[axis] for i in range(d)]
                ).astype(complex),
            )
        if kind == "classical_channel":
            output = []
            for i, row in enumerate(op["matrix"]):
                for j, value in enumerate(row):
                    q = exact(value)
                    if q:
                        k = np.zeros((d, d), dtype=complex)
                        k[i, j] = np.sqrt(float(q))
                        output.append(k)
            return tuple(output)
        axes = [self.labels.index(s) for s in op["systems"]]
        factors = [[exact(v) for v in p] for p in op["probabilities"]]
        assignments = list(product(*(range(self.dims[i]) for i in axes)))
        output = []
        for dest in assignments:
            weight = prod(factors[i][dest[i]] for i in range(len(axes)))
            if not weight:
                continue
            for source in assignments:
                k = np.zeros((d, d), dtype=complex)
                for j in range(d):
                    digits = list(coordinates(j, self.dims))
                    if tuple(digits[i] for i in axes) == source:
                        for axis, v in zip(axes, dest):
                            digits[axis] = v
                        k[basis_index(digits, self.dims), j] = np.sqrt(float(weight))
                output.append(k)
        return tuple(output)

    def numerical_view(self):
        """Build the same recipe's finite quantum model under an array budget."""
        d = self.dimension
        check_size(
            "recipe_dense_state_elements", 2 * d * d, self.limits.max_matrix_elements
        )
        actions = {}
        accumulated = 2 * d * d
        for syntax, row in self.actions.items():
            rendered = []
            for a in row:
                kraus = (np.eye(d, dtype=complex),)
                for op in a["operations"]:
                    nxt = self._kraus(op)
                    check_size(
                        "composite_kraus_working_elements",
                        accumulated
                        + (len(nxt) + len(kraus) + len(nxt) * len(kraus)) * d * d,
                        self.limits.max_matrix_elements,
                    )
                    kraus = tuple(b @ k for b in nxt for k in kraus)
                accumulated += len(kraus) * d * d
                check_size(
                    "recipe_model_elements",
                    accumulated,
                    self.limits.max_matrix_elements,
                )
                kwargs = (
                    {"halt_kraus": {"q": kraus}}
                    if a["successor"] is None
                    else {"continue_kraus": {("q", "q"): kraus}}
                )
                rendered.append(
                    Action(a["name"], a["codeword"], a["successor"], **kwargs)
                )
            actions[syntax] = tuple(rendered)
        model = FiniteControlModel(
            tuple(self.actions),
            {"q": d},
            actions,
            self.start,
            {"q": np.diag([float(v) for v in self.initial])},
            d,
            np.eye(d) / d,
            name=self.document["id"],
            scope_note="numeric view of a declared exact diagonal-preserving quantum recipe",
        )
        require_valid_model(model)
        return model
