from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from . import __version__
from .audit import CaseAnalysis, ReferenceSuite
from .cases import (
    H1_REALIZATION,
    H2_LINEAR_FIXED_POINT,
    H3_BELLMAN_CHOI,
    H4_REFERENCE_POTENTIAL,
    H6_GAIN_COST,
    H34_DOMINATION,
    CaseKind,
)
from .numeric import format_certificate_constant, format_number
from .status import CheckOutcome, CheckResult


def _number(
    value: float | None,
    *,
    zero_tolerance: float | None = None,
) -> str:
    return format_number(value, zero_tolerance=zero_tolerance)


def _expected_text(observed: CheckOutcome, expected: CheckOutcome | None) -> str:
    text = observed.value.replace("_", " ")
    if expected is not None and observed is expected:
        if observed in {
            CheckOutcome.FAIL,
            CheckOutcome.INCONCLUSIVE,
            CheckOutcome.NOT_APPLICABLE,
        }:
            return f"{text} (expected)"
        return text
    if expected is not None:
        return f"{text} (expected {expected.value.replace('_', ' ')})"
    return text


def _case_summary(result: CaseAnalysis) -> str:
    if not result.matches_expectations:
        return "mismatch"
    if result.case.kind is CaseKind.BOUNDARY:
        return "expected boundary"
    if any(
        outcome is CheckOutcome.FAIL for _, outcome in result.case.expected_outcomes
    ):
        return "expected route failure"
    return "pass"


def _minimum_check_value(
    checks: Iterable[CheckResult],
    *,
    starts_with: str | None = None,
    ends_with: str | None = None,
) -> float | None:
    values = []
    for check in checks:
        if starts_with is not None and not check.name.startswith(starts_with):
            continue
        if ends_with is not None and not check.name.endswith(ends_with):
            continue
        if check.value is not None:
            values.append(check.value)
    return min(values) if values else None


