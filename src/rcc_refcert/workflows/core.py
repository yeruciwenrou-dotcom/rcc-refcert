"""Shared identities, exact inputs and resource limits for research workflows."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, fields
from decimal import Decimal, InvalidOperation
from fractions import Fraction

from ..bounds.scalar import BudgetError, InputError, UnsupportedContract, require_int
from ..limits import ComputationLimits, ResourceLimitError


@dataclass(frozen=True)
class WorkflowLimits:
    max_dp_cells: int = 100_000
    max_dp_updates: int = 1_000_000
    max_fraction_bits: int = 65_536
    max_candidate_steps: int = 10_000
    max_trajectory_states: int = 256
    max_windows: int = 256
    max_matrix_elements: int = 1_048_576

    def __post_init__(self):
        for item in fields(self):
            require_int(getattr(self, item.name), item.name, 1)
        if self.max_fraction_bits > 65_536:
            raise BudgetError("max_fraction_bits: supported maximum is 65536")

    @classmethod
    def from_value(cls, value=None):
        if value is None:
            return cls()
        if isinstance(value, cls):
            return value
        if isinstance(value, ComputationLimits):
            return cls(max_matrix_elements=value.max_matrix_elements)
        obj = mapping(value, "limits")
        allowed = {f.name for f in fields(cls)}
        unknown = set(obj) - allowed
        if unknown:
            raise InputError("limits: unknown resource field")
        return cls(**obj)

    def as_dict(self):
        return asdict(self)


def mapping(value, name):
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        raise InputError(f"{name}: expected an object with string keys")
    return value


def keys(value, required, optional=(), name="object"):
    obj = mapping(value, name)
    if set(required) - set(obj) or set(obj) - set(required) - set(optional):
        raise InputError(f"{name}: missing or unknown fields; check the template")
    return obj


def text(value, name):
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise InputError(f"{name}: expected nonempty text of at most 4096 characters")
    return value


def check_size(resource, estimate, limit):
    if estimate > limit:
        raise ResourceLimitError(resource, estimate, limit)


def integer_text(value):
    """Serialize bounded integers without changing Python's process-wide guard."""
    if abs(value).bit_length() <= 4096:
        return str(value)
    sign = "-" if value < 0 else ""
    value = abs(value)
    chunks = []
    while value:
        value, chunk = divmod(value, 1_000_000_000)
        chunks.append(chunk)
    return sign + str(chunks[-1]) + "".join(f"{c:09d}" for c in reversed(chunks[:-1]))


def exact_text(value):
    value = Fraction(value)
    a = integer_text(value.numerator)
    return a if value.denominator == 1 else a + "/" + integer_text(value.denominator)


def _integer(value):
    sign = -1 if value.startswith("-") else 1
    digits = value.lstrip("+-")
    if not digits or not digits.isascii() or not digits.isdecimal():
        raise ValueError("invalid integer")
    result = 0
    for i in range(0, len(digits), 9):
        chunk = digits[i : i + 9]
        result = result * 10 ** len(chunk) + int(chunk)
    return sign * result


def exact(value, name="value", *, limits=None):
    limits = WorkflowLimits.from_value(limits)
    bits = limits.max_fraction_bits
    if isinstance(value, (bool, float)):
        raise InputError(f"{name}: use an exact integer, decimal or fraction string")
    if not isinstance(value, (str, int, Fraction, Decimal)):
        raise InputError(f"{name}: unsupported exact scalar type")
    if isinstance(value, int) and value.bit_length() > bits:
        raise BudgetError(f"{name}: rational bit budget exceeded")
    if isinstance(value, str):
        if len(value) > 2 * bits + 32:
            raise BudgetError(f"{name}: scalar text budget exceeded")
        value = value.strip()
    try:
        if isinstance(value, str) and "/" in value:
            a, b = value.split("/")
            # A decimal digit needs fewer than four bits. Check before allocation.
            if max(len(a.lstrip("+-")), len(b.lstrip("+-"))) > bits:
                raise BudgetError(f"{name}: integer representation budget exceeded")
            result = Fraction(_integer(a), _integer(b))
        elif isinstance(value, (str, Decimal)):
            dec = Decimal(value)
            if not dec.is_finite():
                raise InputError(f"{name}: must be finite")
            tup = dec.as_tuple()
            if abs(tup.exponent) > bits or len(tup.digits) > bits:
                raise BudgetError(f"{name}: decimal representation budget exceeded")
            result = Fraction(dec)
        else:
            result = Fraction(value)
    except (ValueError, ZeroDivisionError, InvalidOperation, OverflowError) as exc:
        if isinstance(exc, InputError):
            raise
        raise InputError(f"{name}: invalid finite rational") from exc
    return check_fraction(result, name, limits)


