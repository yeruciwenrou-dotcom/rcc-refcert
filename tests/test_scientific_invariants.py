from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pytest

from rcc_refcert.bellman_choi import (
    BellmanChoiCertificate,
    verify_bellman_choi,
)
from rcc_refcert.domination import minimum_domination_constant
from rcc_refcert.examples import (
    make_dephase_bellman_choi_certificate,
    make_dephase_or_halt_model,
    make_dephase_reference_potential_certificates,
    make_multiblock_bellman_choi_certificate,
    make_multiblock_rectangular_model,
    make_multiblock_reference_potential_certificate,
)
from rcc_refcert.fixed_point import linear_fixed_point, linear_value_choi_envelopes
from rcc_refcert.gain_cost import GainCostReport, analyze_reference_gain_cost
from rcc_refcert.model import Action, BlockKey, FiniteControlModel, require_valid_model
from rcc_refcert.reference_potential import (
    ReferencePotentialCertificate,
    verify_reference_potential,
)
from rcc_refcert.semantics import (
    block_slices,
    depth_contribution_by_enumeration,
    depth_contribution_by_maps,
    halt_matrix,
    transient_matrix,
    truncated_semidensity,
)
from rcc_refcert.status import CheckOutcome

ATOL = 5e-11


def _fourier_unitary(size: int, phase: float) -> np.ndarray:
    rows = np.arange(size, dtype=float)[:, None]
    columns = np.arange(size, dtype=float)[None, :]
    fourier = np.exp(2j * np.pi * rows * columns / size) / np.sqrt(size)
    row_phases = np.exp(1j * phase * (np.arange(size, dtype=float) + 1.0))
    return row_phases[:, None] * fourier


def _mix_kraus_group(
    kraus: Iterable[np.ndarray], phase: float
) -> tuple[np.ndarray, ...]:
    matrices = tuple(np.asarray(matrix, dtype=complex) for matrix in kraus)
    unitary = _fourier_unitary(len(matrices), phase)
    return tuple(
        sum(
            (
                unitary[row, column] * matrices[column]
                for column in range(len(matrices))
            ),
            np.zeros_like(matrices[0]),
        )
        for row in range(len(matrices))
    )


def _kraus_mixed_model(model: FiniteControlModel) -> FiniteControlModel:
    actions_by_syntax: dict[str, tuple[Action, ...]] = {}
    group_index = 1
    for syntax_state, actions in model.actions_by_syntax.items():
        mixed_actions = []
        for action in actions:
            continuing = {}
            for key, kraus in action.continue_kraus.items():
                continuing[key] = _mix_kraus_group(kraus, phase=0.17 * group_index)
                group_index += 1
            halting = {}
            for key, kraus in action.halt_kraus.items():
                halting[key] = _mix_kraus_group(kraus, phase=0.17 * group_index)
                group_index += 1
            mixed_actions.append(
                Action(
                    name=action.name,
                    codeword=action.codeword,
                    successor=action.successor,
                    continue_kraus=continuing,
                    halt_kraus=halting,
                )
            )
        actions_by_syntax[syntax_state] = tuple(mixed_actions)
    return FiniteControlModel(
        syntax_states=model.syntax_states,
        control_dims=dict(model.control_dims),
        actions_by_syntax=actions_by_syntax,
        start_syntax=model.start_syntax,
        initial_blocks={
            key: value.copy() for key, value in model.initial_blocks.items()
        },
        output_dim=model.output_dim,
        reference_state=model.reference_state.copy(),
        name=f"{model.name}-kraus-mixed",
        scope_note=model.scope_note,
    )


def _random_unitary(rng: np.random.Generator, dim: int) -> np.ndarray:
    raw = rng.normal(size=(dim, dim)) + 1j * rng.normal(size=(dim, dim))
    unitary, triangular = np.linalg.qr(raw)
    diagonal = np.diag(triangular)
    phases = np.ones(dim, dtype=complex)
    nonzero = np.abs(diagonal) > 0
    phases[nonzero] = diagonal[nonzero] / np.abs(diagonal[nonzero])
    return unitary @ np.diag(phases.conj())


