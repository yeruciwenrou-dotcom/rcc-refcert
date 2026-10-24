"""Prepare, independently verify, and share a two-phase qubit model.

Run with the current source installed:
    python examples/custom_model_workflow.py --bundle alternating.rccbundle
"""

from __future__ import annotations

import argparse
import json
import sys
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


def probability(value: str) -> Fraction:
    """Parse an exact channel probability for the command line."""
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise argparse.ArgumentTypeError(
            "use a rational probability, such as 2/5"
        ) from exc
    if not 0 <= result <= 1:
        raise argparse.ArgumentTypeError("channel probabilities must lie in [0, 1]")
    return result


def analytic_reference_constant(p: Fraction, q: Fraction) -> Fraction:
    """Sum the geometrically weighted terminal Bloch z components exactly.

    At even times z -> (1-p)(1-q)z + p(1-q)-q; odd times
    apply damping first. Halting at time n has weight 2**(-n-1).
    Relative to I/2, the least domination constant is 1 + abs(mean z).
    """
    mean_z = (6 * p - p * q - 3 * q) / (3 * (3 + p + q - p * q))
    return 1 + abs(mean_z)


def build_model(
    p: Fraction = Fraction(3, 5), q: Fraction = Fraction(1, 5)
) -> FiniteControlModel:
    """Alternate amplitude damping p and pumping q, both in [0, 1]."""
    if not 0 <= p <= 1 or not 0 <= q <= 1:
        raise ValueError("channel probabilities must lie in [0, 1]")
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


def run(
    bundle_path: Path | None = None,
    *,
    p: Fraction = Fraction(3, 5),
    q: Fraction = Fraction(1, 5),
) -> dict:
    model = build_model(p, q)
    require_valid_model(model)
    local = analyze_reference_gain_cost(
        model, {key: model.reference_state for key in model.transient_keys()}
    )
    preparation = prepare_bellman_choi(model)
    result = {
        "model": model.name,
        "parameters": {"p": str(p), "q": str(q)},
        "local_H70": local.outcome.value,
        "local_sums": {
            item.syntax_state: item.current_weighted_sum
            for item in local.syntax_reports
        },
        "candidate_preparation": preparation.status,
        "diagnostics": list(preparation.diagnostics),
        "analytic_reference_constant": str(analytic_reference_constant(p, q)),
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
            source=f"Alternating damping/pumping example; p={p}, q={q}; docs/CUSTOM_MODELS.md",
        )
        result["bundle"] = str(saved)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, help="new complete-input bundle path")
    parser.add_argument(
        "--p",
        type=probability,
        default=Fraction(3, 5),
        help="damping probability (default: 3/5)",
    )
    parser.add_argument(
        "--q",
        type=probability,
        default=Fraction(1, 5),
        help="pumping probability (default: 1/5)",
    )
    arguments = parser.parse_args()
    try:
        result = run(arguments.bundle, p=arguments.p, q=arguments.q)
    except FileExistsError as exc:
        if arguments.bundle is None or not arguments.bundle.exists():
            print(
                f"Cannot write bundle: {exc}. Check the destination directory and permissions.",
                file=sys.stderr,
            )
            return 2
        print(
            f"Bundle already exists: {arguments.bundle}. Choose an unused --bundle path.",
            file=sys.stderr,
        )
        return 2
    except OSError as exc:
        print(
            f"Cannot write bundle: {exc}. Check the destination directory and permissions.",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result.get("H3", {}).get("outcome") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
