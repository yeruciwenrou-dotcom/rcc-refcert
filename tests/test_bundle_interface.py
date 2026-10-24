"""Check receiving-side metadata and public CLI failure semantics."""

import json

import pytest

from rcc_refcert import prepare_bellman_choi, save_analysis_bundle
from rcc_refcert.bounds.terminal_model import build_terminal_model
from rcc_refcert.bundle import inspect_analysis_bundle
from rcc_refcert.bundle_storage import load_bundle_payload, save_bundle_payload
from rcc_refcert.cli import main


@pytest.fixture
def evidence(tmp_path):
    model = build_terminal_model()
    prepared = prepare_bellman_choi(model)
    assert prepared.status == "candidate_ready"
    return save_analysis_bundle(
        tmp_path / "proof.rccbundle", model, prepared.certificate
    )


@pytest.mark.parametrize("mutation", ["checks", "constant", "revision", "diagnostic"])
def test_inspection_rejects_malformed_history(evidence, tmp_path, mutation):
    payload = load_bundle_payload(evidence)
    if mutation == "checks":
        payload.analysis["verification"]["checks"] = "not a check list"
    elif mutation == "constant":
        payload.analysis["verification"]["outcome"] = "inconclusive"
    elif mutation == "revision":
        payload.analysis["producer"]["source_revision"] = "main"
    else:
        payload.analysis["verification"]["constant_error_bound_exact"] = "1e999999999"
    path = tmp_path / "malformed.rccbundle"
    save_bundle_payload(
        path, payload.model, payload.certificate, analysis=payload.analysis
    )
    with pytest.raises(ValueError):
        inspect_analysis_bundle(path)


def test_cli_preserves_outputs_and_separates_error_states(evidence, tmp_path, capsys):
    output = tmp_path / "revalidation.json"
    assert main(["bundle", "verify", str(evidence), "--output", str(output)]) == 0
    assert "Historical results supported: yes" in capsys.readouterr().out
    saved = output.read_bytes()
    assert (
        main(
            [
                "bundle",
                "verify",
                str(evidence),
                "--output",
                str(output),
                "--format",
                "json",
            ]
        )
        == 2
    )
    assert json.loads(capsys.readouterr().out)["state"] == "invalid_input"
    assert output.read_bytes() == saved
    assert (
        main(
            [
                "bundle",
                "verify",
                str(evidence),
                "--max-matrix-elements",
                "1",
                "--format",
                "json",
            ]
        )
        == 3
    )
    assert json.loads(capsys.readouterr().out)["state"] == "resource_limit"


def test_inspection_explicitly_does_not_revalidate(evidence, capsys):
    assert main(["bundle", "inspect", str(evidence), "--format", "json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["matrix_revalidation"] == "not_run"
    assert result["external_premises_verified"] is False
