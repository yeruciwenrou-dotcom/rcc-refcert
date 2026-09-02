"""Execute the guided Notebook through its declared Jupyter kernel."""

from __future__ import annotations

from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "RCC_Quickstart.ipynb"


def main() -> None:
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    nbformat.validate(notebook)
    kernel_name = notebook.metadata.kernelspec.name
    executed = NotebookClient(
        notebook,
        kernel_name=kernel_name,
        timeout=180,
        resources={"metadata": {"path": str(ROOT)}},
    ).execute()
    errors = [
        output
        for cell in executed.cells
        for output in cell.get("outputs", [])
        if output.get("output_type") == "error"
    ]
    if errors:
        raise RuntimeError(f"Notebook produced error outputs: {errors}")
    print(
        f"Validated and executed {len(executed.cells)} cells with kernel {kernel_name}."
    )


if __name__ == "__main__":
    main()
