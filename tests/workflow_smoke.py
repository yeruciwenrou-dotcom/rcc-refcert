"""Run installed cost, window and recipient workflows outside the checkout."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from importlib.resources import files
from pathlib import Path

from rcc_refcert.bundle import verify_analysis_bundle
from rcc_refcert.workflows import (
    analyze_cost,
    analyze_windows,
    export_probe,
    list_probes,
    load_workflow_template,
    save_workflow_bundle,
)


def main():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for name, interval in (
            ("cyclic-reset", [5, 5]),
            ("algorithmic-cooling", [6, 6]),
        ):
            request = load_workflow_template(name)
            result = analyze_cost(request)
            assert result["cost"]["interval_slots"] == interval
            path = root / (name + ".rccbundle")
            save_workflow_bundle(path, request, result)
            verified = verify_analysis_bundle(path)
            assert verified["historical_results_supported"] is True
        for probe in list_probes():
            request = export_probe(probe["probe_id"])
            result = (
                analyze_cost if request["kind"] == "cost_analysis" else analyze_windows
            )(request)
            path = root / (probe["probe_id"] + ".rccbundle")
            save_workflow_bundle(path, request, result)
            assert verify_analysis_bundle(path)["historical_results_supported"] is True
        for schema in (
            "state.schema.json",
            "request.schema.json",
            "result.schema.json",
        ):
            assert json.loads(
                files("rcc_refcert.workflows").joinpath("data", schema).read_text()
            )["$schema"]
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)

        def run(*args):
            return subprocess.run(
                [sys.executable, "-m", "rcc_refcert", *args],
                cwd=root,
                env=environment,
                text=True,
                capture_output=True,
                check=True,
            ).stdout

        request = run("cost", "template", "cyclic-reset")
        (root / "task.json").write_text(request)
        result = json.loads(
            run(
                "cost",
                "analyze",
                "task.json",
                "--format",
                "json",
                "--bundle",
                "cli.rccbundle",
            )
        )
        assert result["cost"]["interval_slots"] == [5, 5]
        assert (
            json.loads(run("bundle", "verify", "cli.rccbundle", "--format", "json"))[
                "historical_results_supported"
            ]
            is True
        )
        (root / "windows.json").write_text(
            run("probe", "export", "w1-quantum-organization")
        )
        assert "paired-bell" in run(
            "window", "analyze", "windows.json", "--csv", "windows.csv"
        )
        assert (root / "windows.csv").read_text().startswith("state,window,")
    print(
        "Installed cost, window, probe, schema and independent-recipient workflows passed."
    )


if __name__ == "__main__":
    main()
