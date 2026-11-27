"""Exercise installed bounds outside the source checkout, using only runtime dependencies."""

import json
import subprocess
import sys
import tempfile
from importlib.metadata import distribution, version
from importlib.resources import files
from pathlib import Path

import rcc_refcert
from rcc_refcert.bounds import (
    bound_from_counts,
    bound_from_spectrum,
    load_template,
    replay_record,
)


def main():
    assert rcc_refcert.__version__ == version("rcc-refcert")
    assert (
        files("rcc_refcert.bounds")
        .joinpath("data", "bound_record.schema.json")
        .is_file()
    )
    with tempfile.TemporaryDirectory() as temporary:
        vigo = subprocess.run(
            [
                sys.executable,
                "-m",
                "rcc_refcert",
                "study",
                "import-counts",
                "--example",
                "ibm-vigo",
            ],
            check=True,
            capture_output=True,
            text=True,
            cwd=temporary,
        )
        readout = json.loads(vigo.stdout)
        assert readout["samples"] == 1024 and readout["counts"]["00101"] == 909
        data = files("rcc_refcert.workflows").joinpath("data")
        source = json.loads(data.joinpath("ibm_vigo_source.json").read_bytes())
        assert source["dataset_doi"] == "10.5281/zenodo.5197499"
        package = distribution("rcc-refcert")
        assert package.metadata["License-Expression"] == "MIT AND CC-BY-4.0"
        assert source["dataset_doi"] in package.read_text("licenses/NOTICE.md")
        assert "Creative Commons Attribution 4.0" in package.read_text(
            "licenses/LICENSES/CC-BY-4.0.txt"
        )
        for name, compute in (
            ("spectrum", bound_from_spectrum),
            ("counts", bound_from_counts),
        ):
            result = compute(load_template(name))
            assert replay_record(result)["matches"]
            path = Path(temporary) / "request.json"
            path.write_text(json.dumps(load_template(name)), encoding="utf-8")
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "rcc_refcert",
                    "bound",
                    name,
                    str(path),
                    "--format",
                    "json",
                ],
                check=True,
                capture_output=True,
                text=True,
                cwd=temporary,
            )
            assert json.loads(process.stdout) == result
    print(
        f"Installed {version('rcc-refcert')}: bounds, replay and the attributed Vigo readout passed."
    )


if __name__ == "__main__":
    main()