def _random_channel(
    rng: np.random.Generator,
    input_dim: int,
    output_dim: int,
    kraus_rank: int,
) -> tuple[np.ndarray, ...]:
    raw = rng.normal(size=(kraus_rank * output_dim, input_dim)) + 1j * rng.normal(
        size=(kraus_rank * output_dim, input_dim)
    )
    isometry, _ = np.linalg.qr(raw, mode="reduced")
    return tuple(
        isometry[index * output_dim : (index + 1) * output_dim, :]
        for index in range(kraus_rank)
    )


def _random_full_rank_state(rng: np.random.Generator, dim: int) -> np.ndarray:
    raw = rng.normal(size=(dim, dim)) + 1j * rng.normal(size=(dim, dim))
    matrix = raw @ raw.conj().T + 0.5 * np.eye(dim, dtype=complex)
    return matrix / np.trace(matrix).real


def _generated_cptp_model(seed: int) -> FiniteControlModel:
    rng = np.random.default_rng(seed)
    dim = 2
    actions = (
        Action(
            name="continue",
            codeword="0",
            successor="s",
            continue_kraus={("q", "q"): _random_channel(rng, dim, dim, kraus_rank=3)},
        ),
        Action(
            name="halt-left",
            codeword="10",
            successor=None,
            halt_kraus={"q": _random_channel(rng, dim, dim, kraus_rank=3)},
        ),
        Action(
            name="halt-right",
            codeword="11",
            successor=None,
            halt_kraus={"q": _random_channel(rng, dim, dim, kraus_rank=3)},
        ),
    )
    return FiniteControlModel(
        syntax_states=("s",),
        control_dims={"q": dim},
        actions_by_syntax={"s": actions},
        start_syntax="s",
        initial_blocks={"q": _random_full_rank_state(rng, dim)},
        output_dim=dim,
        reference_state=_random_full_rank_state(rng, dim),
        name=f"generated-cptp-{seed}",
        scope_note="deterministic generated-model cross-validation fixture",
    )


def _basis_transformed_model(
    model: FiniteControlModel,
    control_unitaries: dict[str, np.ndarray],
    output_unitary: np.ndarray,
) -> FiniteControlModel:
    actions_by_syntax: dict[str, tuple[Action, ...]] = {}
    for syntax_state, actions in model.actions_by_syntax.items():
        transformed_actions = []
        for action in actions:
            continuing = {
                (source, target): tuple(
                    control_unitaries[target]
                    @ matrix
                    @ control_unitaries[source].conj().T
                    for matrix in kraus
                )
                for (source, target), kraus in action.continue_kraus.items()
            }
            halting = {
                source: tuple(
                    output_unitary @ matrix @ control_unitaries[source].conj().T
                    for matrix in kraus
                )
                for source, kraus in action.halt_kraus.items()
            }
            transformed_actions.append(
                Action(
                    name=action.name,
                    codeword=action.codeword,
                    successor=action.successor,
                    continue_kraus=continuing,
                    halt_kraus=halting,
                )
            )
        actions_by_syntax[syntax_state] = tuple(transformed_actions)
    return FiniteControlModel(
        syntax_states=model.syntax_states,
        control_dims=dict(model.control_dims),
        actions_by_syntax=actions_by_syntax,
        start_syntax=model.start_syntax,
        initial_blocks={
            key: control_unitaries[key] @ value @ control_unitaries[key].conj().T
            for key, value in model.initial_blocks.items()
        },
        output_dim=model.output_dim,
        reference_state=(
            output_unitary @ model.reference_state @ output_unitary.conj().T
        ),
        name=f"{model.name}-basis-transformed",
        scope_note=model.scope_note,
    )


def _basis_change_matrix(
    model: FiniteControlModel, control_unitaries: dict[str, np.ndarray]
) -> np.ndarray:
    keys, slices = block_slices(model)
    size = sum(model.control_dims[key[1]] ** 2 for key in keys)
    matrix = np.zeros((size, size), dtype=complex)
    for key in keys:
        dim = model.control_dims[key[1]]
        unitary = control_unitaries[key[1]]
        for row in range(dim):
            for column in range(dim):
                basis = np.zeros((dim, dim), dtype=complex)
                basis[row, column] = 1.0
                transformed = unitary @ basis @ unitary.conj().T
                local_column = row + column * dim
                matrix[slices[key], slices[key].start + local_column] = (
                    transformed.reshape(-1, order="F")
                )
    return matrix


