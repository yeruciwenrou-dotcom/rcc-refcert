from __future__ import annotations

import math
from decimal import ROUND_CEILING, Decimal, localcontext


def normalize_diagnostic(value: float | None, tolerance: float) -> float | None:
    """Return a stable display value for a diagnostic resolved at ``tolerance``."""

    if value is None or not math.isfinite(value):
        return value
    return 0.0 if abs(value) <= tolerance else float(value)


def canonical_float(value: float, significant_digits: int = 12) -> float:
    """Round a finite scalar to the precision carried by the frozen contract."""

    return float(f"{value:.{significant_digits}g}")


def canonical_upper_float(value: float, significant_digits: int = 12) -> float:
    """Round an upper bound toward positive infinity for display or freezing."""
    if value == 0:
        return 0.0
    with localcontext() as context:
        context.prec = max(32, significant_digits + 2)
        decimal = Decimal.from_float(value)
        quantum = Decimal(1).scaleb(decimal.adjusted() - significant_digits + 1)
        rounded = float(decimal.quantize(quantum, rounding=ROUND_CEILING))
    return max(value, rounded)


def format_certificate_constant(
    constant: float | None,
    candidate: float | None,
    error_bound: float | None,
) -> str:
    if constant is None:
        return f"no usable constant; candidate {format_number(candidate)}"
    upper = canonical_upper_float(constant)
    if error_bound is None:
        return f"C <= {upper:.12g}"
    bound = canonical_upper_float(error_bound, 3)
    return f"C <= {upper:.12g}; candidate {format_number(candidate)}; correction <= {bound:.3g}"


def format_number(
    value: float | None,
    *,
    zero_tolerance: float | None = None,
) -> str:
    """Format a scalar, optionally resolving its numerical zero band."""

    if value is None:
        return "not evaluated"
    if not math.isfinite(value):
        return "infinite"
    if zero_tolerance is not None:
        value = normalize_diagnostic(value, zero_tolerance)
    if value == 0:
        return "0"
    nearest = round(value)
    if nearest != 0 and abs(value - nearest) <= 1e-12 * max(1.0, abs(value)):
        return str(nearest)
    if abs(value) < 1e-3 or abs(value) >= 1e6:
        return f"{value:.3e}"
    return f"{value:.12g}"
