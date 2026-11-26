"""Independent exact binomial sums, acquisition boundaries, and actual RCC replay."""

import json
from fractions import Fraction as F
from importlib import resources
from math import comb

import pytest

from rcc_refcert.bounds import (
    BudgetError,
    InputError,
    binary_readout_preimage,
    bound_from_counts,
    clopper_pearson_lower,
    clopper_pearson_upper,
    load_template,
    plan_counts,
    prepare_effect_protocol,
    render_record,
    replay_record,
)
from rcc_refcert.bundle import verify_analysis_bundle
from rcc_refcert.workflows import save_effect_bundle


def tail(n, k, p):
    return sum((comb(n, j) * p**j * (1 - p) ** (n - j) for j in range(k, n + 1)), F(0))


def rebind(q):
    hashes = prepare_effect_protocol(q["protocol"])["arm_sha256"]
    for role, data in q["data"].items():
        data["arm_sha256"] = hashes[role]


def calibration(f, h):
    return {
        "kind": "known_binary",
        "false_positive": f,
        "false_negative": h,
        "source": "fixed test channel",
    }


@pytest.mark.parametrize("n", [1, 2, 5, 12, 25])
def test_exact_endpoints_against_independent_tail_sum(n):
    alpha = F(1, 20)
    for k in range(n + 1):
        l = clopper_pearson_lower(k, n, alpha)
        u = clopper_pearson_upper(k, n, alpha)
        if k:
            assert tail(n, k, l.lower) <= alpha <= tail(n, k, l.upper)
        else:
            assert l.lower == l.upper == 0
        if k < n:
            assert tail(n, n - k, 1 - u.upper) <= alpha <= tail(n, n - k, 1 - u.lower)
        else:
            assert u.lower == u.upper == 1
        assert l.upper - l.lower <= F(1, 2**48) and u.upper - u.lower <= F(1, 2**48)


def test_small_sample_integer_gain_and_freeze():
    q = load_template("binomial-counts")
    r = bound_from_counts(q)
    assert F(r["target_response_lower_exact"]) > F(3, 8)
    assert r["cost"]["integer_lower_bound_slots"] == 1
    q["protocol"]["target"]["method"] = "hoeffding"
    with pytest.raises(InputError, match="frozen"):
        bound_from_counts(q)
    rebind(q)
    assert bound_from_counts(q)["cost"]["integer_lower_bound_slots"] == 0


@pytest.mark.parametrize(
    "f,h,lo,hi,expected",
    [
        ("1/10", "1/5", "1/5", "9/10", (F(1, 7), F(1))),
        ("9/10", "4/5", "1/5", "9/10", (F(0), F(1))),
        ("9/10", "4/5", "1/5", "11/20", (F(1, 2), F(1))),
        ("1/4", "3/4", "1/4", 1, (F(0), F(1))),
        ("1/4", "3/4", "1/2", 1, None),
        ("1/2", "1/4", 0, "1/4", None),
        ("3/4", "3/4", 0, "1/5", None),
    ],
)
def test_known_readout_inverse(f, h, lo, hi, expected):
    assert binary_readout_preimage(lo, hi, f, h) == expected


@pytest.mark.parametrize(
    "f,h,decision",
    [
        (0, 0, "cost_lower_bound"),
        (1, 1, "cost_lower_bound"),
        ("3/5", "2/5", "cost_lower_bound"),
        ("1/10", "9/10", "readout_conflict"),
    ],
)
def test_calibrated_record_bundle(f, h, decision, tmp_path):
    q = load_template("binomial-counts")
    q["protocol"]["effect"]["calibration"] = calibration(f, h)
    rebind(q)
    r = bound_from_counts(q)
    assert r["decision"] == decision
    assert replay_record(r)["matches"]
    event = r["coverage"]["events"][0]
    assert event["endpoint"] == ("lower" if F(f) + F(h) <= 1 else "upper")
    assert "Observed" in render_record(r)
    if decision == "readout_conflict":
        assert event["ideal_feasible_interval"] is None and r["cost"] is None
    path = tmp_path / "study.rccbundle"
    save_effect_bundle(path, q, r)
    assert verify_analysis_bundle(path)["historical_results_supported"]


