"""Independent checks of the scientific meaning of complete-evidence transfer."""

from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction

import pytest

from rcc_refcert import ReferencePotentialCertificate
from rcc_refcert.bounds import (
    InputError,
    bound_from_counts,
    load_template,
    prepare_protocol,
    replay_record,
    with_reference_certificate,
)
from rcc_refcert.bounds.contracts import canonical_hash
from rcc_refcert.bounds.terminal_model import build_terminal_model
from rcc_refcert.bundle import save_analysis_bundle, verify_analysis_bundle
from rcc_refcert.bundle_storage import load_bundle_payload, save_bundle_payload


def _evidence(tmp_path, tolerance=1e-10, requests=True):
    """The eight terminal channels average to the reference: H.4 uses b=v=1."""
    model = build_terminal_model()
    key = ("s", "q")
    certificate = ReferencePotentialCertificate(
        theta={key: model.reference_state.copy()},
        a={key: 1.0},
        transition_coefficients={},
        halt_coefficients={key: 1.0},
        potential={key: 1.0},
    )
    task = with_reference_certificate(
        load_template("spectrum")["task"],
        model,
        certificate,
        source="Independent eight-channel reference identity",
        tol=tolerance,
    )
    spectrum = {**load_template("spectrum"), "task": task}
    frozen = prepare_protocol(task, load_template("protocol")["protocol"])
    counts = {
        "task": task,
        "protocol": frozen["protocol"],
        "data": {
            **load_template("counts")["data"],
            "protocol_sha256": frozen["protocol_sha256"],
        },
    }
    path = tmp_path / "analysis.rcc"
    save_analysis_bundle(
        path,
        model,
        certificate,
        tol=tolerance,
        requests=[
            {"kind": "spectrum", "request": spectrum},
            {"kind": "counts", "request": counts},
        ]
        if requests
        else [],
    )
    return path, model, certificate, spectrum, counts


def _as_decimal(value):
    q = Fraction(value)
    return Decimal(q.numerator) / Decimal(q.denominator)


def test_mixed_requests_keep_separate_revalidation_layers(tmp_path):
    path, _, _, _, _ = _evidence(tmp_path)
    original = path.read_bytes()
    result = verify_analysis_bundle(path)
    assert result["record_consistency"] == "pass"
    assert result["fresh_verification"]["outcome"] == "pass"
    assert result["fresh_verification"]["evidence"] == "numerical"
    assert result["historical_results_supported"] is True
    assert result["external_premises_verified"] is False
    assert {entry["kind"] for entry in result["requests"]} == {"spectrum", "counts"}
    for entry in result["requests"]:
        assert entry["same_version_replay"]["matches"] is True
        assert entry["current_scalar_comparison"]["matches"] is True
        assert entry["fresh_bound"]["schema"] == "rcc-refcert.bundle-derived-bound"
        assert (
            entry["fresh_bound"]["cost"]["enclosure_upper_is_process_upper_bound"]
            is False
        )
    assert path.read_bytes() == original


@pytest.mark.parametrize(
    ("saved_tolerance", "fresh_tolerance", "supported"),
    [(1e-10, 1e-6, False), (1e-6, 1e-10, True)],
)
def test_counts_new_constant_uses_original_event_and_correct_cost_shift(
    tmp_path, saved_tolerance, fresh_tolerance, supported
):
    path, _, _, _, counts = _evidence(tmp_path, saved_tolerance)
    original = deepcopy(counts)
    result = verify_analysis_bundle(path, tol=fresh_tolerance)
    entry = next(x for x in result["requests"] if x["kind"] == "counts")
    assert result["fresh_verification"]["outcome"] == "pass"
    assert result["historical_results_supported"] is supported
    assert entry["historical_constant_supported"] is supported
    assert entry["historical_record"]["provenance"]["input_snapshot"] == original
    fresh = entry["fresh_bound"]
    old = bound_from_counts(original)
    assert fresh["original_input_sha256"] == canonical_hash(original)
    assert (
        fresh["original_acquisition_protocol_sha256"]
        == original["data"]["protocol_sha256"]
    )
    assert fresh["confidence"] == old["confidence"]
    assert fresh["information_bits"] == old["information"]["information_bits"]
    assert counts == original
    # Eight action classes give exactly 3 bits/slot. With a=gamma=0,
    # the positive continuous lower bound changes by -log2(Cfresh/Cold)/3.
    with localcontext() as context:
        context.prec = 80
        ratio = _as_decimal(entry["fresh_constant_exact"]) / _as_decimal(
            entry["historical_constant_exact"]
        )
        expected_shift = -ratio.ln() / Decimal(2).ln() / Decimal(3)
        observed_shift = Decimal(fresh["cost"]["lower_bound_slots"]) - Decimal(
            old["cost"]["lower_bound_slots"]
        )
        assert abs(observed_shift - expected_shift) < Decimal("1e-40")


