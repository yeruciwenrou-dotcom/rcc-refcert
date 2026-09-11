"""Matrix bindings, finite truncation and serialized scalar boundaries."""

import json
import os
import subprocess
import sys
from copy import deepcopy
from fractions import Fraction as Q
from pathlib import Path

import numpy as np
import pytest

from rcc_refcert import Action, BellmanChoiCertificate, FiniteControlModel
from rcc_refcert.bounds import (
    BudgetError,
    InputError,
    bound_from_counts,
    bound_from_spectrum,
    load_template,
    prepare_protocol,
    replay_record,
    validate_record,
    with_reference_certificate,
)
from rcc_refcert.bounds.certificates import _snapshot
from rcc_refcert.bounds.contracts import Task, canonical_hash, json_ready
from rcc_refcert.bounds.scalar import decimal_endpoint, rational
from rcc_refcert.limits import ComputationLimits
from rcc_refcert.quantum import choi_from_kraus
from rcc_refcert.semantics import depth_contribution_by_maps, truncated_semidensity
from rcc_refcert.weights import NumericalRangeError


def identity_halt(d):
    identity = np.eye(d, dtype=complex)
    model = FiniteControlModel(
        syntax_states=("s",),
        control_dims={"q": d},
        actions_by_syntax={
            "s": (Action("halt", "0", None, halt_kraus={"q": (identity,)}),)
        },
        start_syntax="s",
        initial_blocks={"q": identity / d},
        output_dim=d,
        reference_state=identity / d,
        name=f"identity-halt-{d}",
    )
    # W = H + Tr(.) I/(4d): W(sigma) = 3 sigma/4, leaving slack below C=1.
    matrix = choi_from_kraus((identity,)) / 2 + np.eye(d * d) / (4 * d)
    proof = BellmanChoiCertificate({("s", "q"): matrix}, 1.0)
    task = load_template()["task"]
    task["model"].update(id=model.name, dimension=d, reference_id=f"uniform-{d}")
    task["model"]["qualification"] = {
        key: {"basis": "user_declared", "source": "binding test fixture"}
        for key in ("RCon", "TC", "RA")
    }
    return model, proof, task


@pytest.mark.parametrize("d", [10, 11, 16])
def test_h3_binding_across_matrix_snapshot_boundary(d):
    model, proof, task = identity_halt(d)
    bound = with_reference_certificate(task, model, proof, source="identity-halt")
    reference = bound["model"]["reference_domination"]
    assert reference["upper_constant"] == "1"
    assert reference["evidence"]["outcome"] == "pass"
    assert reference["evidence"]["level"] == "numerical"
    assert reference["evidence"]["input_hash_format"] == "rcc-refcert.matrix-bytes.v1"


def test_matrix_hash_preserves_values_shape_dtype_and_logical_order():
    matrix = np.arange(12, dtype=np.float64).reshape(3, 4).astype(complex)
    matrix += 1j * matrix / 4
    digest = canonical_hash(_snapshot(matrix))
    padded = np.zeros((3, 8), dtype=complex)
    padded[:, ::2] = matrix
    for same in (np.asfortranarray(matrix), matrix.astype(">c16"), padded[:, ::2]):
        assert canonical_hash(_snapshot(same)) == digest
    changed = matrix.copy()
    changed[1, 1] += 0.125
    for different in (changed, matrix.reshape(4, 3), matrix.astype(np.complex64)):
        assert canonical_hash(_snapshot(different)) != digest
    with pytest.raises(InputError, match="numeric NumPy dtype"):
        _snapshot(np.array([object()], dtype=object))
    with pytest.raises(BudgetError, match="10000"):
        canonical_hash([0] * 10001)


@pytest.mark.parametrize("change", ["control_dimension", "blocks", "kraus", "proof"])
def test_binding_budget_precedes_hashing_and_verification(monkeypatch, change):
    model, proof, task = identity_halt(4)
    if change == "control_dimension":
        model.control_dims["q"] = 40
    elif change == "blocks":
        model.syntax_states = tuple(f"s{i}" for i in range(16))
    elif change == "kraus":
        action = model.actions_by_syntax["s"][0]
        action.halt_kraus["q"] *= 100
    else:
        proof.choi_envelopes[("s", "q")] = np.broadcast_to(0.0, (64, 64))

    def unexpected(*args, **kwargs):
        pytest.fail("budget rejection must precede hashing and verification")

    monkeypatch.setattr("rcc_refcert.bounds.certificates._snapshot", unexpected)
    monkeypatch.setattr(
        "rcc_refcert.bounds.certificates.verify_bellman_choi", unexpected
    )
    with pytest.raises(BudgetError, match="certificate_matrix_elements"):
        with_reference_certificate(
            task,
            model,
            proof,
            source="preflight",
            limits=ComputationLimits(max_matrix_elements=1024),
        )


