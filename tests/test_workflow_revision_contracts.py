"""Independent direction, evidence, capacity and failure-path regressions."""

from copy import deepcopy

import numpy as np
import pytest
from test_workflow_bundles import _rehash
from test_workflow_numerical import numerical_request
from test_workflow_windows import request_for

from rcc_refcert.bundle import inspect_analysis_bundle, verify_analysis_bundle
from rcc_refcert.cli import main
from rcc_refcert.examples import make_multiblock_rectangular_model
from rcc_refcert.limits import ResourceLimitError
from rcc_refcert.semantics import AcceptedProgram, program_output
from rcc_refcert.workflows import (
    StateInput,
    WorkflowLimits,
    analyze_cost,
    analyze_windows,
    load_workflow_template,
    render_workflow_result,
    save_workflow_bundle,
    serialize_numeric_model,
)
from rcc_refcert.workflows.core import BudgetError, canonical_bytes, read_json
from rcc_refcert.workflows.numerical import parse_numeric_model

POLICY = {"mode": "roundoff_only", "tolerance": 1e-10, "repair_budget": 1e-10}


def test_rectangular_migration_preserves_each_edge_and_physical_output(tmp_path):
    old = make_multiblock_rectangular_model()
    request, _ = numerical_request()
    document = serialize_numeric_model(
        old,
        subsystem_dims=[2],
        subsystem_labels=["output"],
        reference=request["model"]["reference"],
        cost=request["model"]["cost"],
    )
    assert document["schema_version"] == 2
    _, restored, _, _ = parse_numeric_model(document)
    for syntax, row in old.actions_by_syntax.items():
        for action in row:
            got = next(
                a for a in restored.actions_by_syntax[syntax] if a.name == action.name
            )
            assert set(got.continue_kraus) == set(action.continue_kraus)
            for edge, matrices in action.continue_kraus.items():
                for expected, actual in zip(matrices, got.continue_kraus[edge]):
                    assert np.array_equal(expected, actual)
    names = ["compress-and-continue", "halt-from-s1"]
    expected = program_output(old, AcceptedProgram(tuple(names), "00"))
    # The first operation traces q2 into q1; the halt prepares |1>.
    assert expected == pytest.approx(np.diag([0, 1]))
    request.update(
        model=document,
        target=StateInput.numeric(expected, [2], ["output"], policy=POLICY).as_dict(),
        candidates=[
            {
                "id": "rectangular",
                "source": "user",
                "action_names": names,
                "codeword": "00",
            }
        ],
    )
    result = analyze_cost(request)
    assert StateInput.from_dict(
        result["candidates"][0]["output"]
    ).matrix() == pytest.approx(expected)
    path = tmp_path / "rectangular.rccbundle"
    save_workflow_bundle(path, request, result)
    assert verify_analysis_bundle(path)["historical_results_supported"] is True


def test_independently_authored_direction_is_source_to_destination():
    request, _ = numerical_request()
    doc = request["model"]
    zero = [[[1, 0], [0, 0]], [[0, 0], [0, 0]]]
    identity = [[[1, 0], [0, 0]], [[0, 0], [1, 0]]]
    flip = [[[0, 0], [1, 0]], [[1, 0], [0, 0]]]
    doc.update(
        id="directed-two-control",
        subsystem_dims=[2],
        subsystem_labels=["q"],
        control_dims={"a": 2, "b": 2},
        start_syntax="s",
        initial_blocks={"a": zero},
        reference_state=[[[0.5, 0], [0, 0]], [[0, 0], [0.5, 0]]],
        actions={
            "s": [
                {
                    "name": "move",
                    "codeword": "0",
                    "successor": "s",
                    "halt_kraus": [],
                    "continue_kraus": [
                        {"source": "a", "destination": "b", "matrices": [flip]},
                        {"source": "b", "destination": "a", "matrices": [identity]},
                    ],
                },
                {
                    "name": "halt",
                    "codeword": "1",
                    "successor": None,
                    "continue_kraus": [],
                    "halt_kraus": [
                        {"source": q, "matrices": [identity]} for q in ("a", "b")
                    ],
                },
            ]
        },
    )
    request.update(
        target=StateInput.numeric(np.diag([0, 1]), [2], ["q"], policy=POLICY).as_dict(),
        candidates=[
            {
                "id": "one-move",
                "source": "user",
                "action_names": ["move", "halt"],
                "codeword": "01",
            }
        ],
    )
    result = analyze_cost(request)
    assert StateInput.from_dict(
        result["candidates"][0]["output"]
    ).matrix() == pytest.approx(np.diag([0, 1]))
    doc["schema_version"] = 1
    with pytest.raises(ValueError, match="re-export the original"):
        analyze_cost(request)


