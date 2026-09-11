"""Lossless JSON entry points for conditional terminal-state bounds."""

from __future__ import annotations

import json
from decimal import Decimal
from importlib import resources

from .api import bound_from_counts, bound_from_spectrum, render_record, replay_record
from .contracts import keys, prepare_protocol
from .scalar import BudgetError, InputError, UnsupportedContract


def load_template(name: str = "spectrum") -> dict:
    """Return a fresh installed example; counts are explicitly synthetic."""
    names = {
        "spectrum": "spectrum.json",
        "counts": "projection_counts.json",
        "protocol": "protocol_spec.json",
    }
    if name not in names:
        raise InputError("template must be spectrum, counts or protocol")
    return json.loads(
        resources.files("rcc_refcert.bounds")
        .joinpath("data", names[name])
        .read_text(encoding="utf-8")
    )


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise InputError(f"non-finite JSON constant: {value}")


def run(arguments) -> int:
    try:
        if arguments.bound_command == "template":
            result = load_template(arguments.name)
        else:
            # Bound the bytes actually read, including files that grow or lack a size.
            with arguments.input.open("rb") as stream:
                raw = stream.read(2_000_001)
            if len(raw) > 2_000_000:
                raise BudgetError("input exceeds the 2 MB calculation budget")
            request = json.loads(
                raw.decode("utf-8"),
                parse_float=Decimal,
                parse_constant=_invalid_constant,
                object_pairs_hook=_unique_object,
            )
            if arguments.bound_command == "replay":
                result = replay_record(request)
            elif arguments.bound_command == "prepare-protocol":
                keys(request, {"task", "protocol"}, "protocol request")
                result = prepare_protocol(request["task"], request["protocol"])
            else:
                compute = (
                    bound_from_spectrum
                    if arguments.bound_command == "spectrum"
                    else bound_from_counts
                )
                result = compute(request)
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        ArithmeticError,
        RecursionError,
    ) as exc:
        state = (
            "resource_limit"
            if isinstance(exc, (BudgetError, RecursionError))
            else "unsupported_contract"
            if isinstance(exc, UnsupportedContract)
            else "invalid_input"
        )
        error = {
            "schema": "rcc-refcert.bound-error",
            "schema_version": 2,
            "analysis_state": state,
            "error_type": type(exc).__name__,
            "message": str(exc),
            "cost": None,
        }
        print(
            json.dumps(error, ensure_ascii=False)
            if arguments.output_format == "json"
            else f"{state}: {exc}"
        )
        return 2
    if arguments.output_format == "json" or arguments.bound_command in {
        "template",
        "prepare-protocol",
        "replay",
    }:
        print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    else:
        print(render_record(result, details=arguments.details), end="")
    return 0 if result.get("analysis_state", "complete") == "complete" else 2
