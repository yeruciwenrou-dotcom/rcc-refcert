"""Finite counts, physical scope, joint evidence, and independent recipient replay."""

import json
from copy import deepcopy
from fractions import Fraction as F
from itertools import combinations, pairwise
from math import log2

import pytest

from rcc_refcert.bounds import InputError, hoeffding_lower
from rcc_refcert.bounds.multinomial import HistogramRegion
from rcc_refcert.bounds.scalar import Interval
from rcc_refcert.bundle import inspect_analysis_bundle, verify_analysis_bundle
from rcc_refcert.cli import main
from rcc_refcert.limits import ResourceLimitError
from rcc_refcert.workflows import (
    analyze_windows,
    load_workflow_template,
    prepare_pvm_protocol,
    save_workflow_bundle,
)


def fixture(name="pvm-counts"):
    return load_workflow_template(name)


def freeze(entry):
    entry["data"]["protocol_sha256"] = prepare_pvm_protocol(entry["protocol"])[
        "protocol_sha256"
    ]


def batch(request):
    return analyze_windows(request)["batches"][0]


def test_four_outcomes_match_best_joint_subset_and_single_event_comparison():
    req = fixture()
    r = analyze_windows(req)
    b = r["batches"][0]
    point = b["process"][0]
    assert r["coverage"]["at_least"] == "99/100"
    assert point["pooled_outcomes"] == ["0", "1"]
    assert F(".34832863") < F(point["one_shot_lower_bits"]) < F(".34832864")
    assert point["cost"]["integer_lower_bound_slots"] == 1
    assert F(".11610") < F(point["cost"]["lower_bound_slots"]) < F(".11612")
    counts = list(b["counts"].values())
    s = F(b["tv_radius_upper"]) + F(".3")
    ratios = [
        (sum(F(counts[i], 20000) for i in group) - s) / F(len(group), 4)
        for k in range(1, 5)
        for group in combinations(range(4), k)
    ]
    assert F(point["cap_ratio_exact"]) == max(ratios)
    assert (
        max((hoeffding_lower(k, 20000, "1/400").lower - F(".3")) * 4 for k in counts)
        < 1
    )
    best = (hoeffding_lower(19000, 20000, "1/100").lower - F(".3")) * 2
    assert log2(float(best)) > 0.35449 > float(point["one_shot_lower_bits"])


def test_joint_window_comparison_and_quantum_scope():
    req = fixture("bell-ghz-counts")
    r = analyze_windows(req)
    assert r["coverage"]["at_least"] == "99/100"
    assert (
        F(".37086784")
        < F(r["comparisons"][0]["difference_lower_st_R"])
        < F(".37086785")
    )
    for e in req["batches"]:
        e["protocol"]["measurement"]["window_scope"] = "containing_quantum"
        freeze(e)
    r = analyze_windows(req)
    assert r["comparisons"][0]["difference_lower_st_R"] is None
    b = r["batches"][1]
    assert b["window"]["window_st_R"]["upper"] is None
    assert F(b["window"]["classical_st_R"]["upper"]) < F(".565")
    assert b["process"][0]["cost"] is None


@pytest.mark.parametrize("radius", [F(0), F(1, 40), F(1, 8), F(1, 2), F(1)])
def test_unequal_rank_optimization_against_direct_search(radius):
    counts = [4, 3, 1, 0]
    ranks = [1, 2, 3, 2]
    region = HistogramRegion(counts, ranks, radius)
    bounds, q = region.classical(Interval.point(1))
    assert sum(q) == 1 and min(q) >= 0
    assert sum(abs(p - x) for p, x in zip(region.p, q)) / 2 <= radius
    for a in range(9):
        for b in range(9 - a):
            for c in range(9 - a - b):
                v = [F(i, 8) for i in (a, b, c, 8 - a - b - c)]
                if sum(abs(x - y) for x, y in zip(v, region.p)) / 2 <= radius:
                    d = sum(
                        float(x) * log2(float(x / y)) for x, y in zip(v, region.u) if x
                    )
                    assert (
                        float(bounds.lower) - 1e-14 <= d <= float(bounds.upper) + 1e-14
                    )
    _, cap, group = region.smooth_floor(F(1, 20))
    direct = max(
        [F(1)]
        + [
            (sum(region.p[i] for i in g) - radius - F(1, 20))
            / sum(region.u[i] for i in g)
            for k in range(1, 5)
            for g in combinations(range(4), k)
        ]
    )
    assert cap == direct
    assert bool(group) == (cap > 1)


