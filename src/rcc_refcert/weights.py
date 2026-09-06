"""Represent prefix weights without silently discarding nonzero mass."""

from __future__ import annotations

import math

import numpy as np

from .quantum import Array

# Relative roundoff estimates require normal binary64 weights.
MAX_CODE_LENGTH = 1022


class NumericalRangeError(ValueError):
    """A nonzero program contribution exceeds the numerical support range."""


def code_weight(length: int) -> float:
    if length < 0 or length > MAX_CODE_LENGTH:
        raise NumericalRangeError(
            f"code length {length} exceeds the supported weight range "
            f"0..{MAX_CODE_LENGTH}; a nonzero weight cannot be discarded"
        )
    return math.ldexp(1.0, -length)


def weighted_operator(weight: float, operator: Array) -> Array:
    try:
        with np.errstate(under="raise"):
            result = weight * operator
    except FloatingPointError as error:
        raise NumericalRangeError(
            "program-weight multiplication underflowed"
        ) from error
    if weight > 0 and np.any((operator != 0) & (result == 0)):
        raise NumericalRangeError("program weighting lost a nonzero matrix entry")
    return result