def _case_section(result: CaseAnalysis) -> list[str]:
    analysis = result.model_analysis
    fixed = analysis.fixed_point
    lines = [
        f"## {result.case.title}",
        "",
        result.case.purpose,
        "",
        f"RCC paper map: {', '.join(result.case.paper_references)}.",
        "",
        "| check | observed outcome | expected outcome | key value |",
        "|---|---|---|---:|",
    ]
    expected = dict(result.case.expected_outcomes)
    values = {
        H1_REALIZATION: (
            "max error "
            + _number(
                analysis.maximum_realization_error,
                zero_tolerance=analysis.tolerance,
            )
        ),
        H2_LINEAR_FIXED_POINT: f"rho(T) = {_number(fixed.spectral_radius)}",
        H34_DOMINATION: (
            "not evaluated"
            if analysis.fixed_model_domination is None
            else f"C* = {_number(analysis.fixed_model_domination.constant)}"
        ),
    }
    if result.bellman_choi is not None:
        report = result.bellman_choi
        values[H3_BELLMAN_CHOI] = format_certificate_constant(
            report.constant,
            report.candidate_constant,
            report.constant_error_bound,
        )
    if result.reference_potentials:
        values[H4_REFERENCE_POTENTIAL] = ", ".join(
            format_certificate_constant(
                report.constant, report.candidate_constant, report.constant_error_bound
            )
            for report in result.reference_potentials
        )
    if result.gain_cost is not None:
        values[H6_GAIN_COST] = ", ".join(
            f"{syntax.syntax_state}: {_number(syntax.current_weighted_sum)}"
            for syntax in result.gain_cost.syntax_reports
        )
    labels = {
        H1_REALIZATION: "H.1 realization",
        H2_LINEAR_FIXED_POINT: "H.2 linear fixed point",
        H34_DOMINATION: "H.34 fixed-model domination",
        H3_BELLMAN_CHOI: "H.3 Bellman–Choi",
        H4_REFERENCE_POTENTIAL: "H.4 reference potential",
        H6_GAIN_COST: "H.6 gain–cost",
    }
    for name, outcome in result.observed_outcomes():
        lines.append(
            f"| {labels[name]} | {_expected_text(outcome, expected.get(name))} | "
            f"{expected.get(name).value.replace('_', ' ') if name in expected else 'not specified'} | "
            f"{values[name]} |"
        )

    lines.extend(
        [
            "",
            "### Numerical diagnostics",
            "",
            (
                f"- H.1 was checked at action depths 1–{len(analysis.realization_checks)}; "
                f"the maximum spectral-norm difference was "
                f"`{_number(analysis.maximum_realization_error, zero_tolerance=analysis.tolerance)}`."
            ),
            (
                f"- The partial sum through {analysis.max_transient_steps} transient "
                "continuations has output trace "
                f"`{analysis.truncated_trace:.12g}`."
            ),
        ]
    )
    if fixed.applicable:
        lines.append(
            f"- The linear solve has condition number `{fixed.condition_number:.3e}` "
            f"and residual "
            f"`{_number(fixed.solve_residual, zero_tolerance=analysis.tolerance)}`."
        )
    else:
        lines.append(
            "- The full transient spectral radius lies at the linear-inverse boundary; "
            "the least fixed-point series remains the defining semantics."
        )

    if result.bellman_choi is not None:
        minimum = _minimum_check_value(result.bellman_choi.checks, ends_with="-psd")
        lines.append(
            f"- `{result.bellman_choi.name}` has minimum PSD residual eigenvalue "
            f"`{_number(minimum, zero_tolerance=analysis.tolerance)}`."
        )
    for report in result.reference_potentials:
        margin = _minimum_check_value(report.checks, starts_with="bellman[")
        lines.append(
            f"- `{report.name}` has minimum scalar Bellman margin "
            f"`{_number(margin, zero_tolerance=analysis.tolerance)}`."
        )
    if result.gain_cost is not None:
        lines.extend(
            [
                "",
                "### H.6 code-length diagnostic",
                "",
                "| syntax | current H.70 sum | current route | H.76 sum | suggested codewords |",
                "|---|---:|---|---:|---|",
            ]
        )
        for syntax in result.gain_cost.syntax_reports:
            route = {"pass": "passes", "fail": "fails"}.get(
                syntax.current_outcome.value, syntax.current_outcome.value
            )
            suggestions = ", ".join(
                f"`{action.action_name}={action.suggested_codeword}`"
                for action in syntax.actions
            )
            lines.append(
                f"| `{syntax.syntax_state}` | {_number(syntax.current_weighted_sum)} | "
                f"{route} | {_number(syntax.suggested_weighted_sum)} | {suggestions} |"
            )

    if result.case.interpretation:
        lines.extend(["", f"Interpretation: {result.case.interpretation}"])
    if result.expectation_mismatches:
        lines.extend(
            ["", "Unexpected differences:"]
            + [f"- {message}" for message in result.expectation_mismatches]
        )
    lines.append("")
    return lines