def _output_basis_change_matrix(unitary: np.ndarray) -> np.ndarray:
    dim = unitary.shape[0]
    matrix = np.zeros((dim * dim, dim * dim), dtype=complex)
    for row in range(dim):
        for column in range(dim):
            basis = np.zeros((dim, dim), dtype=complex)
            basis[row, column] = 1.0
            local_column = row + column * dim
            matrix[:, local_column] = (unitary @ basis @ unitary.conj().T).reshape(
                -1, order="F"
            )
    return matrix


def _basis_transformed_potential(
    certificate: ReferencePotentialCertificate,
    control_unitaries: dict[str, np.ndarray],
) -> ReferencePotentialCertificate:
    return ReferencePotentialCertificate(
        theta={
            key: control_unitaries[key[1]] @ value @ control_unitaries[key[1]].conj().T
            for key, value in certificate.theta.items()
        },
        a=dict(certificate.a),
        transition_coefficients=dict(certificate.transition_coefficients),
        halt_coefficients=dict(certificate.halt_coefficients),
        potential=dict(certificate.potential),
        name=f"{certificate.name} under basis change",
    )


def _basis_transformed_bellman(
    certificate: BellmanChoiCertificate,
    control_unitaries: dict[str, np.ndarray],
    output_unitary: np.ndarray,
) -> BellmanChoiCertificate:
    """Transport H.3 proof objects in the input-tensor-output convention."""
    envelopes = {}
    for key, value in certificate.choi_envelopes.items():
        change = np.kron(control_unitaries[key[1]].conj(), output_unitary)
        envelopes[key] = change @ value @ change.conj().T
    return BellmanChoiCertificate(
        choi_envelopes=envelopes,
        constant=certificate.constant,
        name=f"{certificate.name} under basis change",
    )


def _compare_gain_cost(
    left: GainCostReport, right: GainCostReport, *, numerical_transform: bool = False
) -> None:
    if numerical_transform and left.outcome is CheckOutcome.PASS:
        assert right.outcome in {CheckOutcome.PASS, CheckOutcome.INCONCLUSIVE}
    else:
        assert left.outcome is right.outcome
    assert left.fixed_model_initial_constant == pytest.approx(
        right.fixed_model_initial_constant, abs=ATOL
    )
    left_syntax = {report.syntax_state: report for report in left.syntax_reports}
    right_syntax = {report.syntax_state: report for report in right.syntax_reports}
    assert left_syntax.keys() == right_syntax.keys()
    for syntax_state, first in left_syntax.items():
        second = right_syntax[syntax_state]
        if numerical_transform and second.current_outcome is CheckOutcome.INCONCLUSIVE:
            assert second.current_weighted_sum == pytest.approx(1.0, abs=ATOL)
            assert second.current_weighted_sum_upper > 1
            assert not second.current_condition_satisfied
            assert right.constant is None
        else:
            assert (
                first.current_condition_satisfied is second.current_condition_satisfied
            )
        assert (
            first.suggested_condition_satisfied is second.suggested_condition_satisfied
        )
        assert first.current_weighted_sum == pytest.approx(
            second.current_weighted_sum, abs=ATOL
        )
        if numerical_transform:
            # Integer code lengths can increase when transformed binary inputs
            # no longer resolve equality; both completions must remain sound.
            assert first.suggested_weighted_sum_upper <= 1
            assert second.suggested_weighted_sum_upper <= 1
        else:
            assert first.suggested_weighted_sum == pytest.approx(
                second.suggested_weighted_sum, abs=ATOL
            )
        first_actions = {action.action_name: action for action in first.actions}
        second_actions = {action.action_name: action for action in second.actions}
        assert first_actions.keys() == second_actions.keys()
        for action_name, first_action in first_actions.items():
            assert first_action.reference_gain == pytest.approx(
                second_actions[action_name].reference_gain, abs=ATOL
            )


