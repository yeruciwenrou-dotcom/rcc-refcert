import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from rcc_refcert import __version__
from rcc_refcert.paired_reset_example import run_paired_reset_example

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "examples" / "paired_reset_lower_bound.py"


def test_paired_reset_chain_has_fixed_numerical_result() -> None:
    result = run_paired_reset_example()
    model = result["model"]
    checks = result["software_checks"]
    consequence = result["theorem_consequence"]

    assert result["artifact_role"] == "fixed-end-to-end-example-result"
    assert result["producer"] == {"name": "rcc-refcert", "version": __version__}
    assert "provenance" not in result
    assert model["complete_program_domain"] == [
        {
            "codeword": "0",
            "actions": ["reset-to-zero"],
            "cost_slots": 1,
            "output_state": [[1.0, 0.0], [0.0, 0.0]],
        },
        {
            "codeword": "1",
            "actions": ["reset-to-one"],
            "cost_slots": 1,
            "output_state": [[0.0, 0.0], [0.0, 1.0]],
        },
    ]
    assert np.allclose(
        checks["program_semidensity"],
        [[0.5, 0.0], [0.0, 0.5]],
        atol=1e-12,
        rtol=0.0,
    )
    assert checks["program_semidensity_trace"] == 1.0
    assert checks["nonhalting_mass"] == 0.0
    assert checks["transient_spectral_radius"] == 0.0
    assert checks["minimum_fixed_model_domination_C_star"] == 1.0
    assert checks["H3_Bellman_Choi"] == {"outcome": "pass", "constant": 1.0}
    assert checks["H4_reference_potential"] == {
        "outcome": "pass",
        "constant": 1.0,
    }
    assert checks["H77_aggregate_balance_error"] == 0.0
    assert checks["target_domination_constant"] == 2.0
    assert checks["Dmax_zero_bits"] == 1.0
    assert checks["Dmax_zero_structons"] == 1.0
    assert model["reporting_unit"] == {
        "name": "R-structon",
        "symbol": "st_R",
        "bits_per_unit": 1.0,
        "definition": "1 st_R = g_R bits",
    }
    assert consequence["inversion_input_bits"] == 1.0
    assert consequence["one_shot_gap_structons"] == 1.0
    assert consequence["continuous_lower_bound_slots"] == 1.0
    assert consequence["integer_lower_bound_slots"] == 1
    assert consequence["explicit_upper_bound_witness"] == {
        "codeword": "0",
        "actions": ["reset-to-zero"],
        "cost_slots": 1,
        "prepares_target_exactly": True,
    }
    assert consequence["upper_bound_slots"] == 1
    assert consequence["exact_optimal_cost_slots"] == 1


def test_paired_reset_example_keeps_certificate_boundaries_explicit() -> None:
    result = run_paired_reset_example()
    checks = result["software_checks"]
    analytic = result["analytic_inputs"]
    consequence = result["theorem_consequence"]

    assert checks["H70_local_sufficient_route"] == {
        "outcome": "fail",
        "current_weighted_sum": 2.0,
        "used_for_final_inference": False,
    }
    assert checks["H76_reencoding_diagnostic"]["suggested_weighted_sum"] == 1.0
    assert analytic["family_scope"] == "this fixed finite model only"
    assert analytic["semantic_reference_constant_C_U"] == 1.0
    assert analytic["chi_U_bits"] == 0.0
    assert "specific to this fixed declared model" in consequence["claim_boundary"]
    assert "model-family uniformity remain separate" in consequence["claim_boundary"]


def test_paired_reset_example_script_runs_in_text_and_json_modes() -> None:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT / "src")
    text_result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert text_result.returncode == 0, text_result.stderr
    assert "# RCC paired-reset lower-bound example" in text_result.stdout
    assert "## Evidence boundary" in text_result.stdout
    assert "1.0 st_R" in text_result.stdout
    assert "C_opt^(0) = 1 atomic resource slot" in text_result.stdout

    revision = "c" * 40
    environment["RCC_REFCERT_SOURCE_REVISION"] = revision
    json_result = subprocess.run(
        [sys.executable, str(SCRIPT), "--json"],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert json_result.returncode == 0, json_result.stderr
    payload = json.loads(json_result.stdout)
    assert payload["schema"] == "rcc-refcert.paired-reset-lower-bound"
    assert payload["schema_version"] == 2
    assert payload["producer"] == {"name": "rcc-refcert", "version": __version__}
    assert payload["provenance"]["tested_revision"] == revision
    assert payload["theorem_consequence"]["integer_lower_bound_slots"] == 1
    assert payload["theorem_consequence"]["exact_optimal_cost_slots"] == 1


@pytest.mark.parametrize("tol", [0.0, -1.0, float("inf"), float("nan")])
def test_paired_reset_example_rejects_invalid_tolerance(tol: float) -> None:
    with pytest.raises(ValueError, match="tol must be finite and positive"):
        run_paired_reset_example(tol=tol)
