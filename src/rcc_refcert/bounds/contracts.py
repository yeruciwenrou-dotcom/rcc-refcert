"""Task identity, model assumptions and their supporting sources."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

from .scalar import BudgetError, InputError, UnsupportedContract, rational, require_int

QUALIFICATION_NAMES = {"RCon", "TC", "RA"}
MATRIX_HASH_FORMAT = "rcc-refcert.matrix-bytes.v1"


def json_ready(value: object, depth: int = 0) -> object:
    """Lossless JSON representation of supported exact Python input types.

    Identity strings stay strings. Fraction/Decimal values retain their exact
    values as reduced fraction strings. Binary floats remain unsupported.
    """
    if depth > 32:
        raise BudgetError("input nesting exceeds 32 levels")
    if isinstance(value, (Fraction, Decimal)):
        return str(rational(value))
    if value is None or type(value) in (str, bool):
        return value
    if type(value) is int:
        if value.bit_length() > 8192:
            raise BudgetError("integer input exceeds 8192-bit budget")
        return value
    if isinstance(value, (list, tuple)):
        if len(value) > 10000:
            raise BudgetError("input array exceeds 10000 entries")
        return [json_ready(v, depth + 1) for v in value]
    if isinstance(value, dict):
        if any(type(k) is not str for k in value):
            raise InputError("JSON object keys must be strings")
        return {k: json_ready(v, depth + 1) for k, v in value.items()}
    raise InputError(
        "use exact scalars, strings, arrays and objects; binary floats are not silently reinterpreted"
    )


def canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            json_ready(value),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{name}: a nonempty identity or source is required")
    if len(value) > 4096:
        raise BudgetError(f"{name}: text exceeds 4096 characters")
    return value


def keys(
    obj: object, required: set[str], name: str, optional: set[str] | None = None
) -> dict:
    if not isinstance(obj, dict):
        raise InputError(f"{name}: expected an object")
    if any(type(k) is not str for k in obj):
        raise InputError(f"{name}: object keys must be strings")
    missing = required - obj.keys()
    extra = obj.keys() - required - (optional or set())
    if missing or extra:
        raise InputError(
            f"{name}: missing={sorted(missing)}, unexpected={sorted(extra)}"
        )
    return obj


@dataclass(frozen=True)
class Task:
    """A validated preparation task with a fixed model, target and tolerance."""

    declaration_json: str
    dimension: int
    gamma_classes: int
    a: Fraction
    gamma_bits: Fraction
    reference_constant: Fraction
    epsilon: Fraction
    integer_cost: bool

    @classmethod
    def from_dict(cls, raw: dict) -> Task:
        return cls._parse(raw, allow_missing_qualifications=False)

    @classmethod
    def _parse(cls, raw: dict, *, allow_missing_qualifications: bool) -> Task | None:
        keys(raw, {"model", "target"}, "task")
        m = keys(
            raw["model"],
            {
                "id",
                "reference_id",
                "dimension",
                "atomic_action_classes",
                "transcription",
                "reference_domination",
                "cost_domain",
                "reference_treatment",
            },
            "model",
            {"qualification"},
        )
        text(m["id"], "model.id")
        text(m["reference_id"], "model.reference_id")
        d = require_int(m["dimension"], "dimension", 1)
        classes = require_int(m["atomic_action_classes"], "atomic_action_classes", 2)
        if max(classes.bit_length(), d.bit_length()) > 4096:
            raise BudgetError("model dimension or action count exceeds 4096-bit budget")
        t = keys(m["transcription"], {"mode", "a", "gamma_bits"}, "transcription")
        if t["mode"] != "exact":
            raise UnsupportedContract(
                "approximate TC is not implemented; see Appendix C.5"
            )
        a = rational(t["a"], "transcription.a")
        gamma = rational(t["gamma_bits"], "transcription.gamma_bits")
        if a < 0 or gamma < 0:
            raise InputError("a and gamma must be nonnegative")
        r = keys(
            m["reference_domination"],
            {"upper_constant", "source", "source_kind"},
            "reference_domination",
            {"evidence"},
        )
        text(r["source"], "reference_domination.source")
        if not isinstance(r["source_kind"], str) or r["source_kind"] not in {
            "analytic_argument",
            "numerical_upper_constant",
            "user_declared_upper_bound",
        }:
            raise InputError(
                "reference domination requires an upper constant; H.34 point estimates are not accepted"
            )
        cu = rational(r["upper_constant"], "reference upper constant")
        if cu < 1:
            raise InputError(
                "use the nonnegative-overhead convention: supply max(1, a valid upper constant)"
            )
        if "evidence" in r:
            e = keys(
                r["evidence"],
                {
                    "method",
                    "outcome",
                    "level",
                    "model_id",
                    "reference_id",
                    "model_sha256",
                    "certificate_sha256",
                    "reported_constant_exact",
                    "tolerance_exact",
                },
                "reference evidence",
                {"input_hash_format"},
            )
            if (
                "input_hash_format" in e
                and e["input_hash_format"] != MATRIX_HASH_FORMAT
            ):
                raise InputError("unsupported reference input hash format")
            if (
                r["source_kind"] != "numerical_upper_constant"
                or e["method"] not in ("H.3", "H.4")
                or e["outcome"] != "pass"
                or e["level"] != "numerical"
                or e["model_id"] != m["id"]
                or e["reference_id"] != m["reference_id"]
            ):
                raise InputError(
                    "reference evidence does not match its model, method or numerical role"
                )
            for key in ("model_sha256", "certificate_sha256"):
                if (
                    not isinstance(e[key], str)
                    or len(e[key]) != 64
                    or any(c not in "0123456789abcdef" for c in e[key])
                ):
                    raise InputError(
                        "reference evidence requires full SHA-256 input identities"
                    )
            endpoint = rational(e["reported_constant_exact"])
            if (
                endpoint < 0
                or cu != max(Fraction(1), endpoint)
                or rational(e["tolerance_exact"]) <= 0
            ):
                raise InputError("reference evidence endpoint or tolerance differs")
        required = set() if allow_missing_qualifications else QUALIFICATION_NAMES
        quals = keys(
            m.get("qualification", {}), required, "qualification", QUALIFICATION_NAMES
        )
        for key, value in quals.items():
            keys(value, {"basis", "source"}, f"qualification.{key}")
            if not isinstance(value["basis"], str) or value["basis"] not in {
                "analytic_argument_supplied",
                "numerical_certificate_supplied",
                "user_declared",
            }:
                raise InputError(f"unknown qualification basis for {key}")
            text(value["source"], f"qualification.{key}.source")
        if m["reference_treatment"] != "ideal_support":
            raise UnsupportedContract(
                "only declared ideal reference support is implemented"
            )
        if not isinstance(m["cost_domain"], str) or m["cost_domain"] not in {
            "integer_atomic_slots",
            "unspecified",
        }:
            raise UnsupportedContract(
                "task.model.cost_domain: choose integer_atomic_slots or unspecified"
            )
        target = keys(raw["target"], {"id", "epsilon", "metric"}, "target")
        text(target["id"], "target.id")
        if target["metric"] != "normalized_trace_distance":
            raise UnsupportedContract(
                "task.target.metric: use normalized_trace_distance and specify epsilon in that metric"
            )
        eps = rational(target["epsilon"], "target.epsilon")
        if not 0 <= eps <= 1:
            raise InputError("target epsilon must lie in [0,1]")
        # Exact scalar spellings become canonical fraction strings for identity.
        clean = json_ready(raw)
        clean["model"]["transcription"]["a"] = str(a)
        clean["model"]["transcription"]["gamma_bits"] = str(gamma)
        clean["model"]["reference_domination"]["upper_constant"] = str(cu)
        clean["target"]["epsilon"] = str(eps)
        if QUALIFICATION_NAMES - quals.keys():
            return None
        return cls(
            json.dumps(clean, sort_keys=True, ensure_ascii=False),
            d,
            classes,
            a,
            gamma,
            cu,
            eps,
            m["cost_domain"] == "integer_atomic_slots",
        )

    @property
    def declaration(self) -> dict:
        return json.loads(self.declaration_json)

    @property
    def fingerprint(self) -> str:
        return canonical_hash(self.declaration)


PROTOCOL_KEYS = {
    "id",
    "task_fingerprint",
    "witness_id",
    "rank",
    "samples",
    "delta_stat",
    "sampling",
    "selection",
    "readout",
    "support",
}


def validate_protocol(task: Task, raw: dict) -> dict:
    """Validate a single fixed-N protocol and normalize exact scalar spellings."""
    p = keys(raw, PROTOCOL_KEYS, "protocol")
    for key in ("id", "witness_id"):
        text(p[key], f"protocol.{key}")
    if p["task_fingerprint"] != task.fingerprint:
        raise InputError("protocol and task identities differ")
    supported = {
        "sampling": "fixed_n_iid",
        "selection": "predeclared",
        "readout": "ideal",
        "support": "no_leakage",
    }
    for key, value in supported.items():
        if p[key] != value:
            raise UnsupportedContract(f"{key}: this calculator supports only {value}")
    n = require_int(p["samples"], "protocol.samples", 1)
    k = require_int(p["rank"], "protocol.rank", 1)
    if n > 10**12:
        raise BudgetError("sample count exceeds calculation budget")
    if k > task.dimension:
        raise InputError("projector rank cannot exceed reference dimension")
    delta = rational(p["delta_stat"], "protocol.delta_stat")
    if not 0 < delta < 1:
        raise InputError("delta_stat must lie in (0,1)")
    result = json_ready(p)
    result["delta_stat"] = str(delta)
    return result


def validate_projector_hits(hits, protocol, dimension):
    hits = require_int(hits, "data.hits", 0)
    samples = protocol["samples"]
    if hits > samples:
        raise InputError("data.hits exceeds the declared sample count")
    # validate_protocol establishes ideal readout and support without leakage.
    if protocol["rank"] == dimension and hits != samples:
        raise InputError(
            f"data.hits: the full-support projector under this protocol requires "
            f"{samples} hits in {samples} trials, received {hits}"
        )
    return hits


def prepare_protocol(task_declaration: dict, protocol_spec: dict) -> dict:
    """Freeze the protocol before sampling and save its digest with the acquisition record."""
    task = Task.from_dict(task_declaration)
    spec = deepcopy(protocol_spec)
    keys(
        spec,
        PROTOCOL_KEYS - {"task_fingerprint"},
        "protocol specification",
        {"task_fingerprint"},
    )
    if "task_fingerprint" in spec and spec["task_fingerprint"] != task.fingerprint:
        raise InputError("existing protocol task fingerprint differs")
    spec["task_fingerprint"] = task.fingerprint
    protocol = validate_protocol(task, spec)
    return {
        "protocol": protocol,
        "protocol_sha256": canonical_hash(protocol),
        "record_role": "protocol_declaration_not_a_measurement_result",
        "chronology_or_iid_independently_verified": False,
    }
