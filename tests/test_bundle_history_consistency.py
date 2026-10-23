"""Reject digest-correct contradictory history without changing matrix evidence."""

import json
from copy import deepcopy

import pytest

from rcc_refcert import ReferencePotentialCertificate, prepare_bellman_choi
from rcc_refcert.bounds import InputError
from rcc_refcert.bounds.terminal_model import build_terminal_model
from rcc_refcert.bundle import (
    inspect_analysis_bundle,
    save_analysis_bundle,
    verify_analysis_bundle,
)
from rcc_refcert.bundle_storage import load_bundle_payload, save_bundle_payload
from rcc_refcert.cli import main


@pytest.fixture(params=["H.3", "H.4"])
def proof(request):
    model = build_terminal_model()
    key = ("s", "q")
    certificate = (
        prepare_bellman_choi(model).certificate
        if request.param == "H.3"
        else ReferencePotentialCertificate(
            theta={key: model.reference_state.copy()},
            a={key: 1.0},
            transition_coefficients={},
            halt_coefficients={key: 1.0},
            potential={key: 1.0},
        )
    )
    return model, certificate


@pytest.mark.parametrize(
    "mutation",
    [
        "failed_check",
        "unresolved_check",
        "skipped_check",
        "empty_checks",
        "unsupported_failure",
        "unsupported_inconclusive",
        "missing_candidate",
        "candidate_above_bound",
        "negative_error",
        "nonfinite_error",
    ],
)
def test_digest_correct_contradictions_are_rejected(
    proof, tmp_path, monkeypatch, mutation
):
    model, certificate = proof
    original = save_analysis_bundle(tmp_path / "original.rcc", model, certificate)
    payload = load_bundle_payload(original)
    history = payload.analysis["verification"]
    assert history["outcome"] == "pass"
    if mutation.endswith("_check"):
        history["checks"][0]["outcome"] = {
            "failed_check": "fail",
            "unresolved_check": "inconclusive",
            "skipped_check": "not_applicable",
        }[mutation]
    elif mutation == "empty_checks":
        history["checks"] = []
    elif mutation.startswith("unsupported_"):
        history["outcome"] = (
            "fail" if mutation == "unsupported_failure" else "inconclusive"
        )
        history["constant_exact"] = None
    elif mutation == "missing_candidate":
        history["candidate_constant_exact"] = None
    elif mutation == "candidate_above_bound":
        history["candidate_constant_exact"] = "100"
    elif mutation == "negative_error":
        history["constant_error_bound_exact"] = "-1"
    else:
        history["constant_error_bound_exact"] = "inf"
    changed = save_bundle_payload(
        tmp_path / "contradiction.rcc",
        payload.model,
        payload.certificate,
        analysis=payload.analysis,
    )
    # The storage loader accepts the newly computed digests and unchanged arrays.
    assert load_bundle_payload(changed).analysis == payload.analysis

    def unexpected_verification(*args, **kwargs):
        pytest.fail("contradictory history reached matrix verification")

    monkeypatch.setattr("rcc_refcert.bundle._verify", unexpected_verification)
    for reader in (inspect_analysis_bundle, verify_analysis_bundle):
        with pytest.raises(InputError):
            reader(changed)


@pytest.mark.parametrize("outcome", ["pass", "fail", "inconclusive"])
def test_actual_verifier_histories_remain_readable(proof, tmp_path, outcome):
    model, certificate = deepcopy(proof)
    tolerance = 1e-14 if outcome == "inconclusive" else 1e-10
    if outcome == "fail":
        if hasattr(certificate, "constant"):
            certificate.constant = 0.0
        else:
            certificate.potential[("s", "q")] = 0.0
    path = save_analysis_bundle(
        tmp_path / "diagnostic.rcc", model, certificate, tol=tolerance
    )
    original = path.read_bytes()
    inspected = inspect_analysis_bundle(path)
    verified = verify_analysis_bundle(path)
    assert inspected["record_consistency"] == "pass"
    assert inspected["historical_verification"]["outcome"] == outcome
    assert verified["fresh_verification"]["outcome"] == outcome
    assert verified["historical_results_supported"] is (
        True if outcome == "pass" else None
    )
    assert path.read_bytes() == original


def test_cli_rejects_contradiction_without_claiming_fresh_verification(
    proof, tmp_path, capsys
):
    model, certificate = proof
    path = save_analysis_bundle(tmp_path / "valid.rcc", model, certificate)
    payload = load_bundle_payload(path)
    payload.analysis["verification"]["checks"][0]["outcome"] = "fail"
    changed = save_bundle_payload(
        tmp_path / "contradiction.rcc", model, certificate, analysis=payload.analysis
    )
    for action in ("inspect", "verify"):
        assert main(["bundle", action, str(changed), "--format", "json"]) == 2
        result = json.loads(capsys.readouterr().out)
        assert result["state"] == "invalid_input"
        assert "fresh_verification" not in result


def test_source_revision_distinguishes_author_and_recipient(
    proof, tmp_path, monkeypatch
):
    model, certificate = proof
    author, recipient = "1" * 40, "2" * 40
    monkeypatch.setenv("RCC_REFCERT_SOURCE_REVISION", author)
    path = save_analysis_bundle(tmp_path / "revision.rcc", model, certificate)
    original = path.read_bytes()
    monkeypatch.setenv("RCC_REFCERT_SOURCE_REVISION", recipient)
    assert inspect_analysis_bundle(path)["producer"]["source_revision"] == author
    assert verify_analysis_bundle(path)["producer"]["source_revision"] == recipient
    monkeypatch.delenv("RCC_REFCERT_SOURCE_REVISION")
    assert verify_analysis_bundle(path)["producer"]["source_revision"] is None
    assert path.read_bytes() == original
