"""Complete finite-model evidence and independent numerical revalidation.

Historical inputs remain immutable. In particular, counts protocols keep their
original task identity; new constants are applied as deterministic postprocessing
of the same validated information interval, in a separately identified result.
"""

from __future__ import annotations

import math
import platform
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path

import numpy as np

from ._version import __version__
from .bellman_choi import BellmanChoiCertificate, verify_bellman_choi
from .bounds.api import bound_from_counts, bound_from_spectrum, replay_record
from .bounds.certificates import _snapshot, with_reference_certificate
from .bounds.contracts import (
    MATRIX_HASH_FORMAT,
    Task,
    canonical_hash,
    json_ready,
    keys,
    text,
)
from .bounds.records import validate_record
from .bounds.scalar import (
    InputError,
    Interval,
    ceil_fraction,
    decimal_endpoint,
    decimal_string,
    rational,
)
from .bundle_storage import load_bundle_payload, save_bundle_payload
from .limits import DEFAULT_LIMITS, ComputationLimits, _resource_diagnostic
from .metadata import source_revision_from_environment, validate_source_revision
from .reference_potential import (
    ReferencePotentialCertificate,
    verify_reference_potential,
)
from .status import CheckOutcome

_ANALYSIS_KEYS = {
    "schema",
    "schema_version",
    "producer",
    "source",
    "controls",
    "input_bindings",
    "verification",
    "requests",
}


def _tolerance(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.floating)):
        raise InputError(
            "tolerance must be a finite positive binary floating-point number"
        )
    if not math.isfinite(value) or value <= 0:
        raise InputError("tolerance must be finite and positive")
    return float(value)


def _number(value) -> str | None:
    if value is None:
        return None
    value = float(value)
    return str(Fraction.from_float(value)) if math.isfinite(value) else str(value)


def _report(report) -> dict:
    return {
        "name": report.name,
        "outcome": report.outcome.value,
        "evidence": report.evidence.value,
        "constant_exact": _number(report.constant),
        "candidate_constant_exact": _number(report.candidate_constant),
        "constant_error_bound_exact": _number(report.constant_error_bound),
        "checks": [
            {
                "name": c.name,
                "outcome": c.outcome.value,
                "evidence": c.evidence.value,
                "message": c.message,
                "value_exact": _number(c.value),
                "tolerance_exact": _number(c.tolerance),
            }
            for c in report.checks
        ],
    }


def _verify(model, certificate, tol, limits):
    if isinstance(certificate, BellmanChoiCertificate):
        return verify_bellman_choi(model, certificate, tol=tol, limits=limits)
    if isinstance(certificate, ReferencePotentialCertificate):
        return verify_reference_potential(model, certificate, tol=tol, limits=limits)
    raise InputError("supply an H.3 or H.4 certificate object")


