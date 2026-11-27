"""Tabulate the scientific fields of a finite-study result for plotting or reuse."""

import csv
import io
import json


def study_table(record):
    """CSV rows preserve exact stored endpoints and identify the quantity and units."""
    rows = []

    def row(
        sample,
        quantity,
        unit,
        lower,
        upper=None,
        *,
        origin,
        tolerance=False,
        summary=None,
    ):
        rows.append(
            (
                record["decision"],
                sample,
                quantity,
                unit,
                lower,
                upper,
                origin,
                record["epsilon"] if tolerance else None,
                summary["coverage_at_least"] if summary else None,
                json.dumps(summary["witnesses"], ensure_ascii=False)
                if summary
                else None,
                json.dumps(summary["events"], ensure_ascii=False) if summary else None,
            )
        )

    if record["decision"] == "cluster":
        profiles = [record["color_windows"], record["z_windows"]]
        if "strongest_bounds" in record:
            for scope, summary in record["strongest_bounds"].items():
                attributes = {
                    "origin": record["sources"]["A"]["origin"],
                    "tolerance": True,
                    "summary": summary,
                }
                row(
                    scope,
                    "one_shot_information",
                    "bit",
                    summary["one_shot_bits_lower"],
                    **attributes,
                )
                if summary["integer_slots"] is not None:
                    row(
                        scope,
                        "process_cost",
                        "integer_slot",
                        summary["integer_slots"],
                        **attributes,
                    )
        for name, v in record["witnesses"].items():
            # Both colors of the joint graph event share the declared preparation and origin.
            origin = record["sources"][name if name in ("A", "B") else "A"]["origin"]
            row(
                name,
                "occupation",
                "probability",
                v["target_response_lower"],
                origin=origin,
            )
            row(
                name,
                "one_shot_information",
                "bit",
                v["one_shot_bits_lower"],
                origin=origin,
                tolerance=True,
            )
            if v["integer_slots"] is not None:
                row(
                    name,
                    "process_cost",
                    "integer_slot",
                    v["integer_slots"],
                    origin=origin,
                    tolerance=True,
                )
    else:
        profiles = [record["finite_windows"]]
        for name, v in record["observed_polarizations"].items():
            row(
                name,
                "polarization",
                "polarization",
                v["lower"],
                v["upper"],
                origin=record["sources"][name]["origin"],
            )
        c = record["calibrated"]
        row(
            c["event"],
            "calibrated_polarization",
            "polarization",
            c["polarization_lower"],
            c["polarization_upper"],
            origin=record["sources"]["calibrated"]["origin"],
        )
        row(
            "complete model target",
            "model_cost",
            "integer_slot",
            record["model_cost"]["lower_bound_slots"],
            record["model_cost"]["upper_bound_slots"],
            origin="preparation_model",
            tolerance=True,
        )
    for profile in profiles:
        for b in profile["batches"]:
            v = b["window"]["window_st_R"]
            row(
                b["dataset_id"],
                "classical_window",
                "st_R",
                v["lower"],
                v["upper"],
                origin=b["origin"],
            )
            if b["product"]:
                v = b["product"]["classical_correlation_st_R"]
                row(
                    b["dataset_id"],
                    "classical_correlation",
                    "st_R",
                    v["lower"],
                    v["upper"],
                    origin=b["origin"],
                )
    file = io.StringIO(newline="")
    writer = csv.writer(file)
    writer.writerow(
        (
            "study",
            "measurement_or_task",
            "quantity",
            "unit",
            "lower",
            "upper",
            "evidence_origin",
            "generation_epsilon",
            "coverage_at_least",
            "witnesses",
            "coverage_events",
        )
    )
    writer.writerows(rows)
    return file.getvalue()