def test_binding_budget_is_configurable():
    model, proof, task = identity_halt(11)
    with pytest.raises(BudgetError, match="preflight estimate"):
        with_reference_certificate(
            task,
            model,
            proof,
            source="budget",
            limits=ComputationLimits(max_matrix_elements=10000),
        )
    assert (
        with_reference_certificate(
            task,
            model,
            proof,
            source="budget",
            limits=ComputationLimits(max_matrix_elements=40000),
        )["model"]["reference_domination"]["upper_constant"]
        == "1"
    )


def test_legacy_hash_declarations_remain_valid_and_unknown_formats_fail():
    model, proof, task = identity_halt(4)
    task = with_reference_certificate(task, model, proof, source="identity-halt")
    legacy = deepcopy(task)
    del legacy["model"]["reference_domination"]["evidence"]["input_hash_format"]
    record = bound_from_spectrum({"task": legacy, "spectrum": ["1", "0", "0", "0"]})
    validate_record(record)
    assert replay_record(record)["matches"]
    task["model"]["reference_domination"]["evidence"]["input_hash_format"] = "unknown"
    with pytest.raises(InputError, match="hash format"):
        Task.from_dict(task)


def test_truncation_does_not_propagate_an_unused_underflowing_state():
    model, _, _ = identity_halt(1)
    identity = np.ones((1, 1), dtype=complex)
    model.actions_by_syntax["s"] = (
        Action("continue", "0" * 600, "s", continue_kraus={("q", "q"): (identity,)}),
        Action("halt", "1", None, halt_kraus={"q": (identity,)}),
    )
    first = depth_contribution_by_maps(model, 1)
    second = depth_contribution_by_maps(model, 2)
    assert first[0, 0] == 0.5
    assert second[0, 0] == 2.0**-601
    np.testing.assert_array_equal(truncated_semidensity(model, 0), first)
    np.testing.assert_array_equal(truncated_semidensity(model, 1), first + second)
    with pytest.raises(NumericalRangeError, match="underflow"):
        truncated_semidensity(model, 2)


@pytest.mark.parametrize("route", ["spectrum", "counts"])
@pytest.mark.parametrize(
    "gamma",
    [
        10**2095,
        10**2096,
        2**8192 - 1,
        Q(1, 3 * 10**2000),
        Q(1, 3 * 10**2001),
        Q(1, 2**8192 - 1),
    ],
    ids=[
        "large-neighbor",
        "large",
        "max-integer",
        "tiny-neighbor",
        "tiny",
        "max-denominator",
    ],
)
def test_extreme_exact_inputs_complete_the_record_roundtrip(route, gamma):
    request = load_template(route)
    request["task"]["model"]["transcription"]["gamma_bits"] = gamma
    assert rational(gamma) == gamma
    if route == "counts":
        spec = {k: v for k, v in request["protocol"].items() if k != "task_fingerprint"}
        frozen = prepare_protocol(request["task"], spec)
        request["protocol"] = frozen["protocol"]
        request["data"]["protocol_sha256"] = frozen["protocol_sha256"]
    compute = bound_from_spectrum if route == "spectrum" else bound_from_counts
    record = json.loads(json.dumps(compute(request)))
    validate_record(record)
    assert replay_record(record)["matches"]
    assert record["analysis_state"] == "complete"
    lower = decimal_endpoint(record["parameters"]["beta_bits"]["lower"])
    upper = decimal_endpoint(record["parameters"]["beta_bits"]["upper"])
    assert lower <= gamma <= upper
    if gamma > 1:
        assert record["cost"]["lower_bound_slots"] == "0"
        assert record["cost"]["zero_reason"] == "model_overhead_exhausted"


@pytest.mark.parametrize("gamma", [10**2096, Q(1, 3 * 10**2001)], ids=["large", "tiny"])
def test_extreme_endpoint_cli_compute_and_replay(tmp_path, gamma):
    request = load_template()
    request["task"]["model"]["transcription"]["gamma_bits"] = gamma
    input_file = tmp_path / "request.json"
    record_file = tmp_path / "record.json"
    input_file.write_text(json.dumps(json_ready(request)), encoding="utf-8")
    for command, path in (("spectrum", input_file), ("replay", record_file)):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "rcc_refcert",
                "bound",
                command,
                str(path),
                "--format",
                "json",
            ],
            cwd=tmp_path,
            env={
                **os.environ,
                "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
            },
            capture_output=True,
            text=True,
            check=True,
        )
        if command == "spectrum":
            record_file.write_text(completed.stdout, encoding="utf-8")
        else:
            assert json.loads(completed.stdout)["matches"]


@pytest.mark.parametrize("value", ["1e8193", "1e-8193", "0." + "1" * 511])
def test_result_decimal_parser_remains_bounded(value):
    with pytest.raises(BudgetError):
        decimal_endpoint(value)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "1/2", "nonsense", 1.0])
def test_result_decimal_parser_rejects_non_decimal_or_nonfinite_values(value):
    with pytest.raises(InputError):
        decimal_endpoint(value)


def test_result_representation_does_not_expand_user_input_budgets():
    assert decimal_endpoint("1e2096") == 10**2096
    with pytest.raises(BudgetError):
        rational("1e2096")
    with pytest.raises(BudgetError):
        rational(2**8192)
