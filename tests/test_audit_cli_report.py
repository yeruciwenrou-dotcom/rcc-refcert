from dataclasses import replace

from rcc_refcert import __version__
from rcc_refcert.audit import audit_case, audit_model, audit_reference_suite
from rcc_refcert.cases import get_case
from rcc_refcert.examples import (
    make_dark_nonhalting_loop_model,
    make_dephase_or_halt_model,
)
from rcc_refcert.render import reference_payload, suite_payload
from rcc_refcert.report import build_reference_report
from rcc_refcert.status import CheckOutcome, EvidenceLevel


def test_structured_evidence_declares_artifact_roles() -> None:
    suite = audit_reference_suite(max_depth=2, max_transient_steps=2)
    revision = "a" * 40
    fresh = suite_payload(suite, source_revision=revision)
    frozen = reference_payload(suite)

    assert fresh["artifact_role"] == "fresh-run-evidence"
    assert frozen["artifact_role"] == "canonical-frozen-evidence"
    assert fresh["producer"] == {"name": "rcc-refcert", "version": __version__}
    assert frozen["producer"] == {"name": "rcc-refcert", "version": __version__}
    assert fresh["provenance"] == {
        "repository": "https://github.com/yeruciwenrou-dotcom/rcc-refcert",
        "tested_revision": revision,
    }
    assert "provenance" not in frozen
    assert "artifact_role" not in frozen["suite"]
    assert "producer" not in frozen["suite"]


def test_model_audit_keeps_mathematical_layers_separate() -> None:
    positive = audit_model(
        make_dephase_or_halt_model(), max_depth=5, max_transient_steps=8
    )
    assert positive.realization_outcome is CheckOutcome.PASS
    assert positive.linear_fixed_point_outcome is CheckOutcome.PASS
    assert positive.fixed_model_domination is not None
    assert positive.fixed_model_domination.evidence is EvidenceLevel.NUMERICAL
    assert abs(positive.fixed_model_domination.constant - 1.0) < 1e-12

    dark = audit_model(
        make_dark_nonhalting_loop_model(), max_depth=5, max_transient_steps=8
    )
    assert dark.realization_outcome is CheckOutcome.PASS
    assert dark.linear_fixed_point_outcome is CheckOutcome.NOT_APPLICABLE
    assert dark.domination_outcome is CheckOutcome.INCONCLUSIVE
    assert any("minimum fixed-point semantics" in note for note in dark.notes)


def test_unstable_linear_solve_is_inconclusive_not_a_pass() -> None:
    analysis = audit_model(make_dephase_or_halt_model())
    unstable = replace(analysis.fixed_point, condition_number=1e20)
    observed = replace(
        analysis,
        fixed_point=unstable,
        fixed_model_domination=None,
    )
    assert observed.linear_fixed_point_outcome is CheckOutcome.INCONCLUSIVE
    assert observed.domination_outcome is CheckOutcome.INCONCLUSIVE


def test_case_audit_includes_every_supplied_proof_object() -> None:
    multiblock = audit_case(
        get_case("multiblock-rectangular"), max_depth=4, max_transient_steps=8
    )
    assert multiblock.matches_expectations
    assert multiblock.bellman_choi is not None
    assert multiblock.bellman_choi.outcome is CheckOutcome.PASS
    assert len(multiblock.reference_potentials) == 1
    assert multiblock.reference_potentials[0].outcome is CheckOutcome.PASS
    assert multiblock.gain_cost is not None
    assert multiblock.gain_cost.outcome is CheckOutcome.FAIL
    assert all(
        syntax.suggested_condition_satisfied
        for syntax in multiblock.gain_cost.syntax_reports
    )


def test_reference_report_is_deterministic_and_covers_the_math_spine() -> None:
    suite = audit_reference_suite(max_depth=4, max_transient_steps=8)
    first = build_reference_report(suite)
    second = build_reference_report(suite)
    assert first == second
    for marker in (
        "Run summary",
        "H.1 realization",
        "H.2 linear fixed point",
        "H.34 fixed-model domination",
        "H.3 Bellman–Choi",
        "H.4 reference potential",
        "H.6 gain–cost",
        "Appendix F executable witnesses",
        "Scientific scope",
    ):
        assert marker in first
    assert "NUMERICAL_CHECK" not in first
    assert "`True`" not in first
    assert suite.matches_reference_expectations


def test_frozen_views_resolve_diagnostics_at_the_suite_tolerance() -> None:
    suite = audit_reference_suite(max_depth=4, max_transient_steps=8)
    multiblock = suite.cases[1]
    raw_residual = multiblock.model_analysis.fixed_point.solve_residual
    assert raw_residual is not None and 0 < raw_residual < suite.tolerance

    changed_fixed = replace(
        multiblock.model_analysis.fixed_point,
        condition_number=(
            multiblock.model_analysis.fixed_point.condition_number * (1.0 + 1e-14)
        ),
        solve_residual=0.5 * suite.tolerance,
    )
    changed_analysis = replace(multiblock.model_analysis, fixed_point=changed_fixed)
    changed_case = replace(multiblock, model_analysis=changed_analysis)
    changed_suite = replace(
        suite,
        cases=(suite.cases[0], changed_case, suite.cases[2]),
    )

    raw = suite_payload(suite, detailed=True)
    raw_changed = suite_payload(changed_suite, detailed=True)
    assert raw != raw_changed
    assert reference_payload(suite) == reference_payload(changed_suite)
    assert build_reference_report(suite) == build_reference_report(changed_suite)

    outside_fixed = replace(
        multiblock.model_analysis.fixed_point,
        solve_residual=2.0 * suite.tolerance,
    )
    outside_case = replace(
        multiblock,
        model_analysis=replace(multiblock.model_analysis, fixed_point=outside_fixed),
    )
    outside_suite = replace(
        suite,
        cases=(suite.cases[0], outside_case, suite.cases[2]),
    )
    assert reference_payload(suite) != reference_payload(outside_suite)


def test_appendix_f_status_covers_the_declared_witness_values() -> None:
    suite = audit_reference_suite(max_depth=2, max_transient_steps=2)
    appendix = suite.appendix_f
    assert appendix.matches_reference_expectations(suite.tolerance)
    wrong_constants = replace(
        appendix,
        global_reset_constants=appendix.global_reset_constants[:-1],
    )
    assert not wrong_constants.matches_reference_expectations(suite.tolerance)
