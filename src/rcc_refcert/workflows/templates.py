"""Installed request templates, returned as independent editable objects."""

import json
from importlib.resources import files

from .core import InputError


def load_workflow_template(name):
    if name not in {"cyclic-reset", "algorithmic-cooling", "window-state"}:
        raise InputError(
            "template: choose cyclic-reset, algorithmic-cooling or window-state"
        )
    return json.loads(
        files("rcc_refcert.workflows")
        .joinpath("data", name + ".json")
        .read_text(encoding="utf-8")
    )
