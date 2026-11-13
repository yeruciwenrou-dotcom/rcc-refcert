"""Schema-2 workflow archives with bounded parsing and independent replay."""

from __future__ import annotations

import hashlib
import os
import stat
import tempfile
import zipfile
import zlib
from fractions import Fraction
from pathlib import Path

from .._version import __version__
from ..bundle_storage import (
    FORMAT,
    MAX_ARCHIVE_BYTES,
    MAX_MANIFEST_BYTES,
    MAX_UNCOMPRESSED_BYTES,
    BundleFormatError,
    _preflight_directory,
    _read_json,
    _read_member,
)
from .api import (
    _point,
    analyze_cost,
    compose_interval,
    normalize_cost_request,
    producer,
)
from .core import (
    InputError,
    WorkflowLimits,
    canonical_bytes,
    digest,
    exact,
    json_value,
    keys,
)
from .gain import exclude_budgets, spectral_threshold
from .states import StateInput


def _manifest(path):
    """Read only bounded container metadata; legacy validation still runs later."""
    with Path(path).open("rb") as stream:
        if os.fstat(stream.fileno()).st_size > MAX_ARCHIVE_BYTES:
            raise BundleFormatError("archive byte budget exceeded")
        try:
            _preflight_directory(stream)
            with zipfile.ZipFile(stream) as archive:
                items = [i for i in archive.infolist() if i.filename == "manifest.json"]
                if len(items) != 1 or items[0].file_size > MAX_MANIFEST_BYTES:
                    raise BundleFormatError("missing, duplicate or oversized manifest")
                result = _read_json(_read_member(archive, items[0], items[0].file_size))
        except (
            zipfile.BadZipFile,
            zlib.error,
            EOFError,
            RuntimeError,
            OverflowError,
        ) as exc:
            raise BundleFormatError("invalid archive bytes") from exc
    if (
        result.get("format") != FORMAT
        or type(result.get("schema_version")) is not int
        or result["schema_version"] not in (1, 2)
    ):
        raise BundleFormatError("unsupported analysis-bundle schema")
    return result


def workflow_bundle_version(path):
    return _manifest(path)["schema_version"]


