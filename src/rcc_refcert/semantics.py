from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .limits import (
    DEFAULT_LIMITS,
    ComputationLimits,
    check_enumeration_budget,
    check_matrix_budget,
)
from .model import Action, BlockKey, FiniteControlModel, require_valid_model
from .quantum import Array, apply_kraus, unvec, vec
from .weights import code_weight, weighted_operator


@dataclass(frozen=True)
class AcceptedProgram:
    action_names: tuple[str, ...]
    codeword: str

    @property
    def action_count(self) -> int:
        return len(self.action_names)

    @property
    def weight(self) -> float:
        return code_weight(len(self.codeword))


def action_lookup(model: FiniteControlModel, syntax_state: str) -> dict[str, Action]:
    return {action.name: action for action in model.actions_by_syntax[syntax_state]}


def enumerate_accepted_programs(
    model: FiniteControlModel,
    max_actions: int,
    *,
    tol: float = 1e-10,
    limits: ComputationLimits = DEFAULT_LIMITS,
) -> list[AcceptedProgram]:
    require_valid_model(model, tol=tol)
    check_enumeration_budget(model, max_actions, limits)
    accepted: list[AcceptedProgram] = []
    pending = [(model.start_syntax, (), "")]
    while pending:
        syntax_state, names, bits = pending.pop()
        if syntax_state is None:
            accepted.append(AcceptedProgram(names, bits))
            continue
        if len(names) >= max_actions:
            continue
        # Stack entries preserve the original depth-first action order.
        for action in reversed(model.actions_by_syntax[syntax_state]):
            next_names = names + (action.name,)
            next_bits = bits + action.codeword
            code_weight(len(next_bits))
            if action.is_halt:
                pending.append((None, next_names, next_bits))
            else:
                pending.append((action.successor, next_names, next_bits))
    return accepted


def _apply_continue_action(
    model: FiniteControlModel,
    action: Action,
    blocks: dict[str, Array],
) -> dict[str, Array]:
    output = {
        q: np.zeros((dim, dim), dtype=complex) for q, dim in model.control_dims.items()
    }
    for (source, target), kraus in action.continue_kraus.items():
        output[target] += apply_kraus(kraus, blocks[source])
    return output


def _apply_halt_action(
    model: FiniteControlModel, action: Action, blocks: dict[str, Array]
) -> Array:
    output = np.zeros((model.output_dim, model.output_dim), dtype=complex)
    for source, kraus in action.halt_kraus.items():
        output += apply_kraus(kraus, blocks[source])
    return output


def program_output(
    model: FiniteControlModel, program: AcceptedProgram, *, tol: float = 1e-10
) -> Array:
    require_valid_model(model, tol=tol)
    return _program_output(model, program)


def _program_output(model: FiniteControlModel, program: AcceptedProgram) -> Array:
    syntax_state = model.start_syntax
    blocks = {
        q: np.asarray(
            model.initial_blocks.get(q, np.zeros((dim, dim))), dtype=complex
        ).copy()
        for q, dim in model.control_dims.items()
    }
    realized_codeword = ""
    for index, name in enumerate(program.action_names):
        actions = action_lookup(model, syntax_state)
        if name not in actions:
            raise ValueError(
                f"unknown action {name!r} at syntax state {syntax_state!r}"
            )
        action = actions[name]
        realized_codeword += action.codeword
        if action.is_halt:
            if index != len(program.action_names) - 1:
                raise ValueError("program contains actions after halt")
            if program.codeword != realized_codeword:
                raise ValueError(
                    "accepted-program codeword does not match its action sequence"
                )
            return _apply_halt_action(model, action, blocks)
        blocks = _apply_continue_action(model, action, blocks)
        assert action.successor is not None
        syntax_state = action.successor
    raise ValueError("accepted program did not halt")


def depth_contribution_by_enumeration(
    model: FiniteControlModel,
    action_count: int,
    *,
    tol: float = 1e-10,
    limits: ComputationLimits = DEFAULT_LIMITS,
) -> Array:
    contribution = np.zeros((model.output_dim, model.output_dim), dtype=complex)
    for program in enumerate_accepted_programs(
        model, action_count, tol=tol, limits=limits
    ):
        if program.action_count == action_count:
            contribution += weighted_operator(
                program.weight, _program_output(model, program)
            )
    return contribution


def apply_transient_map(
    model: FiniteControlModel,
    state: dict[BlockKey, Array],
) -> dict[BlockKey, Array]:
    output = {
        key: np.zeros(
            (model.control_dims[key[1]], model.control_dims[key[1]]), dtype=complex
        )
        for key in model.transient_keys()
    }
    for (syntax_state, source), operator in state.items():
        for action in model.actions_by_syntax[syntax_state]:
            if action.is_halt:
                continue
            assert action.successor is not None
            weight = code_weight(action.code_length)
            for (branch_source, target), kraus in action.continue_kraus.items():
                if branch_source == source:
                    output[(action.successor, target)] += weighted_operator(
                        weight, apply_kraus(kraus, operator)
                    )
    return output


