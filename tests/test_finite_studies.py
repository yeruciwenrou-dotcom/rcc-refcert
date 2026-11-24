"""Research tasks, register alignment, evidence scope and recipient replay."""

import json
from copy import deepcopy
from fractions import Fraction as F
from pathlib import Path
from types import SimpleNamespace

import pytest

from rcc_refcert.bounds import InputError
from rcc_refcert.bundle import inspect_analysis_bundle, verify_analysis_bundle
from rcc_refcert.cli import main
from rcc_refcert.workflows import (
    analyze_study,
    import_readout,
    prepare_study_protocol,
    qiskit_readout,
    save_workflow_bundle,
    study_template,
)
from rcc_refcert.workflows.bundles import _write_json_bundle
from rcc_refcert.workflows.core import digest


def test_cluster_at_common_budget_and_color_event():
    r = analyze_study(study_template("cluster"))
    w = r["witnesses"]
    assert [a["hits"] for a in r["color_events"]] == [8574, 8574]
    assert [v["integer_slots"] for v in w.values()] == [1, 1, 2]
    assert w["graph intersection"]["events"] == [e["id"] for e in r["color_events"]]
    assert (
        F(w["graph intersection"]["target_response_lower"])
        == 2 * F(w["A"]["target_response_lower"]) - 1
    )
    assert r["strategy_coverage"] == "99/100" and r["joint_coverage"] == "97/100"
    assert r["z_control"]["bits_lower"] == "0"
    small = analyze_study(study_template("cluster", shots=10))
    assert small["witnesses"]["graph intersection"]["integer_slots"] == 0
    assert r["budget_per_strategy"] == 20000
    req = study_template("cluster", noise="1/2")
    assert analyze_study(req)["witnesses"]["graph intersection"]["integer_slots"] == 0
    req["process_model"] = None
    assert all(
        v["integer_slots"] is None for v in analyze_study(req)["witnesses"].values()
    )
    assert study_template("cluster", noise="0")["process_model"] is None


def test_model_or_data_identity_changes_are_detected():
    req = study_template("cluster")
    req["parameters"]["noise"] = "1/10"
    with pytest.raises(InputError):
        analyze_study(req)
    req = study_template("cluster")
    req["acquisitions"]["A"]["data"]["dataset_id"] = "other"
    with pytest.raises(InputError):
        analyze_study(req)
    req = study_template("cluster")
    req["acquisitions"]["A"]["protocol"]["layout"]["registers"][0][
        "bits_lsb_first"
    ].reverse()
    with pytest.raises(InputError):
        analyze_study(req)
    req = study_template("cluster")
    req["failure"] = "1/50"
    with pytest.raises(InputError):
        analyze_study(req)


def test_replacing_the_measured_state_changes_the_witness():
    req = study_template("cluster")
    req["acquisitions"]["Z"]["data"].update(
        origin="simulation", source="uniform Z control from the same simulation"
    )
    for color in ("A", "B"):
        e = req["acquisitions"][color]
        # For either color a string with all X results negative fails the color test.
        e["data"].update(origin="simulation", source="all X eigenvalues negative")
        key = "".join("1" if s == "X" else "0" for s in e["protocol"]["setting"])
        e["data"]["outcomes"] = {"counts": {key: 10000}}
    r = analyze_study(req)
    assert r["witnesses"]["graph intersection"]["integer_slots"] == 0


def test_cooling_scopes_sampling_and_change_of_model():
    req = study_template("cooling")
    r = analyze_study(req)
    assert r["model_cost"]["interval_slots"] == [6, 6]
    assert r["candidates"]["shorter-program"]["trace_distance_exact"] == "81/6250"
    assert r["candidates"]["target-program"]["slots"] == 8
    assert r["sampling_plan"]["samples"] == 39
    assert r["sampling_plan"]["minimum_hits"] <= 39
    assert r["joint_coverage"] == "99/100"
    assert len(r["finite_windows"]["coverage"]["events"]) == 3
    assert r["finite_windows"]["batches"][0]["product"]["marginals"].keys() == {
        "q1",
        "bath",
    }
    assert F(r["calibrated"]["polarization_lower"]) > F(".93")
    assert (
        r["model_cost"]["task_core_digest"]
        != analyze_study(study_template("cooling", bath="4/5"))["model_cost"][
            "task_core_digest"
        ]
    )
    e = req["acquisitions"]["calibrated"]
    e["data"]["outcomes"] = {"counts": {"1": 10000}}
    conflict = analyze_study(req)
    assert conflict["calibrated"]["status"] == "readout_conflict"
    assert conflict["model_cost"] == r["model_cost"]


