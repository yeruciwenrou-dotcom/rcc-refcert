from __future__ import annotations

import math


def normalize_diagnostic(value: float | None, tolerance: float) -> float | None:
    """Return a stable display value for a diagnostic resolved at ``tolerance``."""

    if value is None or not math.isfinite(value):
        return value
    return 0.0 if abs(value) <= tolerance else float(value)


def canonical_float(value: float, significant_digits: int = 12) -> float:
    """Round a finite scalar to the precision carried by the frozen contract."""

    return float(f"{value:.{significant_digits}g}")


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
