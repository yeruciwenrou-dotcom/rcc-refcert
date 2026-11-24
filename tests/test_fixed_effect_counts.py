"""The two response endpoints describe one physical test and one joint event."""

import copy
import hashlib
import json
import zipfile
from fractions import Fraction as F

import pytest

from rcc_refcert.bounds import (
    InputError,
    bound_from_counts,
    load_template,
    prepare_effect_protocol,
    prepare_protocol,
    replay_record,
    validate_record,
)
from rcc_refcert.bundle import inspect_analysis_bundle, verify_analysis_bundle
from rcc_refcert.workflows.bundles import save_effect_bundle
from rcc_refcert.workflows.core import canonical_bytes, digest


@pytest.fixture
def request_data():
    return load_template("effect-counts")


def known_reference(request, response, kind="exact"):
    request["protocol"]["reference"] = {
        "kind": kind,
        "response": response,
        "state_id": "uniform-C4",
        "source": "specified analytical response of the fixed effect on I/4",
    }
    del request["data"]["reference"]


def test_two_arm_cost_and_shared_coverage(request_data):
    r = bound_from_counts(request_data)
    direct, test = r["routes"]
    assert F(".50705") < F(r["target_response_lower_exact"]) < F(".50706")
    assert F(".29294") < F(r["reference_response_upper_exact"]) < F(".29295")
    assert (
        F(".47457747") < F(direct["information_floor_bits"]["lower"]) < F(".47457748")
    )
    assert F(".44936061") < F(test["information_floor_bits"]["lower"]) < F(".44936062")
    assert r["cost"]["selected_route"] == direct["route"]
    assert F(".15819249") < F(r["cost"]["lower_bound_slots"]) < F(".15819250")
    assert r["cost"]["integer_lower_bound_slots"] == 1
    assert (
        direct["event_ids"] == test["event_ids"] == ["target-lower", "reference-upper"]
    )
    assert len(r["coverage"]["events"]) == 2
    assert r["coverage"]["coverage_at_least_exact"] == "19/20"
    assert r["coverage"]["delta_total"] == "1/20"
    assert replay_record(r)["matches"]


def test_known_reference_reproduces_old_projection(request_data):
    known_reference(request_data, "1/4")
    old = load_template("counts")
    spec = load_template("protocol")
    spec["protocol"]["delta_stat"] = "1/40"
    frozen = prepare_protocol(spec["task"], spec["protocol"])
    old["protocol"] = frozen["protocol"]
    old["data"]["protocol_sha256"] = frozen["protocol_sha256"]
    legacy = bound_from_counts(old)
    r = bound_from_counts(request_data)
    assert (
        r["routes"][0]["information_floor_bits"]
        == legacy["information"]["information_bits"]
    )
    assert r["cost"]["lower_bound_slots"] == legacy["cost"]["lower_bound_slots"]
    assert r["coverage"]["delta_total"] == "1/40"
    assert len(r["coverage"]["events"]) == 1
    assert replay_record(legacy)["matches"]


def test_zero_margin_and_hypothesis_eligibility(request_data):
    request_data["data"]["target"]["counts"] = {"yes": 300, "no": 700}
    r = bound_from_counts(request_data)
    assert r["cost"]["integer_lower_bound_slots"] == 0
    assert r["cost"]["zero_reason"] == "reference_contrast_not_resolved"
    assert r["routes"][0]["eligible"]
    assert r["routes"][1]["reason"] == "target_lower_below_one_minus_eta"
    request_data["derivation"]["eta"] = "9/10"
    assert (
        bound_from_counts(request_data)["routes"][1]["reason"]
        == "eta_plus_radius_must_be_less_than_one"
    )
    request_data["data"]["target"]["counts"] = {"yes": 0, "no": 1000}
    r = bound_from_counts(request_data)
    assert all(not route["eligible"] for route in r["routes"])
    assert r["cost"]["selected_route"] is None
    assert r["cost"]["zero_reason"] == "sampling_margin_exhausted"
    assert r["information_lower_bits"] == "0"


