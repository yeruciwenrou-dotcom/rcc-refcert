from copy import deepcopy

import pytest

from rcc_refcert.bellman_choi import BellmanChoiCertificate, verify_bellman_choi
from rcc_refcert.bounds import BudgetError, load_template, with_reference_certificate
from rcc_refcert.bounds.terminal_model import build_terminal_model
from rcc_refcert.fixed_point import linear_value_choi_envelopes
from rcc_refcert.limits import (
    ComputationLimits,
    ResourceLimitError,
    check_certificate_budget,
    estimate_certificate_resources,
)
from rcc_refcert.reference_potential import (
    ReferencePotentialCertificate,
    verify_reference_potential,
)
from rcc_refcert.status import CheckOutcome


def inputs(method):
    model = build_terminal_model()
    if method == "H.3":
        certificate = BellmanChoiCertificate(linear_value_choi_envelopes(model), 1.0)
        verifier = verify_bellman_choi
    else:
        key = ("s", "q")
        certificate = ReferencePotentialCertificate(
            theta={key: model.reference_state},
            a={key: 1.0},
            transition_coefficients={},
            halt_coefficients={key: 1.0},
            potential={key: 1.0},
        )
        verifier = verify_reference_potential
    return model, certificate, verifier


@pytest.mark.parametrize("method", ["H.3", "H.4"])
def test_identical_admission_threshold_for_direct_and_bound_entry(method):
    model, certificate, verifier = inputs(method)
    estimate = estimate_certificate_resources(model, certificate)
    threshold = estimate["estimated_elements"]
    assert estimate["route"] == method
    limited = ComputationLimits(max_matrix_elements=threshold - 1)
    with pytest.raises(ResourceLimitError) as error:
        verifier(model, certificate, limits=limited)
    assert error.value.estimate == threshold
    with pytest.raises(BudgetError, match=str(threshold)):
        with_reference_certificate(
            load_template()["task"], model, certificate, source="test", limits=limited
        )
    admitted = ComputationLimits(max_matrix_elements=threshold)
    assert check_certificate_budget(model, certificate, admitted) == estimate
    assert verifier(model, certificate, limits=admitted).outcome is CheckOutcome.PASS
    task = with_reference_certificate(
        load_template()["task"], model, certificate, source="test", limits=admitted
    )
    assert task["model"]["reference_domination"]["evidence"]["outcome"] == "pass"


@pytest.mark.parametrize("method", ["H.3", "H.4"])
def test_resource_guard_precedes_validation_and_input_hashing(method, monkeypatch):
    import rcc_refcert.bellman_choi as h3
    import rcc_refcert.bounds.certificates as binding
    import rcc_refcert.reference_potential as h4

    model, certificate, verifier = inputs(method)

    def unexpected(*args, **kwargs):
        raise AssertionError("resource guard ran too late")

    monkeypatch.setattr(
        h3 if method == "H.3" else h4, "require_valid_model", unexpected
    )
    monkeypatch.setattr(binding, "_snapshot", unexpected)
    tiny = ComputationLimits(max_matrix_elements=1)
    with pytest.raises(ResourceLimitError):
        verifier(model, certificate, limits=tiny)
    with pytest.raises(BudgetError):
        with_reference_certificate(
            load_template()["task"], model, certificate, source="test", limits=tiny
        )


def test_declared_shape_is_preflighted_without_constructing_the_shape():
    model, certificate, verifier = inputs("H.4")
    huge = deepcopy(model)
    huge.control_dims["q"] = 10**100
    with pytest.raises(ResourceLimitError):
        verifier(huge, certificate)
