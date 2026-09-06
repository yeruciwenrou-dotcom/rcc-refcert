"""Preflight budgets for the explicit small-model reference algorithms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

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


class ResourceLimitError(ValueError):
    """An analysis was refused before an estimated resource budget was exceeded."""

    outcome = CheckOutcome.INCONCLUSIVE

    def __init__(self, resource: str, estimate: int, limit: int):
        self.resource = resource
        self.estimate = estimate
        self.limit = limit
        super().__init__(
            f"{resource} preflight estimate {estimate} exceeds budget {limit}; "
            "reduce the requested work or supply larger ComputationLimits"
        )


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
