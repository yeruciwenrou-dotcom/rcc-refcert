"""Prepare, independently verify, and share a two-phase qubit model.

Run with the current source installed:
    python examples/custom_model_workflow.py --bundle alternating.rccbundle
"""

from __future__ import annotations

import argparse
import json
from fractions import Fraction
from pathlib import Path

import numpy as np

from rcc_refcert import (
    Action,
    FiniteControlModel,
    analyze_reference_gain_cost,
    require_valid_model,
    verify_bellman_choi,
)
from rcc_refcert.bundle import save_analysis_bundle
from rcc_refcert.candidate import prepare_bellman_choi


def build_model() -> FiniteControlModel:
    """Alternate amplitude damping p=3/5 and pumping q=1/5."""
    p, q = Fraction(3, 5), Fraction(1, 5)
    identity = np.eye(2, dtype=complex)
    damping = (
        np.diag([1.0, np.sqrt(float(1 - p))]).astype(complex),
        np.array([[0, np.sqrt(float(p))], [0, 0]], dtype=complex),
    )
    pumping = (
        np.diag([np.sqrt(float(1 - q)), 1.0]).astype(complex),
        np.array([[0, 0], [np.sqrt(float(q)), 0]], dtype=complex),
    )
    actions = {
        "A": (
            Action("halt-A", "0", None, halt_kraus={"q": (identity,)}),
            Action("damp", "1", "B", continue_kraus={("q", "q"): damping}),
        ),
        "B": (
            Action("halt-B", "0", None, halt_kraus={"q": (identity,)}),
            Action("pump", "1", "A", continue_kraus={("q", "q"): pumping}),
        ),
    }
    return FiniteControlModel(
        syntax_states=("A", "B"),
        control_dims={"q": 2},
        actions_by_syntax=actions,
        start_syntax="A",
        initial_blocks={"q": identity / 2},
        output_dim=2,
        reference_state=identity / 2,
        name="alternating-damping-pumping",
        scope_note="Two fixed CPTP channels, unweighted Kraus operators, one-bit actions.",
    )


def run(bundle_path: Path | None = None) -> dict:
    model = build_model()
    require_valid_model(model)
    local = analyze_reference_gain_cost(
        model, {key: model.reference_state for key in model.transient_keys()}
    )
    preparation = prepare_bellman_choi(model)
    result = {
        "model": model.name,
        "local_H70": local.outcome.value,
        "local_sums": {
            item.syntax_state: item.current_weighted_sum
            for item in local.syntax_reports
        },
        "candidate_preparation": preparation.status,
        "diagnostics": list(preparation.diagnostics),
        "analytic_reference_constant": "29/23",
    }
    if preparation.certificate is None:
        return result
    report = verify_bellman_choi(model, preparation.certificate)
    result["H3"] = {
        "outcome": report.outcome.value,
        "evidence": report.evidence.value,
        "candidate_constant": report.candidate_constant,
        "upper_constant": report.constant,
        "constant_error_bound": report.constant_error_bound,
    }
    if bundle_path is not None:
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        saved = save_analysis_bundle(
            bundle_path,
            model,
            preparation.certificate,
            requests=[],
            source="Alternating damping/pumping example; docs/CUSTOM_MODELS.md",
        )
        result["bundle"] = str(saved)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, help="new complete-input bundle path")
    arguments = parser.parse_args()
    result = run(arguments.bundle)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result.get("H3", {}).get("outcome") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