def _validate_report(report: dict) -> None:
    keys(
        report,
        {
            "name",
            "outcome",
            "evidence",
            "constant_exact",
            "candidate_constant_exact",
            "constant_error_bound_exact",
            "checks",
        },
        "historical verification",
    )
    text(report["name"], "historical verification name")
    outcomes = {x.value for x in CheckOutcome}
    if report["outcome"] not in outcomes or report["evidence"] != "numerical":
        raise InputError("invalid historical outcome or matrix evidence level")
    constant = report["constant_exact"]
    if report["outcome"] == "pass":
        if not isinstance(constant, str) or rational(constant, "verified constant") < 0:
            raise InputError("passing history requires a nonnegative finite constant")
    elif constant is not None:
        raise InputError("non-passing history cannot supply a usable constant")
    for field in ("candidate_constant_exact", "constant_error_bound_exact"):
        value = report[field]
        if value is not None:
            if not isinstance(value, str):
                raise InputError(
                    "historical numerical diagnostics must be strings or null"
                )
            if value not in {"inf", "-inf", "nan"}:
                rational(value, field)
    checks = report["checks"]
    if not isinstance(checks, list) or len(checks) > 10000:
        raise InputError("historical checks must be a bounded list")
    for check in checks:
        keys(
            check,
            {
                "name",
                "outcome",
                "evidence",
                "message",
                "value_exact",
                "tolerance_exact",
            },
            "historical check",
        )
        text(check["name"], "check name")
        text(check["message"], "check message")
        if check["outcome"] not in outcomes or check["evidence"] != "numerical":
            raise InputError("invalid historical check outcome or evidence")
        for field in ("value_exact", "tolerance_exact"):
            value = check[field]
            if value is not None:
                if not isinstance(value, str):
                    raise InputError(
                        "check numerical diagnostics must be strings or null"
                    )
                if value not in {"inf", "-inf", "nan"}:
                    rational(value, field)

    check_outcomes = {check["outcome"] for check in checks}
    outcome = report["outcome"]
    if not checks:
        raise InputError("historical verification requires at least one check")
    if outcome == "pass":
        if check_outcomes != {"pass"}:
            raise InputError("passing history requires every reported check to pass")
        diagnostics = []
        for field in ("candidate_constant_exact", "constant_error_bound_exact"):
            value = report[field]
            if value is None or value in {"inf", "-inf", "nan"}:
                raise InputError("passing history requires finite constant diagnostics")
            diagnostic = rational(value, field)
            if diagnostic < 0:
                raise InputError("passing history requires nonnegative diagnostics")
            diagnostics.append(diagnostic)
        upper = rational(constant, "verified constant")
        candidate, error = diagnostics
        for value in (upper, candidate, error):
            try:
                binary = float(value)
            except OverflowError as exc:
                raise InputError(
                    "historical constants must be finite binary64 values"
                ) from exc
            if not math.isfinite(binary) or Fraction.from_float(binary) != value:
                raise InputError("historical constants must be exact binary64 values")
        if upper < candidate:
            raise InputError("verified constant cannot be below its candidate")
        # accepted_constant serializes a binary64 subtraction. Requiring the
        # rational identity upper == candidate + error would reject valid
        # histories when that subtraction rounds.
        if error != Fraction.from_float(float(upper - candidate)):
            raise InputError(
                "historical reserved error differs from upper minus candidate"
            )
    elif outcome not in check_outcomes:
        raise InputError("historical outcome requires a matching reported check")


def _bindings(model, certificate) -> dict:
    return {
        "model_sha256": canonical_hash(_snapshot(model)),
        "certificate_sha256": canonical_hash(_snapshot(certificate)),
        "input_hash_format": MATRIX_HASH_FORMAT,
    }


def _compute(kind: str, request: dict) -> dict:
    if kind == "spectrum":
        return bound_from_spectrum(request)
    if kind == "counts":
        return bound_from_counts(request)
    raise InputError("bundle request kind must be 'spectrum' or 'counts'")


def _check_request_binding(request, model, certificate, binding, tolerance, constant):
    task = Task.from_dict(request["task"])
    if task.declaration != request["task"]:
        raise InputError(
            "bundle tasks must use normalized declarations from certificate binding"
        )
    model_decl = task.declaration["model"]
    domination = model_decl["reference_domination"]
    if domination.get("source_kind") != "numerical_upper_constant":
        raise InputError("bundle bounds require a numerical certificate binding")
    evidence = domination["evidence"]
    method = "H.3" if isinstance(certificate, BellmanChoiCertificate) else "H.4"
    if any(evidence[k] != v for k, v in binding.items()):
        raise InputError("request binding differs from the stored model or certificate")
    if (
        evidence["method"] != method
        or evidence["tolerance_exact"] != tolerance
        or evidence["reported_constant_exact"] != constant
        or evidence["model_id"] != model.name
        or model_decl["id"] != model.name
        or task.dimension != model.output_dim
    ):
        raise InputError(
            "request binding differs from the stored verification controls or result"
        )
    if task.dimension > 1024:
        raise InputError("certificate-bound reference dimension exceeds 1024")
    if not np.array_equal(
        model.reference_state, np.eye(task.dimension) / task.dimension
    ):
        raise InputError(
            "bound requests require the declared nominal uniform reference"
        )
    if task.reference_constant != max(
        Fraction(1), rational(constant, "verified constant")
    ):
        raise InputError(
            "bound task must use the actual conservative verified constant"
        )
    return task


