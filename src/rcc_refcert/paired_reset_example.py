"""Fixed end-to-end RCC lower-bound example built from the Appendix-F reset pair.

The module deliberately implements one declared finite model.  It is an
executable bridge from model qualification to the one-shot lower-bound theorem,
not a general RCC optimizer, smoothing engine, or model-ingestion interface.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from .audit import audit_model
from .bellman_choi import BellmanChoiCertificate, verify_bellman_choi
from .domination import minimum_domination_constant
from .fixed_point import linear_value_choi_envelopes
from .gain_cost import analyze_reference_gain_cost
from .metadata import document_metadata
from .model import Action, FiniteControlModel
from .quantum import apply_kraus, reset_kraus_qubit
from .reference_potential import (
    ReferencePotentialCertificate,
    verify_reference_potential,
)
from .semantics import enumerate_accepted_programs, program_output
from .status import CheckOutcome

EXAMPLE_SCHEMA = "rcc-refcert.paired-reset-lower-bound"
EXAMPLE_SCHEMA_VERSION = 2
DEFAULT_TOLERANCE = 1e-10


def build_paired_reset_model() -> FiniteControlModel:
    """Return the one-qubit terminal restriction of the Appendix-F reset pair."""

    reference = np.eye(2, dtype=complex) / 2.0
    reset_zero = Action(
        name="reset-to-zero",
        codeword="0",
        successor=None,
        halt_kraus={"q": reset_kraus_qubit(0)},
    )
    reset_one = Action(
        name="reset-to-one",
        codeword="1",
        successor=None,
        halt_kraus={"q": reset_kraus_qubit(1)},
    )
    return FiniteControlModel(
        syntax_states=("s",),
        control_dims={"q": 2},
        actions_by_syntax={"s": (reset_zero, reset_one)},
        start_syntax="s",
        initial_blocks={"q": reference},
        output_dim=2,
        reference_state=reference,
        name="paired-reset-terminal",
        scope_note=(
            "one-qubit, one-step terminal restriction of the Appendix-F reset pair"
        ),
    )


def _paired_reset_potential(
    model: FiniteControlModel,
) -> ReferencePotentialCertificate:
    key = ("s", "q")
    return ReferencePotentialCertificate(
        theta={key: model.reference_state},
        a={key: 1.0},
        transition_coefficients={},
        halt_coefficients={key: 1.0},
        potential={key: 1.0},
        name="paired-reset reference-potential certificate",
    )


def _stable_number(value: float, tol: float) -> float:
    if abs(value) <= tol:
        return 0.0
    nearest = round(value)
    if abs(value - nearest) <= tol:
        return float(nearest)
    return float(value)


def _real_matrix(matrix: np.ndarray, tol: float) -> list[list[float]]:
    array = np.asarray(matrix, dtype=complex)
    if float(np.max(np.abs(array.imag))) > tol:
        raise RuntimeError("the fixed example unexpectedly produced a complex matrix")
    return [[_stable_number(float(entry.real), tol) for entry in row] for row in array]


def _require_close(
    left: np.ndarray | float,
    right: np.ndarray | float,
    *,
    tol: float,
    message: str,
) -> None:
    if not np.allclose(left, right, atol=tol, rtol=0.0):
        raise RuntimeError(message)


def run_paired_reset_example(
    *,
    tol: float = DEFAULT_TOLERANCE,
    source_revision: str | None = None,
) -> dict[str, Any]:
    """Execute the fixed qualification-to-lower-bound chain.

    The software computes finite-model quantities and checks supplied proof
    objects.  The returned ``analytic_inputs`` section keeps the physical
    interpretation, complete-domain identification, faithful transcription,
    and theorem hypotheses separate from those numerical checks.
    """

    if not np.isfinite(tol) or tol <= 0:
        raise ValueError("tol must be finite and positive")

    model = build_paired_reset_model()
    reference = model.reference_state
    target = np.array([[1.0, 0.0], [0.0, 0.0]], dtype=complex)
    key = ("s", "q")

    accepted = enumerate_accepted_programs(model, max_actions=1)
    accepted_outputs = [program_output(model, program) for program in accepted]
    analysis = audit_model(
        model,
        max_depth=2,
        max_transient_steps=1,
        tol=tol,
    )
    semidensity = analysis.fixed_point.output
    if semidensity is None:
        raise RuntimeError("the fixed example did not produce a completed semidensity")

    bellman = verify_bellman_choi(
        model,
        BellmanChoiCertificate(
            choi_envelopes=linear_value_choi_envelopes(model, tol=tol),
            constant=1.0,
            name="paired-reset minimum value-map certificate",
        ),
        tol=tol,
    )
    potential = verify_reference_potential(
        model,
        _paired_reset_potential(model),
        tol=tol,
    )
    gain_cost = analyze_reference_gain_cost(model, {key: reference}, tol=tol)
    syntax_gain = gain_cost.syntax_reports[0]

    semidensity_domination = minimum_domination_constant(
        semidensity, reference, tol=tol
    )
    target_domination = minimum_domination_constant(target, reference, tol=tol)
    reset_zero_output = apply_kraus(reset_kraus_qubit(0), reference)
    reset_one_output = apply_kraus(reset_kraus_qubit(1), reference)
    h77_average = 0.5 * (reset_zero_output + reset_one_output)
    h77_error = float(np.linalg.norm(h77_average - reference, ord=2))

    _require_close(
        semidensity,
        reference,
        tol=tol,
        message="the program semidensity no longer equals the declared reference",
    )
    _require_close(
        accepted_outputs[0],
        target,
        tol=tol,
        message="program 0 no longer prepares the declared target",
    )
    if bellman.outcome is not CheckOutcome.PASS:
        raise RuntimeError("the supplied H.3 certificate did not pass")
    if potential.outcome is not CheckOutcome.PASS:
        raise RuntimeError("the supplied H.4 certificate did not pass")
    if semidensity_domination.outcome is not CheckOutcome.PASS:
        raise RuntimeError("fixed-model reference domination was not established")
    if target_domination.outcome is not CheckOutcome.PASS:
        raise RuntimeError("the target information gap was not finite")
    if h77_error > tol:
        raise RuntimeError("the aggregate H.77 reference balance did not close")

    program_trace = float(np.trace(semidensity).real)
    nonhalting_mass = max(0.0, 1.0 - program_trace)
    fixed_constant = _stable_number(semidensity_domination.constant, tol)
    target_constant = _stable_number(target_domination.constant, tol)
    current_h70_sum = _stable_number(syntax_gain.current_weighted_sum, tol)
    suggested_h76_sum = _stable_number(syntax_gain.suggested_weighted_sum, tol)

    epsilon = 0.0
    gamma_r = 2
    g_r = math.log2(gamma_r)
    transcription_a = 0.0
    transcription_gamma = 0.0
    declared_reference_constant = 1.0
    chi_u = math.log2(declared_reference_constant)
    beta_u = transcription_gamma + chi_u
    dmax_zero = math.log2(target_constant)
    dmax_zero_structons = dmax_zero / g_r
    inversion_input = dmax_zero - beta_u
    continuous_lower_bound = max(0.0, inversion_input / g_r)
    nearest_slot = round(continuous_lower_bound)
    integer_lower_bound = (
        int(nearest_slot)
        if abs(continuous_lower_bound - nearest_slot) <= tol
        else math.ceil(continuous_lower_bound)
    )
    upper_bound_program = accepted[0]
    upper_bound_slots = upper_bound_program.action_count
    if integer_lower_bound > upper_bound_slots:
        raise RuntimeError("the lower bound exceeds the explicit preparation cost")
    exact_optimal_cost_slots = (
        upper_bound_slots if integer_lower_bound == upper_bound_slots else None
    )

    return {
        **document_metadata(source_revision),
        "schema": EXAMPLE_SCHEMA,
        "schema_version": EXAMPLE_SCHEMA_VERSION,
        "artifact_role": "fixed-end-to-end-example-result",
        "model": {
            "name": model.name,
            "scope": model.scope_note,
            "reference_state": _real_matrix(reference, tol),
            "target_state": _real_matrix(target, tol),
            "generation_tolerance_epsilon": epsilon,
            "cost_unit": "one atomic terminal reset slot",
            "atomic_action_classes_Gamma_R": gamma_r,
            "atomic_control_bandwidth_g_R_bits": g_r,
            "reporting_unit": {
                "name": "R-structon",
                "symbol": "st_R",
                "bits_per_unit": g_r,
                "definition": "1 st_R = g_R bits",
            },
            "transcription_envelope": "Lambda_R(L) = Phi_{1,0}(L) = L",
            "transcription_parameters": {
                "a": transcription_a,
                "gamma": transcription_gamma,
            },
            "complete_program_domain": [
                {
                    "codeword": program.codeword,
                    "actions": list(program.action_names),
                    "cost_slots": program.action_count,
                    "output_state": _real_matrix(output, tol),
                }
                for program, output in zip(accepted, accepted_outputs, strict=True)
            ],
        },
        "software_checks": {
            "program_semidensity": _real_matrix(semidensity, tol),
            "program_semidensity_trace": _stable_number(program_trace, tol),
            "nonhalting_mass": _stable_number(nonhalting_mass, tol),
            "transient_spectral_radius": _stable_number(
                analysis.fixed_point.spectral_radius, tol
            ),
            "maximum_realization_error": _stable_number(
                analysis.maximum_realization_error, tol
            ),
            "minimum_fixed_model_domination_C_star": fixed_constant,
            "H3_Bellman_Choi": {
                "outcome": bellman.outcome.value,
                "constant": _stable_number(float(bellman.constant), tol),
            },
            "H4_reference_potential": {
                "outcome": potential.outcome.value,
                "constant": _stable_number(float(potential.constant), tol),
            },
            "H77_aggregate_balance_error": _stable_number(h77_error, tol),
            "H70_local_sufficient_route": {
                "outcome": gain_cost.outcome.value,
                "current_weighted_sum": current_h70_sum,
                "used_for_final_inference": False,
            },
            "H76_reencoding_diagnostic": {
                "suggested_weighted_sum": suggested_h76_sum,
                "suggested_codewords": {
                    action.action_name: action.suggested_codeword
                    for action in syntax_gain.actions
                },
            },
            "target_domination_constant": target_constant,
            "Dmax_zero_bits": _stable_number(dmax_zero, tol),
            "Dmax_zero_structons": _stable_number(dmax_zero_structons, tol),
        },
        "analytic_inputs": {
            "reference_consistency": (
                "The one-qubit input and output space, sigma_R = I/2 background "
                "and initial state, paired reset dynamics, unconditional output, "
                "error semantics, and one-slot cost rule are fixed together "
                "before the target is selected. The numerical matrix check is "
                "applied after this physical identification is declared."
            ),
            "faithful_transcription": (
                "The only legal finite histories are the two one-slot terminal "
                "preparations, represented exactly by the prefix-free programs "
                "0 and 1. Thus Lambda_R(L) = L with g_R = 1, a = 0, and "
                "gamma = 0."
            ),
            "reference_admissibility": (
                "The model declaration identifies the enumerated two-program set "
                "as the complete program domain. Together with the computed "
                "identity M_U = sigma_R, this supplies C_U = 1 and chi_U = 0 "
                "for this fixed example. Family uniformity requires an additional "
                "analytic argument."
            ),
            "semantic_reference_constant_C_U": declared_reference_constant,
            "chi_U_bits": chi_u,
            "beta_U_bits": beta_u,
            "family_scope": "this fixed finite model only",
        },
        "theorem_consequence": {
            "paper_formula": ("C_opt^(0) >= F_{1,0}(Dmax^0(rho || sigma_R) - beta_U)"),
            "inversion_input_bits": _stable_number(inversion_input, tol),
            "one_shot_gap_structons": _stable_number(dmax_zero_structons, tol),
            "continuous_lower_bound_slots": _stable_number(continuous_lower_bound, tol),
            "integer_lower_bound_slots": integer_lower_bound,
            "explicit_upper_bound_witness": {
                "codeword": upper_bound_program.codeword,
                "actions": list(upper_bound_program.action_names),
                "cost_slots": upper_bound_slots,
                "prepares_target_exactly": True,
            },
            "upper_bound_slots": upper_bound_slots,
            "exact_optimal_cost_slots": exact_optimal_cost_slots,
            "statement": (
                "The RCC theorem gives a one-slot lower bound, while program 0 "
                "prepares the target exactly in one slot; therefore the declared "
                "fixed model has C_opt^(0) = 1 atomic resource slot."
            ),
            "claim_boundary": (
                "The equality is specific to this fixed declared model. General "
                "RCC optimization and model-family uniformity remain separate "
                "problems."
            ),
        },
        "paper_map": {
            "physical_model": "Appendix F, Eqs. (F.41)-(F.44)",
            "program_semidensity_and_qualification": (
                "Appendix H, H.1-H.4 and Eqs. (H.67)-(H.77)"
            ),
            "information_gap": "Appendix A, Eqs. (A.6)-(A.7)",
            "reporting_unit": "Section II, Definition 2.6",
            "main_lower_bound": "Section III, Theorem 3.1 and Eq. (3.1)",
            "cost_inversion": (
                "Section III, Theorem 3.1; Appendix A, Eqs. (A.45)-(A.46)"
            ),
        },
    }


def render_paired_reset_report(result: dict[str, Any]) -> str:
    """Render the fixed result as a compact Markdown report."""

    model = result["model"]
    checks = result["software_checks"]
    analytic = result["analytic_inputs"]
    consequence = result["theorem_consequence"]
    reporting_unit = model["reporting_unit"]
    h70 = checks["H70_local_sufficient_route"]
    h76 = checks["H76_reencoding_diagnostic"]

    lines = [
        "# RCC paired-reset lower-bound example",
        "",
        (
            "A fixed one-qubit model connects an explicit program semidensity "
            "to the one-shot RCC lower-bound theorem."
        ),
        "",
        "## Declared model",
        "",
        "| Quantity | Value |",
        "|---|---|",
        f"| Reference state | `{model['reference_state']}` |",
        f"| Target state | `{model['target_state']}` |",
        f"| Generation tolerance | `{model['generation_tolerance_epsilon']}` |",
        f"| Cost unit | {model['cost_unit']} |",
        f"| Transcription envelope | `{model['transcription_envelope']}` |",
        "",
        "## Executed chain",
        "",
        "| Stage | Result |",
        "|---|---|",
        f"| Program semidensity | `{checks['program_semidensity']}` |",
        f"| Trace / nonhalting mass | `{checks['program_semidensity_trace']}` / `{checks['nonhalting_mass']}` |",
        f"| Transient spectral radius | `{checks['transient_spectral_radius']}` |",
        f"| Fixed-model domination constant | `{checks['minimum_fixed_model_domination_C_star']}` |",
        f"| H.3 / H.4 supplied certificates | `{checks['H3_Bellman_Choi']['outcome']}` / `{checks['H4_reference_potential']['outcome']}` |",
        f"| H.77 aggregate-balance error | `{checks['H77_aggregate_balance_error']}` |",
        f"| Target information gap | `Dmax^0 = {checks['Dmax_zero_bits']} bit` |",
        (
            "| RCC reporting unit | "
            f"`{checks['Dmax_zero_structons']} {reporting_unit['symbol']}` "
            f"(`1 {reporting_unit['symbol']} = {reporting_unit['bits_per_unit']} bit`) |"
        ),
        (
            "| Cost inversion | "
            f"continuous floor `{consequence['continuous_lower_bound_slots']}` slot; "
            f"discrete lower bound `{consequence['integer_lower_bound_slots']}` atomic slot |"
        ),
        (
            "| Explicit feasible preparation | "
            f"program `{consequence['explicit_upper_bound_witness']['codeword']}`; "
            f"upper bound `{consequence['upper_bound_slots']}` atomic slot |"
        ),
        (
            "| Fixed-model optimum | "
            f"`C_opt^(0) = {consequence['exact_optimal_cost_slots']}` atomic slot |"
        ),
        "",
        "## Evidence boundary",
        "",
        "| Layer | What is established here |",
        "|---|---|",
        (
            "| Software | Constructs the finite program semidensity; evaluates its "
            "trace, spectrum, and domination constant; checks supplied H.3/H.4 "
            "proof objects and H.77 balance; computes the exact epsilon-zero "
            "information gap; verifies the one-slot target-preparation witness. |"
        ),
        (
            "| Analytic model inputs | Declares the physical reference meaning, "
            "identifies the complete two-program domain, supplies exact faithful "
            "transcription, and fixes the model scope. |"
        ),
        ("| Joint theorem consequence | " + consequence["statement"] + " |"),
        "",
        (
            f"The local H.70 sufficient route returns `{h70['outcome']}` with "
            f"weighted sum `{h70['current_weighted_sum']}`; H.76 re-encoding "
            f"reduces that diagnostic sum to `{h76['suggested_weighted_sum']}`. "
            "The final inference instead uses the exact complete-domain identity "
            "and aggregate H.77 balance."
        ),
        "",
        consequence["claim_boundary"],
        "",
        "Analytic inputs retained explicitly:",
        "",
        f"- RCon: {analytic['reference_consistency']}",
        f"- TC: {analytic['faithful_transcription']}",
        f"- RA: {analytic['reference_admissibility']}",
    ]
    return "\n".join(lines) + "\n"