def test_archived_hardware_counts_and_projected_axis():
    root = Path(__file__).resolve().parents[1] / "examples" / "readouts"
    data = json.loads((root / "sherbrooke_counts.json").read_text())
    layout = json.loads((root / "sherbrooke_layout.json").read_text())
    for axis, expected in (("c0", 524), ("c3", 291)):
        r = import_readout(data, {**layout, "axes": [axis]})
        assert r["samples"] == 1024 and r["counts"]["1"] == expected
    with pytest.raises(InputError):
        import_readout({"counts": {"01": 1}}, layout)
    with pytest.raises(InputError):
        import_readout({"counts": {"0101": -1}}, layout)


def test_qiskit_adapter_preserves_shot_pairing_and_rejects_unselected_locations():
    class Register:
        num_bits = 1
        shape = (2,)

        def __init__(self, values):
            self.values = values

        def get_bitstrings(self, loc):
            assert loc == 0
            return self.values

    layout = {
        "registers": [{"name": name, "bits_lsb_first": [name]} for name in ("b", "a")],
        "axes": ["a", "b"],
    }
    pub = SimpleNamespace(
        data=SimpleNamespace(a=Register(["1", "0", "1"]), b=Register(["0", "1", "0"]))
    )
    with pytest.raises(InputError, match="location"):
        qiskit_readout(pub, layout)
    raw = qiskit_readout(pub, layout, loc=0)
    assert import_readout(raw, layout)["counts"] == {"10": 2, "01": 1}
    assert import_readout(
        {"bitstrings": ["0 1", "1 0", "0 1"]}, layout
    ) == import_readout(raw, layout)


@pytest.mark.parametrize("name", ["cluster", "cooling"])
def test_study_cli_transfer_and_consistently_changed_history(name, tmp_path, capsys):
    assert main(["study", "template", name]) == 0
    req = json.loads(capsys.readouterr().out)
    input_path = tmp_path / "request.json"
    input_path.write_text(json.dumps(req))
    archive = tmp_path / "result.rccbundle"
    assert (
        main(
            [
                "study",
                "analyze",
                str(input_path),
                "--bundle",
                str(archive),
                "--format",
                "json",
            ]
        )
        == 0
    )
    record = json.loads(capsys.readouterr().out)
    assert (
        inspect_analysis_bundle(archive)["record_consistency"] == "input_bindings_pass"
    )
    v = verify_analysis_bundle(archive)
    assert (
        v["historical_results_supported"]
        and v["same_version_replay"]["status"] == "match"
    )
    wrong = deepcopy(record)
    wrong["joint_coverage"] = "1"
    with pytest.raises(InputError):
        save_workflow_bundle(tmp_path / "bad.rccbundle", req, wrong)
    _write_json_bundle(
        archive,
        req,
        wrong,
        version=5,
        kind="finite_study",
        author=wrong["producer"],
        request_digest=digest(req),
        overwrite=True,
    )
    assert verify_analysis_bundle(archive)["historical_results_supported"] is False
    p = next(iter(req["acquisitions"].values()))["protocol"]
    input_path.write_text(json.dumps(p))
    assert main(["study", "prepare-protocol", str(input_path)]) == 0
    assert json.loads(capsys.readouterr().out) == prepare_study_protocol(p)