def _rename_model(
    model: FiniteControlModel,
    syntax_names: dict[str, str],
    control_names: dict[str, str],
    action_names: dict[str, str],
) -> FiniteControlModel:
    actions_by_syntax = {}
    for syntax_state in reversed(model.syntax_states):
        renamed_actions = []
        for action in reversed(model.actions_by_syntax[syntax_state]):
            renamed_actions.append(
                Action(
                    name=action_names[action.name],
                    codeword=action.codeword,
                    successor=(
                        syntax_names[action.successor]
                        if action.successor is not None
                        else None
                    ),
                    continue_kraus={
                        (control_names[source], control_names[target]): kraus
                        for (source, target), kraus in reversed(
                            tuple(action.continue_kraus.items())
                        )
                    },
                    halt_kraus={
                        control_names[source]: kraus
                        for source, kraus in reversed(tuple(action.halt_kraus.items()))
                    },
                )
            )
        actions_by_syntax[syntax_names[syntax_state]] = tuple(renamed_actions)
    return FiniteControlModel(
        syntax_states=tuple(
            syntax_names[state] for state in reversed(model.syntax_states)
        ),
        control_dims={
            control_names[control]: model.control_dims[control]
            for control in reversed(tuple(model.control_dims))
        },
        actions_by_syntax=actions_by_syntax,
        start_syntax=syntax_names[model.start_syntax],
        initial_blocks={
            control_names[control]: value.copy()
            for control, value in reversed(tuple(model.initial_blocks.items()))
        },
        output_dim=model.output_dim,
        reference_state=model.reference_state.copy(),
        name=f"{model.name}-fully-renamed",
        scope_note=model.scope_note,
    )


def _rename_key(
    key: BlockKey, syntax_names: dict[str, str], control_names: dict[str, str]
) -> BlockKey:
    return syntax_names[key[0]], control_names[key[1]]


def _rename_potential(
    certificate: ReferencePotentialCertificate,
    syntax_names: dict[str, str],
    control_names: dict[str, str],
) -> ReferencePotentialCertificate:
    rename = lambda key: _rename_key(key, syntax_names, control_names)
    return ReferencePotentialCertificate(
        theta={rename(key): value for key, value in certificate.theta.items()},
        a={rename(key): value for key, value in certificate.a.items()},
        transition_coefficients={
            (rename(source), rename(target)): value
            for (source, target), value in certificate.transition_coefficients.items()
        },
        halt_coefficients={
            rename(key): value for key, value in certificate.halt_coefficients.items()
        },
        potential={rename(key): value for key, value in certificate.potential.items()},
        name=f"{certificate.name} under relabeling",
    )


def _rename_bellman(
    certificate: BellmanChoiCertificate,
    syntax_names: dict[str, str],
    control_names: dict[str, str],
) -> BellmanChoiCertificate:
    return BellmanChoiCertificate(
        choi_envelopes={
            _rename_key(key, syntax_names, control_names): value
            for key, value in certificate.choi_envelopes.items()
        },
        constant=certificate.constant,
        name=f"{certificate.name} under relabeling",
    )


def _relabeling_permutation(
    model: FiniteControlModel,
    renamed: FiniteControlModel,
    syntax_names: dict[str, str],
    control_names: dict[str, str],
) -> np.ndarray:
    old_keys, old_slices = block_slices(model)
    _, new_slices = block_slices(renamed)
    size = sum(model.control_dims[key[1]] ** 2 for key in old_keys)
    permutation = np.zeros((size, size), dtype=complex)
    for key in old_keys:
        renamed_key = _rename_key(key, syntax_names, control_names)
        width = model.control_dims[key[1]] ** 2
        for index in range(width):
            permutation[
                new_slices[renamed_key].start + index,
                old_slices[key].start + index,
            ] = 1.0
    return permutation


