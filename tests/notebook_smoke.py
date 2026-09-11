"""Execute the guided Notebook through its declared Jupyter kernel."""

from __future__ import annotations

from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "RCC_Quickstart.ipynb"


def execute(path: Path) -> None:
    notebook = nbformat.read(path, as_version=4)
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
        f"Validated and executed {path.name}: {len(executed.cells)} cells with kernel {kernel_name}."
    )


def main() -> None:
    for path in (NOTEBOOK, ROOT / "RCC_Bounds_Quickstart.ipynb"):
        execute(path)


if __name__ == "__main__":
    main()
