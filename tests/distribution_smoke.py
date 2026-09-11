"""Exercise installed bounds outside the source checkout, using only runtime dependencies."""

import json
import subprocess
import sys
import tempfile
from importlib.metadata import version
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
        f"Installed {version('rcc-refcert')}: both API/CLI routes, resources and replay passed."
    )


if __name__ == "__main__":
    main()
