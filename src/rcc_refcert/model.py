from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .prefix import is_binary_word, prefix_conflicts
from .quantum import (
    Array,
    completeness_operator,
    is_density_matrix,
    is_psd,
    min_hermitian_eigenvalue,
)

BlockKey = tuple[str, str]


@dataclass
class Action:
    """One prefix-coded syntax action and its total physical channel.

    Kraus operators are unweighted physical branches. The semantics applies
    the prefix weight ``2**(-len(codeword))`` exactly once.
    """

    name: str
    codeword: str
    successor: str | None
    continue_kraus: dict[tuple[str, str], tuple[Array, ...]] = field(
        default_factory=dict
    )
    halt_kraus: dict[str, tuple[Array, ...]] = field(default_factory=dict)

    @property
    def code_length(self) -> int:
        return len(self.codeword)

    @property
    def is_halt(self) -> bool:
        return self.successor is None


@dataclass
class FiniteControlModel:
    """A finite synchronous prefix-control quantum process.

    Transient states are direct-sum blocks indexed by syntax and physical
    control labels. Halting actions emit into the common output space.
    """

    syntax_states: tuple[str, ...]
    control_dims: dict[str, int]
    actions_by_syntax: dict[str, tuple[Action, ...]]
    start_syntax: str
    initial_blocks: dict[str, Array]
    output_dim: int
    reference_state: Array
    name: str = "unnamed-model"
    scope_note: str = "finite synchronous total-output model"

    def transient_keys(self) -> tuple[BlockKey, ...]:
        """Return the canonical direct-sum block order.

        Block ordering is representational rather than physical.  Sorting the
        declared labels makes matrix realizations independent of Python mapping
        insertion order and therefore reproducible across equivalent model
        constructions.
        """
        return tuple(
            (s, q)
            for s in sorted(self.syntax_states)
            for q in sorted(self.control_dims)
        )

    def initial_transient_state(self) -> dict[BlockKey, Array]:
        state: dict[BlockKey, Array] = {}
        for s, q in self.transient_keys():
            dim = self.control_dims[q]
            state[(s, q)] = np.zeros((dim, dim), dtype=complex)
        for q, block in self.initial_blocks.items():
            state[(self.start_syntax, q)] = np.asarray(block, dtype=complex).copy()
        return state


class ModelValidationError(ValueError):
    """Raised when a finite-control model violates its semantic contract."""


