"""Analyze and share candidates for a complete two-action quantum model."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from rcc_refcert import Action, FiniteControlModel
from rcc_refcert.bundle import verify_analysis_bundle
from rcc_refcert.workflows import (
    StateInput,
    analyze_cost,
    render_workflow_result,
    save_workflow_bundle,
    serialize_numeric_model,
)


def make_request():
    """Keep the model, reference, costs, target and candidates in one request."""
    identity = np.eye(2, dtype=complex)
    reference_state = identity / 2
    model = FiniteControlModel(
        syntax_states=("s",),
        control_dims={"q": 2},
        actions_by_syntax={
            "s": (
                Action(
                    name="continue",
                    codeword="1",
                    successor="s",
                    continue_kraus={("q", "q"): (identity,)},
                ),
                Action(
                    name="halt",
                    codeword="0",
                    successor=None,
                    halt_kraus={"q": (identity,)},
                ),
            )
        },
        start_syntax="s",
        initial_blocks={"q": reference_state},
        output_dim=2,
        reference_state=reference_state,
        name="identity-or-halt",
    )
    reference = {
        "kind": "uniform_product_support",
        "gamma": 2,
        "source": "Two declared action classes: continue and halt.",
    }
    cost = {
        "kind": "integer_atomic_slots",
        "action_slots": 1,
        "halt_slots": 1,
        "initial_preparation": "The maximally mixed qubit is supplied.",
        "auxiliary_systems": "One control block; no auxiliary register.",
        "output_rule": "complete_unconditional_output",
    }
    return {
        "schema": "rcc-refcert.workflow-request",
        "schema_version": 1,
        "kind": "cost_analysis",
        "mode": "numerical",
        "model": serialize_numeric_model(
            model,
            subsystem_dims=[2],
            subsystem_labels=["q"],
            reference=reference,
            cost=cost,
            tolerance=1e-10,
        ),
        "target": StateInput.numeric(np.diag([0.6, 0.4]), [2], ["q"]).as_dict(),
        "epsilon": "1/5",
        "max_cost": 4,
        "candidates": [
            {
                "id": "halt-now",
                "source": "Halt at the supplied input.",
                "action_names": ["halt"],
                "codeword": "0",
            },
            {
                "id": "continue-then-halt",
                "source": "Apply one identity continuation, then halt.",
                "action_names": ["continue", "halt"],
                "codeword": "10",
            },
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, help="save and reverify this analysis")
    args = parser.parse_args()
    request = make_request()
    result = analyze_cost(request)
    print(render_workflow_result(result), end="")
    if args.bundle is not None:
        try:
            save_workflow_bundle(args.bundle, request, result)
        except FileExistsError:
            parser.exit(2, f"{args.bundle} already exists; choose a new bundle path.\n")
        except OSError as exc:
            parser.exit(2, f"Could not save {args.bundle}: {exc}\n")
        verified = verify_analysis_bundle(args.bundle)
        print(f"Saved: {args.bundle.resolve()}")
        print(
            f"Historical results supported: {verified['historical_results_supported']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
