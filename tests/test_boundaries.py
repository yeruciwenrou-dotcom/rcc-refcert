import numpy as np
import pytest

from rcc_refcert.examples import (
    global_reset_family_constants,
    make_dark_nonhalting_loop_model,
    make_incomplete_instrument_model,
    make_invalid_prefix_model,
    make_rank_deficient_reference_model,
)
from rcc_refcert.fixed_point import linear_fixed_point
from rcc_refcert.model import Action, ModelValidationError, require_valid_model
from rcc_refcert.quantum import identity_kraus
from rcc_refcert.semantics import (
    depth_contribution_by_enumeration,
    depth_contribution_by_maps,
    truncated_semidensity,
)


def test_prefix_conflict_is_rejected() -> None:
    with pytest.raises(ModelValidationError, match="prefix"):
        require_valid_model(make_invalid_prefix_model())


def test_incomplete_instrument_is_rejected() -> None:
    with pytest.raises(ModelValidationError, match="trace preserving"):
        require_valid_model(make_incomplete_instrument_model())


def test_global_reset_family_exposes_nonuniform_growth() -> None:
    constants = global_reset_family_constants(8)
    assert constants == [(n, 2**n) for n in range(1, 9)]
    assert constants[-1][1] > constants[0][1]


def test_dark_nonhalting_sector_does_not_require_linear_inverse() -> None:
    model = make_dark_nonhalting_loop_model()
    require_valid_model(model)
    for depth in range(1, 5):
        assert np.allclose(depth_contribution_by_enumeration(model, depth), 0.0)
        assert np.allclose(depth_contribution_by_maps(model, depth), 0.0)
    assert np.allclose(truncated_semidensity(model, 5), 0.0)
    result = linear_fixed_point(model)
    assert not result.applicable
    assert abs(result.spectral_radius - 1.0) < 1e-12


def test_rank_deficient_reference_requires_support_reduction() -> None:
    with pytest.raises(ModelValidationError, match="full rank"):
        require_valid_model(make_rank_deficient_reference_model())


def test_undeclared_control_branch_is_rejected_at_preflight() -> None:
    model = make_dark_nonhalting_loop_model()
    model.actions_by_syntax["s"] = (
        Action(
            name="bad-source-branch",
            codeword="0",
            successor="s",
            continue_kraus={
                ("q", "q"): identity_kraus(2),
                ("ghost", "q"): identity_kraus(2),
            },
        ),
        model.actions_by_syntax["s"][1],
    )
    with pytest.raises(ModelValidationError, match="source 'ghost' is undeclared"):
        require_valid_model(model)


def test_boolean_dimension_and_invalid_tolerance_are_rejected() -> None:
    model = make_dark_nonhalting_loop_model()
    model.output_dim = True
    with pytest.raises(ModelValidationError, match="output dimension"):
        require_valid_model(model)

    model = make_dark_nonhalting_loop_model()
    with pytest.raises(ValueError, match="finite and positive"):
        require_valid_model(model, tol=0.0)


def test_syntax_state_requires_an_action() -> None:
    model = make_dark_nonhalting_loop_model()
    model.actions_by_syntax["s"] = ()
    with pytest.raises(ModelValidationError, match="at least one action"):
        require_valid_model(model)
