"""Complete states with explicit tensor axes and numerical input policies."""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction

import numpy as np

from .core import (
    InputError,
    WorkflowLimits,
    check_size,
    digest,
    exact_text,
    json_value,
    keys,
    layout,
    probabilities,
    require_supported,
    text,
)


@dataclass(frozen=True)
class StateInput:
    kind: str
    data: tuple
    subsystem_dims: tuple[int, ...]
    subsystem_labels: tuple[str, ...]
    basis_order: str = "tensor_msb_first"
    provenance: dict = field(default_factory=lambda: {"source": "supplied full state"})
    numeric_policy: dict = field(
        default_factory=lambda: {"mode": "none", "tolerance": 1e-10}
    )
    support: dict = field(
        default_factory=lambda: {
            "kind": "complete_working_support",
            "source": "declared tensor layout",
        }
    )

    def __post_init__(self):
        # Public construction and JSON parsing share these invariants.
        ds, ls, size = layout(self.subsystem_dims, self.subsystem_labels)
        require_supported(self.basis_order, "tensor_msb_first", "basis_order")
        object.__setattr__(self, "subsystem_dims", ds)
        object.__setattr__(self, "subsystem_labels", ls)
        object.__setattr__(self, "provenance", json_value(self.provenance))
        sup = keys(self.support, {"kind", "source"}, name="support")
        require_supported(sup["kind"], "complete_working_support", "support.kind")
        text(sup["source"], "support.source")
        object.__setattr__(self, "support", dict(sup))
        if self.kind == "diagonal_exact":
            object.__setattr__(self, "data", probabilities(self.data, size))
            object.__setattr__(self, "numeric_policy", {})
        elif self.kind == "density_numeric":
            check_size(
                "density_matrix_elements",
                size * size,
                WorkflowLimits().max_matrix_elements,
            )
            if (
                not isinstance(self.data, (list, tuple, np.ndarray))
                or len(self.data) != size
            ):
                raise InputError("density matrix: shape does not match subsystem_dims")
            rows = []
            for row in self.data:
                if not isinstance(row, (list, tuple, np.ndarray)) or len(row) != size:
                    raise InputError("density matrix: expected a square matrix")
                out = []
                for cell in row:
                    if isinstance(cell, (list, tuple)):
                        if len(cell) != 2:
                            raise InputError(
                                "density matrix: complex entries use [real, imaginary]"
                            )
                        if any(
                            isinstance(x, bool) or not isinstance(x, (int, float))
                            for x in cell
                        ):
                            raise InputError(
                                "density matrix: real and imaginary parts must be finite numbers"
                            )
                        z = complex(*cell)
                    else:
                        if isinstance(cell, (bool, str)):
                            raise InputError("density matrix: expected numeric entries")
                        try:
                            z = complex(cell)
                        except (TypeError, ValueError, OverflowError) as exc:
                            raise InputError(
                                "density matrix: expected finite complex entries"
                            ) from exc
                    if not np.isfinite(z):
                        raise InputError("density matrix: entries must be finite")
                    out.append(z)
                rows.append(tuple(out))
            object.__setattr__(self, "data", tuple(rows))
            p = keys(
                self.numeric_policy,
                {"mode", "tolerance"},
                {"repair_budget"},
                "numeric_policy",
            )
            if p["mode"] not in {"none", "roundoff_only"}:
                raise InputError("numeric_policy.mode: use none or roundoff_only")
            for key in ("tolerance", "repair_budget"):
                if key in p and (
                    isinstance(p[key], bool)
                    or not isinstance(p[key], (int, float))
                    or not np.isfinite(p[key])
                    or p[key] <= 0
                    or p[key] > 1e-3
                ):
                    raise InputError(
                        f"numeric_policy.{key}: require a finite positive number <= 0.001"
                    )
            if p["mode"] == "roundoff_only" and "repair_budget" not in p:
                raise InputError(
                    "numeric_policy: roundoff_only needs an explicit repair_budget"
                )
            object.__setattr__(self, "numeric_policy", dict(p))
        else:
            raise InputError("state.kind: use diagonal_exact or density_numeric")

    @classmethod
    def from_dict(cls, obj, *, limits=None):
        limits = WorkflowLimits.from_value(limits)
        if isinstance(obj, cls):
            obj = obj.as_dict()
        obj = keys(
            obj,
            {
                "schema",
                "schema_version",
                "kind",
                "data",
                "subsystem_dims",
                "subsystem_labels",
                "basis_order",
                "support",
                "provenance",
            },
            {"numeric_policy", "content_digest"},
            "state",
        )
        require_supported(obj["schema"], "rcc-refcert.state", "state.schema")
        if type(obj["schema_version"]) is not int or obj["schema_version"] != 1:
            raise InputError("state.schema_version: expected 1")
        _, _, size = layout(
            obj["subsystem_dims"], obj["subsystem_labels"], limits=limits
        )
        if obj["kind"] == "density_numeric":
            check_size(
                "density_matrix_working_elements",
                6 * size * size,
                limits.max_matrix_elements,
            )
        else:
            probabilities(obj["data"], size, limits=limits)
        result = cls(
            **{
                k: obj[k]
                for k in (
                    "kind",
                    "data",
                    "subsystem_dims",
                    "subsystem_labels",
                    "basis_order",
                    "support",
                    "provenance",
                )
            },
            numeric_policy=obj.get(
                "numeric_policy", {"mode": "none", "tolerance": 1e-10}
            ),
        )
        if "content_digest" in obj and obj["content_digest"] != result.content_digest:
            raise InputError("state.content_digest: state content has changed")
        return result

    @classmethod
    def diagonal(cls, values, dims, labels, *, source="supplied exact diagonal state"):
        return cls(
            "diagonal_exact",
            tuple(values),
            tuple(dims),
            tuple(labels),
            provenance={"source": source},
        )

    @classmethod
    def numeric(
        cls, matrix, dims, labels, *, policy=None, source="supplied density matrix"
    ):
        return cls(
            "density_numeric",
            matrix,
            tuple(dims),
            tuple(labels),
            provenance={"source": source},
            numeric_policy=policy or {"mode": "none", "tolerance": 1e-10},
        )

    @property
    def dimension(self):
        return len(self.data)

    def _body(self):
        data = (
            [exact_text(v) for v in self.data]
            if self.kind == "diagonal_exact"
            else [[[z.real, z.imag] for z in row] for row in self.data]
        )
        return {
            "schema": "rcc-refcert.state",
            "schema_version": 1,
            "kind": self.kind,
            "data": data,
            "subsystem_dims": list(self.subsystem_dims),
            "subsystem_labels": list(self.subsystem_labels),
            "basis_order": self.basis_order,
            "support": json_value(self.support),
            "provenance": json_value(self.provenance),
            "numeric_policy": json_value(self.numeric_policy),
        }

    @property
    def content_digest(self):
        # Provenance is retained but physical identity is the complete state/layout.
        body = self._body()
        body.pop("provenance")
        return digest(body)

    def as_dict(self):
        return {**self._body(), "content_digest": self.content_digest}

    def matrix(self, *, limits=None):
        limits = WorkflowLimits.from_value(limits)
        check_size(
            "density_matrix_elements", self.dimension**2, limits.max_matrix_elements
        )
        if self.kind == "diagonal_exact":
            return np.diag([float(v) for v in self.data]).astype(complex)
        return np.asarray(self.data, dtype=complex)