def check_fraction(value, name, limits):
    if (
        max(value.numerator.bit_length(), value.denominator.bit_length())
        > limits.max_fraction_bits
    ):
        raise BudgetError(f"{name}: rational bit budget exceeded")
    return value


def json_value(value, *, _depth=0, _budget=None):
    """Copy data-only public values with bounds before hashing or serialization."""
    if _budget is None:
        _budget = [0, 0]
    _budget[0] += 1
    if _depth > 40 or _budget[0] > 200_000:
        raise BudgetError("workflow JSON nesting or node budget exceeded")
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (Fraction, Decimal)):
        return exact_text(exact(value))
    if isinstance(value, int):
        if value.bit_length() > 256:
            raise BudgetError(
                "JSON integer exceeds 256 bits; use an exact scalar string"
            )
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise InputError("workflow JSON: nonfinite numeric value")
        return value
    if isinstance(value, str):
        _budget[1] += len(value)
        if _budget[1] > 16 * 1024 * 1024:
            raise BudgetError("workflow JSON text budget exceeded")
        return value
    if isinstance(value, (list, tuple)):
        if len(value) > 200_000 - _budget[0]:
            raise BudgetError("workflow JSON node budget exceeded")
        return [json_value(v, _depth=_depth + 1, _budget=_budget) for v in value]
    if isinstance(value, dict):
        mapping(value, "workflow JSON")
        return {
            json_value(k, _depth=_depth + 1, _budget=_budget): json_value(
                v, _depth=_depth + 1, _budget=_budget
            )
            for k, v in value.items()
        }
    raise InputError("workflow JSON: unsupported value type")


def canonical_bytes(value):
    try:
        return json.dumps(
            json_value(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (UnicodeError, RecursionError) as exc:
        raise InputError("workflow data must be bounded valid UTF-8 JSON") from exc


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def layout(dims, labels, *, limits=None):
    limits = WorkflowLimits.from_value(limits)
    if not isinstance(dims, (list, tuple)) or not dims or len(dims) > 64:
        raise InputError("subsystem_dims: supply one to 64 dimensions")
    ds = tuple(require_int(d, "subsystem dimension", 1) for d in dims)
    if not isinstance(labels, (list, tuple)) or len(labels) != len(ds):
        raise InputError("subsystem_labels: provide one label per dimension")
    ls = tuple(text(s, "subsystem label") for s in labels)
    if len(set(ls)) != len(ls):
        raise InputError("subsystem_labels: labels must be unique")
    size = 1
    for d in ds:
        if d > limits.max_matrix_elements // size:
            raise ResourceLimitError(
                "state_dimension", d * size, limits.max_matrix_elements
            )
        size *= d
    return ds, ls, size


def probabilities(values, size, *, name="probabilities", limits=None):
    limits = WorkflowLimits.from_value(limits)
    if not isinstance(values, (list, tuple)) or len(values) != size:
        raise InputError(f"{name}: supply every basis probability, including zeros")
    result = tuple(exact(v, name, limits=limits) for v in values)
    # This estimate bounds intermediate denominator growth without building it.
    if sum(v.denominator.bit_length() for v in result) > 4 * limits.max_fraction_bits:
        raise BudgetError(f"{name}: conservative denominator preflight exceeded")
    total = Fraction(0)
    for value in result:
        if value < 0:
            raise InputError(f"{name}: probabilities must be nonnegative")
        total = check_fraction(total + value, name, limits)
    if total != 1:
        raise InputError(f"{name}: probabilities must sum exactly to one")
    return result


def require_supported(value, expected, name):
    if value != expected:
        raise UnsupportedContract(f"{name}: supported value is {expected}")