def apply_halt_map(model: FiniteControlModel, state: dict[BlockKey, Array]) -> Array:
    output = np.zeros((model.output_dim, model.output_dim), dtype=complex)
    for (syntax_state, source), operator in state.items():
        for action in model.actions_by_syntax[syntax_state]:
            if not action.is_halt:
                continue
            weight = code_weight(action.code_length)
            kraus = action.halt_kraus[source]
            output += weighted_operator(weight, apply_kraus(kraus, operator))
    return output


def depth_contribution_by_maps(
    model: FiniteControlModel, action_count: int, *, tol: float = 1e-10
) -> Array:
    require_valid_model(model, tol=tol)
    if action_count < 1:
        return np.zeros((model.output_dim, model.output_dim), dtype=complex)
    state = model.initial_transient_state()
    for _ in range(action_count - 1):
        state = apply_transient_map(model, state)
    return apply_halt_map(model, state)


def truncated_semidensity(
    model: FiniteControlModel, max_transient_steps: int, *, tol: float = 1e-10
) -> Array:
    require_valid_model(model, tol=tol)
    if max_transient_steps < 0:
        raise ValueError("max_transient_steps must be nonnegative")
    total = np.zeros((model.output_dim, model.output_dim), dtype=complex)
    state = model.initial_transient_state()
    for _ in range(max_transient_steps + 1):
        total += apply_halt_map(model, state)
        state = apply_transient_map(model, state)
    return total


def block_slices(
    model: FiniteControlModel,
) -> tuple[tuple[BlockKey, ...], dict[BlockKey, slice]]:
    keys = model.transient_keys()
    offset = 0
    slices: dict[BlockKey, slice] = {}
    for key in keys:
        dim = model.control_dims[key[1]]
        width = dim * dim
        slices[key] = slice(offset, offset + width)
        offset += width
    return keys, slices


def flatten_state(model: FiniteControlModel, state: dict[BlockKey, Array]) -> Array:
    keys, _ = block_slices(model)
    return np.concatenate([vec(state[key]) for key in keys])


def unflatten_state(model: FiniteControlModel, vector: Array) -> dict[BlockKey, Array]:
    keys, slices = block_slices(model)
    state: dict[BlockKey, Array] = {}
    for key in keys:
        dim = model.control_dims[key[1]]
        state[key] = unvec(vector[slices[key]], dim)
    return state


def transient_matrix(
    model: FiniteControlModel,
    *,
    tol: float = 1e-10,
    limits: ComputationLimits = DEFAULT_LIMITS,
) -> Array:
    require_valid_model(model, tol=tol)
    check_matrix_budget(model, limits)
    keys, slices = block_slices(model)
    total_dim = sum(model.control_dims[key[1]] ** 2 for key in keys)
    matrix = np.zeros((total_dim, total_dim), dtype=complex)
    for source_key in keys:
        dim = model.control_dims[source_key[1]]
        for i in range(dim):
            for j in range(dim):
                basis_state = {
                    key: np.zeros(
                        (model.control_dims[key[1]], model.control_dims[key[1]]),
                        dtype=complex,
                    )
                    for key in keys
                }
                basis_state[source_key][i, j] = 1.0
                column_local = i + j * dim
                column = slices[source_key].start + column_local
                matrix[:, column] = flatten_state(
                    model, apply_transient_map(model, basis_state)
                )
    return matrix


def halt_matrix(
    model: FiniteControlModel,
    *,
    tol: float = 1e-10,
    limits: ComputationLimits = DEFAULT_LIMITS,
) -> Array:
    require_valid_model(model, tol=tol)
    check_matrix_budget(model, limits)
    keys, slices = block_slices(model)
    total_dim = sum(model.control_dims[key[1]] ** 2 for key in keys)
    matrix = np.zeros((model.output_dim**2, total_dim), dtype=complex)
    for source_key in keys:
        dim = model.control_dims[source_key[1]]
        for i in range(dim):
            for j in range(dim):
                basis_state = {
                    key: np.zeros(
                        (model.control_dims[key[1]], model.control_dims[key[1]]),
                        dtype=complex,
                    )
                    for key in keys
                }
                basis_state[source_key][i, j] = 1.0
                column_local = i + j * dim
                column = slices[source_key].start + column_local
                matrix[:, column] = vec(apply_halt_map(model, basis_state))
    return matrix