def test_legacy_self_edge_numeric_model_still_reads():
    request, _ = numerical_request()
    request["model"]["schema_version"] = 1
    assert analyze_cost(request)["decision"] == "numerical_analysis"


@pytest.mark.parametrize(
    "field",
    ["strict-decision", "status", "legality", "tolerance", "diagnostics", "evidence"],
)
def test_numeric_history_rejects_rehashed_evidence_contradictions(tmp_path, field):
    request, _ = numerical_request()
    result = analyze_cost(request)
    path = tmp_path / "numeric.rccbundle"
    save_workflow_bundle(path, request, result)

    def mutate(data):
        history = data["history.json"]
        candidate = history["candidates"][0]
        if field == "strict-decision":
            history["decision"] = "certified_optimal"
        elif field == "status":
            assert candidate["numerical_target_status"] == "outside_tolerance"
            candidate["numerical_target_status"] = "within_tolerance"
        elif field == "legality":
            candidate["legality"] = "unknown"
        elif field == "tolerance":
            candidate["comparison_tolerance"] = 1
        elif field == "diagnostics":
            history["diagnostics"]["target"]["outcome"] = "unresolved"
        else:
            history["evidence"]["candidates"] = "exact_rational"

    changed = deepcopy(result)
    mutate({"history.json": changed})
    with pytest.raises(ValueError, match="history"):
        save_workflow_bundle(tmp_path / "contradiction.rccbundle", request, changed)
    _rehash(path, mutate)
    with pytest.raises(ValueError, match="history"):
        inspect_analysis_bundle(path)
    with pytest.raises(ValueError, match="history"):
        verify_analysis_bundle(path)


def test_eight_qubit_cli_bundle_roundtrip(tmp_path, capsys):
    # Analytic maximally mixed state: every entropy deficit is exactly zero.
    state = StateInput.numeric(
        np.eye(256) / 256, [2] * 8, list("abcdefgh"), policy=POLICY
    )
    request = request_for(state, [{"id": "left", "keep": list("abcd")}])
    source = tmp_path / "large.json"
    source.write_bytes(canonical_bytes(request))
    path = tmp_path / "large.rccbundle"
    status = main(
        ["window", "analyze", str(source), "--bundle", str(path), "--format", "json"]
    )
    output = read_json(capsys.readouterr().out, document=True)
    assert status == 0
    assert output["execution"]["state"] == "completed"
    assert output["profiles"][0]["global_quantity"]["rcc_main_term"] == pytest.approx(
        0, abs=1e-12
    )
    before = path.read_bytes()
    assert inspect_analysis_bundle(path)["record_consistency"] == "pass"
    verified = verify_analysis_bundle(path)
    assert verified["historical_results_supported"] is True
    assert verified["fresh_verification"]["outcome"] == "pass"
    assert path.read_bytes() == before


def test_json_writer_and_reader_share_aggregate_budget():
    document = {"history": [None] * 210_000}
    with pytest.raises(BudgetError):
        canonical_bytes(document)
    encoded = canonical_bytes(document, document=True)
    assert read_json(encoded, document=True) == document
    with pytest.raises(BudgetError):
        read_json(encoded)
    with pytest.raises(BudgetError):
        canonical_bytes([None] * 2_000_001, document=True)


@pytest.mark.parametrize(
    "failure", [OSError("disk unavailable"), BudgetError("aggregate record limit")]
)
def test_bundle_delivery_failure_preserves_completed_calculation(
    tmp_path, capsys, monkeypatch, failure
):
    source = tmp_path / "request.json"
    source.write_bytes(canonical_bytes(load_workflow_template("cyclic-reset")))

    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr("rcc_refcert.workflows.cli.save_workflow_bundle", fail)
    status = main(
        [
            "cost",
            "analyze",
            str(source),
            "--bundle",
            str(tmp_path / "result.rccbundle"),
            "--format",
            "json",
        ]
    )
    result = read_json(capsys.readouterr().out, document=True)
    assert status == 1
    assert result["cost"]["interval_slots"] == [5, 5]
    assert result["decision"] == "certified_optimal"
    assert result["execution"] == {"state": "partial", "reason": "bundle_write_failed"}
    assert result["delivery"]["bundle"]["state"] == "failed"
    assert "was not saved" in render_workflow_result(result)
    assert not (tmp_path / "result.rccbundle").exists()