def _read_workflow(path):
    manifest = _manifest(path)
    keys(
        manifest,
        {
            "format",
            "schema_version",
            "kind",
            "producer",
            "members",
            "request_digest",
            "manifest_sha256",
        },
        name="workflow manifest",
    )
    if manifest["schema_version"] != 2:
        raise BundleFormatError("expected workflow schema 2")
    if manifest["manifest_sha256"] != digest(
        {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    ):
        raise BundleFormatError("workflow manifest digest mismatch")
    if not isinstance(manifest["members"], dict) or set(manifest["members"]) != {
        "request.json",
        "history.json",
    }:
        raise BundleFormatError("workflow member contract mismatch")
    with Path(path).open("rb") as stream:
        _preflight_directory(stream)
        with zipfile.ZipFile(stream) as archive:
            infos = archive.infolist()
            names = [i.filename for i in infos]
            if len(names) != 3 or set(names) != {
                "manifest.json",
                "request.json",
                "history.json",
            }:
                raise BundleFormatError("unexpected or duplicate workflow member")
            if sum(i.file_size for i in infos) > MAX_UNCOMPRESSED_BYTES:
                raise BundleFormatError("workflow uncompressed size budget exceeded")
            payloads = {}
            for info in infos:
                if (
                    stat.S_IFMT(info.external_attr >> 16) not in (0, stat.S_IFREG)
                    or info.flag_bits & 1
                    or info.compress_type
                    not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                ):
                    raise BundleFormatError(
                        "unsupported workflow member type or compression"
                    )
                if info.filename == "manifest.json":
                    continue
                if info.file_size > 32 * 1024 * 1024:
                    raise BundleFormatError("workflow JSON member byte budget exceeded")
                data = _read_member(archive, info, info.file_size)
                descriptor = keys(
                    manifest["members"][info.filename],
                    {"sha256", "bytes"},
                    name="member",
                )
                if (
                    descriptor["bytes"] != len(data)
                    or descriptor["sha256"] != hashlib.sha256(data).hexdigest()
                ):
                    raise BundleFormatError("workflow member digest or size mismatch")
                payloads[info.filename] = _read_json(data)
    request = keys(
        payloads["request.json"], {"original", "effective"}, name="saved request"
    )
    history = payloads["history.json"]
    if manifest["request_digest"] != digest(request["effective"]):
        raise BundleFormatError("workflow effective request digest mismatch")
    if manifest["kind"] != request["effective"].get("kind"):
        raise BundleFormatError("workflow request kind mismatch")
    return manifest, request, history


def _check_cost_history(history, *, limits):
    effective = history["effective_request"]
    _, _, model, target, _, core = normalize_cost_request(effective, limits=limits)
    core_digest = digest(core)
    expected = {"request": digest(effective), "task_core": core_digest, **core}
    if history["digests"] != expected:
        raise InputError("history: complete task or request binding mismatch")
    cert = history["gain_certificate"]
    if any(
        cert.get(k) != effective["gain_certificate"].get(k)
        for k in ("model_digest", "envelopes", "initial_coefficient", "coefficients")
    ):
        raise InputError("history: gain evidence differs from the effective request")
    if cert.get("model_digest") != model.content_digest:
        raise InputError("history: gain certificate belongs to another model")
    if cert.get("verification", {}).get("outcome") != "pass":
        raise InputError("history: a strict lower bound needs a passing gain check")
    verification = cert["verification"]
    if exact(verification["initial_minimum_exact"]) > exact(
        cert["initial_coefficient"]
    ):
        raise InputError("history: initial coefficient contradicts its stored check")
    checks = verification.get("checks", [])
    if len(checks) != sum(map(len, model.actions.values())):
        raise InputError("history: local gain check count mismatch")
    seen = set()
    for check in checks:
        pair = (check["syntax"], check["action"])
        if pair in seen or pair[0] not in model.actions:
            raise InputError("history: repeated or unknown local gain check")
        action = model.lookup(*pair)
        expected_role = "halt" if action["successor"] is None else "continue"
        if (
            check["outcome"] != "pass"
            or check["role"] != expected_role
            or exact(check["minimum_exact"]) < 0
            or exact(check["minimum_exact"]) > exact(check["supplied_exact"])
            or check["supplied_exact"] != cert["coefficients"][pair[0]][pair[1]]
        ):
            raise InputError(
                "history: gain coefficient contradicts its stored local check"
            )
        seen.add(pair)
    if len(history["candidates"]) != len(effective["candidates"]):
        raise InputError("history: candidate count mismatch")
    epsilon = exact(effective["epsilon"])
    for saved, raw in zip(history["candidates"], effective["candidates"]):
        if (
            saved["id"] != raw["id"]
            or saved["target_digest"] != target.content_digest
            or saved["model_digest"] != model.content_digest
        ):
            raise InputError("history: candidate object bindings mismatch")
        if saved["legality"] == "pass":
            syntax, bits = model.start, ""
            for name in raw["action_names"]:
                if syntax is None:
                    raise InputError("history: candidate has actions after halt")
                action = model.lookup(syntax, name)
                syntax = action["successor"]
                bits += action["codeword"]
            if (
                syntax is not None
                or bits != raw["codeword"]
                or saved["slots"] != len(raw["action_names"])
            ):
                raise InputError("history: accepted word or charged cost mismatch")
            output = StateInput.from_dict(saved["output"], limits=limits)
            if (
                output.kind != "diagonal_exact"
                or output.subsystem_dims != model.dims
                or output.subsystem_labels != model.labels
            ):
                raise InputError("history: candidate output layout mismatch")
            distance = (
                sum((abs(a - b) for a, b in zip(output.data, target.data)), Fraction(0))
                / 2
            )
            if exact(saved["trace_distance_exact"]) != distance or saved[
                "target_satisfied"
            ] != (distance <= epsilon):
                raise InputError(
                    "history: stored candidate error or feasibility is inconsistent"
                )
            trajectory = saved.get("trajectory", [])
            if trajectory:
                if len(trajectory) != len(raw["action_names"]) + 1:
                    raise InputError("history: candidate trajectory length mismatch")
                for index, step in enumerate(trajectory):
                    if (
                        step["step"] != index
                        or step["slots"] != index
                        or step["action"]
                        != (raw["action_names"][index - 1] if index else None)
                    ):
                        raise InputError(
                            "history: trajectory step, action or cost mismatch"
                        )
                    state = StateInput.from_dict(step["state"], limits=limits)
                    if (state.subsystem_dims, state.subsystem_labels) != (
                        model.dims,
                        model.labels,
                    ):
                        raise InputError("history: trajectory axes mismatch")
                if trajectory[-1]["state"]["data"] != saved["output"]["data"]:
                    raise InputError(
                        "history: trajectory endpoint differs from candidate output"
                    )
        elif (
            saved["legality"] != "fail"
            or saved["target_satisfied"]
            or saved["slots"] is not None
        ):
            raise InputError("history: invalid candidate status")
    bound = history["gain_bound"]
    q = spectral_threshold(target.data, epsilon, model.limits)
    if exact(bound["threshold_exact"]) != q:
        raise InputError("history: spectral threshold disagrees with the full target")
    # Scalar bookkeeping is checked without re-running any physical channel.
    recorded_limits = WorkflowLimits.from_value(effective.get("limits"))
    scalar_limits = WorkflowLimits(
        **{k: min(v, getattr(limits, k)) for k, v in recorded_limits.as_dict().items()}
    )
    model.limits = scalar_limits
    scalar = exclude_budgets(model, cert, q, effective["max_cost"])
    if scalar != bound:
        raise InputError(
            "history: dynamic-program history is inconsistent with its coefficients"
        )
    upper = min(
        (r["slots"] for r in history["candidates"] if r["target_satisfied"]),
        default=None,
    )
    cost = compose_interval(
        bound["integer_lower_bound_slots"],
        upper,
        core_digest=core_digest,
        epsilon=epsilon,
    )
    if (
        any(history["cost"].get(k) != v for k, v in cost.items())
        or history["decision"] != cost["decision"]
    ):
        raise InputError(
            "history: cost interval or decision is inconsistent with its endpoints"
        )
    expected_ids = [
        r["id"]
        for r in history["candidates"]
        if r["target_satisfied"] and r["slots"] == upper
    ]
    if (
        history["cost"].get("upper_witness_ids") != expected_ids
        or history["cost"].get("lower_route") != "exact_gain_budget"
    ):
        raise InputError("history: cost endpoint provenance mismatch")
    if len(history["epsilon_scan"]) != len(effective["epsilon_values"]):
        raise InputError("history: tolerance scan count mismatch")
    for point, e in zip(history["epsilon_scan"], effective["epsilon_values"]):
        ecost, ebound, ewitnesses = _point(
            model,
            target,
            cert,
            history["candidates"],
            exact(e),
            effective["max_cost"],
            core_digest,
            compact=True,
        )
        expected = {
            "request_digest": digest({**effective, "epsilon": e, "epsilon_values": []}),
            "epsilon_exact": e,
            "cost": ecost,
            "gain_bound": ebound,
            "candidates": ewitnesses,
        }
        if point != expected:
            raise InputError("history: tolerance scan evidence is inconsistent")
    if history["execution"]["state"] == "completed" and (
        not bound["completed"]
        or any(not p["gain_bound"]["completed"] for p in history["epsilon_scan"])
        or any(
            c.get("trajectory_status") == "resource_limited"
            for c in history["candidates"]
        )
    ):
        raise InputError("history: resource-limited analysis claims completion")


def check_workflow_history(history, *, limits=None):
    limits = WorkflowLimits.from_value(limits)
    json_value(history)
    if (
        not isinstance(history, dict)
        or history.get("schema") != "rcc-refcert.workflow-result"
        or type(history.get("schema_version")) is not int
        or history["schema_version"] != 1
    ):
        raise InputError("history: unsupported workflow result")
    required = {
        "effective_request",
        "original_request",
        "digests",
        "execution",
        "decision",
        "producer",
        "kind",
    }
    if not required <= set(history):
        raise InputError("history: required workflow fields are missing")
    if history["kind"] != history["effective_request"].get("kind"):
        raise InputError("history: request kind mismatch")
    if history["execution"].get("state") not in {"completed", "partial"}:
        raise InputError("history: invalid execution state")
    # Re-expand declarative inputs to check raw/effective object relationships.
    # This does not run any channel or create a new scientific result.
    controls = history["effective_request"].get("limits")
    if history["kind"] == "window_analysis":
        from .windows import normalize_window_request

        raw_effective = normalize_window_request(
            history["original_request"], limits=controls
        )[1]
    elif history["effective_request"].get("mode") == "numerical":
        from .numerical import normalize_numerical_request

        raw_effective = normalize_numerical_request(
            history["original_request"], limits=controls
        )[1]
    else:
        raw_effective = normalize_cost_request(
            history["original_request"], limits=controls
        )[1]
    for key, value in raw_effective.items():
        if key != "gain_certificate" and history["effective_request"].get(key) != value:
            raise InputError(
                "history: original and effective requests describe different objects"
            )
    if history["kind"] == "cost_analysis":
        if history["effective_request"].get("mode") == "numerical":
            from .numerical import check_numerical_history

            check_numerical_history(history, limits=limits)
        else:
            _check_cost_history(history, limits=limits)
    elif history["kind"] == "window_analysis":
        from .windows import check_window_history

        check_window_history(history, limits=limits)
    else:
        raise InputError("history: unsupported workflow kind")
    nested = history.get("windows")
    if isinstance(nested, dict) and nested.get("kind") == "window_analysis":
        check_workflow_history(nested, limits=limits)
        known = {
            f"{c['id']}:{step['step']}": step
            for c in history["candidates"]
            for step in c["trajectory"]
        }
        for record in nested["effective_request"]["states"]:
            if record["id"] not in known or any(
                record[k] != known[record["id"]][k]
                for k in ("step", "slots", "action", "state")
            ):
                raise InputError(
                    "history: windows do not belong to the saved candidate trajectory"
                )


def save_workflow_bundle(path, request, result, *, overwrite=False):
    """Save original and effective inputs with immutable author-side history."""
    limits = WorkflowLimits.from_value(
        result.get("effective_request", {}).get("limits")
    )
    check_workflow_history(result, limits=limits)
    if digest(request) != digest(result["original_request"]):
        raise InputError(
            "save: supplied request differs from the analyzed original request"
        )
    request_data = {
        "original": json_value(request),
        "effective": result["effective_request"],
    }
    members = {
        "request.json": canonical_bytes(request_data),
        "history.json": canonical_bytes(result),
    }
    if any(len(v) > 32 * 1024 * 1024 for v in members.values()):
        raise BundleFormatError("workflow JSON member byte budget exceeded")
    manifest = {
        "format": FORMAT,
        "schema_version": 2,
        "kind": result["kind"],
        "producer": producer(),
        "members": {
            k: {"sha256": hashlib.sha256(v).hexdigest(), "bytes": len(v)}
            for k, v in members.items()
        },
        "request_digest": digest(result["effective_request"]),
    }
    manifest["manifest_sha256"] = digest(manifest)
    destination = Path(path)
    if destination.exists() and not overwrite:
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=".rcc-workflow-", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(fd, "wb") as stream:
            with zipfile.ZipFile(
                stream, "w", compression=zipfile.ZIP_DEFLATED
            ) as archive:
                archive.writestr("manifest.json", canonical_bytes(manifest))
                for name, data in members.items():
                    archive.writestr(name, data)
            stream.flush()
            os.fsync(stream.fileno())
        if os.path.getsize(temporary) > MAX_ARCHIVE_BYTES:
            raise BundleFormatError("workflow archive byte budget exceeded")
        if overwrite:
            os.replace(temporary, destination)
        else:
            os.link(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return destination


def inspect_workflow_bundle(path, *, limits=None):
    limits = WorkflowLimits.from_value(limits)
    manifest, request, history = _read_workflow(path)
    if request["original"] != history.get("original_request") or request[
        "effective"
    ] != history.get("effective_request"):
        raise InputError(
            "history: raw or effective request differs from the saved input"
        )
    check_workflow_history(history, limits=limits)
    return {
        "schema": "rcc-refcert.bundle-inspection",
        "schema_version": 2,
        "kind": manifest["kind"],
        "producer": manifest["producer"],
        "record_consistency": "pass",
        "physical_revalidation": "not_run",
        "historical_decision": history["decision"],
        "request_digest": manifest["request_digest"],
        "request_count": 1,
    }


def _scientific_result(result):
    selected = {
        k: result.get(k)
        for k in (
            "kind",
            "decision",
            "evidence",
            "cost",
            "gain_certificate",
            "gain_bound",
            "candidates",
            "epsilon_scan",
            "windows",
            "profiles",
            "reference",
            "diagnostics",
        )
    }

    def stable(value):
        if isinstance(value, dict):
            return {
                k: stable(v)
                for k, v in value.items()
                if k
                not in {
                    "run_id",
                    "producer",
                    "source_revision",
                    "artifact_role",
                    "original_request",
                    "effective_request",
                }
            }
        if isinstance(value, list):
            return [stable(v) for v in value]
        return value

    return stable(selected)


def verify_workflow_bundle(path, *, limits=None, tol=None):
    limits = WorkflowLimits.from_value(limits)
    inspect_workflow_bundle(path, limits=limits)
    manifest, request, history = _read_workflow(path)
    if tol is not None:
        raise InputError(
            "workflow verification: use the saved numerical policy; a changed policy is a separately identified analysis"
        )
    recorded = WorkflowLimits.from_value(request["effective"].get("limits"))
    limits = WorkflowLimits(
        **{k: min(v, getattr(limits, k)) for k, v in recorded.as_dict().items()}
    )
    if manifest["kind"] == "cost_analysis":
        fresh = analyze_cost(request["effective"], limits=limits)
    else:
        from .windows import analyze_windows

        fresh = analyze_windows(request["effective"], limits=limits)
    fresh["artifact_role"] = "recipient_revalidation"
    fresh["original_request"] = request["original"]
    complete = (
        fresh["execution"]["state"] == "completed"
        and fresh["decision"] != "numerical_unresolved"
    )
    old_science, new_science = _scientific_result(history), _scientific_result(fresh)
    from .windows import _close

    def numerical_view(value):
        if isinstance(value, dict):
            # Derived numerical arrays carry bitwise digests separately; compare
            # their values under the saved arithmetic contract for semantic replay.
            skip = {
                "derived_digest",
                "derived_state",
                "repair_applied",
                "perturbation_trace_norm_half",
                "original_digest",
                "digests",
            }
            if "input_diagnostics" in value:
                skip.add("state_digest")
            if value.get("kind") == "density_numeric":
                skip.add("content_digest")
            return {k: numerical_view(v) for k, v in value.items() if k not in skip}
        if isinstance(value, list):
            return [numerical_view(v) for v in value]
        return value

    matches = _close(numerical_view(old_science), numerical_view(new_science))
    if not complete and not matches:
        matches = None
    same_version = history["producer"]["version"] == __version__
    return {
        "schema": "rcc-refcert.bundle-verification",
        "schema_version": 2,
        "kind": manifest["kind"],
        "producer": producer(),
        "record_consistency": "pass",
        "fresh_verification": {
            "outcome": "pass" if complete else "inconclusive",
            "evidence": fresh["evidence"],
        },
        "historical_results_supported": matches,
        "same_version_replay": {
            "status": "different_producer_version"
            if not same_version
            else "match"
            if old_science == new_science
            else "mismatch"
            if complete
            else "inconclusive",
            "producer_version_matches": same_version,
        },
        "historical_result": history,
        "fresh_result": fresh,
        "scope": "Independent computation from the complete saved recipe and target; author history is retained.",
    }