def test_marginals_and_arbitrary_complete_coarse_windows_reuse_coverage():
    req = fixture("product-counts")
    req["tolerances"] = ["0", "1/10", "1"]
    e = req["batches"][0]
    e["coarse_windows"] = {
        "parity": {x: str(x[0] != x[1]) for x in ("00", "01", "10", "11")}
    }
    r = analyze_windows(req)
    b = r["batches"][0]
    assert len(r["coverage"]["events"]) == 1
    assert b["coarse_windows"]["parity"]["ranks"] == {"False": 2, "True": 2}
    assert b["counts"] == {"00": 10000, "01": 0, "10": 0, "11": 10000}
    for w in b["product"]["marginals"].values():
        assert w["counts"] == {"0": 10000, "1": 10000}
        assert F(w["window_st_R"]["lower"]) == 0
    lo, hi = (
        F(b["product"]["classical_correlation_st_R"][k]) for k in ("lower", "upper")
    )
    assert F(".3456") < lo <= hi == F(1, 2)
    assert b["process"][-1]["one_shot_lower_bits"] == "0"
    with pytest.raises(ResourceLimitError):
        analyze_windows(req, limits={"max_windows": 4})
    del e["coarse_windows"]["parity"]["01"]
    with pytest.raises(InputError, match="coarse-graining"):
        analyze_windows(req)


def test_retention_random_denominator_and_known_zero_have_distinct_meanings():
    req = fixture("retained-counts")
    r = analyze_windows(req)
    b = r["batches"][0]
    assert r["coverage"]["at_least"] == "99/100" and len(r["coverage"]["events"]) == 2
    assert b["state_object"] == "normalized_projected_state"
    assert (
        F(b["retention"]["probability_lower"])
        == hoeffding_lower(20000, 25000, "1/200").lower
    )
    assert F(b["retention"]["discounted_state_lower_st_R"]) > F(".35")
    assert b["process"][0]["cost"] is None
    e = req["batches"][0]
    e["data"].update(discarded=25000, counts={})
    b = batch(req)
    assert b["status"] == "no_retained_observations" and b["window"] is None
    assert "discounted_state_exact_st_R" not in b["retention"]
    e["protocol"]["retention"] = {
        "method": "known",
        "probability": "0",
        "state": "normalized_projected",
        "source": "orthogonal sector",
    }
    freeze(e)
    b = batch(req)
    assert (
        b["status"] == "conditional_state_undefined"
        and b["retention"]["discounted_state_exact_st_R"] == "0"
    )
    e["data"].update(discarded=24999, counts={"00": 1})
    with pytest.raises(InputError, match="deterministic retention"):
        batch(req)


def test_conditioned_per_count_and_cp_retention():
    req = fixture("retained-counts")
    e = req["batches"][0]
    e["protocol"].update(samples=50)
    e["protocol"]["retention"]["method"] = "clopper_pearson"
    e["data"].update(discarded=25, counts={"00": 25})
    freeze(e)
    b = batch(req)
    full = deepcopy(req)
    p = full["batches"][0]
    p["protocol"].update(samples=25, support="no_leakage")
    del p["protocol"]["retention"], p["data"]["discarded"]
    freeze(p)
    assert b["window"] == batch(full)["window"]


def test_single_outcome_and_large_blocks_without_spectrum_expansion():
    req = fixture()
    del req["models"]
    p = req["batches"][0]["protocol"]
    d = 1 << 100
    p.update(dimension=d, delta=0)
    p["measurement"]["ranks"] = {"all": d}
    e = req["batches"][0]
    e["data"]["counts"] = {"all": 20000}
    freeze(e)
    r = analyze_windows(req)
    assert r["coverage"]["at_least"] == "1"
    b = r["batches"][0]
    assert b["tv_radius_upper"] == "0" and b["window"]["classical_st_R"] == {
        "lower": "0",
        "upper": "0",
    }
    p["measurement"]["ranks"] = {"thin": 1, "wide": d - 1}
    p["delta"] = "1/100"
    e["data"]["counts"] = {"thin": 20000}
    freeze(e)
    assert F(batch(req)["process"][0]["one_shot_lower_bits"]) > 99


