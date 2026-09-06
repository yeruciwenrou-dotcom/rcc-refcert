from __future__ import annotations

import json
import math
from collections.abc import Iterable
from pathlib import Path

from .audit import CaseAnalysis, ReferenceSuite
from .bellman_choi import BellmanChoiReport
from .cases import (
    H1_REALIZATION,
    H2_LINEAR_FIXED_POINT,
    H3_BELLMAN_CHOI,
    H4_REFERENCE_POTENTIAL,
    H6_GAIN_COST,
    H34_DOMINATION,
    CaseKind,
    CaseStudy,
)
from .gain_cost import GainCostReport
from .metadata import document_metadata
from .numeric import (
    canonical_float,
    canonical_upper_float,
    format_certificate_constant,
    format_domination_constant,
    format_number,
    normalize_diagnostic,
)
from .reference_potential import CertificateReport
from .status import CheckOutcome, CheckResult, EvidenceLevel

CASE_SCHEMA = "rcc-refcert.case-audit"
SUITE_SCHEMA = "rcc-refcert.reference-suite"
REFERENCE_SCHEMA = "rcc-refcert.reference-suite-freeze"
SCHEMA_VERSION = 2
FRESH_RUN_ARTIFACT_ROLE = "fresh-run-evidence"
FROZEN_REFERENCE_ARTIFACT_ROLE = "canonical-frozen-evidence"

_ZERO_DIAGNOSTIC_FIELDS = frozenset(
    {
        "generation_error",
        "maximum_spectral_norm_error",
        "reference_balance_error",
        "reset_balance_error",
        "solve_residual",
        "spectral_norm_error",
        "support_leakage",
        "word_average_errors",
    }
)

CHECK_TITLES = {
    H1_REALIZATION: "H.1 realization identity",
    H2_LINEAR_FIXED_POINT: "H.2 linear fixed point",
    H34_DOMINATION: "H.34 fixed-model domination",
    H3_BELLMAN_CHOI: "H.3 Bellman–Choi certificate",
    H4_REFERENCE_POTENTIAL: "H.4 reference-potential certificate",
    H6_GAIN_COST: "H.6 reference gain–cost",
}