def test_state_identity_and_large_native_per_shot_bundle(tmp_path):
    r = study_template("cluster")
    e = r["acquisitions"]["Z"]
    e["data"]["origin"] = "observed_counts"
    with pytest.raises(InputError, match="preparation identity"):
        analyze_study(r)
    e["data"]["origin"] = "synthetic_fixture"
    e["protocol"]["preparation_id"] = "separately prepared target"
    e["data"]["protocol_sha256"] = prepare_study_protocol(e["protocol"])[
        "protocol_sha256"
    ]
    with pytest.raises(InputError, match="preparation identity"):
        analyze_study(r)
    e["protocol"]["preparation_id"] = r["acquisitions"]["A"]["protocol"][
        "preparation_id"
    ]
    e["data"]["protocol_sha256"] = prepare_study_protocol(e["protocol"])[
        "protocol_sha256"
    ]
    canonical = analyze_study(r)
    histogram = e["data"]["outcomes"]["counts"]
    e["data"]["outcomes"] = [bits for bits, n in histogram.items() for _ in range(n)]
    result = analyze_study(r)
    assert result["run_id"] != canonical["run_id"]
    assert (
        result["witnesses"] == canonical["witnesses"]
        and len(e["data"]["outcomes"]) == 20000
    )
    path = tmp_path / "shots.rccbundle"
    save_workflow_bundle(path, r, result)
    assert verify_analysis_bundle(path)["historical_results_supported"]


def test_color_readout_against_statevector_with_independent_basis_rotation():
    import numpy as np

    from rcc_refcert.workflows.study_cluster import COLORS, EDGES, syndrome

    q = F(1, 20)
    bits = np.array([[int(c) for c in format(i, "06b")] for i in range(64)])
    amplitudes = (-1.0) ** sum(bits[:, a] * bits[:, b] for a, b in EDGES) / 8
    h = np.array([[1, 1], [1, -1]]) / np.sqrt(2)
    for color, sites in COLORS.items():
        basis = np.ones((1, 1))
        for k in range(6):
            basis = np.kron(basis, h if k in sites else np.eye(2))
        weights = np.zeros(64)
        for noise in bits:
            weight = int(noise.sum())
            psi = amplitudes * ((-1.0) ** (bits @ noise))
            weights += (
                float(q**weight * (1 - q) ** (6 - weight)) * abs(basis @ psi) ** 2
            )
        acceptance = sum(
            p
            for i, p in enumerate(weights)
            if not any(syndrome(format(i, "06b"), color))
        )
        assert acceptance == pytest.approx(float((1 - q) ** 3))


def test_partial_cooling_run_replays_its_recorded_budget(tmp_path):
    from rcc_refcert.workflows.studies import render_study

    request = study_template("cooling")
    result = analyze_study(request, limits={"max_dp_updates": 10})
    assert result["analysis_state"] == "partial"
    assert result["model_cost"]["interval_slots"] == [3, 6]
    assert "Partial analysis" in render_study(result)
    path = tmp_path / "limited.rccbundle"
    save_workflow_bundle(path, request, result)
    report = verify_analysis_bundle(path)
    assert report["same_version_replay"]["status"] == "match"
    assert report["fresh_verification"]["outcome"] == "inconclusive"
    assert report["historical_results_supported"] is None
    assert report["fresh_result"]["model_cost"]["interval_slots"] == [3, 6]
    full = analyze_study(request)
    save_workflow_bundle(path, request, full, overwrite=True)
    restricted = verify_analysis_bundle(path, limits={"max_dp_updates": 10})
    assert restricted["same_version_replay"]["status"] == "inconclusive"
    assert restricted["fresh_result"]["analysis_state"] == "partial"


def test_study_report_and_csv_keep_observation_and_model_sources():
    import csv
    import io

    from rcc_refcert.workflows.studies import render_study
    from rcc_refcert.workflows.study_tables import study_table

    request = study_template("cooling")
    for key in ("calibrated", "target-program"):
        request["acquisitions"][key]["data"]["origin"] = "observed_counts"
    result = analyze_study(request)
    for markdown in (True, False):
        report = render_study(result, markdown=markdown)
        for label in (
            "synthetic counts",
            "observed counts",
            "complete model target",
            "1/50",
        ):
            assert label in report
    rows = list(csv.DictReader(io.StringIO(study_table(result))))
    model = next(row for row in rows if row["quantity"] == "model_cost")
    assert (model["evidence_origin"], model["generation_epsilon"]) == (
        "preparation_model",
        "1/50",
    )
    assert {
        row["evidence_origin"] for row in rows if row["quantity"] == "polarization"
    } == {"synthetic_fixture", "observed_counts"}


