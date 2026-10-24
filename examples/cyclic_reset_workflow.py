"""Verify a cyclic noisy-reset model, compute bounds, and share complete inputs.

The counts are a synthetic fixture. Each reset-with-rotation and the halt
action costs one declared primitive slot. The model-specific optimum is five
slots; the RCC terminal bound supplied here is two slots.
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
    BellmanChoiCertificate,
    FiniteControlModel,
    ReferencePotentialCertificate,
    linear_value_choi_envelopes,
    require_valid_model,
    verify_bellman_choi,
    verify_reference_potential,
)
from rcc_refcert.bounds import (
    bound_from_counts,
    bound_from_spectrum,
    prepare_protocol,
    replay_record,
    with_reference_certificate,
)
from rcc_refcert.bundle import save_analysis_bundle
from rcc_refcert.semantics import AcceptedProgram, program_output

N_QUBITS = 4
RESET_BIAS = Fraction(19, 20)
BLOCK = ("s", "q")
SOURCE = "Cyclic noisy-reset example; docs/CUSTOM_MODELS.md#cyclic-noisy-reset-register"


def exact_spectrum() -> tuple[Fraction, ...]:
    """Exact target eigenvalues in computational-basis order."""
    return tuple(
        RESET_BIAS ** (N_QUBITS - word.bit_count())
        * (1 - RESET_BIAS) ** word.bit_count()
        for word in range(2**N_QUBITS)
    )


def build_model() -> FiniteControlModel:
    dimension = 2**N_QUBITS
    suffix_dimension = dimension // 2
    identity = np.eye(dimension, dtype=complex)
    rotation = np.zeros((dimension, dimension), dtype=complex)
    for word in range(dimension):
        rotation[2 * (word % suffix_dimension) + word // suffix_dimension, word] = 1

    def reset_kraus(probability_zero: Fraction) -> tuple[np.ndarray, ...]:
        operators = []
        for target, probability in enumerate((probability_zero, 1 - probability_zero)):
            for source in range(2):
                local = np.zeros((2, 2), dtype=complex)
                local[target, source] = np.sqrt(float(probability))
                operators.append(rotation @ np.kron(local, np.eye(suffix_dimension)))
        return tuple(operators)

    phase = np.diag([1.0] * suffix_dimension + [-1.0] * suffix_dimension)
    actions = (
        Action("halt", "00", None, halt_kraus={"q": (identity,)}),
        Action("phase", "01", "s", continue_kraus={("q", "q"): (phase,)}),
        Action(
            "reset-0", "10", "s", continue_kraus={("q", "q"): reset_kraus(RESET_BIAS)}
        ),
        Action(
            "reset-1",
            "11",
            "s",
            continue_kraus={("q", "q"): reset_kraus(1 - RESET_BIAS)},
        ),
    )
    return FiniteControlModel(
        syntax_states=("s",),
        control_dims={"q": dimension},
        actions_by_syntax={"s": actions},
        start_syntax="s",
        initial_blocks={"q": identity / dimension},
        output_dim=dimension,
        reference_state=identity / dimension,
        name="cyclic-noisy-reset-four-qubits",
        scope_note="Fixed four-channel register; each reset plus rotation and halt costs one slot.",
    )


def build_certificate(model: FiniteControlModel) -> ReferencePotentialCertificate:
    return ReferencePotentialCertificate(
        theta={BLOCK: model.reference_state.copy()},
        a={BLOCK: 1.0},
        transition_coefficients={(BLOCK, BLOCK): 0.75},
        halt_coefficients={BLOCK: 0.25},
        potential={BLOCK: 1.0},
        name="cyclic-register-reference-potential",
    )


def task_declaration(model: FiniteControlModel) -> dict:
    return {
        "model": {
            "id": model.name,
            "reference_id": "uniform-C16",
            "dimension": model.output_dim,
            "atomic_action_classes": 4,
            "transcription": {"mode": "exact", "a": "0", "gamma_bits": "0"},
            "reference_domination": {
                "upper_constant": "1",
                "source": SOURCE,
                "source_kind": "analytic_argument",
            },
            "cost_domain": "integer_atomic_slots",
            "reference_treatment": "ideal_support",
            "qualification": {
                label: {
                    "basis": "analytic_argument_supplied",
                    "source": SOURCE + "; " + label,
                }
                for label in ("RCon", "TC", "RA")
            },
        },
        "target": {
            "id": "rho0-product-four-r19-20",
            "epsilon": "1/10",
            "metric": "normalized_trace_distance",
        },
    }


def build_requests(
    model: FiniteControlModel, certificate: ReferencePotentialCertificate
) -> list[dict]:
    task = with_reference_certificate(
        task_declaration(model), model, certificate, source=SOURCE
    )
    spectrum = {"task": task, "spectrum": [str(value) for value in exact_spectrum()]}
    # The example fixes the task and protocol before creating its synthetic data.
    protocol = prepare_protocol(
        task,
        {
            "id": "cyclic-register-fixed-projector-N1000",
            "witness_id": "computational-projector-0000",
            "rank": 1,
            "samples": 1000,
            "delta_stat": "1/100",
            "sampling": "fixed_n_iid",
            "selection": "predeclared",
            "readout": "ideal",
            "support": "no_leakage",
        },
    )
    counts = {
        "task": task,
        "protocol": protocol["protocol"],
        "data": {
            "protocol_id": protocol["protocol"]["id"],
            "protocol_sha256": protocol["protocol_sha256"],
            "samples": 1000,
            "hits": 815,
            "origin": "synthetic_fixture",
            "dataset_id": "illustrative-815-of-1000",
        },
    }
    return [
        {"kind": "spectrum", "request": spectrum},
        {"kind": "counts", "request": counts},
    ]


def run(
    bundle_path: Path | None = None,
    *,
    diagnose_h3: bool = False,
    h3_tolerance: float | None = None,
) -> dict:
    model = build_model()
    require_valid_model(model)
    certificate = build_certificate(model)
    report = verify_reference_potential(model, certificate)
    requests = build_requests(model, certificate)
    records = [
        bound_from_spectrum(requests[0]["request"]),
        bound_from_counts(requests[1]["request"]),
    ]
    program = AcceptedProgram(
        ("reset-0",) * N_QUBITS + ("halt",), "10" * N_QUBITS + "00"
    )
    target = np.diag([float(value) for value in exact_spectrum()])
    result = {
        "model": model.name,
        "H4": {"outcome": report.outcome.value, "upper_constant": report.constant},
        "cost_unit": "declared primitive slot, including halt",
        "feasible_program_cost": N_QUBITS + 1,
        "feasible_program_target_error": float(
            np.max(np.abs(program_output(model, program) - target))
        ),
        "counts_origin": "synthetic_fixture",
        "bounds": {
            entry["kind"]: {
                "lower_bound_slots": record["cost"]["lower_bound_slots"],
                "integer_lower_bound_slots": record["cost"][
                    "integer_lower_bound_slots"
                ],
                "replay_matches": replay_record(record)["matches"],
            }
            for entry, record in zip(requests, records)
        },
    }
    if diagnose_h3 or h3_tolerance is not None:
        h3 = BellmanChoiCertificate(linear_value_choi_envelopes(model), 1.0)
        default = verify_bellman_choi(model, h3)
        result["H3_default"] = {
            "tolerance": 1e-10,
            "outcome": default.outcome.value,
            "constant_error_bound": default.constant_error_bound,
            "upper_constant": default.constant,
        }
        if h3_tolerance is not None:
            explicit = verify_bellman_choi(model, h3, tol=h3_tolerance)
            result["H3_explicit_budget"] = {
                "tolerance": h3_tolerance,
                "outcome": explicit.outcome.value,
                "upper_constant": explicit.constant,
                "arithmetic": "binary64",
            }
    if bundle_path is not None:
        bundle_path.parent.mkdir(parents=True, exist_ok=True)
        saved = save_analysis_bundle(
            bundle_path, model, certificate, requests=requests, source=SOURCE
        )
        result["bundle"] = str(saved)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, help="new complete-input bundle path")
    parser.add_argument(
        "--diagnose-h3", action="store_true", help="also report the default H.3 result"
    )
    parser.add_argument(
        "--h3-tolerance",
        type=float,
        help="explicit additional H.3 error-budget diagnostic",
    )
    arguments = parser.parse_args()
    try:
        result = run(
            arguments.bundle,
            diagnose_h3=arguments.diagnose_h3,
            h3_tolerance=arguments.h3_tolerance,
        )
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
    return 0 if result["H4"]["outcome"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
