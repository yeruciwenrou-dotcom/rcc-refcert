"""Preflight budgets for the explicit small-model reference algorithms."""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass
from typing import TYPE_CHECKING

import numpy as np

from .status import CheckOutcome

if TYPE_CHECKING:
    from .model import FiniteControlModel


@dataclass(frozen=True)
class ComputationLimits:
    max_enumeration_nodes: int = 100_000
    max_matrix_elements: int = 1_048_576

    def __post_init__(self) -> None:
        for name in ("max_enumeration_nodes", "max_matrix_elements"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")


DEFAULT_LIMITS = ComputationLimits()


def _resource_diagnostic(value: int) -> int | str:
    """Bound diagnostic output without expanding an oversized decimal integer."""
    bits = value.bit_length()
    if bits <= 256:
        return value
    sign = "negative " if value < 0 else ""
    return f"<{sign}integer with {bits} bits; decimal expansion omitted>"


class ResourceLimitError(ValueError):
    """An analysis was refused before an estimated resource budget was exceeded."""

    outcome = CheckOutcome.INCONCLUSIVE

    def __init__(self, resource: str, estimate: int, limit: int):
        self.resource = resource
        self.estimate = estimate
        self.limit = limit
        super().__init__(
            f"{resource} preflight estimate {_resource_diagnostic(estimate)} "
            f"exceeds budget {_resource_diagnostic(limit)}; "
            "reduce the requested work or supply larger ComputationLimits"
        )


def _input_elements(value: object) -> int:
    """Count supplied numerical entries without copying or hashing arrays."""
    if isinstance(value, np.ndarray):
        return value.size
    if is_dataclass(value) and not isinstance(value, type):
        return sum(_input_elements(getattr(value, f.name)) for f in fields(value))
    if isinstance(value, dict):
        return sum(_input_elements(v) for v in value.values())
    if isinstance(value, (tuple, list)):
        return sum(_input_elements(v) for v in value)
    return int(isinstance(value, (int, float, complex, np.number)))


def estimate_certificate_resources(model, certificate) -> dict[str, int | str]:
    """Estimate an H.3/H.4 verification's numerical elements before allocation.

    The estimate counts supplied inputs, one block-operator family, the output,
    and the scalar correction system. It is a common admission rule for direct
    verification, task binding, and bundle loading, not a peak-memory or runtime
    guarantee. No matrices are constructed and no input hashes are computed.
    """
    # Local imports keep the shared limits module independent at import time.
    from .bellman_choi import BellmanChoiCertificate
    from .model import FiniteControlModel, ModelValidationError
    from .reference_potential import ReferencePotentialCertificate

    if not isinstance(model, FiniteControlModel):
        raise TypeError("a finite-control model is required")
    dims = tuple(model.control_dims.values())
    if any(type(d) is not int or d < 1 for d in dims):
        raise ModelValidationError("control dimensions must be positive integers")
    if type(model.output_dim) is not int or model.output_dim < 1:
        raise ModelValidationError("output dimension must be a positive integer")
    if isinstance(certificate, BellmanChoiCertificate):
        route = "H.3"
    elif isinstance(certificate, ReferencePotentialCertificate):
        route = "H.4"
    else:
        raise TypeError("supply an H.3 or H.4 proof object")
    blocks = len(model.syntax_states) * len(dims)
    block_elements = len(model.syntax_states) * sum(d * d for d in dims)
    if route == "H.3":
        block_elements *= model.output_dim**2
    inputs = _input_elements(model) + _input_elements(certificate)
    output = model.output_dim**2
    correction = blocks**2
    return {
        "route": route,
        "input_elements": inputs,
        "block_operator_elements": block_elements,
        "output_elements": output,
        "correction_elements": correction,
        "estimated_elements": inputs + block_elements + output + correction,
    }


def check_certificate_budget(
    model, certificate, limits: ComputationLimits = DEFAULT_LIMITS
) -> dict[str, int | str]:
    """Apply the shared certificate admission rule, returning its estimate."""
    estimate = estimate_certificate_resources(model, certificate)
    elements = estimate["estimated_elements"]
    if elements > limits.max_matrix_elements:
        raise ResourceLimitError(
            "certificate_matrix_elements", elements, limits.max_matrix_elements
        )
    return estimate


def check_matrix_budget(model: FiniteControlModel, limits: ComputationLimits) -> None:
    dimension = len(model.syntax_states) * sum(
        d * d for d in model.control_dims.values()
    )
    elements = dimension * (dimension + model.output_dim**2)
    if elements > limits.max_matrix_elements:
        raise ResourceLimitError(
            "dense_matrix_elements", elements, limits.max_matrix_elements
        )


def check_enumeration_budget(
    model: FiniteControlModel,
    depth: int,
    limits: ComputationLimits,
    *,
    repeated_depths: bool = False,
) -> None:
    # Count visited syntax-tree nodes, including prefixes that never halt.
    # Saturate at the budget: huge integer counts need not be constructed.
    active = {model.start_syntax: 1}
    visited = 0
    total = 0
    cap = limits.max_enumeration_nodes + 1
    for _ in range(depth):
        next_active: dict[str, int] = {}
        for state, count in active.items():
            for action in model.actions_by_syntax[state]:
                visited = min(cap, visited + count)
                if not action.is_halt:
                    target = action.successor
                    assert target is not None
                    next_active[target] = min(cap, next_active.get(target, 0) + count)
        total = min(cap, total + visited) if repeated_depths else visited
        if total > limits.max_enumeration_nodes:
            raise ResourceLimitError(
                "enumeration_nodes", total, limits.max_enumeration_nodes
            )
        active = next_active
        if not active:
            if repeated_depths:
                total = min(cap, total + visited * (depth - _ - 1))
                if total > limits.max_enumeration_nodes:
                    raise ResourceLimitError(
                        "enumeration_nodes", total, limits.max_enumeration_nodes
                    )
            break