def build_reference_report(suite: ReferenceSuite) -> str:
    """Render a deterministic Markdown report from a completed reference suite."""

    lines: list[str] = [
        "# RCC RefCert reference report",
        "",
        (
            "This report presents executable evidence for RCC's finite-control "
            "model-qualification layer. It records declared processes, terminating "
            "program semidensities, and supplied proof objects, including diagnostics "
            "for whether action code lengths account for their reference gain. "
            "Paper references use RCC manuscript version 4."
        ),
        "",
        "## Run summary",
        "",
        f"Package: `rcc-refcert {__version__}`  ",
        f"Action depth: `1–{suite.max_depth}`  ",
        f"Maximum transient continuations: `{suite.max_transient_steps}`  ",
        f"Numerical tolerance: `{suite.tolerance:.1e}`",
        "",
        (
            "Residual diagnostics with absolute value at or below the numerical "
            "tolerance are shown as `0`. Certificate upper bounds and their error "
            "budgets round upward. Fresh CLI JSON retains the computed finite "
            "diagnostics."
        ),
        "",
        "| case | purpose | reference result |",
        "|---|---|---|",
    ]
    for result in suite.cases:
        lines.append(
            f"| `{result.case.name}` | {result.case.purpose} | {_case_summary(result)} |"
        )
    appendix_status = (
        "pass"
        if suite.appendix_f.matches_reference_expectations(suite.tolerance)
        else "mismatch"
    )
    lines.extend(
        [
            (
                f"| Appendix F witnesses | Rank encoding, reference balance, "
                f"nontrivial generation, and global reset | {appendix_status} |"
            ),
            "",
            "The summary reports agreement with the declared reference cases.",
            "",
            "## Reading the outcomes",
            "",
            "- `pass` means that a stated finite numerical condition holds at the displayed tolerance.",
            "- `fail (expected)` marks the designed cost shortfall along a sufficient route.",
            "- `inconclusive (expected)` marks a quantity left open by the current numerical route.",
            "- `not applicable (expected)` marks a mathematical boundary where that calculation is unavailable.",
            "- Matrix and certificate outcomes use floating-point numerical evidence at the displayed tolerance.",
            "",
        ]
    )
    for result in suite.cases:
        lines.extend(_case_section(result))

    appendix = suite.appendix_f
    midpoint = (appendix.natural_constant_lower + appendix.natural_constant_upper) / 2
    width = appendix.natural_constant_upper - appendix.natural_constant_lower
    word_errors = ", ".join(
        _number(value, zero_tolerance=suite.tolerance)
        for value in appendix.gamma5_word_average_errors
    )
    constants = ", ".join(
        f"n={n}: {constant}" for n, constant in appendix.global_reset_constants
    )
    lines.extend(
        [
            "## Appendix F executable witnesses",
            "",
            (
                f"- F.3 whole-word rank decoder: all `{appendix.rank_roundtrip_count}` "
                f"words over a `Gamma=5` alphabet at lengths 0–4, including the "
                "empty word, with "
                f"`{appendix.rank_roundtrip_failures}` round-trip failures."
            ),
            (
                f"- `Gamma=5` reference-balance error: "
                f"`{_number(appendix.gamma5_reference_balance_error, zero_tolerance=suite.tolerance)}`."
            ),
            f"- Word-average errors for lengths 1–5: `{word_errors}`.",
            (
                f"- Partial program Kraft mass over lengths 0–5: "
                f"`{appendix.gamma5_partial_kraft_mass:.12g}`."
            ),
            (
                f"- F.5 two-qubit witness: reset-pair balance error "
                f"`{_number(appendix.f5_reset_balance_error, zero_tolerance=suite.tolerance)}`, "
                "Bell-state generation error "
                f"`{_number(appendix.f5_generation_error, zero_tolerance=suite.tolerance)}`, "
                "and purity "
                f"`{appendix.f5_initial_purity:.2f} → {appendix.f5_final_purity:.2f}`."
            ),
            (
                f"- Natural fixed-model `C>1`: `{midpoint:.18f}`, inside a decimal "
                f"interval of width `{width:.3E}`."
            ),
            f"- Global-reset fixed-size constants: {constants}.",
            "",
            "### Global-reset H.6 diagnostic",
            "",
            "| model | current H.70 sum | current route | H.76 sum | suggested halt length |",
            "|---|---:|---|---:|---:|",
        ]
    )
    for report in appendix.global_reset_gain_costs:
        syntax = report.syntax_reports[0]
        halt = next(
            action
            for action in syntax.actions
            if action.action_name == "global-reset-and-halt"
        )
        lines.append(
            f"| `{report.model_name}` | {_number(syntax.current_weighted_sum)} | "
            f"fails as expected | {_number(syntax.suggested_weighted_sum)} | "
            f"{halt.suggested_code_length} |"
        )

    lines.extend(
        [
            "",
            "## Scientific scope",
            "",
            (
                "The calculations above establish finite-input and fixed-model numerical "
                "statements for the declared processes and supplied proof objects. They make "
                "the Appendix F/H constructions inspectable. The RCC paper supplies the physical "
                "reference-consistency, faithful-transcription (`TC`), and uniform model-family "
                "arguments used by the lower bound. An H.70 failure identifies a cost shortfall "
                "along that sufficient gain–cost route."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def write_reference_report(path: str | Path, suite: ReferenceSuite) -> Path:
    """Write a rendered reference suite to ``path``."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_reference_report(suite), encoding="utf-8")
    return output
