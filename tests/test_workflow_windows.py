"""Analytic controls and independent tensor contractions for state windows."""

from copy import deepcopy
from fractions import Fraction
from itertools import product

import numpy as np
import pytest

from rcc_refcert.bundle import inspect_analysis_bundle, verify_analysis_bundle
from rcc_refcert.workflows import (
    StateInput,
    analyze_cost,
    analyze_windows,
    export_probe,
    list_probes,
    load_workflow_template,
    save_workflow_bundle,
)
from rcc_refcert.workflows.core import InputError
from rcc_refcert.workflows.windows import reduced_matrix


def request_for(state, windows, partition=None):
    request = load_workflow_template("window-state")
    request.update(
        states=[{"id": "test", "state": state.as_dict()}],
        windows=windows,
        partition=partition,
    )
    return request


@pytest.mark.parametrize(
    "probe,expected",
    [
        ("w1-quantum-organization", [[1, 0, 1], [0.5, 0.5, 0.5]]),
        ("w2-noise-distribution", [[0.5, 0, 1], [0.75, 0, 0.75]]),
    ],
)
def test_quantum_seed_analytic_controls(probe, expected):
    result = analyze_windows(export_probe(probe))
    for profile, values in zip(result["profiles"], expected):
        assert [q["rcc_main_term"] for q in profile["windows"]] == pytest.approx(
            values, abs=1e-12
        )
        assert profile["partition"]["decomposition_residual"] == pytest.approx(
            0, abs=1e-12
        )
    if probe.startswith("w2"):
        for profile in result["profiles"]:
            assert profile["global_quantity"]["entropy_bits"] == pytest.approx(
                1, abs=1e-12
            )
        source = result["effective_request"]["states"][0]["state"]["provenance"]
        assert source["distributed_probability"] == pytest.approx(
            0.11002786443835955, abs=1e-15
        )
        assert abs(source["root_entropy_residual"]) < 1e-15


def test_partial_trace_against_explicit_index_sum_and_axis_permutation():
    rng = np.random.default_rng(811)
    dims = (2, 3, 2)
    a = rng.normal(size=(12, 12)) + 1j * rng.normal(size=(12, 12))
    rho = a @ a.conj().T
    rho /= np.trace(rho)
    # A deliberately independent index sum; complex and nonuniform dimensions
    # expose transposes and qubit-order mistakes hidden by Bell/GHZ symmetry.
    for keep in ([], [0], [1], [0, 2], [0, 1, 2]):
        kd = tuple(dims[i] for i in keep)
        expected = np.zeros((int(np.prod(kd)), int(np.prod(kd))), dtype=complex)
        for left in product(*(range(d) for d in dims)):
            for right in product(*(range(d) for d in dims)):
                if all(left[i] == right[i] for i in range(3) if i not in keep):
                    li = (
                        np.ravel_multi_index(tuple(left[i] for i in keep), kd)
                        if kd
                        else 0
                    )
                    ri = (
                        np.ravel_multi_index(tuple(right[i] for i in keep), kd)
                        if kd
                        else 0
                    )
                    expected[li, ri] += rho[
                        np.ravel_multi_index(left, dims),
                        np.ravel_multi_index(right, dims),
                    ]
        assert reduced_matrix(rho, dims, keep) == pytest.approx(expected, abs=1e-14)
    policy = {"mode": "roundoff_only", "tolerance": 1e-10, "repair_budget": 1e-10}
    state = StateInput.numeric(rho, dims, ("a", "b", "c"), policy=policy)
    perm = (2, 0, 1)
    moved = (
        rho.reshape(dims + dims)
        .transpose(perm + tuple(3 + i for i in perm))
        .reshape(12, 12)
    )
    other = StateInput.numeric(
        moved,
        tuple(dims[i] for i in perm),
        tuple(state.subsystem_labels[i] for i in perm),
        policy=policy,
    )
    window = [{"id": "ac", "keep": ["a", "c"]}]
    a = analyze_windows(request_for(state, window))["profiles"][0]["windows"][0]
    b = analyze_windows(request_for(other, window))["profiles"][0]["windows"][0]
    assert a["entropy_bits"] == pytest.approx(b["entropy_bits"], abs=1e-12)


