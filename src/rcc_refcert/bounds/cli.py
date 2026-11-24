"""Lossless JSON entry points for terminal-state complexity bounds."""

from __future__ import annotations

import json
from decimal import Decimal
from importlib import resources

from .api import bound_from_counts, bound_from_spectrum, render_record, replay_record
from .contracts import keys, prepare_protocol
from .effects import PROTOCOL, REQUEST, prepare_effect_protocol
from .scalar import BudgetError, InputError, UnsupportedContract


def load_template(name: str = "spectrum") -> dict:
    """Return a fresh installed example; counts are explicitly synthetic."""
    if name == "sample-plan":
        protocol = load_template("effect-protocol")
        protocol["target"].update(
            state_id="design-target", dataset_id="planned-target-batch"
        )
        del protocol["target"]["samples"]
        protocol["target"].update(method="clopper_pearson", delta="1/20")
        protocol["reference"] = {
            "kind": "exact",
            "state_id": protocol["reference"]["state_id"],
            "response": "1/4",
            "source": "rank-one projector on I/4",
        }
        return {
            "schema": "rcc-refcert.fixed-effect-plan",
            "schema_version": 1,
            "protocol": protocol,
            "goal": {"response_above": "4/5"},
            "derivation": {"smoothing_radius": "1/10"},
            "expected_response": "9/10",
            "power": "9/10",
            "max_samples": 512,
        }
    if name == "binomial-counts":
        request = load_template("effect-counts")
        protocol = request["protocol"]
        protocol["target"].update(
            method="clopper_pearson", delta="1/20", samples=25, dataset_id="target-25"
        )
        protocol["reference"] = load_template("sample-plan")["protocol"]["reference"]
        frozen = prepare_effect_protocol(protocol)
        request["data"] = {
            "target": {
                "origin": "synthetic_fixture",
                "dataset_id": "target-25",
                "arm_sha256": frozen["arm_sha256"]["target"],
                "counts": {"yes": 14, "no": 11},
            }
        }
        return request
    if name == "effect-counts":
        frozen = prepare_effect_protocol(load_template("effect-protocol"))
        return {
            "schema": REQUEST,
            "schema_version": 1,
            "task": load_template("counts")["task"],
            "protocol": frozen["protocol"],
            "derivation": {"smoothing_radius": "1/10", "eta": "1/2"},
            "data": {
                role: {
                    "arm_sha256": frozen["arm_sha256"][role],
                    "dataset_id": frozen["protocol"][role]["dataset_id"],
                    "origin": "synthetic_fixture",
                    "counts": {"yes": hits, "no": 1000 - hits},
                }
                for role, hits in (("target", 550), ("reference", 250))
            },
        }
    names = {
        "effect-protocol": "effect_protocol.json",
        "spectrum": "spectrum.json",
        "counts": "projection_counts.json",
        "protocol": "protocol_spec.json",
    }
    if name not in names:
        raise InputError("unknown bound template")
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
            if arguments.bound_command == "plan":
                from .planning import plan_counts

                result = plan_counts(request)
                destination = getattr(arguments, "counts_request", None)
                if destination is not None and result["counts_request"] is not None:
                    from ..workflows.cli import write_atomic

                    write_atomic(
                        destination,
                        json.dumps(result["counts_request"], indent=2) + "\n",
                    )
            elif arguments.bound_command == "replay":
                result = replay_record(request)
            elif arguments.bound_command == "prepare-protocol":
                if isinstance(request, dict) and request.get("schema") == PROTOCOL:
                    result = prepare_effect_protocol(request)
                else:
                    keys(request, {"task", "protocol"}, "protocol request")
                    result = prepare_protocol(request["task"], request["protocol"])
            else:
                compute = (
                    bound_from_spectrum
                    if arguments.bound_command == "spectrum"
                    else bound_from_counts
                )
                result = compute(request)
                if getattr(arguments, "bundle", None) is not None:
                    from ..workflows.bundles import save_effect_bundle

                    save_effect_bundle(arguments.bundle, request, result)
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
    elif arguments.bound_command == "plan":
        descriptions = {
            "power_met": "The design reaches the requested power.",
            "fixed_n_below_power": "This fixed sample size falls short of the requested power.",
            "search_limit_reached": "No sample size in the searched range reached the requested power.",
            "threshold_unreachable": "The goal exceeds what this measurement can certify.",
            "uninformative_readout": "This readout has the same response for both ideal outcomes.",
            "empty_reference_readout_preimage": "The reference observations conflict with the declared readout.",
            "zero_reference_requires_support_assessment": "The zero reference response requires a support assessment.",
        }
        print(descriptions[result["status"]])
        if "samples" in result:
            print(
                f"Trials: {result['samples']} | counted outcome: {result['counted_outcome']}"
            )
            if result["minimum_hits"] <= result["maximum_hits"]:
                print(
                    f"Passing counts: {result['minimum_hits']} to {result['maximum_hits']} | design power >= {result['design_power_lower']}"
                )
            else:
                print("No count at this sample size meets the goal.")
        elif result["status"] == "search_limit_reached":
            print(
                "Checked every sample size through", result["samples_evaluated_through"]
            )
    else:
        print(render_record(result, details=arguments.details), end="")
    return 0 if result.get("analysis_state", "complete") == "complete" else 2