def test_scan_and_multiple_settings_only_combine_equal_process_tasks():
    req = fixture()
    e = deepcopy(req["batches"][0])
    e["protocol"].update(event_id="second measurement", dataset_id="second batch")
    e["protocol"]["measurement"]["setting"] = "computational basis"
    e["data"].update(dataset_id="second batch", counts={"0": 20000})
    freeze(e)
    req["batches"].append(e)
    req["tolerances"] = ["0", "3/10"]
    r = analyze_windows(req)
    assert (
        len(r["strongest_process_bounds"]) == 2 and r["coverage"]["at_least"] == "49/50"
    )
    assert all(
        b["event_id"] == "second measurement"
        for b in r["strongest_process_bounds"].values()
    )
    del req["models"]["pure-0"]["qualification"]["RA"]
    r = analyze_windows(req)
    assert not r["strongest_process_bounds"]
    assert r["batches"][0]["process"][0]["missing_process_premises"] == ["RA"]
    req["comparisons"] = [[q["protocol"]["event_id"] for q in req["batches"]]]
    with pytest.raises(InputError, match="common window"):
        analyze_windows(req)


@pytest.mark.parametrize("form", ["text", "markdown"])
def test_quantum_window_and_measured_marginals_are_identified_on_each_row(form):
    from rcc_refcert.workflows import render_workflow_result

    request = fixture("product-counts")
    entry = request["batches"][0]
    entry["protocol"]["measurement"].update(
        window_scope="containing_quantum", window="AB"
    )
    entry["data"]["counts"] = dict.fromkeys(["00", "01", "10", "11"], 5000)
    freeze(entry)
    report = render_workflow_result(analyze_windows(request), format=form, width=180)
    assert "AB (containing quantum window): >= 0 st_R" in report
    for name in ("A", "B"):
        assert (
            f"{name} (measured classical marginal): >= 0, <= 0.0514642595 st_R"
            in report
        )
    assert "classical correlation (measured classical window): >= 0, <=" in report


def test_retained_batches_keep_their_identity_and_calibration_in_the_figure(
    tmp_path, monkeypatch
):
    pytest.importorskip("matplotlib")
    from rcc_refcert.workflows import windows
    from rcc_refcert.workflows.pvm_render import export_pvm

    request = fixture("retained-counts")
    first = request["batches"][0]
    second = deepcopy(first)
    request["batches"].append(second)
    for entry, label in zip(request["batches"], ["run-A", "run-B"]):
        entry["protocol"].update(dataset_id=label, event_id=label + "-measurement")
        entry["protocol"]["retention"]["event_id"] = label + "-retention"
        entry["data"]["dataset_id"] = label
        freeze(entry)
    second["data"]["counts"] = dict.fromkeys(["00", "01", "10", "11"], 5000)

    def inspect(fig, path, overwrite):
        fig.canvas.draw()
        ax = fig.axes[0]
        labels = [label.get_text() for label in ax.get_yticklabels()]
        assert len(set(labels)) == len(labels) == 10
        assert all(
            sum(batch in label for label in labels) == 5 for batch in ["run-A", "run-B"]
        )
        extent = ax.xaxis.label.get_window_extent(fig.canvas.get_renderer())
        assert 0 <= extent.x0 < extent.x1 <= fig.bbox.width

    monkeypatch.setattr(windows, "save_window_figure", inspect)
    export_pvm(analyze_windows(request), None, tmp_path / "retained.png", False)


def test_repeated_window_acquisitions_keep_distinct_csv_and_figure_labels(tmp_path):
    import csv
    from importlib.util import find_spec

    from rcc_refcert.workflows.pvm_render import export_pvm

    request = fixture()
    first = request["batches"][0]
    second = deepcopy(first)
    second["protocol"].update(event_id="repeat-event", dataset_id="repeat-dataset")
    second["data"]["dataset_id"] = "repeat-dataset"
    freeze(second)
    request["batches"].append(second)
    result = analyze_windows(request)
    csv_path = tmp_path / "windows.csv"
    export_pvm(result, csv_path, None, False)
    with csv_path.open() as handle:
        rows = list(csv.DictReader(handle))
    assert {(r["dataset_id"], r["event_id"]) for r in rows} == {
        (e["data"]["dataset_id"], e["protocol"]["event_id"]) for e in (first, second)
    }
    if find_spec("matplotlib"):
        from matplotlib import rc_context

        svg = tmp_path / "windows.svg"
        with rc_context({"svg.fonttype": "none"}):
            export_pvm(result, None, svg, False)
        drawing = svg.read_text()
        assert all(e["data"]["dataset_id"] in drawing for e in (first, second))
        assert (
            "Interval lower endpoint" in drawing
            and "Interval upper endpoint" in drawing
        )


