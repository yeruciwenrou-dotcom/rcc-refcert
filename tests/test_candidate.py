from copy import deepcopy

import numpy as np
import pytest

from rcc_refcert.bellman_choi import verify_bellman_choi
from rcc_refcert.candidate import prepare_bellman_choi
from rcc_refcert.examples import (
    make_dark_nonhalting_loop_model,
    make_dephase_or_halt_model,
    make_multiblock_rectangular_model,
)
from rcc_refcert.limits import ComputationLimits
from rcc_refcert.status import CheckOutcome


@pytest.mark.parametrize(
    "factory,expected",
    [(make_dephase_or_halt_model, 1.0), (make_multiblock_rectangular_model, 15 / 14)],
)
def test_linear_candidates_match_analytic_models_and_require_verification(
    factory, expected
):
    model = factory()
    result = prepare_bellman_choi(model)
    assert result.status == "candidate_ready"
    assert result.certificate.constant == pytest.approx(expected)
    report = verify_bellman_choi(model, result.certificate)
    assert report.outcome is CheckOutcome.PASS
    assert report.constant >= result.certificate.constant
    damaged = deepcopy(result.certificate)
    damaged.constant *= 0.9
    assert verify_bellman_choi(model, damaged).outcome is CheckOutcome.FAIL


def test_candidate_constant_uses_declared_nonuniform_reference():
    model = make_dephase_or_halt_model()
    model.reference_state = np.diag([0.8, 0.2])
    result = prepare_bellman_choi(model)
    assert result.status == "candidate_ready"
    assert result.certificate.constant == pytest.approx(2.5)
    assert verify_bellman_choi(model, result.certificate).outcome is CheckOutcome.PASS


def test_preparation_distinguishes_invalid_dark_and_resource_cases():
    invalid = make_dephase_or_halt_model()
    invalid.actions_by_syntax["s"][0].codeword = "nonbinary"
    assert prepare_bellman_choi(invalid).status == "invalid_model"
    dark = prepare_bellman_choi(make_dark_nonhalting_loop_model())
    assert dark.status == "not_applicable"
    assert dark.certificate is None
    limited = prepare_bellman_choi(
        make_dephase_or_halt_model(), limits=ComputationLimits(max_matrix_elements=1)
    )
    assert limited.status == "resource_limit"
    assert limited.certificate is None
    assert limited.resource_estimate["dense_matrix_elements"] > 1


def test_unresolved_solver_has_no_candidate_and_does_not_retry(monkeypatch):
    import rcc_refcert.candidate as module

    calls = []

    def unresolved(model, *, tol, limits):
        calls.append(tol)
        raise np.linalg.LinAlgError("singular numerical solve")

    monkeypatch.setattr(module, "linear_value_choi_envelopes", unresolved)
    result = prepare_bellman_choi(make_dephase_or_halt_model(), tol=1e-12)
    assert result.status == "inconclusive"
    assert result.certificate is None
    assert calls == [1e-12]


def test_bad_tolerance_remains_a_call_error():
    with pytest.raises(ValueError, match="tol"):
        prepare_bellman_choi(make_dephase_or_halt_model(), tol=0)