@pytest.mark.parametrize("numeric", [False, True])
@pytest.mark.parametrize("operation", [inspect_analysis_bundle, verify_analysis_bundle])
def test_recipient_budget_applies_before_matrix_allocation(
    tmp_path, monkeypatch, numeric, operation
):
    request = (
        numerical_request()[0] if numeric else load_workflow_template("cyclic-reset")
    )
    result = analyze_cost(request)
    path = tmp_path / "budget.rccbundle"
    save_workflow_bundle(path, request, result)

    def allocation(*args, **kwargs):
        pytest.fail("matrix allocation happened before recipient preflight")

    monkeypatch.setattr(np, "empty", allocation)
    monkeypatch.setattr(np, "zeros", allocation)
    monkeypatch.setattr(np, "eye", allocation)
    with pytest.raises(ResourceLimitError):
        operation(path, limits=WorkflowLimits(max_matrix_elements=8))


@pytest.mark.parametrize("case", ["invalid-target", "boundary", "failed-candidate"])
def test_numerical_cli_completion_reflects_available_evidence(tmp_path, capsys, case):
    request, _ = numerical_request()
    if case == "invalid-target":
        rho = StateInput.from_dict(request["target"]).matrix()
        rho[0, 0] += 1e-6
        request["target"] = StateInput.numeric(
            rho, [2] * 4, request["target"]["subsystem_labels"], policy=POLICY
        ).as_dict()
    elif case == "boundary":
        request["epsilon"] = "0"
    else:
        request["candidates"] = request["candidates"][:1]
    source = tmp_path / "request.json"
    source.write_bytes(canonical_bytes(request))
    result = analyze_cost(request)
    path = tmp_path / "numeric.rccbundle"
    status = main(
        ["cost", "analyze", str(source), "--bundle", str(path), "--format", "json"]
    )
    output = read_json(capsys.readouterr().out, document=True)
    if case == "failed-candidate":
        assert status == 0
        assert output["candidates"][0]["numerical_target_status"] == "outside_tolerance"
    else:
        assert status == 1
        assert output["execution"]["state"] == "partial"
        assert result["decision"] == "numerical_unresolved"
        verified = verify_analysis_bundle(path)
        assert verified["fresh_verification"]["outcome"] == "inconclusive"


@pytest.mark.parametrize("value", [None, [], "request"])
@pytest.mark.parametrize("command", ["cost", "window"])
@pytest.mark.parametrize("override", [[], ["--max-matrix-elements", "1000"]])
def test_non_object_json_is_a_structured_input_error(
    tmp_path, capsys, value, command, override
):
    source = tmp_path / "invalid.json"
    source.write_bytes(canonical_bytes(value))
    status = main([command, "analyze", str(source), "--format", "json", *override])
    captured = capsys.readouterr()
    assert status == 2
    assert "Traceback" not in captured.out + captured.err
    error = read_json(captured.out)
    assert error["schema"] == "rcc-refcert.workflow-error"
    assert error["state"] == "invalid_input"
    if command == "cost":
        with pytest.raises(ValueError, match="expected an object"):
            analyze_cost(value)


def test_unresolved_window_is_partial(tmp_path):
    request = request_for(
        StateInput.numeric(np.eye(2) * 0.6, [2], ["q"], policy=POLICY),
        [{"id": "q", "keep": ["q"]}],
    )
    result = analyze_windows(request)
    assert result["decision"] == "numerical_unresolved"
    assert result["execution"]["state"] == "partial"
    path = tmp_path / "unresolved.rccbundle"
    save_workflow_bundle(path, request, result)
    assert (
        verify_analysis_bundle(path)["fresh_verification"]["outcome"] == "inconclusive"
    )
    result["execution"]["state"] = "completed"
    with pytest.raises(ValueError, match="history"):
        save_workflow_bundle(tmp_path / "incorrect.rccbundle", request, result)