def tensor_probabilities(factors):
    result = [Fraction(1)]
    for factor in factors:
        result = [a * b for a in result for b in factor]
    return tuple(result)


def prepare_numeric_state(state, *, limits=None):
    """Return an explicit derived matrix and diagnostics; never repair in place."""
    limits = WorkflowLimits.from_value(limits)
    d = state.dimension
    check_size("density_matrix_working_elements", 6 * d * d, limits.max_matrix_elements)
    raw = state.matrix(limits=limits)
    if state.kind == "diagonal_exact":
        return raw, {
            "outcome": "pass",
            "policy": "exact_diagonal_numeric_view",
            "original_digest": state.content_digest,
            "repair_applied": False,
        }
    policy = state.numeric_policy
    tol = policy["tolerance"]
    herm_error = float(np.linalg.norm(raw - raw.conj().T, ord="fro"))
    trace_error = float(abs(np.trace(raw) - 1))
    herm = (raw + raw.conj().T) / 2
    vals, vecs = np.linalg.eigh(herm)
    minimum = float(vals[0])
    diagnostics = {
        "outcome": "inconclusive",
        "policy": json_value(policy),
        "hermiticity_error": herm_error,
        "trace_error": trace_error,
        "minimum_eigenvalue": minimum,
        "original_digest": state.content_digest,
        "repair_applied": False,
    }
    if max(herm_error, trace_error, max(0.0, -minimum)) > tol:
        diagnostics["reason"] = "density checks exceed the declared numerical tolerance"
        return None, diagnostics
    if policy["mode"] == "none":
        if herm_error or trace_error or minimum < 0:
            diagnostics["reason"] = (
                "roundoff is unresolved; explicitly select roundoff_only with a repair budget"
            )
            return None, diagnostics
        diagnostics["outcome"] = "pass"
        return raw, diagnostics
    positive = np.maximum(vals, 0)
    norm = float(positive.sum())
    if norm <= 0:
        diagnostics["reason"] = "density has no positive normalized support"
        return None, diagnostics
    repaired = (vecs * (positive / norm)) @ vecs.conj().T
    # Trace norm applies to arbitrary differences, including a non-Hermitian input.
    perturbation = float(np.linalg.svd(repaired - raw, compute_uv=False).sum() / 2)
    diagnostics["perturbation_trace_norm_half"] = perturbation
    if perturbation > policy["repair_budget"]:
        diagnostics["reason"] = "roundoff correction exceeds repair_budget"
        return None, diagnostics
    derived = StateInput.numeric(
        repaired,
        state.subsystem_dims,
        state.subsystem_labels,
        policy=policy,
        source="roundoff-derived diagnostic state",
    )
    diagnostics.update(
        outcome="pass",
        repair_applied=bool(perturbation),
        derived_digest=derived.content_digest,
        derived_state=derived.as_dict(),
    )
    return repaired, diagnostics


