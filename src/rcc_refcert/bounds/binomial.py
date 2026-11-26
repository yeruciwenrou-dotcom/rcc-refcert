"""Fixed-N binomial tails and outward one-sided Clopper–Pearson endpoints."""

from fractions import Fraction
from math import comb

from .information import hoeffding_lower, hoeffding_upper
from .scalar import BudgetError, InputError, Interval, rational, require_int

CP = "clopper_pearson"
HOEFFDING = "hoeffding"
CP_MAX_N = 4096
CP_BITS = 48
GRID = 1 << CP_BITS


def _upper_tail_parts(n, k, p):
    """Integer numerator and denominator of P[Bin(n,p) >= k]."""
    if k <= 0:
        return 1, 1
    if k > n or p == 0:
        return 0, 1
    if p == 1:
        return 1, 1
    a, b = p.numerator, p.denominator
    c = b - a
    # Use the shorter of the upper tail and the reflected lower tail.
    if k <= n - k:
        tail, denominator = _upper_tail_parts(n, n - k + 1, 1 - p)
        return denominator - tail, denominator
    term = comb(n, k) * a**k * c ** (n - k)
    total = term
    for j in range(k, n):
        term = (term * (n - j) * a) // ((j + 1) * c)
        total += term
    return total, b**n


def _tail_at_most(n, k, p, alpha):
    num, den = _upper_tail_parts(n, k, p)
    return num * alpha.denominator <= den * alpha.numerator


def clopper_pearson_lower(hits, samples, delta):
    """Enclose the exact lower endpoint on a 48-bit dyadic grid."""
    n = require_int(samples, "samples", 1)
    h = require_int(hits, "hits")
    alpha = rational(delta, "delta")
    if n > CP_MAX_N:
        raise BudgetError(f"Clopper-Pearson supports up to {CP_MAX_N} trials")
    if h > n or not 0 < alpha < 1:
        raise InputError("require hits <= samples and delta in (0,1)")
    if h == 0:
        return Interval.point(0)
    lo, hi = 0, GRID
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if _tail_at_most(n, h, Fraction(mid, GRID), alpha):
            lo = mid
        else:
            hi = mid
    return Interval(Fraction(lo, GRID), Fraction(hi, GRID))


def clopper_pearson_upper(hits, samples, delta):
    """Use the complementary count to enclose the exact upper endpoint."""
    n = require_int(samples, "samples", 1)
    k = require_int(hits, "hits")
    return Interval.point(1) - clopper_pearson_lower(n - k, n, delta)


def sampling_endpoint(hits, arm, direction):
    method = arm.get("method", HOEFFDING)
    if method == CP:
        calculate = (
            clopper_pearson_lower if direction == "lower" else clopper_pearson_upper
        )
    elif method == HOEFFDING:
        calculate = hoeffding_lower if direction == "lower" else hoeffding_upper
    else:
        raise InputError("unknown binomial endpoint method")
    interval = calculate(hits, arm["samples"], arm["delta"])
    return interval.lower if direction == "lower" else interval.upper
