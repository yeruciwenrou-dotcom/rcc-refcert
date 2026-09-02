from copy import deepcopy

import numpy as np

from rcc_refcert.examples import (
    make_multiblock_rectangular_model,
    make_multiblock_reference_potential_certificate,
)
from rcc_refcert.fixed_point import linear_fixed_point
from rcc_refcert.model import require_valid_model
from rcc_refcert.reference_potential import verify_reference_potential
from rcc_refcert.semantics import (
    depth_contribution_by_enumeration,
    depth_contribution_by_maps,
    halt_matrix,
    transient_matrix,
    truncated_semidensity,
)
from rcc_refcert.status import CheckOutcome


def test_multiblock_rectangular_realization_and_fixed_point() -> None:
    model = make_multiblock_rectangular_model()
    require_valid_model(model)
    assert model.transient_keys() == (
        ("s0", "q1"),
        ("s0", "q2"),
        ("s1", "q1"),
        ("s1", "q2"),
    )
    for depth in range(1, 9):
        enumerated = depth_contribution_by_enumeration(model, depth)
        mapped = depth_contribution_by_maps(model, depth)
        assert np.allclose(enumerated, mapped, atol=1e-12, rtol=0.0)

    assert transient_matrix(model).shape == (10, 10)
    assert halt_matrix(model).shape == (4, 10)
    fixed = linear_fixed_point(model)
    assert fixed.applicable
    assert fixed.output is not None
    expected = np.diag([9.0 / 28.0, 15.0 / 28.0]).astype(complex)
    assert np.allclose(fixed.output, expected, atol=1e-12, rtol=0.0)
    assert abs(np.trace(fixed.output).real - 6.0 / 7.0) < 1e-12
    error_at_20 = np.linalg.norm(truncated_semidensity(model, 20) - fixed.output, ord=2)
    error_at_30 = np.linalg.norm(truncated_semidensity(model, 30) - fixed.output, ord=2)
    assert error_at_30 < error_at_20
    assert error_at_30 < 1e-12


def test_matrix_realization_is_independent_of_declaration_order() -> None:
    model = make_multiblock_rectangular_model()
    reordered = deepcopy(model)
    reordered.syntax_states = ("s0", "s1")
    reordered.control_dims = {"q1": 1, "q2": 2}
    reordered.actions_by_syntax = {
        "s0": reordered.actions_by_syntax["s0"],
        "s1": reordered.actions_by_syntax["s1"],
    }
    require_valid_model(reordered)
    assert model.transient_keys() == reordered.transient_keys()
    assert np.allclose(
        transient_matrix(model), transient_matrix(reordered), atol=1e-12, rtol=0.0
    )
    assert np.allclose(halt_matrix(model), halt_matrix(reordered), atol=1e-12, rtol=0.0)


def test_multiblock_reference_potential_certificate() -> None:
    model = make_multiblock_rectangular_model()
    report = verify_reference_potential(
        model, make_multiblock_reference_potential_certificate()
    )
    assert report.outcome == CheckOutcome.PASS
    assert report.constant is not None
    assert abs(report.constant - 4.0 / 3.0) < 1e-12
