"""Independent finite-program oracles and complete-task cost contracts."""

from copy import deepcopy
from fractions import Fraction as F
from itertools import product

import numpy as np
import pytest

from rcc_refcert.bounds.scalar import BudgetError, InputError
from rcc_refcert.limits import ResourceLimitError
from rcc_refcert.semantics import AcceptedProgram, program_output
from rcc_refcert.workflows import (
    StateInput,
    WorkflowLimits,
    analyze_cost,
    compose_interval,
    load_workflow_template,
)
from rcc_refcert.workflows.core import exact, exact_text
from rcc_refcert.workflows.models import ExactModel
from rcc_refcert.workflows.presets import expand_preset


@pytest.mark.parametrize(
    "epsilon,expected", [("1/10", [5, 5]), ("9/20", [4, 4]), ("11/25", [4, 5])]
)
def test_cyclic_cost_interval(epsilon, expected):
    req = load_workflow_template("cyclic-reset")
    req["epsilon"] = epsilon
    result = analyze_cost(req)
    assert result["cost"]["interval_slots"] == expected
    assert result["evidence"]["gain"] == "exact_rational"
    for candidate in result["candidates"]:
        assert sum(F(v) for v in candidate["output"]["data"]) == 1


def _enumerated_cyclic(n, p, target, epsilon, maximum):
    """Separate bit-index simulation, including every phase/opposite reset word."""
    d = 2**n
    for length in range(maximum):
        for word in product((0, 1, 2), repeat=length):
            state = [F(1, d)] * d
            for action in word:
                if action == 2:
                    continue
                new = [F(0)] * d
                for old, probability in enumerate(state):
                    low = p if action == 0 else 1 - p
                    new[(old % (d // 2)) * 2] += probability * low
                    new[(old % (d // 2)) * 2 + 1] += probability * (1 - low)
                state = new
            if sum(abs(a - b) for a, b in zip(state, target)) / 2 <= epsilon:
                return length + 1
    return None


def test_cyclic_against_independent_accepting_words():
    req = load_workflow_template("cyclic-reset")
    target = [
        F(19, 20) ** (4 - i.bit_count()) * F(1, 20) ** i.bit_count() for i in range(16)
    ]
    for epsilon, optimum in [(F(1, 10), 5), (F(9, 20), 4), (F(11, 25), 5)]:
        assert _enumerated_cyclic(4, F(19, 20), target, epsilon, 5) == optimum
        req["epsilon"] = str(epsilon)
        result = analyze_cost(req)
        assert (
            result["cost"]["lower_bound_slots"]
            <= optimum
            <= result["cost"]["upper_bound_slots"]
        )


def _enumerated_cooling(epsilon):
    bath = [F(81, 100), F(9, 100), F(9, 100), F(1, 100)]
    target = [a * b for a in (F(3078, 3125), F(47, 3125)) for b in bath]
    for length in range(8):
        for word in product("RC", repeat=length):
            state = [F(1, 8)] * 8
            for action in word:
                if action == "C":
                    state[3], state[4] = state[4], state[3]
                else:
                    state = [
                        mass * b
                        for mass in (sum(state[:4]), sum(state[4:]))
                        for b in bath
                    ]
            if sum(abs(a - b) for a, b in zip(state, target)) / 2 <= epsilon:
                return length + 1
    return None


@pytest.mark.parametrize(
    "epsilon,interval,optimum", [("1/50", [6, 6], 6), ("1/100", [6, 8], 8)]
)
def test_cooling_independent_oracle(epsilon, interval, optimum):
    req = load_workflow_template("algorithmic-cooling")
    req["epsilon"] = epsilon
    result = analyze_cost(req)
    assert result["cost"]["interval_slots"] == interval
    assert _enumerated_cooling(F(epsilon)) == optimum
    assert result["gain_bound"]["rows"][5]["budget_max_exact"] == "729/125"


def test_modified_preset_rebuilds_target_and_program():
    req = load_workflow_template("cyclic-reset")
    old = analyze_cost(req)
    req["model"]["parameters"] = {"qubits": 3, "p": "9/10"}
    new = analyze_cost(req)
    assert new["cost"]["interval_slots"] == [4, 4]
    assert old["digests"]["task_core"] != new["digests"]["task_core"]
    assert len(old["effective_request"]["target"]["data"]) == 16


def test_complete_target_not_sorted_spectrum():
    req = analyze_cost(load_workflow_template("cyclic-reset"))["effective_request"]
    changed = deepcopy(req)
    target = changed["target"]
    target.pop("content_digest")
    target["data"] = [target["data"][i ^ 1] for i in range(16)]
    result = analyze_cost(changed)
    assert result["cost"]["upper_bound_slots"] is None
    assert result["candidates"][-1]["trace_distance_exact"] == "9/10"
    assert result["digests"]["target_digest"] != req["target"]["content_digest"]


@pytest.mark.parametrize(
    "mutation", ["wrong-code", "missing-halt", "after-halt", "unknown"]
)
def test_bad_program_never_supplies_upper(mutation):
    req = analyze_cost(load_workflow_template("cyclic-reset"))["effective_request"]
    req["candidates"] = [req["candidates"][-1]]
    p = req["candidates"][0]
    if mutation == "wrong-code":
        p["codeword"] = "0"
    if mutation == "missing-halt":
        p["action_names"].pop()
    if mutation == "after-halt":
        p["action_names"].append("phase")
    if mutation == "unknown":
        p["action_names"][0] = "absent"
    result = analyze_cost(req)
    assert result["cost"]["upper_bound_slots"] is None
    assert result["candidates"][0]["legality"] == "fail"


def test_numerical_quantum_view_preserves_physical_output():
    model, target, candidates, _ = expand_preset(
        {"preset": "cyclic_reset", "parameters": {"qubits": 2, "p": "2/3"}}
    )
    view = model.numerical_view()
    p = candidates[-1]
    out = program_output(view, AcceptedProgram(tuple(p["action_names"]), p["codeword"]))
    np.testing.assert_allclose(out, target.matrix(), atol=1e-14, rtol=0)
    assert abs(np.trace(out) - 1) < 1e-14


def test_custom_classical_channel_recipe():
    req = analyze_cost(load_workflow_template("cyclic-reset"))["effective_request"]
    model, _, _, _ = expand_preset(
        {"preset": "cyclic_reset", "parameters": {"qubits": 1, "p": "9/10"}}
    )
    doc = deepcopy(model.document)
    doc["actions"]["s"][0]["operations"] = [
        {"kind": "classical_channel", "matrix": [["9/10", "9/10"], ["1/10", "1/10"]]}
    ]
    req.update(
        model=doc,
        target=StateInput.diagonal(["9/10", "1/10"], [2], ["q1"]).as_dict(),
        candidates=[
            {
                "id": "custom",
                "action_names": ["reset-0", "halt"],
                "codeword": "0011",
                "source": "custom declared channel",
            }
        ],
        epsilon="0",
    )
    req.pop("gain_certificate")
    assert analyze_cost(req)["cost"]["interval_slots"] == [2, 2]
    bad = deepcopy(doc)
    bad["actions"]["s"][0]["operations"][0]["matrix"][0][0] = "1"
    with pytest.raises(InputError):
        ExactModel(bad)


def test_exact_inputs_and_direct_constructors():
    with pytest.raises(InputError):
        StateInput.diagonal([0.5, 0.5], [2], ["q1"])
    with pytest.raises(InputError):
        StateInput("diagonal_exact", ("1/2", "1/4"), (2,), ("q1",))
    with pytest.raises(InputError):
        WorkflowLimits(max_dp_cells=True)
    with pytest.raises(BudgetError):
        exact("1e999999999")
    with pytest.raises(BudgetError):
        exact(1 << 1_000_000)
    value = F(1 << 15000, 3)
    assert exact(exact_text(value)) == value


def test_budget_refusal_and_exact_equal_threshold():
    req = load_workflow_template("cyclic-reset")
    with pytest.raises(ResourceLimitError):
        analyze_cost(req, limits=WorkflowLimits(max_dp_cells=2))
    req["epsilon"] = "9/20"
    result = analyze_cost(req)
    assert result["gain_bound"]["rows"][3]["excluded"]
    assert not result["gain_bound"]["rows"][4]["excluded"]
    # A zero-tolerance full target is also attained by the complete exact program.
    req["epsilon"] = "0"
    assert analyze_cost(req)["cost"]["upper_bound_slots"] == 5


def test_interval_binding_and_missing_endpoints():
    with pytest.raises(InputError):
        compose_interval(2, 5, core_digest="a", epsilon="1/10", upper_core="b")
    with pytest.raises(InputError):
        compose_interval(2, 5, core_digest="a", epsilon="1/10", epsilon_upper="1/5")
    assert (
        compose_interval(0, 1, core_digest="a", epsilon="0")[
            "multiplicative_overhead_upper_exact"
        ]
        is None
    )
    assert (
        compose_interval(6, 5, core_digest="a", epsilon="0")["decision"]
        == "evidence_conflict"
    )
    req = load_workflow_template("cyclic-reset")
    req["candidates"] = []
    assert analyze_cost(req)["decision"] == "lower_bound_only"


def test_scan_preserves_separate_requests():
    req = load_workflow_template("cyclic-reset")
    req["epsilon_values"] = ["1/10", "9/20", "11/25"]
    result = analyze_cost(req)
    assert [p["cost"]["interval_slots"] for p in result["epsilon_scan"]] == [
        [5, 5],
        [4, 4],
        [4, 5],
    ]
    assert len({p["request_digest"] for p in result["epsilon_scan"]}) == 3