def test_kraus_representation_invariance_on_supplied_certificates() -> None:
    model = make_multiblock_rectangular_model()
    mixed = _kraus_mixed_model(model)
    require_valid_model(mixed)

    for depth in range(1, 9):
        original = depth_contribution_by_enumeration(model, depth)
        assert np.allclose(
            original,
            depth_contribution_by_enumeration(mixed, depth),
            atol=ATOL,
            rtol=0.0,
        )
        assert np.allclose(
            original,
            depth_contribution_by_maps(mixed, depth),
            atol=ATOL,
            rtol=0.0,
        )

    assert np.allclose(
        transient_matrix(model), transient_matrix(mixed), atol=ATOL, rtol=0.0
    )
    assert np.allclose(halt_matrix(model), halt_matrix(mixed), atol=ATOL, rtol=0.0)
    assert np.allclose(
        truncated_semidensity(model, 20),
        truncated_semidensity(mixed, 20),
        atol=ATOL,
        rtol=0.0,
    )

    original_fixed = linear_fixed_point(model)
    mixed_fixed = linear_fixed_point(mixed)
    assert original_fixed.applicable and mixed_fixed.applicable
    assert original_fixed.output is not None and mixed_fixed.output is not None
    assert original_fixed.spectral_radius == pytest.approx(
        mixed_fixed.spectral_radius, abs=ATOL
    )
    assert np.allclose(original_fixed.output, mixed_fixed.output, atol=ATOL, rtol=0.0)
    original_constant = minimum_domination_constant(
        original_fixed.output, model.reference_state
    )
    mixed_constant = minimum_domination_constant(
        mixed_fixed.output, mixed.reference_state
    )
    assert original_constant.constant == pytest.approx(
        mixed_constant.constant, abs=ATOL
    )

    bellman = make_multiblock_bellman_choi_certificate(model)
    assert verify_bellman_choi(model, bellman).outcome is CheckOutcome.PASS
    assert verify_bellman_choi(mixed, bellman).outcome is CheckOutcome.PASS
    potential = make_multiblock_reference_potential_certificate()
    original_potential = verify_reference_potential(model, potential)
    mixed_potential = verify_reference_potential(mixed, potential)
    assert original_potential.outcome is mixed_potential.outcome is CheckOutcome.PASS
    assert original_potential.constant == pytest.approx(
        mixed_potential.constant, abs=ATOL
    )
    _compare_gain_cost(
        analyze_reference_gain_cost(model, potential.theta),
        analyze_reference_gain_cost(mixed, potential.theta),
        numerical_transform=True,
    )


def test_global_basis_change_is_covariant() -> None:
    model = make_dephase_or_halt_model()
    rng = np.random.default_rng(240513)
    control_unitaries = {"q": _random_unitary(rng, 2)}
    output_unitary = _random_unitary(rng, 2)
    transformed = _basis_transformed_model(model, control_unitaries, output_unitary)
    require_valid_model(transformed)

    transient_change = _basis_change_matrix(model, control_unitaries)
    output_change = _output_basis_change_matrix(output_unitary)
    assert np.allclose(
        transient_matrix(transformed),
        transient_change @ transient_matrix(model) @ transient_change.conj().T,
        atol=ATOL,
        rtol=0.0,
    )
    assert np.allclose(
        halt_matrix(transformed),
        output_change @ halt_matrix(model) @ transient_change.conj().T,
        atol=ATOL,
        rtol=0.0,
    )

    for depth in range(1, 9):
        expected = (
            output_unitary
            @ depth_contribution_by_maps(model, depth)
            @ output_unitary.conj().T
        )
        assert np.allclose(
            depth_contribution_by_enumeration(transformed, depth),
            expected,
            atol=ATOL,
            rtol=0.0,
        )
        assert np.allclose(
            depth_contribution_by_maps(transformed, depth),
            expected,
            atol=ATOL,
            rtol=0.0,
        )

    original_fixed = linear_fixed_point(model)
    transformed_fixed = linear_fixed_point(transformed)
    assert original_fixed.applicable and transformed_fixed.applicable
    assert original_fixed.output is not None and transformed_fixed.output is not None
    expected_output = output_unitary @ original_fixed.output @ output_unitary.conj().T
    assert np.allclose(transformed_fixed.output, expected_output, atol=ATOL, rtol=0.0)
    assert np.trace(original_fixed.output).real == pytest.approx(
        np.trace(transformed_fixed.output).real, abs=ATOL
    )
    assert original_fixed.spectral_radius == pytest.approx(
        transformed_fixed.spectral_radius, abs=ATOL
    )
    original_constant = minimum_domination_constant(
        original_fixed.output, model.reference_state
    )
    transformed_constant = minimum_domination_constant(
        transformed_fixed.output, transformed.reference_state
    )
    assert original_constant.constant == pytest.approx(
        transformed_constant.constant, abs=ATOL
    )

    original_bellman = make_dephase_bellman_choi_certificate(model)
    transformed_bellman = BellmanChoiCertificate(
        choi_envelopes=linear_value_choi_envelopes(transformed),
        constant=original_bellman.constant,
        name="minimum Bellman-Choi certificate under basis change",
    )
    assert verify_bellman_choi(model, original_bellman).outcome is CheckOutcome.PASS
    assert (
        verify_bellman_choi(transformed, transformed_bellman).outcome
        is CheckOutcome.PASS
    )

    original_potential = make_dephase_reference_potential_certificates(model)[0]
    transformed_potential = _basis_transformed_potential(
        original_potential, control_unitaries
    )
    first_report = verify_reference_potential(model, original_potential)
    second_report = verify_reference_potential(transformed, transformed_potential)
    assert first_report.outcome is second_report.outcome is CheckOutcome.PASS
    assert first_report.constant == pytest.approx(second_report.constant, abs=ATOL)
    _compare_gain_cost(
        analyze_reference_gain_cost(model, original_potential.theta),
        analyze_reference_gain_cost(transformed, transformed_potential.theta),
        numerical_transform=True,
    )