def validate_model(model: FiniteControlModel, tol: float = 1e-10) -> list[str]:
    """Return every structural or numerical validation error in ``model``."""

    if not np.isfinite(tol) or tol <= 0:
        raise ValueError("tol must be finite and positive")
    errors: list[str] = []
    syntax = set(model.syntax_states)
    controls = set(model.control_dims)

    if any(not isinstance(state, str) or not state for state in model.syntax_states):
        errors.append("syntax state names must be nonempty strings")
    if any(
        not isinstance(control, str) or not control for control in model.control_dims
    ):
        errors.append("control state names must be nonempty strings")
    if len(model.syntax_states) != len(syntax):
        errors.append("syntax state names are not unique")
    for control, dim in model.control_dims.items():
        if not isinstance(dim, int) or isinstance(dim, bool) or dim <= 0:
            errors.append(
                f"control state {control!r}: Hilbert dimension must be a positive integer"
            )
    if model.start_syntax not in syntax:
        errors.append("start syntax state is not declared")
    if (
        not isinstance(model.output_dim, int)
        or isinstance(model.output_dim, bool)
        or model.output_dim <= 0
    ):
        errors.append("output dimension must be a positive integer")
    if set(model.actions_by_syntax) != syntax:
        errors.append(
            "actions_by_syntax must define every and only declared syntax state"
        )

    for state, actions in model.actions_by_syntax.items():
        if not actions:
            errors.append(f"syntax {state}: at least one action is required")
        codewords = [action.codeword for action in actions]
        for codeword in codewords:
            if not is_binary_word(codeword):
                errors.append(
                    f"syntax {state}: invalid nonempty binary codeword {codeword!r}"
                )
        valid_codewords = [
            codeword for codeword in codewords if is_binary_word(codeword)
        ]
        for left, right in prefix_conflicts(valid_codewords):
            errors.append(f"syntax {state}: codeword {left!r} is a prefix of {right!r}")

        names = [action.name for action in actions]
        if any(not isinstance(name, str) or not name for name in names):
            errors.append(f"syntax {state}: action names must be nonempty strings")
        if len(names) != len(set(names)):
            errors.append(f"syntax {state}: action names are not unique")

        for action in actions:
            if action.successor is not None and action.successor not in syntax:
                errors.append(
                    f"action {action.name}: successor {action.successor!r} is undeclared"
                )
            if action.is_halt and action.continue_kraus:
                errors.append(
                    f"action {action.name}: halt action carries continuing branches"
                )
            if not action.is_halt and action.halt_kraus:
                errors.append(
                    f"action {action.name}: continuing action carries halt maps"
                )

            for source, target in action.continue_kraus:
                if source not in controls:
                    errors.append(
                        f"action {action.name}: continuing branch source {source!r} is undeclared"
                    )
                if target not in controls:
                    errors.append(
                        f"action {action.name}: continuing branch target {target!r} is undeclared"
                    )
            for source in action.halt_kraus:
                if source not in controls:
                    errors.append(
                        f"action {action.name}: halt-map source {source!r} is undeclared"
                    )

            for q in controls:
                dim_in = model.control_dims[q]
                matrices: list[Array] = []
                shapes_valid = True
                if action.is_halt:
                    kraus = action.halt_kraus.get(q, ())
                    matrices.extend(kraus)
                    for k in kraus:
                        if np.asarray(k).shape != (model.output_dim, dim_in):
                            shapes_valid = False
                            errors.append(
                                f"action {action.name}, control {q}: halt Kraus shape {np.asarray(k).shape} "
                                f"does not match {(model.output_dim, dim_in)}"
                            )
                else:
                    for (source, target), kraus in action.continue_kraus.items():
                        if source != q:
                            continue
                        if target not in controls:
                            errors.append(
                                f"action {action.name}: target control {target!r} is undeclared"
                            )
                            continue
                        dim_out = model.control_dims[target]
                        matrices.extend(kraus)
                        for k in kraus:
                            if np.asarray(k).shape != (dim_out, dim_in):
                                shapes_valid = False
                                errors.append(
                                    f"action {action.name}, {source}->{target}: Kraus shape {np.asarray(k).shape} "
                                    f"does not match {(dim_out, dim_in)}"
                                )
                if not matrices:
                    errors.append(
                        f"action {action.name}: no total physical map is supplied for control {q}"
                    )
                elif shapes_valid:
                    comp = completeness_operator(matrices)
                    if not np.allclose(comp, np.eye(dim_in), atol=tol, rtol=0.0):
                        errors.append(
                            f"action {action.name}, control {q}: physical outcomes are not trace preserving"
                        )

    total_trace = 0.0
    for q, initial_block in model.initial_blocks.items():
        if q not in controls:
            errors.append(f"initial block uses undeclared control state {q!r}")
            continue
        dim = model.control_dims[q]
        block = np.asarray(initial_block, dtype=complex)
        if block.shape != (dim, dim):
            errors.append(
                f"initial block {q}: shape {block.shape} does not match {(dim, dim)}"
            )
            continue
        if not np.all(np.isfinite(block)):
            errors.append(f"initial block {q}: block contains non-finite entries")
            continue
        if not is_psd(block, tol=tol):
            errors.append(f"initial block {q}: block is not PSD")
        if not np.allclose(block, block.conj().T, atol=tol, rtol=0.0):
            errors.append(f"initial block {q}: block is not Hermitian")
        total_trace += float(np.trace(block).real)
    if abs(total_trace - 1.0) > tol:
        errors.append(f"initial blocks have total trace {total_trace}, not 1")

    reference = np.asarray(model.reference_state, dtype=complex)
    if reference.shape != (model.output_dim, model.output_dim):
        errors.append("reference-state dimension does not match output dimension")
    elif not np.all(np.isfinite(reference)):
        errors.append("reference state contains non-finite entries")
    elif not is_density_matrix(reference, tol=tol):
        errors.append("reference state is not a density matrix")
    elif min_hermitian_eigenvalue(reference) <= tol:
        errors.append(
            "reference state is not numerically certifiable as full rank on the declared output space; "
            "reduce the model to its reference support or provide an explicit support interface"
        )

    return errors


def require_valid_model(model: FiniteControlModel, tol: float = 1e-10) -> None:
    """Raise :class:`ModelValidationError` unless ``model`` is valid."""

    errors = validate_model(model, tol=tol)
    if errors:
        raise ModelValidationError("Model validation failed:\n- " + "\n- ".join(errors))