def test_measured_zero_hits_and_deterministic_zero(request_data):
    request_data["data"]["reference"]["counts"] = {"yes": 0, "no": 1000}
    request_data["data"]["target"]["counts"] = {"yes": 180, "no": 820}
    r = bound_from_counts(request_data)
    assert F("0.042") < F(r["reference_response_upper_exact"]) < F("0.043")
    assert r["cost"]["integer_lower_bound_slots"] == 0
    known_reference(request_data, "0", kind="upper_bound")
    conflict = bound_from_counts(request_data)
    assert conflict["decision"] == "support_conflict"
    assert conflict["cost"] is None
    assert conflict["information_lower_bits"] is None
    request_data["data"]["target"]["counts"] = {"yes": 0, "no": 1000}
    compatible = bound_from_counts(request_data)
    assert compatible["cost"]["integer_lower_bound_slots"] == 0
    assert compatible["cost"]["selected_route"] is None
    del request_data["task"]
    assert bound_from_counts(request_data)["decision"] == "support_assessment_required"


@pytest.mark.parametrize("field", ["target", "reference"])
def test_mismatched_frozen_measurement(request_data, field):
    request_data["protocol"]["effect"]["readout"] = "different readout"
    # Updating one header leaves the other batch bound to the original setting.
    other = "reference" if field == "target" else "target"
    request_data["data"][other]["arm_sha256"] = prepare_effect_protocol(
        request_data["protocol"]
    )["arm_sha256"][other]
    with pytest.raises(InputError, match="data." + field):
        bound_from_counts(request_data)


@pytest.mark.parametrize("key", ["event_id", "dataset_id"])
def test_sampling_observations_cannot_share_an_identity(request_data, key):
    request_data["protocol"]["reference"][key] = request_data["protocol"]["target"][key]
    with pytest.raises(InputError, match="distinct"):
        bound_from_counts(request_data)


@pytest.mark.parametrize(
    "counts",
    [
        {"yes": True, "no": 999},
        {"no": 1000},
        {"yes": 5, "no": 994},
        {"yes": 1001, "no": -1},
    ],
)
def test_invalid_raw_counts(request_data, counts):
    request_data["data"]["target"]["counts"] = counts
    with pytest.raises(InputError):
        bound_from_counts(request_data)


def test_tolerance_changes_derivation_only(request_data):
    baseline = bound_from_counts(request_data)
    request_data["task"]["target"]["epsilon"] = request_data["derivation"][
        "smoothing_radius"
    ] = "1/8"
    scan = bound_from_counts(request_data)
    assert baseline["protocol_sha256"] == scan["protocol_sha256"]
    assert baseline["coverage"] == scan["coverage"]
    assert baseline["task_fingerprint"] != scan["task_fingerprint"]
    assert baseline["derivation_sha256"] != scan["derivation_sha256"]
    request_data["derivation"]["smoothing_radius"] = "1/10"
    with pytest.raises(InputError, match="generation tolerance"):
        bound_from_counts(request_data)
    request_data["task"]["target"]["id"] = "another state"
    with pytest.raises(InputError, match="identity"):
        bound_from_counts(request_data)


def test_information_survives_missing_qualifications(request_data):
    full = bound_from_counts(request_data)
    del request_data["task"]["model"]["qualification"]["RA"]
    for item in ("model.qualification.RA", "task"):
        r = bound_from_counts(request_data)
        assert r["decision"] == "information_only"
        assert r["information_lower_bits"] == full["information_lower_bits"]
        assert r["cost"] is None and r["missing_process_premises"] == [item]
        assert all(route["cost"] is None for route in r["routes"])
        request_data.pop("task", None)


def test_forbids_imported_routes_or_changed_reference(request_data):
    request_data["routes"] = bound_from_counts(request_data)["routes"]
    with pytest.raises(InputError):
        bound_from_counts(request_data)
    del request_data["routes"]
    request_data["task"]["model"]["reference_id"] = "different state"
    with pytest.raises(InputError, match="reference"):
        bound_from_counts(request_data)