def test_supplied_bellman_choi_certificate_transforms_covariantly() -> None:
    model = make_multiblock_rectangular_model()
    rng = np.random.default_rng(240514)
    control_unitaries = {
        control: _random_unitary(rng, dim)
        for control, dim in model.control_dims.items()
    }
    output_unitary = _random_unitary(rng, model.output_dim)
    transformed = _basis_transformed_model(model, control_unitaries, output_unitary)
    require_valid_model(transformed)

    original = make_multiblock_bellman_choi_certificate(model)
    transported = _basis_transformed_bellman(
        original, control_unitaries, output_unitary
    )
    assert verify_bellman_choi(model, original).outcome is CheckOutcome.PASS
    assert verify_bellman_choi(transformed, transported).outcome is CheckOutcome.PASS

    regenerated = linear_value_choi_envelopes(transformed)
    assert transported.choi_envelopes.keys() == regenerated.keys()
    for key, value in transported.choi_envelopes.items():
        assert np.allclose(value, regenerated[key], atol=ATOL, rtol=0.0)


def test_complete_relabeling_and_reordering_is_invariant() -> None:
    model = make_multiblock_rectangular_model()
    syntax_names = {"s0": "node-z", "s1": "node-a"}
    control_names = {"q1": "wire-z", "q2": "wire-a"}
    action_names = {
        action.name: f"renamed-{index}"
        for index, action in enumerate(
            action
            for syntax_state in model.syntax_states
            for action in model.actions_by_syntax[syntax_state]
        )
    }
    renamed = _rename_model(model, syntax_names, control_names, action_names)
    require_valid_model(renamed)

    permutation = _relabeling_permutation(model, renamed, syntax_names, control_names)
    assert np.allclose(
        transient_matrix(renamed),
        permutation @ transient_matrix(model) @ permutation.T,
        atol=ATOL,
        rtol=0.0,
    )
    assert np.allclose(
        halt_matrix(renamed),
        halt_matrix(model) @ permutation.T,
        atol=ATOL,
        rtol=0.0,
    )
    for depth in range(1, 9):
        assert np.allclose(
            depth_contribution_by_enumeration(model, depth),
            depth_contribution_by_enumeration(renamed, depth),
            atol=ATOL,
            rtol=0.0,
        )

    original_fixed = linear_fixed_point(model)
    renamed_fixed = linear_fixed_point(renamed)
    assert original_fixed.output is not None and renamed_fixed.output is not None
    assert np.allclose(original_fixed.output, renamed_fixed.output, atol=ATOL, rtol=0.0)
    original_constant = minimum_domination_constant(
        original_fixed.output, model.reference_state
    )
    renamed_constant = minimum_domination_constant(
        renamed_fixed.output, renamed.reference_state
    )
    assert original_constant.constant == pytest.approx(
        renamed_constant.constant, abs=ATOL
    )

    bellman = make_multiblock_bellman_choi_certificate(model)
    renamed_bellman = _rename_bellman(bellman, syntax_names, control_names)
    assert verify_bellman_choi(model, bellman).outcome is CheckOutcome.PASS
    assert verify_bellman_choi(renamed, renamed_bellman).outcome is CheckOutcome.PASS
    potential = make_multiblock_reference_potential_certificate()
    renamed_potential = _rename_potential(potential, syntax_names, control_names)
    first_report = verify_reference_potential(model, potential)
    second_report = verify_reference_potential(renamed, renamed_potential)
    assert first_report.outcome is second_report.outcome is CheckOutcome.PASS
    assert first_report.constant == pytest.approx(second_report.constant, abs=ATOL)

    original_gain_cost = analyze_reference_gain_cost(model, potential.theta)
    renamed_gain_cost = analyze_reference_gain_cost(renamed, renamed_potential.theta)
    assert original_gain_cost.outcome is renamed_gain_cost.outcome
    assert original_gain_cost.fixed_model_initial_constant == pytest.approx(
        renamed_gain_cost.fixed_model_initial_constant, abs=ATOL
    )
    original_syntax = {
        syntax_names[item.syntax_state]: item
        for item in original_gain_cost.syntax_reports
    }
    renamed_syntax = {
        item.syntax_state: item for item in renamed_gain_cost.syntax_reports
    }
    assert original_syntax.keys() == renamed_syntax.keys()
    for syntax_state, first in original_syntax.items():
        second = renamed_syntax[syntax_state]
        assert first.current_condition_satisfied is second.current_condition_satisfied
        assert (
            first.suggested_condition_satisfied is second.suggested_condition_satisfied
        )
        assert first.current_weighted_sum == pytest.approx(
            second.current_weighted_sum, abs=ATOL
        )
        assert first.suggested_weighted_sum == pytest.approx(
            second.suggested_weighted_sum, abs=ATOL
        )
        assert sorted(
            action.reference_gain for action in first.actions
        ) == pytest.approx(
            sorted(action.reference_gain for action in second.actions), abs=ATOL
        )


