"""Resource refusals stay typed and JSON-safe for large declared integers."""

import hashlib
import json
import os
import subprocess
import sys
import textwrap
import zipfile
from dataclasses import asdict
from pathlib import Path

import pytest

from rcc_refcert import (
    CheckOutcome,
    ComputationLimits,
    ReferencePotentialCertificate,
    ResourceLimitError,
    estimate_certificate_resources,
    inspect_analysis_bundle,
    prepare_bellman_choi,
    save_analysis_bundle,
    verify_analysis_bundle,
    verify_bellman_choi,
    verify_reference_potential,
)
from rcc_refcert.bounds import BudgetError, load_template, with_reference_certificate
from rcc_refcert.bounds.terminal_model import build_terminal_model
from rcc_refcert.bundle_storage import BundleFormatError, load_bundle_payload
from rcc_refcert.cli import main


@pytest.fixture
def evidence(tmp_path):
    model = build_terminal_model()
    prepared = prepare_bellman_choi(model)
    assert prepared.status == "candidate_ready"
    path = save_analysis_bundle(
        tmp_path / "ordinary.rccbundle", model, prepared.certificate
    )
    return model, prepared.certificate, path


@pytest.mark.parametrize(
    ("value", "diagnostic"),
    [
        (2**256 - 1, 2**256 - 1),
        (2**256, "<integer with 257 bits; decimal expansion omitted>"),
    ],
    ids=["256-bits", "257-bits"],
)
def test_public_diagnostics_preserve_integer_boundary(evidence, value, diagnostic):
    model, _, path = evidence
    limits = ComputationLimits(max_matrix_elements=value, max_enumeration_nodes=value)
    report = verify_analysis_bundle(path, limits=limits)
    assert report["fresh_verification"]["outcome"] == "pass"
    assert report["controls"]["limits"] == {
        "max_matrix_elements": diagnostic,
        "max_enumeration_nodes": diagnostic,
    }
    assert json.loads(json.dumps(report)) == report

    error = ResourceLimitError("test_elements", value, value)
    assert error.estimate == value
    assert error.limit == value
    assert f"estimate {diagnostic} exceeds budget {diagnostic}" in str(error)

    model.control_dims["q"] = 1 << 8191
    candidate = prepare_bellman_choi(model, limits=limits)
    assert candidate.status == "resource_limit"
    assert candidate.certificate is None
    assert candidate.resource_estimate["limit"] == diagnostic
    assert isinstance(candidate.resource_estimate["dense_matrix_elements"], str)
    assert isinstance(candidate.resource_estimate["certificate_matrix_elements"], str)
    assert json.loads(json.dumps(asdict(candidate)))["status"] == "resource_limit"


def test_exception_retains_exact_signed_attributes():
    estimate = -(1 << 16384)
    limit = 1 << 16383
    error = ResourceLimitError("test_elements", estimate, limit)
    assert isinstance(error, ValueError)
    assert error.outcome is CheckOutcome.INCONCLUSIVE
    assert error.resource == "test_elements"
    assert error.estimate == estimate
    assert error.limit == limit
    assert "<negative integer with 16385 bits; decimal expansion omitted>" in str(error)
    assert "<integer with 16384 bits; decimal expansion omitted>" in str(error)


@pytest.mark.parametrize("method", ["H.3", "H.4"])
def test_huge_dimension_refuses_direct_and_bound_verification(evidence, method):
    model, certificate, _ = evidence
    verifier = verify_bellman_choi
    if method == "H.4":
        key = ("s", "q")
        certificate = ReferencePotentialCertificate(
            theta={key: model.reference_state},
            a={key: 1.0},
            transition_coefficients={},
            halt_coefficients={key: 1.0},
            potential={key: 1.0},
        )
        verifier = verify_reference_potential
    model.control_dims["q"] = 1 << 8191
    expected = estimate_certificate_resources(model, certificate)["estimated_elements"]
    assert expected.bit_length() > 16380
    with pytest.raises(ResourceLimitError) as caught:
        verifier(model, certificate)
    assert caught.value.estimate == expected
    assert caught.value.limit == ComputationLimits().max_matrix_elements
    assert "decimal expansion omitted" in str(caught.value)
    with pytest.raises(BudgetError, match="decimal expansion omitted"):
        with_reference_certificate(
            load_template()["task"], model, certificate, source="large dimension test"
        )


def _replace_declared_dimension(source, destination):
    with zipfile.ZipFile(source) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(members["manifest.json"])
    manifest["model"]["fields"]["control_dims"]["items"][0][1] = 1 << 8191
    unsigned = {
        key: value for key, value in manifest.items() if key != "manifest_sha256"
    }
    canonical = json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    manifest["manifest_sha256"] = hashlib.sha256(canonical).hexdigest()
    members["manifest.json"] = json.dumps(manifest).encode("utf-8")
    with zipfile.ZipFile(destination, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)


