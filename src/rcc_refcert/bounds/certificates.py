"""Bind finite-control H.3/H.4 numerical evidence to a declared bound task."""

from __future__ import annotations

import hashlib
import math
from dataclasses import fields, is_dataclass
from fractions import Fraction

import numpy as np

from ..bellman_choi import BellmanChoiCertificate, verify_bellman_choi
from ..limits import DEFAULT_LIMITS, ComputationLimits, ResourceLimitError
from ..model import FiniteControlModel
from ..reference_potential import (
    ReferencePotentialCertificate,
    verify_reference_potential,
)
from ..status import CheckOutcome
from .contracts import MATRIX_HASH_FORMAT, Task, canonical_hash, text
from .scalar import BudgetError, InputError


def _array_snapshot(value: np.ndarray) -> dict:
    dtype = value.dtype.newbyteorder("<")
    if dtype.kind not in "biufc" or (dtype.itemsize > (16 if dtype.kind == "c" else 8)):
        raise InputError("matrix hashing requires a standard numeric NumPy dtype")
    digest = hashlib.sha256()
    # C-order chunks preserve logical entries without flattening the whole array.
    with np.nditer(
        value,
        flags=["external_loop", "buffered", "zerosize_ok"],
        op_flags=["readonly"],
        op_dtypes=[dtype],
        order="C",
        buffersize=8192,
    ) as chunks:
        for chunk in chunks:
            digest.update(chunk.tobytes(order="C"))
    return {
        "array_format": MATRIX_HASH_FORMAT,
        "shape": list(value.shape),
        "dtype": dtype.str,
        "sha256": digest.hexdigest(),
    }


def _input_elements(value) -> int:
    if isinstance(value, np.ndarray):
        return value.size
    if is_dataclass(value):
        return sum(_input_elements(getattr(value, f.name)) for f in fields(value))
    if isinstance(value, dict):
        return sum(_input_elements(v) for v in value.values())
    if isinstance(value, (tuple, list)):
        return sum(_input_elements(v) for v in value)
    return int(isinstance(value, (int, float, complex, np.number)))


def _check_binding_budget(model, certificate, limits: ComputationLimits) -> None:
    dims = tuple(model.control_dims.values())
    if any(type(d) is not int or d < 1 for d in dims):
        raise InputError("control dimensions must be positive integers")
    blocks = len(model.syntax_states) * len(dims)
    block_elements = len(model.syntax_states) * sum(d * d for d in dims)
    if isinstance(certificate, BellmanChoiCertificate):
        block_elements *= model.output_dim**2
    # Input entries, one block-operator family, the output, and the correction
    # system form a preflight estimate, not a peak-memory or execution-time bound.
    estimate = (
        _input_elements(model)
        + _input_elements(certificate)
        + block_elements
        + model.output_dim**2
        + blocks**2
    )
    if estimate > limits.max_matrix_elements:
        raise BudgetError(
            str(
                ResourceLimitError(
                    "certificate_matrix_elements", estimate, limits.max_matrix_elements
                )
            )
        )


def _snapshot(value):
    """Hash exact binary inputs, with explicit shapes and dictionary keys."""
    if is_dataclass(value):
        return {f.name: _snapshot(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, np.ndarray):
        return _array_snapshot(value)
    if isinstance(value, (complex, np.complexfloating)):
        return {"real": float(value.real).hex(), "imag": float(value.imag).hex()}
    if isinstance(value, (float, np.floating)):
        return {"binary_float": float(value).hex()}
    if isinstance(value, dict):
        entries = [[_snapshot(k), _snapshot(v)] for k, v in value.items()]
        return sorted(entries, key=lambda item: canonical_hash(item[0]))
    if isinstance(value, (tuple, list)):
        return [_snapshot(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    return value


def with_reference_certificate(
    task_declaration: dict,
    model: FiniteControlModel,
    certificate: BellmanChoiCertificate | ReferencePotentialCertificate,
    *,
    source: str,
    tol: float = 1e-10,
    limits: ComputationLimits = DEFAULT_LIMITS,
) -> dict:
    """Return a new task using a freshly verified H.3/H.4 upper constant.

    The task ID must match the model name and its reference must be the
    nominal uniform state of the declared dimension. Hashes bind the actual
    model and certificate inputs. ``limits`` bounds the matrix preflight estimate
    before reference allocation, input hashing or numerical verification.
    The matrix verification retains its existing
    numerical evidence level; this adapter does not verify RCon, TC or RA.
    Use before freezing any acquisition protocol, since the task changes.
    """
    task = Task.from_dict(task_declaration)
    text(source, "certificate source")
    if task.dimension > 1024:
        raise BudgetError(
            "certificate adapter reference dimension exceeds 1024 before dense allocation"
        )
    if not isinstance(model, FiniteControlModel):
        raise InputError("a finite-control model is required")
    if (
        model.name != task.declaration["model"]["id"]
        or model.output_dim != task.dimension
    ):
        raise InputError(
            "certificate model identity or output dimension differs from the task"
        )
    if isinstance(certificate, BellmanChoiCertificate):
        method, verifier = "H.3", verify_bellman_choi
    elif isinstance(certificate, ReferencePotentialCertificate):
        method, verifier = "H.4", verify_reference_potential
    else:
        raise InputError(
            "supply an H.3 or H.4 proof object; stored reports and H.34 estimates are not accepted"
        )
    _check_binding_budget(model, certificate, limits)
    if not np.array_equal(
        model.reference_state, np.eye(task.dimension) / task.dimension
    ):
        raise InputError(
            "the certificate reference must be the declared nominal uniform state"
        )
    model_hash = canonical_hash(_snapshot(model))
    certificate_hash = canonical_hash(_snapshot(certificate))
    report = verifier(model, certificate, tol=tol)
    if report.outcome is not CheckOutcome.PASS or report.constant is None:
        raise InputError(
            f"{method} verification is {report.outcome.value}; no usable upper constant"
        )
    if not math.isfinite(report.constant) or report.constant < 0:
        raise InputError("certificate returned an invalid upper constant")
    # Converting via str(float) could round the propagated upper endpoint down.
    upper = max(Fraction(1), Fraction.from_float(float(report.constant)))
    result = task.declaration
    result["model"]["reference_domination"] = {
        "upper_constant": str(upper),
        "source": source,
        "source_kind": "numerical_upper_constant",
        "evidence": {
            "method": method,
            "outcome": "pass",
            "level": report.evidence.value,
            "model_id": model.name,
            "reference_id": result["model"]["reference_id"],
            "model_sha256": model_hash,
            "certificate_sha256": certificate_hash,
            "input_hash_format": MATRIX_HASH_FORMAT,
            "reported_constant_exact": str(Fraction.from_float(float(report.constant))),
            "tolerance_exact": str(Fraction.from_float(float(tol))),
        },
    }
    return Task.from_dict(result).declaration