@pytest.mark.parametrize(
    "method,n,k", [("clopper_pearson", 112, 97), ("hoeffding", 253, 222)]
)
def test_minimum_design_fills_and_replays(method, n, k):
    q = load_template("sample-plan")
    q["protocol"]["target"]["method"] = method
    r = plan_counts(q)
    assert (r["samples"], r["minimum_hits"], r["maximum_hits"]) == (n, k, n)
    assert r["minimum_over_all_smaller_n"]
    exact = tail(n, k, F(9, 10))
    assert exact >= F(9, 10) and 0 <= exact - F(r["design_power_lower"]) < F(1, 10**15)
    if method == "clopper_pearson":
        assert tail(n, k, F(4, 5)) < F(1, 20) <= tail(n, k - 1, F(4, 5))
    follow = r["counts_request"]
    with pytest.raises(InputError):
        bound_from_counts(follow)
    for hits in (k - 1, k):
        follow["data"]["target"].update(
            origin="simulation", counts={"yes": hits, "no": n - hits}
        )
        measured = bound_from_counts(follow)
        assert (F(measured["target_response_lower_exact"]) > F(4, 5)) == (hits == k)
    q["max_samples"] = n - 1
    limited = plan_counts(q)
    assert (
        limited["status"] == "search_limit_reached"
        and limited["planned_protocol"] is None
    )


@pytest.mark.parametrize("method", ["clopper_pearson", "hoeffding"])
@pytest.mark.parametrize("flip", [True, False])
def test_cost_plan_matches_all_counts_at_fixed_n(method, flip):
    q = load_template("sample-plan")
    q["task"] = load_template("effect-counts")["task"]
    q["protocol"]["target"].update(method=method, state_id=q["task"]["target"]["id"])
    q["protocol"]["effect"]["calibration"] = (
        calibration("4/5", "7/10") if flip else calibration("1/10", "1/10")
    )
    q.update(
        goal={"cost_above_slots": "1/100"},
        expected_response=["1/2", "7/10"],
        fixed_samples=25,
    )
    del q["max_samples"]
    r = plan_counts(q)
    follow = r["counts_request"]
    assert r["counted_outcome"] == ("no" if flip else "yes")
    for k in range(26):
        yes = 25 - k if flip else k
        follow["data"]["target"].update(
            origin="simulation", counts={"yes": yes, "no": 25 - yes}
        )
        record = bound_from_counts(follow)
        achieved = record["cost"] is not None and F(
            record["cost"]["lower_bound_slots"]
        ) > F(1, 100)
        assert achieved == (r["minimum_hits"] <= k <= r["maximum_hits"])
    assert len(r["sensitivity"]) == 2


def test_prior_reference_preserved_and_billed_once():
    old = load_template("effect-counts")
    old["protocol"]["reference"]["method"] = "clopper_pearson"
    old["protocol"]["reference"]["samples"] = 25
    old["data"]["reference"]["counts"] = {"yes": 5, "no": 20}
    rebind(old)
    q = load_template("sample-plan")
    q["protocol"]["reference"] = old["protocol"]["reference"]
    q["reference_data"] = old["data"]["reference"]
    q["fixed_samples"] = 25
    del q["max_samples"]
    plan = plan_counts(q)
    follow = plan["counts_request"]
    follow["data"]["target"].update(origin="simulation", counts={"yes": 24, "no": 1})
    record = bound_from_counts(follow)
    assert record["reference_response_upper_exact"] == plan["reference_upper_exact"]
    assert plan["reference_event"] == record["coverage"]["events"][1]
    assert (
        record["coverage"]["coverage_at_least_exact"]
        == plan["joint_coverage_at_least_exact"]
        == "37/40"
    )
    q["reference_data"]["dataset_id"] = "wrong-source"
    with pytest.raises(InputError, match="identity"):
        plan_counts(q)