@pytest.mark.parametrize("command", ["inspect", "verify"])
def test_real_bundle_huge_dimension_refuses_before_array_reads(
    evidence, tmp_path, monkeypatch, capsys, command
):
    import rcc_refcert.bundle_storage as storage

    _, _, original = evidence
    path = tmp_path / "huge-dimension.rccbundle"
    _replace_declared_dimension(original, path)
    reads = []
    original_read = storage._read_member

    def watch(*args, **kwargs):
        reads.append(args[1].filename)
        return original_read(*args, **kwargs)

    monkeypatch.setattr(storage, "_read_member", watch)
    api = inspect_analysis_bundle if command == "inspect" else verify_analysis_bundle
    with pytest.raises(ResourceLimitError) as caught:
        api(path)
    assert caught.value.estimate.bit_length() > 16380
    assert reads == ["manifest.json"]
    reads.clear()
    output = tmp_path / "refused.json"
    assert (
        main(
            ["bundle", command, str(path), "--format", "json", "--output", str(output)]
        )
        == 3
    )
    error = json.loads(capsys.readouterr().out)
    assert error["schema"] == "rcc-refcert.bundle-error"
    assert error["schema_version"] == 1
    assert error["state"] == "resource_limit"
    assert error["resource"] == "certificate_matrix_elements"
    assert isinstance(error["estimate"], str)
    assert "decimal expansion omitted" in error["estimate"]
    assert error["limit"] == ComputationLimits().max_matrix_elements
    assert reads == ["manifest.json"]
    assert not output.exists()


def test_cli_ordinary_refusal_preserves_integer_fields(evidence, capsys):
    model, certificate, path = evidence
    expected = estimate_certificate_resources(model, certificate)["estimated_elements"]
    limit = expected - 1
    assert (
        main(
            [
                "bundle",
                "verify",
                str(path),
                "--format",
                "json",
                "--max-matrix-elements",
                str(limit),
            ]
        )
        == 3
    )
    error = json.loads(capsys.readouterr().out)
    assert error["state"] == "resource_limit"
    assert error["estimate"] == expected
    assert type(error["estimate"]) is int
    assert error["limit"] == limit


def test_cli_serializes_oversized_estimate_and_limit(monkeypatch, capsys):
    from rcc_refcert import bundle_cli

    def refuse(*args, **kwargs):
        raise ResourceLimitError("test_elements", 1 << 16384, 1 << 16383)

    monkeypatch.setattr(bundle_cli, "verify_analysis_bundle", refuse)
    assert main(["bundle", "verify", "unused.rccbundle", "--format", "json"]) == 3
    error = json.loads(capsys.readouterr().out)
    assert error["estimate"] == "<integer with 16385 bits; decimal expansion omitted>"
    assert error["limit"] == "<integer with 16384 bits; decimal expansion omitted>"


def test_stored_limits_remain_exact_and_obey_existing_integer_bound(evidence, tmp_path):
    model, certificate, _ = evidence
    value = 1 << 8191
    limits = ComputationLimits(max_matrix_elements=value, max_enumeration_nodes=value)
    path = save_analysis_bundle(
        tmp_path / "exact-limits.rccbundle", model, certificate, limits=limits
    )
    payload = load_bundle_payload(path)
    assert payload.analysis["controls"]["limits"] == asdict(limits)
    assert all(
        type(item) is int for item in payload.analysis["controls"]["limits"].values()
    )
    report = verify_analysis_bundle(path, limits=limits)
    assert report["fresh_verification"]["outcome"] == "pass"
    assert report["controls"]["limits"]["max_matrix_elements"] == (
        "<integer with 8192 bits; decimal expansion omitted>"
    )
    assert json.loads(json.dumps(report)) == report

    rejected = tmp_path / "too-large-limits.rccbundle"
    with pytest.raises(BundleFormatError, match="JSON integer exceeds 8192 bits"):
        save_analysis_bundle(
            rejected,
            model,
            certificate,
            limits=ComputationLimits(max_matrix_elements=1 << 8192),
        )
    assert not rejected.exists()


def test_public_refusal_under_minimum_python_integer_string_limit():
    script = textwrap.dedent(
        """
        from dataclasses import asdict
        import json
        import sys
        from rcc_refcert import ResourceLimitError, prepare_bellman_choi, verify_bellman_choi
        from rcc_refcert.bounds import BudgetError, load_template, with_reference_certificate
        from rcc_refcert.bounds.terminal_model import build_terminal_model

        if hasattr(sys, "get_int_max_str_digits"):
            assert sys.get_int_max_str_digits() == 640
        model = build_terminal_model()
        certificate = prepare_bellman_choi(model).certificate
        model.control_dims["q"] = 1 << 4096
        candidate = prepare_bellman_choi(model)
        assert candidate.status == "resource_limit"
        assert candidate.certificate is None
        json.dumps(asdict(candidate))
        try:
            verify_bellman_choi(model, certificate)
        except ResourceLimitError as error:
            assert error.estimate.bit_length() > 8192
            assert "decimal expansion omitted" in str(error)
        else:
            raise AssertionError("direct verification did not refuse")
        try:
            with_reference_certificate(
                load_template()["task"], model, certificate, source="minimum limit test"
            )
        except BudgetError as error:
            assert "decimal expansion omitted" in str(error)
        else:
            raise AssertionError("binding did not refuse")
        print("resource refusals preserved")
        """
    )
    environment = os.environ.copy()
    environment["PYTHONINTMAXSTRDIGITS"] = "640"
    environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "resource refusals preserved"
