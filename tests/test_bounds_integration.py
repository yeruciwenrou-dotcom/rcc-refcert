"""Link exact target bounds to complete finite-control program witnesses."""

import json
import os
import subprocess
import sys
from copy import deepcopy
from fractions import Fraction as Q
from pathlib import Path

import numpy as np
import pytest
from jsonschema import Draft202012Validator

from rcc_refcert import (
    BellmanChoiCertificate,
    ReferencePotentialCertificate,
    audit_model,
    linear_value_choi_envelopes,
    require_valid_model,
)
from rcc_refcert.bounds import (
    BudgetError,
    InputError,
    bound_from_spectrum,
    load_template,
    replay_record,
    with_reference_certificate,
)
from rcc_refcert.bounds.terminal_model import (
    build_terminal_model,
    declared_spectra,
    exact_semidensity_diagonal,
)
from rcc_refcert.semantics import enumerate_accepted_programs, program_output


def test_eight_output_model_has_complete_one_slot_witnesses():
    model = build_terminal_model()
    require_valid_model(model)
    result = audit_model(model, max_depth=2, max_transient_steps=1)
    assert exact_semidensity_diagonal() == (Q(1, 4),) * 4
    np.testing.assert_allclose(
        result.fixed_point.output, np.eye(4) / 4, atol=1e-14, rtol=0
    )
    programs = enumerate_accepted_programs(model, max_actions=1)
    assert len(programs) == 8
    assert {p.codeword for p in programs} == {format(i, "03b") for i in range(8)}
    for program in programs:
        spectrum = declared_spectra()[program.action_names[0]]
        np.testing.assert_allclose(
            program_output(model, program),
            np.diag([float(x) for x in spectrum]),
            atol=1e-14,
            rtol=0,
        )
        assert program.action_count == 1


@pytest.mark.parametrize("name", list(declared_spectra()))
@pytest.mark.parametrize("epsilon", ["0", "0.1", "0.3", "0.35", "0.75", "1"])
def test_bound_does_not_exceed_named_constructive_cost(name, epsilon):
    request = load_template()
    request["task"]["target"].update(id=name, epsilon=epsilon)
    request["spectrum"] = declared_spectra()[name]
    result = bound_from_spectrum(request)
    assert 0 <= Q(result["cost"]["lower_bound_slots"]) <= Q(2, 3)
    assert result["cost"]["integer_lower_bound_slots"] <= 1
    assert replay_record(json.loads(json.dumps(result)))["matches"]


def certificate_for(model, method):
    if method == "H.3":
        return BellmanChoiCertificate(linear_value_choi_envelopes(model), 1.0)
    key = ("s", "q")
    return ReferencePotentialCertificate(
        theta={key: model.reference_state},
        a={key: 1.0},
        transition_coefficients={},
        halt_coefficients={key: 1.0},
        potential={key: 1.0},
    )


@pytest.mark.parametrize("method", ["H.3", "H.4"])
def test_certificate_adapter_is_bound_and_keeps_numerical_evidence(method):
    model = build_terminal_model()
    request = load_template()
    original = deepcopy(request)
    certificate = certificate_for(model, method)
    task = with_reference_certificate(
        request["task"], model, certificate, source="test supplied proof object"
    )
    assert request == original
    assert task["model"]["qualification"] == request["task"]["model"]["qualification"]
    reference = task["model"]["reference_domination"]
    assert reference["evidence"]["method"] == method
    assert reference["evidence"]["level"] == "numerical"
    from rcc_refcert import verify_bellman_choi, verify_reference_potential

    verify = verify_bellman_choi if method == "H.3" else verify_reference_potential
    report = verify(model, certificate)
    assert Q(reference["upper_constant"]) == Q.from_float(report.constant)
    assert Q(reference["upper_constant"]) >= report.candidate_constant
    request["task"] = task
    result = bound_from_spectrum(request)
    assert replay_record(result)["matches"]
    from importlib.resources import files

    schema = json.loads(
        files("rcc_refcert.bounds")
        .joinpath("data", "bound_record.schema.json")
        .read_text()
    )
    Draft202012Validator(schema).validate(result)
    assert result["record_role"] == "conditional_cost_lower_bound"


@pytest.mark.parametrize(
    "change", ["identity", "reference", "low_constant", "stored_report"]
)
def test_certificate_adapter_rejects_wrong_evidence(change):
    model = build_terminal_model()
    request = load_template()
    certificate = certificate_for(model, "H.3")
    if change == "identity":
        request["task"]["model"]["id"] = "other"
    elif change == "reference":
        model.reference_state = np.diag([0.4, 0.2, 0.2, 0.2])
    elif change == "low_constant":
        certificate.constant = 0.9
    else:
        certificate = {"outcome": "pass", "constant": 1}
    with pytest.raises(InputError):
        with_reference_certificate(
            request["task"], model, certificate, source="supplied object"
        )


def test_model_mutation_changes_the_evidence_binding():
    model = build_terminal_model()
    request = load_template()

    def identity():
        task = with_reference_certificate(
            request["task"],
            model,
            certificate_for(model, "H.3"),
            source="supplied object",
        )
        return task["model"]["reference_domination"]["evidence"]["model_sha256"]

    before = identity()
    # Changing the initial state leaves this reset model valid, but changes its identity.
    model.initial_blocks["q"] = np.diag([1.0, 0.0, 0.0, 0.0])
    assert identity() != before


def test_adapter_checks_dimension_before_allocating_reference():
    task = load_template()["task"]
    task["model"]["dimension"] = 10**100
    with pytest.raises(BudgetError):
        with_reference_certificate(
            task, build_terminal_model(), None, source="large input"
        )


def test_cli_template_compute_and_replay(tmp_path):
    def run(*args):
        result = subprocess.run(
            [sys.executable, "-m", "rcc_refcert", "bound", *args],
            cwd=tmp_path,
            text=True,
            capture_output=True,
            check=False,
            env={
                **os.environ,
                "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
            },
        )
        assert result.returncode == 0, result.stderr + result.stdout
        return result.stdout

    for name in ("spectrum", "counts"):
        request = tmp_path / f"{name}.json"
        request.write_text(run("template", name), encoding="utf-8")
        record = tmp_path / f"{name}-record.json"
        record.write_text(run(name, str(request), "--format", "json"), encoding="utf-8")
        assert json.loads(run("replay", str(record), "--format", "json"))["matches"]


def test_native_bounds_notebook_source_is_executable(tmp_path):
    # A useful code regression; native Notebook execution is a separate gate.
    notebook = json.loads(
        (
            Path(__file__).resolve().parents[1] / "RCC_Bounds_Quickstart.ipynb"
        ).read_text()
    )
    source = "\n\n".join(
        "".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code"
    )
    result = subprocess.run(
        [sys.executable, "-c", source],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
        env={
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
        },
    )
    assert result.returncode == 0, result.stderr