def save_analysis_bundle(
    path: str | Path,
    model,
    certificate,
    *,
    requests: list[dict] | None = None,
    tol: float = 1e-10,
    limits: ComputationLimits = DEFAULT_LIMITS,
    source: str = "finite-model analysis",
    overwrite: bool = False,
) -> Path:
    """Verify and save complete inputs, original requests, and fresh history.

    Requests contain ``kind`` (spectrum/counts) and an already bound ``request``.
    Counts must use the original protocol frozen after certificate binding.
    With no requests, failed or inconclusive certificates can also be preserved
    for diagnosis. Existing files are protected unless overwrite is explicit.
    """
    tol = _tolerance(tol)
    text(source, "bundle source")
    if requests is None:
        requests = []
    if not isinstance(requests, list) or len(requests) > 100:
        raise InputError("bundle requests must be a list of at most 100 entries")
    report = _verify(model, certificate, tol, limits)
    binding = _bindings(model, certificate)
    exact_tol = str(Fraction.from_float(tol))
    stored_requests = []
    for item in requests:
        keys(item, {"kind", "request"}, "bundle request")
        if report.outcome is not CheckOutcome.PASS or report.constant is None:
            raise InputError(
                "bound requests need a passing certificate with a usable constant"
            )
        request = json_ready(item["request"])
        _check_request_binding(
            request, model, certificate, binding, exact_tol, _number(report.constant)
        )
        # Check all adapter qualifications as well as the immutable input binding.
        rebound = with_reference_certificate(
            request["task"],
            model,
            certificate,
            source=request["task"]["model"]["reference_domination"]["source"],
            tol=tol,
            limits=limits,
        )
        if rebound != request["task"]:
            raise InputError("request was not bound to this certificate and tolerance")
        stored_requests.append(
            {
                "kind": item["kind"],
                "request": request,
                "record": _compute(item["kind"], request),
            }
        )
    analysis = {
        "schema": "rcc-refcert.analysis",
        "schema_version": 1,
        "producer": {
            "name": "rcc-refcert",
            "version": __version__,
            "python": platform.python_version(),
            "numpy": np.__version__,
            "source_revision": source_revision_from_environment(),
        },
        "source": source,
        "controls": {
            "tolerance_exact": exact_tol,
            "limits": asdict(limits),
            "matrix_arithmetic": "numpy-binary64",
        },
        "input_bindings": binding,
        "verification": _report(report),
        "requests": stored_requests,
    }
    return save_bundle_payload(
        path, model, certificate, analysis=analysis, limits=limits, overwrite=overwrite
    )