@pytest.mark.parametrize(
    ("preset", "copies"), [("pvm-counts", 2), ("product-counts", 3)]
)
def test_plot_labels_and_legend_clear_the_intervals(
    preset, copies, tmp_path, monkeypatch
):
    import csv

    pytest.importorskip("matplotlib")
    from rcc_refcert.workflows import windows
    from rcc_refcert.workflows.pvm_render import export_pvm

    request = fixture(preset)
    original = request["batches"][0]
    request["batches"] = []
    for i in range(1, copies + 1):
        batch = deepcopy(original)
        batch["protocol"].update(dataset_id=f"Run {i}", event_id=f"Acquisition {i}")
        batch["data"]["dataset_id"] = f"Run {i}"
        freeze(batch)
        request["batches"].append(batch)
    result = analyze_windows(request)

    csv_path = tmp_path / "windows.csv"

    def inspect_figure(fig, path, overwrite):
        fig.canvas.draw()
        ax = fig.axes[0]
        renderer = fig.canvas.get_renderer()
        labels = ax.get_yticklabels()
        assert len(labels) == (2 if copies == 2 else 12)
        boxes = [label.get_window_extent(renderer) for label in labels]
        assert all(upper.y0 > lower.y1 for upper, lower in pairwise(boxes))
        assert not fig.legends[0].get_window_extent(renderer).overlaps(ax.bbox)
        assert all(
            f"Run {i}" in " ".join(label.get_text() for label in labels)
            for i in range(1, copies + 1)
        )
        with csv_path.open() as handle:
            data = list(csv.DictReader(handle))
        for line, y, row in zip(ax.collections, ax.get_yticks(), data, strict=True):
            ((left, right),) = line.get_segments()
            assert tuple(left) == (float(row["lower_st_R"]), y)
            assert tuple(right) == (float(row["upper_st_R"]), y)

    monkeypatch.setattr(windows, "save_window_figure", inspect_figure)
    export_pvm(result, csv_path, tmp_path / "windows.png", False)


@pytest.mark.parametrize(
    "change",
    [
        "dataset",
        "hash",
        "rank",
        "total",
        "extra",
        "origin",
        "boolean",
        "event",
        "product",
        "reference",
        "support",
    ],
)
def test_invalid_evidence(change):
    req = fixture("product-counts")
    e = req["batches"][0]
    p = e["protocol"]
    data = e["data"]
    if change == "dataset":
        data["dataset_id"] = "other"
    if change == "hash":
        p["measurement"]["setting"] = "different basis"
    if change == "rank":
        p["measurement"]["ranks"]["00"] = 2
    if change == "total":
        data["counts"]["01"] = 1
    if change == "extra":
        data["counts"]["other"] = 0
    if change == "origin":
        data["origin"] = "unknown"
    if change == "boolean":
        data["counts"]["01"] = False
    if change == "event":
        req["batches"].append(deepcopy(e))
    if change == "product":
        p["measurement"]["product"]["coordinates"]["00"] = ["1", "1"]
    if change == "reference":
        p["reference_treatment"] = "Gibbs"
    if change == "support":
        p["support"] = "projected_branch"
    with pytest.raises(InputError):
        analyze_windows(req)


def test_cli_freeze_export_and_peer_replay(tmp_path, capsys):
    assert main(["window", "template", "pvm-counts"]) == 0
    raw = json.loads(capsys.readouterr().out)
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps(raw))
    proto = tmp_path / "protocol.json"
    proto.write_text(json.dumps(raw["batches"][0]["protocol"]))
    assert main(["window", "prepare-protocol", str(proto)]) == 0
    assert (
        json.loads(capsys.readouterr().out)["protocol_sha256"]
        == raw["batches"][0]["data"]["protocol_sha256"]
    )
    archive = tmp_path / "example.rccbundle"
    csv = tmp_path / "window.csv"
    assert (
        main(
            [
                "window",
                "analyze",
                str(input_path),
                "--bundle",
                str(archive),
                "--csv",
                str(csv),
            ]
        )
        == 0
    )
    assert (
        "integer bound 1" in capsys.readouterr().out
        and "lower_st_R,upper_st_R" in csv.read_text()
    )
    assert inspect_analysis_bundle(archive)["physical_revalidation"] == "not_run"
    verified = verify_analysis_bundle(archive)
    assert (
        verified["historical_results_supported"]
        and verified["same_version_replay"]["status"] == "match"
    )
    forged = deepcopy(verified["fresh_result"])
    forged["batches"][0]["process"][0]["cost"]["integer_lower_bound_slots"] = True
    with pytest.raises(InputError):
        save_workflow_bundle(tmp_path / "changed.rccbundle", raw, forged)


