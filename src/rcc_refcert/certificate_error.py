"""Propagate one-sided numerical residuals to a certificate's final constant."""

from __future__ import annotations

import numpy as np

from .quantum import Array, hermitian_part
from .status import CheckOutcome, CheckResult


def roundoff_allowance(scale: float, size: int, operations: int = 1) -> float:
    """Working-precision allowance for matrix products, sums and eigensolves."""
    return float(16 * np.finfo(float).eps * size * (operations + 1) * scale)


def psd_deficit(matrix: Array, scale: float, operations: int = 1) -> float:
    """One-sided spectral deficit, including a working-precision allowance."""
    minimum = float(np.linalg.eigvalsh(hermitian_part(matrix)).min())
    return max(0.0, roundoff_allowance(scale, len(matrix), operations) - minimum)


def reference_floor(reference: Array) -> float:
    values = np.linalg.eigvalsh(hermitian_part(reference))
    return float(values.min()) - roundoff_allowance(
        float(np.max(np.abs(values))), len(reference)
    )


def residual_correction(transition: Array, deficit: Array) -> Array | None:
    """Find d >= 0 with d >= deficit + transition @ d.

    Only blocks that can reach a positive deficit need correction. A closed
    zero-deficit recurrent class therefore requires no inverse. On the active
    blocks, a positive Lyapunov vector bounds the solve residual as well as the
    original deficit; the relative condition number alone is insufficient.
    """
    if not np.all(np.isfinite(transition)) or not np.all(np.isfinite(deficit)):
        return None
    active = deficit > 0
    while True:
        expanded = active | np.any(transition[:, active] > 0, axis=1)
        if np.array_equal(expanded, active):
            break
        active = expanded
    correction = np.zeros_like(deficit)
    if not np.any(active):
        return correction
    matrix = transition[np.ix_(active, active)]
    rhs = deficit[active]
    system = np.eye(len(matrix)) - matrix
    try:
        weight = np.linalg.solve(system, np.ones(len(matrix)))
        value = np.maximum(0.0, np.linalg.solve(system, rhs))
    except np.linalg.LinAlgError:
        return None
    if not np.all(np.isfinite(weight)) or np.any(weight <= 0):
        return None
    scale = float(np.max(np.abs(weight) + np.abs(matrix) @ np.abs(weight)))
    margin = float(np.min(weight - matrix @ weight)) - roundoff_allowance(
        scale, len(matrix)
    )
    if margin <= 0 or not np.isfinite(margin):
        return None
    for _ in range(3):
        scale = float(np.max(np.abs(value) + matrix @ np.abs(value) + rhs))
        missing = rhs + matrix @ value - value
        allowance = roundoff_allowance(scale, len(matrix))
        shortfall = float(np.max(missing)) + allowance
        if shortfall <= 0:
            correction[active] = value
            return correction
        value += (2.0 * shortfall / margin) * weight
        if not np.all(np.isfinite(value)):
            return None
    return None


def final_constant_check(
    candidate: float, correction: float | None, tol: float
) -> CheckResult:
    budget = tol * max(1.0, candidate)
    if correction is None or not np.isfinite(correction):
        return CheckResult(
            "constant-error-budget",
            CheckOutcome.INCONCLUSIVE,
            "residual propagation has no resolved nonnegative bound",
            tolerance=budget,
        )
    status = CheckOutcome.PASS if correction <= budget else CheckOutcome.INCONCLUSIVE
    return CheckResult(
        "constant-error-budget",
        status,
        "propagated correction to the candidate constant",
        correction,
        budget,
    )


def accepted_constant(
    candidate: float, correction: float, tol: float
) -> tuple[float, float]:
    """Reserve the accepted error budget in the returned upper constant."""
    if correction == 0:
        return candidate, 0.0
    upper = float(np.nextafter(candidate + tol * max(1.0, candidate), np.inf))
    return upper, upper - candidate