def _history(payload) -> tuple[dict, float]:
    analysis = keys(payload.analysis, _ANALYSIS_KEYS, "bundle analysis")
    if (
        analysis["schema"] != "rcc-refcert.analysis"
        or type(analysis["schema_version"]) is not int
        or analysis["schema_version"] != 1
    ):
        raise InputError("unsupported analysis schema or version")
    text(analysis["source"], "bundle source")
    producer = keys(
        analysis["producer"],
        {"name", "version", "python", "numpy", "source_revision"},
        "bundle producer",
    )
    if producer["name"] != "rcc-refcert":
        raise InputError("unsupported analysis producer")
    for field in ("version", "python", "numpy"):
        text(producer[field], "producer." + field)
    revision = producer["source_revision"]
    if revision is not None and not isinstance(revision, str):
        raise InputError("source revision must be a full Git commit or null")
    if validate_source_revision(revision) != revision:
        raise InputError("source revision must use its normalized full Git commit")
    controls = keys(
        analysis["controls"],
        {"tolerance_exact", "limits", "matrix_arithmetic"},
        "bundle controls",
    )
    if controls["matrix_arithmetic"] != "numpy-binary64":
        raise InputError("unsupported matrix arithmetic")
    exact = rational(controls["tolerance_exact"], "stored tolerance")
    tol = _tolerance(float(exact))
    if Fraction.from_float(tol) != exact:
        raise InputError("stored tolerance is not an exact binary64 value")
    ComputationLimits(**controls["limits"])
    binding = _bindings(payload.model, payload.certificate)
    if analysis["input_bindings"] != binding:
        raise InputError(
            "analysis input identities differ from the complete stored inputs"
        )
    verification = analysis["verification"]
    _validate_report(verification)
    if (
        verification["outcome"] == "pass"
        and isinstance(payload.certificate, BellmanChoiCertificate)
        and rational(verification["candidate_constant_exact"])
        != rational(_number(payload.certificate.constant), "H.3 candidate")
    ):
        raise InputError("historical H.3 candidate differs from the stored certificate")
    constant = verification["constant_exact"]
    if not isinstance(analysis["requests"], list) or len(analysis["requests"]) > 100:
        raise InputError("bundle requests must be a list of at most 100 entries")
    for entry in analysis["requests"]:
        keys(entry, {"kind", "request", "record"}, "historical request")
        if entry["kind"] not in {"spectrum", "counts"}:
            raise InputError("unknown historical request kind")
        if verification["outcome"] != "pass":
            raise InputError("historical bound requests require a passing certificate")
        _check_request_binding(
            entry["request"],
            payload.model,
            payload.certificate,
            binding,
            controls["tolerance_exact"],
            constant,
        )
        validate_record(entry["record"])
        if entry["record"]["provenance"]["input_snapshot"] != entry["request"] or entry[
            "record"
        ]["producer"] != {"name": "rcc-refcert", "version": producer["version"]}:
            raise InputError(
                "historical record differs from its original request or producer"
            )
        expected_path = (
            "spectrum" if entry["kind"] == "spectrum" else "fixed_projector_counts"
        )
        if entry["record"]["path"]["name"] != expected_path:
            raise InputError("historical record path differs from its request kind")
    return analysis, tol


def _derived_bound(original: dict, fresh_task: dict) -> dict:
    # Reuse the scalar cost kernel. The recomputed information interval has
    # outward-rounded endpoints, so reusing it preserves conservative enclosure.
    from .bounds.api import _cost_terms

    task = Task.from_dict(fresh_task)
    raw = original["information"]["information_bits"]
    info = Interval(decimal_endpoint(raw["lower"]), decimal_endpoint(raw["upper"]))
    g, beta, inverse, status, zero = _cost_terms(
        task, info, original["information"], original["path"]["name"]
    )
    return {
        "schema": "rcc-refcert.bundle-derived-bound",
        "schema_version": 1,
        "producer": {"name": "rcc-refcert", "version": __version__},
        "artifact_role": "fresh-certificate-postprocessing",
        "original_input_sha256": original["provenance"]["input_sha256"],
        "original_acquisition_protocol_sha256": original["information"].get(
            "acquisition_protocol_sha256"
        ),
        "task": fresh_task,
        "information_bits": info.strings(),
        "bandwidth_bits_per_slot": g.strings(),
        "beta_bits": beta.strings(),
        "cost": {
            "lower_bound_slots": decimal_string(inverse.lower),
            "calculator_enclosure_slots": inverse.strings(),
            "integer_lower_bound_slots": ceil_fraction(inverse.lower)
            if task.integer_cost
            else None,
            "numerical_status": status,
            "zero_reason": zero,
            "enclosure_upper_is_process_upper_bound": False,
        },
        "confidence": original["confidence"],
        "scope": "deterministic postprocessing of the original validated information interval; acquisition protocol unchanged",
        "external_premises_verified": False,
    }


def inspect_analysis_bundle(path: str | Path, *, limits=DEFAULT_LIMITS) -> dict:
    """Check stored identity/relationships without running matrix verification."""
    payload = load_bundle_payload(path, limits=limits)
    analysis, _ = _history(payload)
    return {
        "schema": "rcc-refcert.bundle-inspection",
        "schema_version": 1,
        "model": payload.model.name,
        "producer": analysis["producer"],
        "input_bindings": analysis["input_bindings"],
        "historical_verification": analysis["verification"],
        "request_count": len(analysis["requests"]),
        "record_consistency": "pass",
        "matrix_revalidation": "not_run",
        "external_premises_verified": False,
    }