def test_exact_marginals_empty_full_overlap_and_nested_windows():
    state = StateInput.diagonal(
        [Fraction(i, 36) for i in range(1, 9)], (2, 2, 2), ("a", "b", "c")
    )
    windows = [
        {"id": str(i), "keep": keep}
        for i, keep in enumerate([[], ["a"], ["a", "b"], ["b", "c"], ["a", "b", "c"]])
    ]
    result = analyze_windows(
        request_for(state, windows, {"left": ["a"], "right": ["b", "c"]})
    )
    p = result["profiles"][0]
    q = p["windows"]
    assert q[0]["entropy_deficit_bits"] == 0
    assert q[1]["probabilities_exact"] == ["5/18", "13/18"]
    assert q[1]["rcc_main_term"] <= q[2]["rcc_main_term"] <= q[4]["rcc_main_term"]
    assert q[4]["entropy_bits"] == p["global_quantity"]["entropy_bits"]
    assert abs(p["partition"]["decomposition_residual"]) < 1e-14
    bad = request_for(state, [{"id": "bad", "keep": ["a", "a"]}])
    with pytest.raises(InputError, match="distinct"):
        analyze_windows(bad)


def test_numerical_policy_preserves_original_and_limits_repairs():
    matrix = np.diag([1 + 1e-12, -1e-12])
    state = StateInput.numeric(matrix, (2,), ("q1",))
    request = request_for(state, [{"id": "all", "keep": ["q1"]}])
    original = deepcopy(request)
    result = analyze_windows(request)
    assert result["decision"] == "numerical_unresolved"
    assert request == original
    for budget, outcome in [
        (1e-10, "window_analysis"),
        (1e-14, "numerical_unresolved"),
    ]:
        repaired = StateInput.numeric(
            matrix,
            (2,),
            ("q1",),
            policy={
                "mode": "roundoff_only",
                "tolerance": 1e-10,
                "repair_budget": budget,
            },
        )
        r = analyze_windows(request_for(repaired, request["windows"]))
        assert r["decision"] == outcome
        if outcome == "window_analysis":
            diag = r["profiles"][0]["input_diagnostics"]
            assert diag["repair_applied"]
            assert diag["derived_digest"] != diag["original_digest"]
    invalid = StateInput.numeric(
        np.diag([1.1, -0.1]),
        (2,),
        ("q1",),
        policy={"mode": "roundoff_only", "tolerance": 1e-10, "repair_budget": 1e-10},
    )
    assert (
        analyze_windows(request_for(invalid, request["windows"]))["decision"]
        == "numerical_unresolved"
    )


def test_cooling_uses_the_candidate_trajectory_and_model_scale():
    request = export_probe("w3-cooling-trajectory")
    result = analyze_cost(request)
    profiles = result["windows"]["profiles"]
    assert result["windows"]["reference"]["g_bits"] == pytest.approx(np.log2(3))
    for c in result["candidates"]:
        for step in c["trajectory"]:
            profile = next(
                p for p in profiles if p["id"] == f"{c['id']}:{step['step']}"
            )
            assert profile["state_digest"] == step["state"]["content_digest"]
            assert abs(profile["partition"]["decomposition_residual"]) < 1e-12
            if step["action"] == "R":
                assert profile["partition"]["total_correlation_bits"] == pytest.approx(
                    0, abs=1e-12
                )
            if step["action"] == "C":
                previous = next(
                    p for p in profiles if p["id"] == f"{c['id']}:{step['step'] - 1}"
                )
                assert profile["global_quantity"]["entropy_bits"] == pytest.approx(
                    previous["global_quantity"]["entropy_bits"], abs=1e-12
                )
    assert Fraction(
        profiles[-1]["partition"]["left"]["probabilities_exact"][0]
    ) == Fraction(3078, 3125)
    request["limits"]["max_windows"] = 2
    partial = analyze_cost(request)
    assert partial["cost"] == result["cost"]
    assert partial["execution"]["state"] == "partial"


@pytest.mark.parametrize("probe", [p["probe_id"] for p in list_probes()])
def test_every_probe_exports_runs_and_revalidates(tmp_path, probe):
    request = export_probe(probe)
    result = (analyze_cost if request["kind"] == "cost_analysis" else analyze_windows)(
        request
    )
    path = tmp_path / "shared.rccbundle"
    save_workflow_bundle(path, request, result)
    assert inspect_analysis_bundle(path)["physical_revalidation"] == "not_run"
    fresh = verify_analysis_bundle(path)
    assert fresh["historical_results_supported"] is True
    assert fresh["fresh_result"]["run_id"] != result["run_id"]


def test_probe_parameter_change_has_an_identity_and_a_real_effect():
    request = export_probe("w1-quantum-organization", parameters={"mixing": "1"})
    assert (
        request["probe"]["instance_digest"]
        != export_probe("w1-quantum-organization")["probe"]["instance_digest"]
    )
    result = analyze_windows(request)
    assert all(
        abs(q["rcc_main_term"]) < 1e-14
        for p in result["profiles"]
        for q in p["windows"]
    )
    request["probe"]["parameters"]["mixing"] = "0"
    with pytest.raises(InputError, match="identity"):
        analyze_windows(request)