def _json_number(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return float(value)


def _format_number(
    value: float | None,
    *,
    zero_tolerance: float | None = None,
) -> str:
    return format_number(value, zero_tolerance=zero_tolerance)


def _check_payload(check: CheckResult) -> dict[str, object]:
    return {
        "name": check.name,
        "outcome": check.outcome.value,
        "evidence": check.evidence.value,
        "message": check.message,
        "value": _json_number(check.value),
        "tolerance": _json_number(check.tolerance),
    }


def _report_payload(
    report: BellmanChoiReport | CertificateReport,
    *,
    detailed: bool,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": report.name,
        "outcome": report.outcome.value,
        "evidence": report.evidence.value,
        "constant": _json_number(report.constant),
        "candidate_constant": _json_number(report.candidate_constant),
        "constant_error_bound": _json_number(report.constant_error_bound),
    }
    if detailed:
        payload["checks"] = [_check_payload(check) for check in report.checks]
    return payload


def _gain_cost_payload(
    report: GainCostReport,
    *,
    detailed: bool,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": report.model_name,
        "outcome": report.outcome.value,
        "evidence": report.evidence.value,
        "constant": _json_number(report.constant),
    }
    if detailed:
        payload["checks"] = [_check_payload(check) for check in report.checks]
    payload["syntax_states"] = [
        {
            "name": syntax.syntax_state,
            "current_weighted_sum": _json_number(syntax.current_weighted_sum),
            "current_condition_satisfied": syntax.current_condition_satisfied,
            "current_outcome": syntax.current_outcome.value,
            "current_weighted_sum_upper": _json_number(
                syntax.current_weighted_sum_upper
            ),
            "suggested_weighted_sum": _json_number(syntax.suggested_weighted_sum),
            "suggested_condition_satisfied": syntax.suggested_condition_satisfied,
            "suggested_outcome": syntax.suggested_outcome.value,
            "suggested_weighted_sum_upper": _json_number(
                syntax.suggested_weighted_sum_upper
            ),
            "actions": [
                {
                    "name": action.action_name,
                    "current_codeword": action.current_codeword,
                    "reference_gain": _json_number(action.reference_gain),
                    "reference_gain_upper": _json_number(action.reference_gain_upper),
                    "suggested_code_length": action.suggested_code_length,
                    "suggested_codeword": action.suggested_codeword,
                    **(
                        {
                            "control_gains": {
                                name: _json_number(value)
                                for name, value in sorted(action.control_gains.items())
                            }
                        }
                        if detailed
                        else {}
                    ),
                }
                for action in syntax.actions
            ],
        }
        for syntax in report.syntax_reports
    ]
    payload["fixed_model_initial_constant"] = _json_number(
        report.fixed_model_initial_constant
    )
    return payload


def _with_expectation(
    case: CaseStudy,
    check_name: str,
    payload: dict[str, object],
) -> dict[str, object]:
    expected = case.expected_outcome(check_name)
    observed = CheckOutcome(str(payload["outcome"]))
    payload["expected_outcome"] = expected.value if expected is not None else None
    payload["matches_expectation"] = expected is None or observed is expected
    return payload


def _case_payload(
    result: CaseAnalysis,
    *,
    detailed: bool = False,
) -> dict[str, object]:
    """Return the versioned, JSON-safe representation of a case audit."""

    analysis = result.model_analysis
    fixed = analysis.fixed_point
    h1: dict[str, object] = {
        "outcome": analysis.realization_outcome.value,
        "evidence": EvidenceLevel.NUMERICAL.value,
        "maximum_spectral_norm_error": _json_number(analysis.maximum_realization_error),
        "action_depth_range": {
            "first": 1,
            "last": len(analysis.realization_checks),
        },
    }
    if detailed:
        h1["depths"] = [
            {
                "action_depth": check.action_depth,
                "spectral_norm_error": _json_number(check.spectral_norm_error),
                "outcome": check.outcome.value,
                "evidence": check.evidence.value,
            }
            for check in analysis.realization_checks
        ]

    h2 = {
        "outcome": analysis.linear_fixed_point_outcome.value,
        "evidence": EvidenceLevel.NUMERICAL.value,
        "spectral_radius": _json_number(fixed.spectral_radius),
        "linear_inverse_applicable": fixed.applicable,
        "condition_number": _json_number(fixed.condition_number),
        "solve_residual": _json_number(fixed.solve_residual),
        "output_valid": fixed.output_valid,
        "assembly_error_estimate": _json_number(fixed.assembly_error_estimate),
        "output_error_estimate": _json_number(fixed.output_error_estimate),
        "max_transient_steps": analysis.max_transient_steps,
        "truncated_output_trace": _json_number(analysis.truncated_trace),
        "message": fixed.message,
    }

    domination = analysis.fixed_model_domination
    h34 = {
        "outcome": analysis.domination_outcome.value,
        "evidence": EvidenceLevel.NUMERICAL.value,
        "constant": _json_number(domination.constant if domination else None),
        "constant_estimate": _json_number(
            domination.constant_estimate if domination else None
        ),
        "constant_error_estimate": _json_number(
            domination.constant_error_estimate if domination else None
        ),
        "constant_upper_bound": None,
        "constant_is_infinite": (
            math.isinf(domination.constant)
            if domination is not None and domination.constant is not None
            else None
        ),
        "support_compatible": domination.support_compatible if domination else None,
        "reference_rank": domination.reference_rank if domination else None,
        "reference_condition_number": _json_number(
            domination.reference_condition_number if domination else None
        ),
        "message": domination.message
        if domination
        else "linear fixed point not evaluated",
        "support_leakage": _json_number(
            domination.support_leakage if domination else None
        ),
    }

    checks: dict[str, object] = {
        H1_REALIZATION: _with_expectation(result.case, H1_REALIZATION, h1),
        H2_LINEAR_FIXED_POINT: _with_expectation(
            result.case, H2_LINEAR_FIXED_POINT, h2
        ),
        H34_DOMINATION: _with_expectation(result.case, H34_DOMINATION, h34),
    }
    if result.bellman_choi is not None:
        checks[H3_BELLMAN_CHOI] = _with_expectation(
            result.case,
            H3_BELLMAN_CHOI,
            _report_payload(result.bellman_choi, detailed=detailed),
        )
    if result.reference_potentials:
        aggregate = dict(result.observed_outcomes())[H4_REFERENCE_POTENTIAL]
        h4: dict[str, object] = {
            "outcome": aggregate.value,
            "evidence": EvidenceLevel.NUMERICAL.value,
            "certificates": [
                _report_payload(report, detailed=detailed)
                for report in result.reference_potentials
            ],
        }
        checks[H4_REFERENCE_POTENTIAL] = _with_expectation(
            result.case, H4_REFERENCE_POTENTIAL, h4
        )
    if result.gain_cost is not None:
        checks[H6_GAIN_COST] = _with_expectation(
            result.case,
            H6_GAIN_COST,
            _gain_cost_payload(result.gain_cost, detailed=detailed),
        )

    return {
        "schema": CASE_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "case": {
            "name": result.case.name,
            "title": result.case.title,
            "kind": result.case.kind.value,
            "purpose": result.case.purpose,
            "paper_references": list(result.case.paper_references),
            "interpretation": result.case.interpretation,
        },
        "parameters": {
            "tolerance": analysis.tolerance,
            "max_depth": len(analysis.realization_checks),
            "max_transient_steps": analysis.max_transient_steps,
        },
        "matches_reference_expectations": result.matches_expectations,
        "expectation_mismatches": list(result.expectation_mismatches),
        "checks": checks,
        "scope": {
            "evidence": "floating-point numerical checks",
            "analytic_obligations": [
                "faithful transcription (TC)",
                "model-family uniformity",
                "the RCC theorem",
            ],
        },
    }


def case_payload(
    result: CaseAnalysis,
    *,
    detailed: bool = False,
    source_revision: str | None = None,
) -> dict[str, object]:
    return {
        **document_metadata(source_revision),
        **_case_payload(result, detailed=detailed),
    }


def cases_payload(
    cases: Iterable[CaseStudy],
    *,
    source_revision: str | None = None,
) -> dict[str, object]:
    return {
        **document_metadata(source_revision),
        "schema": "rcc-refcert.case-list",
        "schema_version": SCHEMA_VERSION,
        "cases": [
            {
                "name": case.name,
                "title": case.title,
                "kind": case.kind.value,
                "purpose": case.purpose,
                "paper_references": list(case.paper_references),
                "interpretation": case.interpretation,
            }
            for case in cases
        ],
    }


def _suite_payload(
    suite: ReferenceSuite,
    *,
    detailed: bool = False,
    artifact_role: str | None = FRESH_RUN_ARTIFACT_ROLE,
) -> dict[str, object]:
    appendix = suite.appendix_f
    payload: dict[str, object] = {
        "schema": SUITE_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "parameters": {
            "max_depth": suite.max_depth,
            "max_transient_steps": suite.max_transient_steps,
            "tolerance": suite.tolerance,
        },
        "matches_reference_expectations": suite.matches_reference_expectations,
        "cases": [_case_payload(case, detailed=detailed) for case in suite.cases],
        "appendix_f": {
            "rank_decoder": {
                "roundtrips": appendix.rank_roundtrip_count,
                "failures": appendix.rank_roundtrip_failures,
            },
            "gamma5": {
                "reference_balance_error": _json_number(
                    appendix.gamma5_reference_balance_error
                ),
                "word_average_errors": [
                    _json_number(value) for value in appendix.gamma5_word_average_errors
                ],
                "partial_kraft_mass": _json_number(appendix.gamma5_partial_kraft_mass),
            },
            "f5_two_qubit_witness": {
                "reset_balance_error": _json_number(appendix.f5_reset_balance_error),
                "generation_error": _json_number(appendix.f5_generation_error),
                "initial_purity": appendix.f5_initial_purity,
                "final_purity": appendix.f5_final_purity,
            },
            "natural_c_gt_one_interval": [
                str(appendix.natural_constant_lower),
                str(appendix.natural_constant_upper),
            ],
            "global_reset_constants": [
                {"n": n, "constant": constant}
                for n, constant in appendix.global_reset_constants
            ],
            "global_reset_gain_costs": [
                _gain_cost_payload(report, detailed=detailed)
                for report in appendix.global_reset_gain_costs
            ],
        },
    }
    if artifact_role is not None:
        payload["artifact_role"] = artifact_role
    return payload


def suite_payload(
    suite: ReferenceSuite,
    *,
    detailed: bool = False,
    artifact_role: str | None = FRESH_RUN_ARTIFACT_ROLE,
    source_revision: str | None = None,
) -> dict[str, object]:
    return {
        **document_metadata(source_revision),
        **_suite_payload(
            suite,
            detailed=detailed,
            artifact_role=artifact_role,
        ),
    }


def _normalize_reference_node(
    node: object,
    suite_tolerance: float,
    *,
    field_name: str | None = None,
) -> object:
    if isinstance(node, dict):
        normalized = {
            key: _normalize_reference_node(
                value,
                suite_tolerance,
                field_name=key,
            )
            for key, value in node.items()
        }
        value = normalized.get("value")
        tolerance = normalized.get("tolerance")
        if isinstance(value, float) and isinstance(tolerance, float):
            normalized["value"] = canonical_float(
                normalize_diagnostic(value, tolerance) or 0.0
            )
        if (
            node.get("candidate_constant") is not None
            or node.get("fixed_model_initial_constant") is not None
        ):
            for key in ("constant", "constant_error_bound"):
                if isinstance(node.get(key), float):
                    normalized[key] = canonical_upper_float(node[key])
        return normalized
    if isinstance(node, list):
        return [
            _normalize_reference_node(
                value,
                suite_tolerance,
                field_name=field_name,
            )
            for value in node
        ]
    if isinstance(node, float):
        if field_name in {
            "assembly_error_estimate",
            "output_error_estimate",
            "constant_error_estimate",
        }:
            # Keep a positive allowance positive, with a platform-stable ceiling.
            return math.ceil(node / suite_tolerance) * suite_tolerance
        if field_name in {
            "reference_gain_upper",
            "current_weighted_sum_upper",
            "suggested_weighted_sum_upper",
            "fixed_model_initial_constant",
        }:
            return canonical_upper_float(node)
        if field_name in _ZERO_DIAGNOSTIC_FIELDS:
            node = normalize_diagnostic(node, suite_tolerance) or 0.0
        return canonical_float(node)
    return node


def reference_payload(suite: ReferenceSuite) -> dict[str, object]:
    """Return the normalized structure used by the frozen-result comparison."""

    normalized = _normalize_reference_node(
        _suite_payload(suite, detailed=True, artifact_role=None),
        suite.tolerance,
    )
    return {
        **document_metadata(),
        "artifact_role": FROZEN_REFERENCE_ARTIFACT_ROLE,
        "schema": REFERENCE_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "normalization": {
            "rule": "abs(value) <= tolerance is stored as 0",
            "significant_digits": 12,
            "suite_tolerance": suite.tolerance,
            "certificate_bounds": "upper constants and error bounds round toward positive infinity",
            "roundoff_estimates": "positive estimates round upward in units of suite_tolerance",
        },
        "suite": normalized,
    }


def write_reference_payload(
    path: str | Path,
    suite: ReferenceSuite,
) -> Path:
    """Write the canonical structured reference result to ``path``."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            reference_payload(suite),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return output


def reference_payload_matches(path: str | Path, suite: ReferenceSuite) -> bool:
    """Compare a stored reference payload with the normalized suite structure."""

    return reference_payload_text_matches(Path(path).read_text(encoding="utf-8"), suite)


def reference_payload_text_matches(text: str, suite: ReferenceSuite) -> bool:
    """Compare serialized reference payload text with the normalized suite."""

    stored = json.loads(text)
    return stored == reference_payload(suite)


def _display_outcome(
    observed: CheckOutcome,
    expected: CheckOutcome | None,
) -> str:
    if expected is not None and observed is not expected:
        return f"UNEXPECTED {observed.value.upper()}"
    if observed is CheckOutcome.FAIL:
        return "EXPECTED FAIL" if expected is CheckOutcome.FAIL else "FAIL"
    if observed is CheckOutcome.INCONCLUSIVE:
        return (
            "EXPECTED INCONCLUSIVE"
            if expected is CheckOutcome.INCONCLUSIVE
            else "INCONCLUSIVE"
        )
    if observed is CheckOutcome.NOT_APPLICABLE:
        return "BOUNDARY"
    return observed.value.upper()


def format_case_list(cases: Iterable[CaseStudy]) -> str:
    lines = ["Bundled RCC cases", ""]
    for case in cases:
        lines.extend(
            [
                f"{case.name}",
                f"  {case.purpose}",
                f"  RCC paper: {', '.join(case.paper_references)}",
                "",
            ]
        )
    lines.extend(
        [
            "Run a case with: rcc-refcert example NAME",
            "Run the complete suite with: rcc-refcert reproduce --check",
        ]
    )
    return "\n".join(lines)


def _case_result_label(result: CaseAnalysis) -> str:
    if not result.matches_expectations:
        return "MISMATCH"
    if result.case.kind is CaseKind.BOUNDARY:
        return "EXPECTED BOUNDARY"
    if any(
        outcome is CheckOutcome.FAIL for _, outcome in result.case.expected_outcomes
    ):
        return "EXPECTED ROUTE FAILURE"
    return "PASS"


def format_case(result: CaseAnalysis, *, detailed: bool = False) -> str:
    analysis = result.model_analysis
    lines = [
        f"{result.case.title} ({result.case.name})",
        result.case.purpose,
        f"RCC paper: {', '.join(result.case.paper_references)}",
        "",
        f"Reference result: {_case_result_label(result)}",
        "",
    ]

    details = {
        H1_REALIZATION: (
            f"depths 1–{len(analysis.realization_checks)}; max error "
            f"{_format_number(analysis.maximum_realization_error, zero_tolerance=analysis.tolerance)}"
        ),
        H2_LINEAR_FIXED_POINT: (
            f"spectral radius {_format_number(analysis.fixed_point.spectral_radius)}"
            if not analysis.fixed_point.applicable
            else (
                f"spectral radius {_format_number(analysis.fixed_point.spectral_radius)}; "
                "solve residual "
                f"{_format_number(analysis.fixed_point.solve_residual, zero_tolerance=analysis.tolerance)}"
            )
        ),
        H34_DOMINATION: (
            "complete fixed-model output unavailable"
            if analysis.fixed_model_domination is None
            else format_domination_constant(
                analysis.fixed_model_domination.constant,
                analysis.fixed_model_domination.constant_estimate,
            )
        ),
    }
    if result.bellman_choi is not None:
        report = result.bellman_choi
        details[H3_BELLMAN_CHOI] = format_certificate_constant(
            report.constant,
            report.candidate_constant,
            report.constant_error_bound,
        )
    if result.reference_potentials:
        constants = ", ".join(
            format_certificate_constant(
                report.constant, report.candidate_constant, report.constant_error_bound
            )
            for report in result.reference_potentials
        )
        count = len(result.reference_potentials)
        noun = "certificate" if count == 1 else "certificates"
        details[H4_REFERENCE_POTENTIAL] = f"{count} {noun}; {constants}"
    if result.gain_cost is not None:
        sums = ", ".join(
            f"{syntax.syntax_state}: {_format_number(syntax.current_weighted_sum)}"
            for syntax in result.gain_cost.syntax_reports
        )
        details[H6_GAIN_COST] = f"current H.70 sums {sums}"
        if result.gain_cost.constant is None:
            details[H6_GAIN_COST] += "; no usable constant for current codewords"

    for name, outcome in result.observed_outcomes():
        expected = result.case.expected_outcome(name)
        lines.append(
            f"{CHECK_TITLES[name]:36} "
            f"{_display_outcome(outcome, expected):22} {details[name]}"
        )

    if detailed:
        lines.extend(
            [
                "",
                "Numerical details",
                f"  tolerance: {analysis.tolerance:.1e}",
                f"  maximum transient continuations: {analysis.max_transient_steps}",
                f"  truncated output trace: {_format_number(analysis.truncated_trace)}",
                f"  linear output: {analysis.fixed_point.message}",
            ]
        )
        if analysis.fixed_point.applicable:
            lines.extend(
                [
                    "  linear solve condition: "
                    + _format_number(analysis.fixed_point.condition_number),
                    "  linear solve residual: "
                    + _format_number(
                        analysis.fixed_point.solve_residual,
                        zero_tolerance=analysis.tolerance,
                    ),
                    "  output error estimate: "
                    + _format_number(analysis.fixed_point.output_error_estimate),
                ]
            )
        if analysis.fixed_model_domination is not None:
            domination = analysis.fixed_model_domination
            lines.extend(
                [
                    "  H.34: " + domination.message,
                    "  constant error estimate: "
                    + _format_number(domination.constant_error_estimate),
                ]
            )
        if result.bellman_choi is not None:
            minima = [
                check.value
                for check in result.bellman_choi.checks
                if check.name.endswith("-psd") and check.value is not None
            ]
            if minima:
                lines.append(
                    "  H.3 minimum PSD residual eigenvalue: "
                    + _format_number(
                        min(minima),
                        zero_tolerance=analysis.tolerance,
                    )
                )
        for report in result.reference_potentials:
            margins = [
                check.value
                for check in report.checks
                if check.name.startswith("bellman[") and check.value is not None
            ]
            if margins:
                lines.append(
                    f"  {report.name}: minimum Bellman margin "
                    + _format_number(
                        min(margins),
                        zero_tolerance=analysis.tolerance,
                    )
                )
        if result.gain_cost is not None:
            for syntax in result.gain_cost.syntax_reports:
                suggestions = ", ".join(
                    f"{action.action_name}={action.suggested_codeword}"
                    for action in syntax.actions
                )
                lines.append(
                    f"  H.76 {syntax.syntax_state}: sum "
                    f"{_format_number(syntax.suggested_weighted_sum)}; {suggestions}"
                )

    if result.case.interpretation:
        lines.extend(["", f"Interpretation: {result.case.interpretation}"])
    if result.expectation_mismatches:
        lines.extend(
            ["", "Unexpected differences:"]
            + [f"  - {message}" for message in result.expectation_mismatches]
        )
    lines.extend(
        [
            "",
            "Evidence: floating-point checks for the declared finite model and supplied proof objects.",
        ]
    )
    if not detailed:
        lines.append("Use --details for residuals, margins, and suggested codewords.")
    return "\n".join(lines)


def format_suite(suite: ReferenceSuite) -> str:
    lines = ["RCC RefCert reference suite", ""]
    for result in suite.cases:
        lines.append(
            f"{result.case.name:28} {_case_result_label(result):24} "
            f"{result.case.purpose}"
        )
    appendix = suite.appendix_f
    appendix_label = (
        "PASS"
        if appendix.matches_reference_expectations(suite.tolerance)
        else "UNEXPECTED RESULT"
    )
    lines.extend(
        [
            f"{'Appendix F witnesses':28} {appendix_label}",
            "",
            (
                "Reference expectations: MATCH"
                if suite.matches_reference_expectations
                else "Reference expectations: MISMATCH"
            ),
            (
                "Evidence: deterministic finite-model numerical checks and supplied proof "
                "objects."
            ),
        ]
    )
    return "\n".join(lines)