def verify_analysis_bundle(
    path: str | Path,
    *,
    tol: float | None = None,
    limits: ComputationLimits = DEFAULT_LIMITS,
) -> dict:
    """Revalidate original inputs and report fresh evidence beside history.

    The caller's resource limits remain authoritative. Stored limits describe
    history; they cannot enlarge the receiving environment's budget.
    In the returned report, limits above 256 bits use bounded diagnostic strings.
    """
    payload = load_bundle_payload(path, limits=limits)
    analysis, original_tol = _history(payload)
    effective_tol = original_tol if tol is None else _tolerance(tol)
    report = _verify(payload.model, payload.certificate, effective_tol, limits)
    fresh = _report(report)
    usable = report.outcome is CheckOutcome.PASS and report.constant is not None
    comparisons = []
    for entry in analysis["requests"]:
        old = entry["record"]
        scalar = _compute(entry["kind"], entry["request"])
        comparable = {
            **scalar,
            "producer": {**scalar["producer"], "version": old["producer"]["version"]},
        }
        matches = comparable == old
        if old["producer"]["version"] == __version__:
            replay = replay_record(old) if matches else {"matches": False}
            replay["status"] = "match" if matches else "mismatch"
        else:
            replay = {
                "status": "unsupported_producer_version",
                "matches": None,
                "stored_version": old["producer"]["version"],
                "current_version": __version__,
            }
        item = {
            "kind": entry["kind"],
            "historical_record": old,
            "same_version_replay": replay,
            "current_scalar_comparison": {
                "matches": matches,
                "scope": "recomputed original inputs; producer version excluded from comparison",
            },
            "historical_constant_supported": None,
            "fresh_bound": None,
        }
        if usable:
            original_task = entry["request"]["task"]
            fresh_task = with_reference_certificate(
                original_task,
                payload.model,
                payload.certificate,
                source=original_task["model"]["reference_domination"]["source"],
                tol=effective_tol,
                limits=limits,
            )
            new_c = Task.from_dict(fresh_task).reference_constant
            old_c = Task.from_dict(original_task).reference_constant
            item["fresh_constant_exact"] = str(new_c)
            item["historical_constant_exact"] = str(old_c)
            item["historical_constant_supported"] = new_c <= old_c
            item["fresh_bound"] = _derived_bound(scalar, fresh_task)
        comparisons.append(item)
    old_c = analysis["verification"]["constant_exact"]
    raw_support = (
        bool(rational(fresh["constant_exact"]) <= rational(old_c))
        if usable and old_c is not None
        else None
    )
    supported = (
        all(
            c["historical_constant_supported"] is True
            and c["current_scalar_comparison"]["matches"]
            for c in comparisons
        )
        if comparisons
        else raw_support
    )
    return {
        "schema": "rcc-refcert.bundle-verification",
        "schema_version": 1,
        "producer": {
            "name": "rcc-refcert",
            "version": __version__,
            "python": platform.python_version(),
            "numpy": np.__version__,
            "source_revision": source_revision_from_environment(),
        },
        "model": payload.model.name,
        "record_consistency": "pass",
        "controls": {
            "tolerance_exact": str(Fraction.from_float(effective_tol)),
            "original_tolerance_exact": str(Fraction.from_float(original_tol)),
            "tolerance_overridden": tol is not None,
            "limits": {
                name: _resource_diagnostic(value)
                for name, value in asdict(limits).items()
            },
        },
        "input_bindings": analysis["input_bindings"],
        "historical_verification": analysis["verification"],
        "fresh_verification": fresh,
        "historical_results_supported": supported if usable else None,
        "requests": comparisons,
        "external_premises_verified": False,
        "scope": "numerical model/certificate revalidation and conditional scalar calculation; external model and sampling premises remain supplied",
    }