def test_installed_pvm_schema_and_recomputed_history(tmp_path):
    from importlib import resources

    from rcc_refcert.workflows.bundles import _write_json_bundle
    from rcc_refcert.workflows.core import digest

    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(
        resources.files("rcc_refcert.workflows")
        .joinpath("data", "pvm_request.schema.json")
        .read_text()
    )
    jsonschema.Draft202012Validator.check_schema(schema)
    for name in ("pvm-counts", "bell-ghz-counts", "product-counts", "retained-counts"):
        jsonschema.validate(fixture(name), schema)
    raw = fixture()
    wrong = analyze_windows(raw)
    wrong["batches"][0]["process"][0]["cost"]["integer_lower_bound_slots"] = 99
    archive = tmp_path / "changed-history.rccbundle"
    _write_json_bundle(
        archive,
        raw,
        wrong,
        version=4,
        kind="pvm_windows",
        author=wrong["producer"],
        request_digest=digest(raw),
        overwrite=False,
    )
    assert (
        inspect_analysis_bundle(archive)["record_consistency"] == "input_bindings_pass"
    )
    result = verify_analysis_bundle(archive)
    assert result["fresh_verification"]["outcome"] == "pass"
    assert result["historical_results_supported"] is False
    assert result["same_version_replay"]["status"] == "mismatch"
    assert (
        result["fresh_result"]["batches"][0]["process"][0]["cost"][
            "integer_lower_bound_slots"
        ]
        == 1
    )


def test_comparison_report_uses_both_window_intervals_in_either_input_order():
    from rcc_refcert.workflows import render_workflow_result

    raw = load_workflow_template("bell-ghz-counts")
    for _ in range(2):
        report = render_workflow_result(
            analyze_windows(raw), format="markdown", details=True
        )
        assert (
            "0.3708678405 st_R higher for Bell pair than for GHZ reduced pair" in report
        )
        for detail in (
            "Gamma=4",
            "1 st_R = 2 bits",
            "uniform-C4",
            "classical measurement window",
        ):
            assert detail in report
        assert report.count("supply a preparation model") == 1
        assert report.index("0.3708678405 st_R higher") < report.index(
            "Protocol SHA-256"
        )
        raw["comparisons"][0].reverse()

    left, right = raw["batches"]
    right["data"]["counts"] = left["data"]["counts"].copy()
    report = render_workflow_result(analyze_windows(raw), format="markdown")
    assert "Bell pair minus GHZ reduced pair) lies between -" in report
    assert "higher for" not in report
    for entry in raw["batches"]:
        entry["protocol"]["measurement"]["window_scope"] = "containing_quantum"
        freeze(entry)
    report = render_workflow_result(
        analyze_windows(raw), format="markdown", details=True
    )
    assert report.index(
        "leave the ordering of Bell pair and GHZ reduced pair open"
    ) < report.index("Protocol SHA-256")


def test_retention_export_separates_conditional_interval_and_discounted_lower(tmp_path):
    import csv

    from rcc_refcert.workflows import (
        analyze_pvm_windows,
        export_window_files,
        render_workflow_result,
    )

    request = fixture("retained-counts")
    result = analyze_pvm_windows(request)
    path = tmp_path / "retention.csv"
    export_window_files(result, csv_path=path)
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    conditional, discounted = rows[0], rows[-1]
    assert conditional["kind"] == "conditional_window" and conditional["upper_st_R"]
    assert (
        discounted["kind"] == "retention_weighted_lower"
        and discounted["upper_st_R"] == ""
    )
    assert float(discounted["lower_st_R"]) == pytest.approx(0.35268060472)
    assert (discounted["retained"], discounted["discarded"]) == ("20000", "5000")
    report = render_workflow_result(result)
    assert (
        "25,000 trials (synthetic counts, 20,000 retained and 5,000 discarded)"
        in " ".join(report.split())
    )
    entry = request["batches"][0]
    entry["protocol"]["samples"] = 4096
    entry["protocol"]["retention"]["method"] = "clopper_pearson"
    entry["data"].update(counts={"00": 2048, "11": 2048}, discarded=0)
    freeze(entry)
    assert analyze_pvm_windows(request)["batches"][0]["retention"]["retained"] == 4096
    entry["protocol"]["samples"] += 1
    from rcc_refcert.bounds import BudgetError

    with pytest.raises(BudgetError):
        freeze(entry)