@pytest.mark.parametrize("workflow,fmt", [("study", "text"), ("window", "markdown")])
def test_failed_optional_deliveries_leave_scientific_results_visible(
    tmp_path, capsys, workflow, fmt
):
    from rcc_refcert.workflows import load_workflow_template

    request = (
        study_template("cluster")
        if workflow == "study"
        else load_workflow_template("pvm-counts")
    )
    source = tmp_path / "input.json"
    source.write_text(json.dumps(request))
    archive = tmp_path / "recipient.rccbundle"
    assert (
        main(
            [
                workflow,
                "analyze",
                str(source),
                "--format",
                fmt,
                "--csv",
                str(source / "table.csv"),
                "--bundle",
                str(archive),
            ]
        )
        == 1
    )
    output = capsys.readouterr().out
    assert "CSV was not saved" in output
    assert ("graph intersection" if workflow == "study" else "st_R") in output
    assert verify_analysis_bundle(archive)["historical_results_supported"]
    assert (
        main(
            [
                workflow,
                "analyze",
                str(source),
                "--format",
                fmt,
                "--bundle",
                str(source / "receipt.rccbundle"),
            ]
        )
        == 1
    )
    report = capsys.readouterr().out
    assert "Bundle was not saved" in report and "receipt.rccbundle" in report


@pytest.mark.parametrize("study", [True, False])
def test_finite_report_details_and_width_follow_the_cli_options(
    tmp_path, capsys, study
):
    from rcc_refcert.workflows import load_workflow_template

    raw = study_template("cluster") if study else load_workflow_template("pvm-counts")
    src = tmp_path / "request.json"
    src.write_text(json.dumps(raw))
    args = ["study" if study else "window", "analyze", str(src)]
    entry = raw["acquisitions"]["A"] if study else raw["batches"][0]
    binding = entry["data"]["protocol_sha256"]
    assert main([*args, "--width", "40"]) == 0
    brief = capsys.readouterr().out
    assert max(map(len, brief.splitlines())) <= 40
    assert binding not in brief
    assert main([*args, "--details", "--format", "markdown"]) == 0
    detailed = capsys.readouterr().out
    assert binding in detailed and entry["data"]["dataset_id"] in detailed
    assert detailed.startswith("# ") and "Run: " in detailed


def test_cooling_report_describes_a_future_measurement_and_its_limits():
    from rcc_refcert.workflows.studies import render_study

    default = analyze_study(study_template("cooling"))
    text = render_study(default)
    assert "37 ground-state outcomes in 39 shots" in text
    assert "4/5 with 99% confidence" in text and "power of 90%" in text
    assert "target exactly in 8 slots" in text
    point = default["observed_polarizations"]["shorter-program"]
    row = next(
        line
        for line in text.splitlines()
        if line.startswith("After the 2-cycle program,")
    )
    endpoints = row.split("[", 1)[1].split("]", 1)[0]
    lo, hi = (F(x) for x in endpoints.split(","))
    assert lo <= F(point["lower"]) <= F(point["upper"]) <= hi
    low_bath = render_study(analyze_study(study_template("cooling", bath="51/100")))
    assert "no sample size through 512 shots reaches power 90%" in low_bath
    assert "None" not in low_bath


def test_user_supplied_synthetic_counts_keep_their_own_source():
    from rcc_refcert.workflows.studies import render_study

    request = study_template("cluster")
    for acquisition in request["acquisitions"].values():
        acquisition["data"]["source"] = "A separate synthetic dataset"
    report = render_study(analyze_study(request), details=True)
    assert "This analysis uses synthetic counts." in report
    assert "A separate synthetic dataset" in report
    assert "analytic probabilities" not in report
    assert (
        "Z-basis control gives a one-shot information lower bound of 0 bits" in report
    )


def test_broadcast_coordinates_validated_before_the_sdk_reads_any_shots():
    reg = SimpleNamespace(num_bits=1, shape=(1, 2))
    pub = SimpleNamespace(data=SimpleNamespace(a=reg, b=reg))
    layout = {
        "registers": [{"name": k, "bits_lsb_first": [k]} for k in ("a", "b")],
        "axes": ["a", "b"],
    }
    for loc in (None, 0, (0,), (0, 2), (False, 0), (0, slice(None))):
        with pytest.raises(InputError, match="complete parameter location"):
            qiskit_readout(pub, layout, loc=loc)
    pub.data.b = SimpleNamespace(num_bits=1, shape=(2,))
    with pytest.raises(InputError, match="same parameter shape"):
        qiskit_readout(pub, layout, loc=(0, 0))