def check_numeric_diagnostics(state, saved, *, limits=None):
    """Check the author's state identity and numerical meaning separately.

    Reconstructing an eigensystem can change the last bits across backends.
    The saved correction must identify and justify itself; its locally
    recomputed counterpart is compared in trace norm under the saved policy.
    """
    from .windows import _close

    fresh_matrix, fresh = prepare_numeric_state(state, limits=limits)
    keys(saved, set(fresh), name="history numerical diagnostics")
    if (
        saved["original_digest"] != state.content_digest
        or saved["policy"] != fresh["policy"]
        or type(saved["repair_applied"]) is not bool
    ):
        raise InputError("history: numerical diagnostic identity or policy mismatch")
    tolerance = state.numeric_policy.get("tolerance", 1e-10)
    derived_fields = {
        "derived_state",
        "derived_digest",
        "repair_applied",
        "perturbation_trace_norm_half",
    }
    if not _close(
        {k: v for k, v in saved.items() if k not in derived_fields},
        {k: v for k, v in fresh.items() if k not in derived_fields},
        tolerance,
    ):
        raise InputError("history: numerical diagnostics mismatch")
    if "derived_state" not in fresh:
        if saved["repair_applied"]:
            raise InputError("history: numerical correction has no derived state")
        if "perturbation_trace_norm_half" in fresh:
            reported = saved["perturbation_trace_norm_half"]
            if (
                isinstance(reported, bool)
                or not isinstance(reported, (int, float))
                or not 0 <= reported < float("inf")
                or (
                    saved.get("reason") == "roundoff correction exceeds repair_budget"
                    and reported <= state.numeric_policy["repair_budget"]
                )
                # The attempted correction was not saved. Compare fresh
                # reconstructions at the policy scale, not at a fixed-array ULP.
                or not _close(
                    reported, fresh["perturbation_trace_norm_half"], tolerance
                )
            ):
                raise InputError(
                    "history: unresolved numerical correction or repair budget mismatch"
                )
        return fresh

    derived = StateInput.from_dict(saved["derived_state"], limits=limits)
    if (
        saved["derived_state"].get("content_digest") != derived.content_digest
        or saved["derived_digest"] != derived.content_digest
        or derived.kind != "density_numeric"
        or derived.subsystem_dims != state.subsystem_dims
        or derived.subsystem_labels != state.subsystem_labels
        or derived.basis_order != state.basis_order
        or derived.support != fresh["derived_state"]["support"]
        or derived.numeric_policy != state.numeric_policy
    ):
        raise InputError("history: derived state identity, layout or policy mismatch")
    raw = state.matrix(limits=limits)
    matrix = derived.matrix(limits=limits)
    perturbation = float(np.linalg.svd(matrix - raw, compute_uv=False).sum() / 2)
    reported = saved["perturbation_trace_norm_half"]
    budget = state.numeric_policy["repair_budget"]
    if (
        isinstance(reported, bool)
        or not isinstance(reported, (int, float))
        or not 0 <= reported <= budget
        or perturbation > budget
        # This norm describes two saved arrays, rather than a fresh correction.
        # Check its own floating-point scale, not the much larger repair budget.
        or abs(reported - perturbation)
        > min(
            tolerance,
            budget,
            32 * state.dimension * max(np.spacing(reported), np.spacing(perturbation)),
        )
        or saved["repair_applied"] != bool(reported)
        or saved["repair_applied"] != bool(perturbation)
    ):
        raise InputError("history: derived state correction or repair budget mismatch")
    hermitian = (matrix + matrix.conj().T) / 2
    if (
        max(
            float(np.linalg.norm(matrix - matrix.conj().T, ord="fro")),
            float(abs(np.trace(matrix) - 1)),
            max(0.0, -float(np.linalg.eigvalsh(hermitian)[0])),
        )
        > tolerance
    ):
        raise InputError("history: derived state fails its density checks")
    difference = float(np.linalg.svd(matrix - fresh_matrix, compute_uv=False).sum() / 2)
    if difference > min(tolerance, budget):
        raise InputError("history: derived states disagree under the numerical policy")
    return fresh