def test_export_names_the_scope_and_an_undetermined_comparison(tmp_path):
    import csv
    from importlib.util import find_spec

    from rcc_refcert.workflows import export_window_files

    request = fixture("bell-ghz-counts")
    for entry in request["batches"]:
        entry["protocol"]["measurement"]["window_scope"] = "containing_quantum"
        freeze(entry)
    result = analyze_windows(request)
    path = tmp_path / "pair.csv"
    export_window_files(result, csv_path=path)
    with path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert {row["window_scope"] for row in rows} == {"containing_quantum"}
    comparison = rows[-1]
    assert comparison["status"] == "ordering_undetermined"
    assert comparison["lower_st_R"] == comparison["upper_st_R"] == ""
    if find_spec("matplotlib"):
        from matplotlib import rc_context

        svg = tmp_path / "pair.svg"
        with rc_context({"svg.fonttype": "none"}):
            export_window_files(result, plot_path=svg)
        assert "Ordering undetermined" in svg.read_text()

    # The local projective marginals and their correlation still describe classical outcomes.
    request = fixture("product-counts")
    entry = request["batches"][0]
    entry["protocol"]["measurement"]["window_scope"] = "containing_quantum"
    freeze(entry)
    export_window_files(analyze_windows(request), csv_path=path, overwrite=True)
    with path.open(newline="") as stream:
        joint, *components = csv.DictReader(stream)
    assert joint["window_scope"] == "containing_quantum"
    assert len(components) == 3
    assert all(row["window_scope"] == "classical_blocks" for row in components)


@pytest.mark.parametrize("known_zero", [False, True])
def test_exports_distinguish_zero_retained_shots_from_zero_probability(
    tmp_path, known_zero
):
    import csv
    from importlib.util import find_spec

    from rcc_refcert.workflows import export_window_files, render_workflow_result

    request = fixture("retained-counts")
    entry = request["batches"][0]
    protocol = entry["protocol"]
    entry["data"].update(counts={}, discarded=protocol["samples"])
    if known_zero:
        protocol["retention"] = {
            "state": "normalized_projected",
            "method": "known",
            "probability": "0",
            "source": "Declared zero retention probability for this preparation.",
        }
    freeze(entry)
    result = analyze_windows(request)
    path = tmp_path / "retained.csv"
    export_window_files(result, csv_path=path)
    with path.open(newline="") as stream:
        conditional, weighted = csv.DictReader(stream)
    assert conditional["lower_st_R"] == conditional["upper_st_R"] == ""
    assert weighted["lower_st_R"] == "0"
    assert weighted["upper_st_R"] == ("0" if known_zero else "")
    assert weighted["kind"] == (
        "retention_weighted_exact" if known_zero else "retention_weighted_lower"
    )
    report = render_workflow_result(result, format="markdown")
    assert "25,000 trials (synthetic counts, 0 retained and 25,000 discarded)" in report
    assert ("contribution is exactly 0 st_R" in report) == known_zero
    if find_spec("matplotlib"):
        from matplotlib import rc_context

        svg = tmp_path / "retained.svg"
        with rc_context({"svg.fonttype": "none"}):
            export_window_files(result, plot_path=svg)
        drawing = svg.read_text()
        assert ("Exact value" in drawing) == known_zero
        assert ("One-sided lower bound" in drawing) != known_zero
        assert (
            "Conditional state undefined" if known_zero else "No retained observations"
        ) in drawing


def test_missing_plot_dependency_gives_a_working_install_hint(
    tmp_path, monkeypatch, capsys
):
    import sys

    monkeypatch.setitem(sys.modules, "matplotlib.backends.backend_agg", None)
    source = tmp_path / "request.json"
    source.write_text(json.dumps(fixture("bell-ghz-counts")))
    csv_path = tmp_path / "result.csv"
    plot_path = tmp_path / "result.png"
    args = ["window", "analyze", str(source), "--plot", str(plot_path)]
    assert main([*args, "--csv", str(csv_path), "--format", "markdown"]) == 1
    report = capsys.readouterr().out
    assert 'python -m pip install "matplotlib>=3.8"' in report
    assert "0.3708678405 st_R higher" in report
    assert csv_path.is_file() and not plot_path.exists()
    assert main([*args, "--format", "json"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["delivery"]["plot"]["reason"] == "optional_plot_dependency_missing"