def test_cluster_strongest_bounds_follow_the_joint_events_through_exports(tmp_path):
    import csv
    import io

    from rcc_refcert.workflows.studies import render_study
    from rcc_refcert.workflows.study_tables import study_table

    req = study_template("cluster", noise="1/4")
    result = analyze_study(req)
    assert result["schema_version"] == 2
    binary = result["strongest_bounds"]["binary_colors"]
    assert binary["witnesses"] == ["A", "B"] and binary["integer_slots"] == 1
    assert result["witnesses"]["graph intersection"]["integer_slots"] == 0
    assert binary["coverage_at_least"] == "99/100" and len(binary["events"]) == 2
    req["acquisitions"]["Z"]["data"]["outcomes"] = {"counts": {"000000": 20000}}
    result = analyze_study(req)
    assert result["strongest_bounds"]["binary_colors"] == binary
    combined = result["strongest_bounds"]["all_measurements"]
    assert (
        combined["witnesses"][0].startswith("Z histogram")
        and combined["integer_slots"] == 2
    )
    assert (
        combined["coverage_at_least"] == "97/100" and len(set(combined["events"])) == 5
    )
    for markdown in (True, False):
        report = render_study(result, markdown=markdown)
        assert all(
            x in report for x in ("99%", "97%", "1 slot", "2 slots", "Z histogram")
        )
    rows = list(csv.DictReader(io.StringIO(study_table(result))))
    for scope, strongest in result["strongest_bounds"].items():
        row = next(
            r
            for r in rows
            if r["measurement_or_task"] == scope and r["quantity"] == "process_cost"
        )
        assert int(row["lower"]) == strongest["integer_slots"]
        assert row["coverage_at_least"] == strongest["coverage_at_least"]
        assert json.loads(row["coverage_events"]) == strongest["events"]
        assert json.loads(row["witnesses"]) == strongest["witnesses"]
    path = tmp_path / "joint.rccbundle"
    save_workflow_bundle(path, req, result)
    assert (
        verify_analysis_bundle(path)["fresh_result"]["strongest_bounds"]
        == result["strongest_bounds"]
    )
    req["process_model"] = None
    state_only = analyze_study(req)["strongest_bounds"]["all_measurements"]
    assert (
        state_only["integer_slots"] is None and F(state_only["one_shot_bits_lower"]) > 0
    )


def test_twelve_cycle_target_reaches_six_slots_and_preserves_historical_replay(
    tmp_path,
):
    from rcc_refcert.workflows.studies import _analyze_study

    req = study_template("cooling", cycles=12)
    result = analyze_study(req)
    candidate = result["candidates"]["cycle-prefix-2"]
    assert F(candidate["trace_distance_exact"]) < F(1, 50) and candidate["slots"] == 6
    assert result["model_cost"]["interval_slots"] == [6, 6]
    assert result["model_cost"]["upper_witness_ids"] == ["cycle-prefix-2"]
    assert set(result["sources"]) == {
        "target-program",
        "shorter-program",
        "after-compression",
        "calibrated",
    }
    previous = _analyze_study(req, limits=None, record_version=1)
    assert previous["model_cost"]["interval_slots"] == [6, 24]
    path = tmp_path / "previous.rccbundle"
    save_workflow_bundle(path, req, previous)
    verified = verify_analysis_bundle(path)
    assert verified["same_version_replay"]["status"] == "match"
    assert verified["historical_results_supported"] is True
    assert verified["fresh_result"]["model_cost"]["interval_slots"] == [6, 6]


@pytest.mark.parametrize("fmt", ["text", "markdown", "json"])
def test_failed_main_report_keeps_results_and_successful_deliveries(
    tmp_path, capsys, fmt
):
    source = tmp_path / "request.json"
    source.write_text(json.dumps(study_template("cluster", noise="1/4")))
    archive, csv = tmp_path / "result.rccbundle", tmp_path / "rows.csv"
    args = ["study", "analyze", str(source), "--format", fmt, "--width", "160"]
    assert (
        main(
            [
                *args,
                "--output",
                str(source / "report"),
                "--csv",
                str(csv),
                "--bundle",
                str(archive),
            ]
        )
        == 1
    )
    fallback = capsys.readouterr().out
    if fmt == "json":
        result = json.loads(fallback)
        assert result["strongest_bounds"]["binary_colors"]["integer_slots"] == 1
        assert result["delivery"]["report"]["state"] == "failed"
        assert all(
            result["delivery"][name]["state"] == "saved" for name in ("csv", "bundle")
        )
    else:
        assert all(
            x in fallback
            for x in ("1 slot", "Report was not saved", archive.name, csv.name)
        )
    assert (
        csv.is_file()
        and verify_analysis_bundle(archive)["historical_results_supported"]
    )
    recovered = tmp_path / "report"
    assert (
        main([*args, "--output", str(recovered)]) == 0 and recovered.stat().st_size > 0
    )


