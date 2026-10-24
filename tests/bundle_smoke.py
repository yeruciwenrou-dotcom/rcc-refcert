"""Check complete-input handoff using only a normally installed distribution.

Run this file from outside the checkout with the installed environment's Python.
It uses NumPy and rcc-refcert, with no pytest or source-tree fixtures.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path

import numpy as np

import rcc_refcert
from rcc_refcert import Action, FiniteControlModel, ReferencePotentialCertificate
from rcc_refcert.bounds import prepare_protocol, with_reference_certificate
from rcc_refcert.bundle import save_analysis_bundle
from rcc_refcert.candidate import prepare_bellman_choi


def model_and_certificate(route: str):
    identity = np.eye(2, dtype=complex)
    reset_zero = (
        np.array([[1, 0], [0, 0]], dtype=complex),
        np.array([[0, 1], [0, 0]], dtype=complex),
    )
    reset_one = (
        np.array([[0, 0], [1, 0]], dtype=complex),
        np.array([[0, 0], [0, 1]], dtype=complex),
    )
    if route == "H3":
        actions = (
            Action("reset-0", "0", None, halt_kraus={"q": reset_zero}),
            Action("reset-1", "1", None, halt_kraus={"q": reset_one}),
        )
    else:
        actions = (
            Action("identity", "00", "s", continue_kraus={("q", "q"): (identity,)}),
            Action(
                "phase", "01", "s", continue_kraus={("q", "q"): (np.diag([1.0, -1.0]),)}
            ),
            Action("reset-0", "10", None, halt_kraus={"q": reset_zero}),
            Action("reset-1", "11", None, halt_kraus={"q": reset_one}),
        )
    model = FiniteControlModel(
        syntax_states=("s",),
        control_dims={"q": 2},
        actions_by_syntax={"s": actions},
        start_syntax="s",
        initial_blocks={"q": identity / 2},
        output_dim=2,
        reference_state=identity / 2,
        name="installed-smoke-" + route,
        scope_note="Fixed complete channels and fixed-width code; every instruction costs one slot.",
    )
    if route == "H3":
        prepared = prepare_bellman_choi(model)
        assert prepared.status == "candidate_ready", prepared.diagnostics
        assert prepared.certificate is not None
        certificate = prepared.certificate
    else:
        key = ("s", "q")
        certificate = ReferencePotentialCertificate(
            theta={key: identity / 2},
            a={key: 1.0},
            transition_coefficients={(key, key): 0.5},
            halt_coefficients={key: 0.5},
            potential={key: 1.0},
        )
    return model, certificate


def bound_requests(model, certificate):
    source = "Installed smoke: fixed reference-preserving channel family and exact fixed-width transcription"
    declaration = {
        "model": {
            "id": model.name,
            "reference_id": "uniform-C2",
            "dimension": 2,
            "atomic_action_classes": len(model.actions_by_syntax["s"]),
            "transcription": {"mode": "exact", "a": "0", "gamma_bits": "0"},
            "reference_domination": {
                "upper_constant": "1",
                "source": source,
                "source_kind": "analytic_argument",
            },
            "cost_domain": "integer_atomic_slots",
            "reference_treatment": "ideal_support",
            "qualification": {
                label: {"basis": "analytic_argument_supplied", "source": source}
                for label in ("RCon", "TC", "RA")
            },
        },
        "target": {
            "id": "pure-zero",
            "epsilon": "0",
            "metric": "normalized_trace_distance",
        },
    }
    task = with_reference_certificate(declaration, model, certificate, source=source)
    protocol = prepare_protocol(
        task,
        {
            "id": model.name + "-N1000",
            "witness_id": "computational-zero",
            "rank": 1,
            "samples": 1000,
            "delta_stat": "1/100",
            "sampling": "fixed_n_iid",
            "selection": "predeclared",
            "readout": "ideal",
            "support": "no_leakage",
        },
    )
    counts = {
        "task": task,
        "protocol": protocol["protocol"],
        "data": {
            "protocol_id": protocol["protocol"]["id"],
            "protocol_sha256": protocol["protocol_sha256"],
            "samples": 1000,
            "hits": 1000,
            "origin": "synthetic_fixture",
            "dataset_id": model.name + "-synthetic-all-hits",
        },
    }
    return [
        {"kind": "spectrum", "request": {"task": task, "spectrum": ["1", "0"]}},
        {"kind": "counts", "request": counts},
    ]


def invoke(
    bundle: Path, output: Path, directory: Path, *, tolerance: str | None = None
):
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    arguments = [
        sys.executable,
        "-m",
        "rcc_refcert",
        "bundle",
        "verify",
        str(bundle),
        "--output",
        str(output),
        "--format",
        "json",
    ]
    if tolerance is not None:
        arguments.extend(("--tolerance", tolerance))
    return subprocess.run(
        arguments,
        cwd=directory,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def main() -> None:
    package_path = Path(rcc_refcert.__file__).resolve()
    assert package_path.is_relative_to(Path(sys.prefix).resolve()), (
        "Use a normally installed wheel or sdist, not a source-path/editable import",
        package_path,
    )
    assert rcc_refcert.__version__ == version("rcc-refcert")
    schema = files("rcc_refcert").joinpath("bundle_data", "analysis_bundle.schema.json")
    assert schema.is_file(), "bundle schema is missing from installed package"
    json.loads(schema.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="rcc-bundle-smoke-") as temporary:
        root = Path(temporary)
        author, recipient = root / "author", root / "recipient"
        author.mkdir()
        recipient.mkdir()
        for route in ("H3", "H4"):
            model, certificate = model_and_certificate(route)
            requests = bound_requests(model, certificate)
            original_protocol = requests[1]["request"]["data"]["protocol_sha256"]
            source = author / (route + ".rccbundle")
            save_analysis_bundle(source, model, certificate, requests=requests)
            bundle_digest = hashlib.sha256(source.read_bytes()).hexdigest()
            try:
                save_analysis_bundle(source, model, certificate, requests=requests)
            except FileExistsError:
                pass
            else:
                raise AssertionError("bundle save overwrote existing evidence")
            assert hashlib.sha256(source.read_bytes()).hexdigest() == bundle_digest
            copied = recipient / source.name
            shutil.copyfile(source, copied)
            output = recipient / (route + "-verification.json")
            process = invoke(copied, output, recipient)
            assert process.returncode == 0, (process.stdout, process.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))
            assert json.loads(process.stdout) == report
            assert report["fresh_verification"]["outcome"] == "pass"
            assert report["historical_results_supported"] is True
            counts = report["requests"][1]
            assert (
                counts["historical_record"]["provenance"]["input_snapshot"]
                == requests[1]["request"]
            )
            assert (
                counts["fresh_bound"]["original_acquisition_protocol_sha256"]
                == original_protocol
            )
            for entry in report["requests"]:
                assert entry["same_version_replay"]["matches"] is True
                assert entry["fresh_bound"]["cost"]["integer_lower_bound_slots"] == 1
            report_bytes = output.read_bytes()
            repeated = invoke(copied, output, recipient)
            assert repeated.returncode == 2
            assert output.read_bytes() == report_bytes
            changed = recipient / (route + "-changed-tolerance.json")
            process = invoke(copied, changed, recipient, tolerance="1e-8")
            assert process.returncode == 1, (process.stdout, process.stderr)
            updated = json.loads(changed.read_text(encoding="utf-8"))
            assert updated["fresh_verification"]["outcome"] == "pass"
            assert updated["historical_results_supported"] is False
            assert (
                updated["requests"][1]["fresh_bound"][
                    "original_acquisition_protocol_sha256"
                ]
                == original_protocol
            )
            assert hashlib.sha256(copied.read_bytes()).hexdigest() == bundle_digest
    print(
        f"Installed {version('rcc-refcert')}: H.3/H.4 bundle handoff, scalar replay, protocol identity and protected outputs passed."
    )


if __name__ == "__main__":
    main()