def test_resources_degenerate_design_and_strict_threshold():
    with pytest.raises(BudgetError):
        clopper_pearson_lower(10, 4097, "1/20")
    q = load_template("sample-plan")
    q["max_samples"] = 1025
    with pytest.raises(BudgetError):
        plan_counts(q)
    q["max_samples"] = 10
    q["goal"]["response_above"] = 1
    assert plan_counts(q)["status"] == "threshold_unreachable"
    q["goal"]["response_above"] = "1/2"
    q["protocol"]["effect"]["calibration"] = calibration("1/4", "3/4")
    assert plan_counts(q)["status"] == "uninformative_readout"
    del q["protocol"]["effect"]["calibration"]
    q.update(fixed_samples=1)
    del q["max_samples"]
    q["protocol"]["target"]["delta"] = "1/2"
    assert plan_counts(q)["minimum_hits"] == 2


def test_calibration_schema_and_nullable_receiving_record():
    schema = pytest.importorskip("jsonschema")
    q = load_template("effect-counts")
    q["protocol"]["reference"]["method"] = "clopper_pearson"
    q["protocol"]["effect"]["calibration"] = calibration(1, 1)
    rebind(q)
    model = json.loads(
        resources.files("rcc_refcert.bounds")
        .joinpath("data", "fixed_effect_counts.schema.json")
        .read_text()
    )
    schema.validate(q, model)


def test_cli_exports_once_and_keeps_the_frozen_acquisition(tmp_path, capsys):
    from rcc_refcert.cli import main

    plan = tmp_path / "plan.json"
    assert main(["bound", "template", "sample-plan"]) == 0
    plan.write_text(capsys.readouterr().out)
    dest = tmp_path / "study" / "counts.json"
    command = ["bound", "plan", str(plan), "--counts-request", str(dest)]
    assert main(command) == 0
    report = capsys.readouterr().out
    assert "112" in report and "97" in report
    original = dest.read_bytes()
    q = json.loads(original)
    assert q["data"]["target"]["counts"] == {"yes": None, "no": None}
    assert q["protocol"]["target"]["samples"] == 112
    assert main(command) == 2 and dest.read_bytes() == original


def test_response_planning_keeps_the_declared_uniform_support():
    request = load_template("sample-plan")
    request["task"] = load_template("effect-counts")["task"]
    del request["task"]["model"]["qualification"]["TC"]
    request["protocol"]["target"]["state_id"] = request["task"]["target"]["id"]
    request["protocol"]["reference"]["response"] = "1/10"
    assert plan_counts(request)["status"] == "threshold_unreachable"
    request["protocol"]["reference"]["response"] = "99/100"
    with pytest.raises(InputError, match="ideal support"):
        plan_counts(request)
    request["protocol"]["reference"]["kind"] = "upper_bound"
    assert plan_counts(request)["status"] == "power_met"


def test_exact_analysis_accepts_4096_while_planning_keeps_its_own_budget():
    n = 4096
    lo = clopper_pearson_lower(n // 2, n, "1/40")
    assert F("0.48") < lo.lower <= lo.upper < F("0.49")
    assert lo.upper - lo.lower <= F(1, 2**48)
    assert clopper_pearson_lower(0, n, "1/40").upper == 0
    assert clopper_pearson_upper(n, n, "1/40").lower == 1
    none = clopper_pearson_upper(0, n, "1/40")
    assert (1 - none.upper) ** n <= F(1, 40) <= (1 - none.lower) ** n
    request = load_template("effect-counts")
    for role, hits in (("target", n), ("reference", 0)):
        request["protocol"][role].update(method="clopper_pearson", samples=n)
        request["data"][role]["counts"] = {"yes": hits, "no": n - hits}
    rebind(request)
    assert replay_record(bound_from_counts(request))["matches"]
    request["protocol"]["target"]["samples"] = 4097
    with pytest.raises(BudgetError):
        prepare_effect_protocol(request["protocol"])
    plan = load_template("sample-plan")
    plan["max_samples"] = 1025
    with pytest.raises(BudgetError):
        plan_counts(plan)