def test_partial_study_cli_identifies_the_budget_and_retry(tmp_path, capsys):
    source = tmp_path / "request.json"
    source.write_text(json.dumps(study_template("cooling")))
    args = ["study", "analyze", str(source), "--max-dp-updates"]
    assert main([*args, "10"]) == 1
    output = capsys.readouterr().out
    assert "10 updates" in output and "--max-dp-updates" in output
    assert main([*args, "100000", "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["model_cost"]["interval_slots"] == [6, 6]


@pytest.mark.parametrize(
    "key,limits",
    [
        ("max_matrix_elements", [24, 64, 104]),
        ("max_candidate_steps", [52, 80, 1000]),
    ],
)
def test_cooling_interval_and_candidate_replay_have_separate_evidence(
    tmp_path, key, limits
):
    from rcc_refcert.bundle_cli import render_bundle_report

    req = study_template("cooling", cycles=12)
    history = analyze_study(req)
    path = tmp_path / "history.rccbundle"
    save_workflow_bundle(path, req, history)
    for limit, interval, supported in zip(limits[:2], ([6, 24], [6, 6]), (None, True)):
        v = verify_analysis_bundle(path, limits={key: limit})
        assert v["fresh_result"]["model_cost"]["interval_slots"] == interval
        assert v["historical_results_supported"] is None
        assert v["same_version_replay"]["status"] == "inconclusive"
        info = v["candidate_replay"]
        assert (
            info["checked"]
            == len(v["fresh_result"]["candidates"])
            < info["expected"]
            == 13
        )
        assert info["historical_interval_supported"] is supported
        assert info["replayed_fields_consistent"]
        text = render_bundle_report(v)
        assert "Candidate programs replayed:" in text
        assert "archived cost interval [6, 6] slots" in text
        assert (
            "verify the archived" if supported else "fresh bounds give [6, 24]"
        ) in text
    assert (
        verify_analysis_bundle(path, limits={key: limits[-1]})["same_version_replay"][
            "status"
        ]
        == "match"
    )
    # An author who used a small budget can still receive a full same-budget replay.
    small = analyze_study(req, limits={key: limits[0]})
    save_workflow_bundle(path, req, small, overwrite=True)
    v = verify_analysis_bundle(path, limits={key: limits[0]})
    assert v["historical_results_supported"] is True and "candidate_replay" not in v
    wrong = deepcopy(history)
    wrong["model_cost"].update(
        lower_bound_slots=7, upper_bound_slots=7, interval_slots=[7, 7]
    )
    _write_json_bundle(
        path,
        req,
        wrong,
        version=5,
        kind="finite_study",
        author=wrong["producer"],
        request_digest=digest(req),
        overwrite=True,
    )
    v = verify_analysis_bundle(path, limits={key: limits[1]})
    assert v["historical_results_supported"] is False
    assert v["candidate_replay"]["historical_interval_supported"] is False


@pytest.mark.parametrize(
    "kind,bad", [("study", ["--width", "39"]), ("window", ["--plot", "bad.bmp"])]
)
def test_invalid_presentation_options_can_be_retried_without_overwrite(
    tmp_path, kind, bad
):
    from rcc_refcert.workflows import load_workflow_template

    req = (
        study_template("cluster")
        if kind == "study"
        else load_workflow_template("pvm-counts")
    )
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps(req))
    args = [
        kind,
        "analyze",
        str(input_path),
        "--csv",
        str(tmp_path / "out.csv"),
        "--bundle",
        str(tmp_path / "out.rccbundle"),
    ]
    assert main([*args, *bad]) == 2
    assert list(tmp_path.iterdir()) == [input_path]
    assert main(args) == 0
