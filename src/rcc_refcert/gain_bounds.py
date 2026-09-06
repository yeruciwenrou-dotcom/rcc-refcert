"""One-sided gain estimates for the local H.6 inequalities."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

import numpy as np

from .certificate_error import reference_floor, roundoff_allowance
from .quantum import Array, apply_kraus, hermitian_part


@dataclass(frozen=True)
class GainBounds:
    estimate: float
    lower: Fraction
    upper: Fraction


def upper_float(value: Fraction) -> float:
    result = float(value)
    return float(np.nextafter(result, np.inf)) if Fraction(result) < value else result


def _diagonal_gain(
    kraus: tuple[Array, ...], source: Array, target: Array
) -> Fraction | None:
    """Resolve diagonal envelopes and column-sparse maps over binary inputs."""
    if any(
        np.any(matrix != np.diag(np.diag(matrix))) or np.any(np.diag(matrix).imag != 0)
        for matrix in (source, target)
    ):
        return None
    diagonal = [Fraction(float(x.real)) for x in np.diag(source)]
    reference = [Fraction(float(x.real)) for x in np.diag(target)]
    if any(x < 0 for x in diagonal) or any(x <= 0 for x in reference):
        return None
    output = [Fraction(0) for _ in reference]
    for matrix in kraus:
        for column, weight in enumerate(diagonal):
            rows = np.flatnonzero(matrix[:, column])
            if len(rows) > 1:
                return None
            if len(rows) == 1:
                row = rows[0]
                entry = matrix[row, column]
                square = (
                    Fraction(float(entry.real)) ** 2 + Fraction(float(entry.imag)) ** 2
                )
                output[row] += weight * square
    return max(value / ref for value, ref in zip(output, reference))


def branch_gain_bounds(
    kraus: tuple[Array, ...], source: Array, target: Array
) -> GainBounds | None:
    kraus = tuple(np.asarray(matrix, dtype=complex) for matrix in kraus)
    if not np.any(source):
        return GainBounds(0.0, Fraction(0), Fraction(0))
    if (
        len(kraus) == 1
        and np.array_equal(source, target)
        and np.array_equal(kraus[0], np.eye(len(source)))
    ):
        return GainBounds(1.0, Fraction(1), Fraction(1))
    exact = _diagonal_gain(kraus, source, target)
    if exact is not None:
        return GainBounds(float(exact), exact, exact)

    floor = reference_floor(target)
    if floor <= 0:
        return None
    values, vectors = np.linalg.eigh(hermitian_part(target))
    inverse = (vectors * values**-0.5) @ vectors.conj().T
    output = apply_kraus(kraus, source)
    scaled = hermitian_part(inverse @ output @ inverse)
    gain = max(0.0, float(np.linalg.eigvalsh(scaled).max()))
    residual = gain * target - output
    minimum = float(np.linalg.eigvalsh(hermitian_part(residual)).min())
    scale = float(np.linalg.norm(source, ord=2)) * sum(
        float(np.linalg.norm(k, ord=2)) ** 2 for k in kraus
    ) + gain * float(np.linalg.norm(target, ord=2))
    # A spectral residual of size e changes the generalized eigenvalue by
    # at most e / lambda_min(target). Include formation of the branch map.
    allowance = roundoff_allowance(
        scale, max(len(source), len(target)), 2 * len(kraus) + 3
    )
    error = (abs(minimum) + allowance) / floor
    if not np.isfinite(gain + error):
        return None
    lower = max(0.0, float(np.nextafter(gain - error, -np.inf)))
    upper = float(np.nextafter(gain + error, np.inf))
    return GainBounds(gain, Fraction(lower), Fraction(upper))


def ceil_log2(value: Fraction) -> int:
    """Nonnegative ceiling without floating-point logarithm rounding."""
    if value <= 1:
        return 0
    exponent = max(0, value.numerator.bit_length() - value.denominator.bit_length())
    return exponent + (value.numerator > value.denominator << exponent)