def test_record_and_bundle_independent_recomputation(request_data, tmp_path):
    record = bound_from_counts(request_data)
    path = tmp_path / "shared.rccbundle"
    save_effect_bundle(path, request_data, record)
    with pytest.raises(FileExistsError):
        save_effect_bundle(path, request_data, record)
    assert inspect_analysis_bundle(path)["physical_revalidation"] == "not_run"
    fresh = verify_analysis_bundle(path)
    assert fresh["historical_results_supported"] is True
    assert fresh["same_version_replay"]["status"] == "match"
    assert fresh["fresh_result"] == record
    forged = copy.deepcopy(record)
    forged["cost"]["integer_lower_bound_slots"] = True
    with pytest.raises(InputError):
        validate_record(forged)

    # Repack with consistent checksums but change the original observations alone.
    with zipfile.ZipFile(path) as archive:
        manifest, raw, history = [
            json.loads(archive.read(n + ".json"))
            for n in ("manifest", "request", "history")
        ]
    raw["data"]["target"]["counts"] = {"yes": 300, "no": 700}
    payload = canonical_bytes(raw)
    manifest["request_digest"] = digest(raw)
    manifest["members"]["request.json"] = {
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    del manifest["manifest_sha256"]
    manifest["manifest_sha256"] = digest(manifest)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", canonical_bytes(manifest))
        archive.writestr("request.json", payload)
        archive.writestr("history.json", canonical_bytes(history))
    with pytest.raises(InputError, match="binding"):
        verify_analysis_bundle(path)


def test_history_with_consistent_wrong_endpoints_is_compared_to_raw_counts(
    request_data, tmp_path
):
    # Both histories can be internally consistent. Only the original 550 hits reproduce the positive floor.
    from rcc_refcert.bounds.effects import _derive_effect_record
    from rcc_refcert.workflows.bundles import _write_json_bundle

    fresh = bound_from_counts(request_data)
    wrong = _derive_effect_record(
        request_data,
        saved_endpoints={
            "target": F("1/4"),
            "reference": F(fresh["reference_response_upper_exact"]),
        },
    )
    assert wrong["cost"]["integer_lower_bound_slots"] == 0
    path = tmp_path / "wrong-endpoints.rccbundle"
    _write_json_bundle(
        path,
        request_data,
        wrong,
        version=3,
        kind="fixed_effect_counts",
        author=wrong["producer"],
        request_digest=digest(request_data),
        overwrite=False,
    )
    assert inspect_analysis_bundle(path)["record_consistency"] == "pass"
    checked = verify_analysis_bundle(path)
    assert checked["fresh_verification"]["outcome"] == "pass"
    assert checked["historical_results_supported"] is False
    assert checked["same_version_replay"]["status"] == "mismatch"
    assert checked["fresh_result"]["cost"]["integer_lower_bound_slots"] == 1


def test_input_schema_for_sampled_and_deterministic_reference(request_data):
    from importlib import resources

    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(
        resources.files("rcc_refcert.bounds")
        .joinpath("data", "fixed_effect_counts.schema.json")
        .read_text()
    )
    jsonschema.Draft202012Validator.check_schema(schema)
    validator = jsonschema.Draft202012Validator(schema)
    validator.validate(request_data)
    known_reference(request_data, "1/4")
    validator.validate(request_data)
    request_data["data"]["reference"] = request_data["data"]["target"]
    assert not validator.is_valid(request_data)


@pytest.mark.parametrize(
    "b,diagnostic",
    [
        ("1/10", "response_incompatible_with_uniform_reference_on_support"),
        ("1", "target_misses_incompatible_with_identity_effect"),
    ],
)
def test_uniform_support_consistency(request_data, b, diagnostic):
    known_reference(request_data, b)
    r = bound_from_counts(request_data)
    assert r["decision"] == "support_conflict"
    assert r["support_diagnostic"] == diagnostic and r["cost"] is None


@pytest.mark.parametrize(
    "b,diagnostic",
    [
        ("0", "target_hits_incompatible_with_zero_effect"),
        ("1/10", "response_incompatible_with_uniform_reference_on_support"),
        ("1", "target_misses_incompatible_with_identity_effect"),
    ],
)
def test_ideal_support_survives_missing_process_qualification(
    request_data, b, diagnostic
):
    known_reference(request_data, b)
    del request_data["task"]["model"]["qualification"]["TC"]
    result = bound_from_counts(request_data)
    assert result["support_diagnostic"] == diagnostic
    assert result["decision"] == "support_conflict"
    assert result["information_lower_bits"] is None and result["cost"] is None
    assert replay_record(result)["matches"]


def test_compatible_information_only_with_declared_support(request_data):
    known_reference(request_data, "1/4")
    del request_data["task"]["model"]["qualification"]["TC"]
    result = bound_from_counts(request_data)
    assert result["decision"] == "information_only"
    assert F(result["information_lower_bits"]) > 0 and result["cost"] is None