def test_changed_candidate_cannot_inherit_historical_binding(tmp_path):
    path, _, _, _, _ = _evidence(tmp_path)
    payload = load_bundle_payload(path)
    payload.certificate.potential[("s", "q")] = 2.0
    changed = tmp_path / "changed-candidate.rcc"
    save_bundle_payload(
        changed, payload.model, payload.certificate, analysis=payload.analysis
    )
    with pytest.raises(InputError, match="identit"):
        verify_analysis_bundle(changed)


def test_incorrect_tolerance_cannot_relabel_frozen_counts(tmp_path):
    _, model, certificate, _, counts = _evidence(tmp_path)
    with pytest.raises(InputError, match="controls|result"):
        save_analysis_bundle(
            tmp_path / "wrong-tolerance.rcc",
            model,
            certificate,
            tol=1e-6,
            requests=[{"kind": "counts", "request": counts}],
        )


def test_old_producer_is_compared_without_claiming_same_version_replay(tmp_path):
    path, _, _, _, _ = _evidence(tmp_path)
    payload = load_bundle_payload(path)
    # Reconstruct a historical producer identity, retaining its exact inputs.
    # Producer hashes are integrity labels, not signatures/authentication.
    payload.analysis["producer"]["version"] = "0.1.3"
    for entry in payload.analysis["requests"]:
        entry["record"]["producer"]["version"] = "0.1.3"
        with pytest.raises(InputError, match="differs"):
            replay_record(entry["record"])
    historical = tmp_path / "historical.rcc"
    save_bundle_payload(
        historical, payload.model, payload.certificate, analysis=payload.analysis
    )
    result = verify_analysis_bundle(historical)
    for entry in result["requests"]:
        assert entry["same_version_replay"]["status"] == "unsupported_producer_version"
        assert entry["same_version_replay"]["matches"] is None
        assert entry["current_scalar_comparison"]["matches"] is True


def test_certificate_only_revalidation_has_no_scalar_or_sampling_claim(tmp_path):
    path, _, _, _, _ = _evidence(tmp_path, requests=False)
    result = verify_analysis_bundle(path)
    assert result["fresh_verification"]["outcome"] == "pass"
    assert result["requests"] == []
    assert result["external_premises_verified"] is False


def test_untrusted_exact_metadata_is_bounded_before_fraction_allocation(
    tmp_path, monkeypatch
):
    from rcc_refcert import bundle

    path, _, _, _, _ = _evidence(tmp_path, requests=False)
    payload = load_bundle_payload(path)
    hostile = "1e999999999"
    payload.analysis["controls"]["tolerance_exact"] = hostile
    changed = tmp_path / "oversized-exponent.rcc"
    save_bundle_payload(
        changed, payload.model, payload.certificate, analysis=payload.analysis
    )

    class GuardedFraction(Fraction):
        def __new__(cls, numerator=0, denominator=None, **kwargs):
            assert numerator != hostile, "unbounded Fraction allocation was attempted"
            return super().__new__(cls, numerator, denominator, **kwargs)

    monkeypatch.setattr(bundle, "Fraction", GuardedFraction)
    with pytest.raises(InputError):
        verify_analysis_bundle(changed)