@pytest.mark.parametrize("seed", range(10))
def test_generated_cptp_models_cross_validate_paths_and_fixed_point(seed: int) -> None:
    model = _generated_cptp_model(seed)
    require_valid_model(model)
    for depth in range(1, 9):
        assert np.allclose(
            depth_contribution_by_enumeration(model, depth),
            depth_contribution_by_maps(model, depth),
            atol=ATOL,
            rtol=0.0,
        )

    fixed = linear_fixed_point(model)
    assert fixed.applicable
    assert fixed.output is not None
    assert fixed.spectral_radius == pytest.approx(0.5, abs=ATOL)
    assert np.allclose(
        truncated_semidensity(model, 40), fixed.output, atol=2e-12, rtol=0.0
    )
    assert np.trace(fixed.output).real == pytest.approx(1.0, abs=ATOL)
    constant = minimum_domination_constant(fixed.output, model.reference_state)
    assert constant.outcome is CheckOutcome.PASS
    assert np.isfinite(constant.constant)

    mixed = _kraus_mixed_model(model)
    mixed_fixed = linear_fixed_point(mixed)
    assert mixed_fixed.output is not None
    assert np.allclose(
        transient_matrix(model), transient_matrix(mixed), atol=ATOL, rtol=0.0
    )
    assert np.allclose(halt_matrix(model), halt_matrix(mixed), atol=ATOL, rtol=0.0)
    assert np.allclose(fixed.output, mixed_fixed.output, atol=ATOL, rtol=0.0)
    mixed_constant = minimum_domination_constant(
        mixed_fixed.output, mixed.reference_state
    )
    assert constant.constant == pytest.approx(mixed_constant.constant, abs=ATOL)

    rng = np.random.default_rng(seed + 10_000)
    control_unitaries = {"q": _random_unitary(rng, 2)}
    output_unitary = _random_unitary(rng, 2)
    transformed = _basis_transformed_model(model, control_unitaries, output_unitary)
    transformed_fixed = linear_fixed_point(transformed)
    assert transformed_fixed.output is not None
    assert transformed_fixed.spectral_radius == pytest.approx(
        fixed.spectral_radius, abs=ATOL
    )
    assert np.allclose(
        transformed_fixed.output,
        output_unitary @ fixed.output @ output_unitary.conj().T,
        atol=ATOL,
        rtol=0.0,
    )
    transformed_constant = minimum_domination_constant(
        transformed_fixed.output, transformed.reference_state
    )
    assert constant.constant == pytest.approx(transformed_constant.constant, abs=ATOL)
