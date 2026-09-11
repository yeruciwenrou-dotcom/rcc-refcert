"""Small scalar enclosure oracle; not a matrix or physical-model verifier.

Arithmetic endpoints are Fractions. Only logarithms use Decimal, with directed
input conversion and neighbouring correctly rounded ln results. See the design
note for the trusted arithmetic contract. No global Decimal context is changed.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_EVEN, Context, Decimal
from fractions import Fraction
from functools import lru_cache
from math import isqrt

Scalar = str | int | Fraction | Decimal
PRECISION = 64
MAX_INPUT_BITS = 8192


class InputError(ValueError):
    """A supplied scientific input is invalid or incomplete."""


class UnsupportedContract(InputError):
    """The input requires a branch outside this reference implementation."""


class BudgetError(InputError):
    """A declared reference-computation budget was exceeded."""


def rational(value: Scalar, name: str = "value") -> Fraction:
    if isinstance(value, (bool, float)):
        raise InputError(
            f"{name}: use an exact integer, decimal string, or fraction string; floats are not silently reinterpreted"
        )
    if not isinstance(value, (str, int, Fraction, Decimal)):
        raise InputError(f"{name}: unsupported scalar type")
    # Canonical integer and fraction spellings can be longer than the original
    # scientific notation. Permit lossless replay within the same bit budget.
    if isinstance(value, str):
        canonical_integer = value.removeprefix("-").isdecimal()
        max_chars = 5000 if "/" in value or canonical_integer else 512
        if len(value) > max_chars:
            raise BudgetError(f"{name}: input string exceeds {max_chars} characters")
    # Bound exponent before constructing a potentially enormous rational.
    if isinstance(value, (str, Decimal)) and "/" not in str(value):
        try:
            dec = Decimal(value)
        except Exception as exc:
            raise InputError(f"{name}: invalid decimal") from exc
        if not dec.is_finite():
            raise InputError(f"{name}: must be finite")
        if abs(dec.as_tuple().exponent) > 2048:
            raise BudgetError(f"{name}: decimal exponent exceeds calculation budget")
    try:
        result = Fraction(value)
    except (ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
        raise InputError(f"{name}: invalid finite rational") from exc
    if (
        max(result.numerator.bit_length(), result.denominator.bit_length())
        > MAX_INPUT_BITS
    ):
        raise BudgetError(f"{name}: rational input exceeds {MAX_INPUT_BITS}-bit budget")
    return result


def require_int(value: object, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise InputError(f"{name}: must be an integer >= {minimum}")
    return value


@dataclass(frozen=True)
class Interval:
    lower: Fraction
    upper: Fraction

    def __post_init__(self) -> None:
        if self.lower > self.upper:
            raise InputError("reversed interval")

    @staticmethod
    def point(value: Scalar) -> Interval:
        q = rational(value)
        return Interval(q, q)

    def __add__(self, other: Interval) -> Interval:
        return Interval(self.lower + other.lower, self.upper + other.upper)

    def __sub__(self, other: Interval) -> Interval:
        return Interval(self.lower - other.upper, self.upper - other.lower)

    def __mul__(self, other: Interval) -> Interval:
        products = [
            a * b for a in (self.lower, self.upper) for b in (other.lower, other.upper)
        ]
        return Interval(min(products), max(products))

    def __truediv__(self, other: Interval) -> Interval:
        if other.lower <= 0 <= other.upper:
            raise InputError("interval division crosses zero")
        reciprocals = [1 / other.lower, 1 / other.upper]
        return self * Interval(min(reciprocals), max(reciprocals))

    def positive_part(self) -> Interval:
        return Interval(max(Fraction(0), self.lower), max(Fraction(0), self.upper))

    def strings(self, digits: int = 48) -> dict[str, str]:
        return {
            "lower": decimal_string(self.lower, digits, ROUND_FLOOR),
            "upper": decimal_string(self.upper, digits, ROUND_CEILING),
        }


def decimal_string(q: Fraction, digits: int = 48, rounding: str = ROUND_FLOOR) -> str:
    ctx = Context(prec=digits, rounding=rounding)
    return str(ctx.divide(Decimal(q.numerator), Decimal(q.denominator)))


def _ln_decimal_bound(d: Decimal, lower: bool) -> Fraction:
    if d == 1:
        return Fraction(0)
    ctx = Context(prec=PRECISION, rounding=ROUND_HALF_EVEN)
    v = d.ln(context=ctx)
    adjacent = ctx.next_minus(v) if lower else ctx.next_plus(v)
    return Fraction(adjacent)


@lru_cache(maxsize=2048)
def ln_interval(q: Fraction) -> Interval:
    if q <= 0:
        raise InputError("ln argument must be positive")
    lo_ctx = Context(prec=PRECISION, rounding=ROUND_FLOOR)
    hi_ctx = Context(prec=PRECISION, rounding=ROUND_CEILING)
    lo = lo_ctx.divide(Decimal(q.numerator), Decimal(q.denominator))
    hi = hi_ctx.divide(Decimal(q.numerator), Decimal(q.denominator))
    return Interval(_ln_decimal_bound(lo, True), _ln_decimal_bound(hi, False))


def log2_interval(q: Fraction) -> Interval:
    if q <= 0:
        raise InputError("log2 argument must be positive")
    n, d = q.numerator, q.denominator
    if n & (n - 1) == 0 and d & (d - 1) == 0:
        return Interval.point(n.bit_length() - d.bit_length())
    return ln_interval(q) / ln_interval(Fraction(2))


def sqrt_interval(q: Fraction) -> Interval:
    if q < 0:
        raise InputError("sqrt argument must be nonnegative")
    scale = 10**PRECISION
    squared = q.numerator * scale * scale
    k = isqrt(squared // q.denominator)
    lo = Fraction(k, scale)
    if k * k * q.denominator == squared:
        return Interval(lo, lo)
    return Interval(lo, Fraction(k + 1, scale))


def phi_interval(length: Fraction, g: Interval, a: Fraction) -> Interval:
    return g * Interval(length, length) + Interval(a, a) * log2_interval(
        max(Fraction(1), length)
    )


def invert_canonical(
    y: Interval, g: Interval, a: Scalar, max_steps: int = 200
) -> tuple[Interval, str]:
    """Enclose F_{g,a}(y) for every value inside the declared input intervals.

    The result's LOWER endpoint is the process-lower-bound input. The upper
    endpoint encloses this mathematical calculator, not the true C_opt.
    """
    aa = rational(a, "a")
    require_int(max_steps, "max_steps", 1)
    if max_steps > 1000:
        raise BudgetError("max_steps exceeds calculation budget")
    if aa < 0 or g.lower <= 0:
        raise InputError("require a >= 0 and a strictly positive bandwidth")
    if y.upper <= 0:
        return Interval.point(0), "complete"
    if aa == 0 or y.upper <= g.lower:
        return (y / g).positive_part(), "complete"
    lo, hi = Fraction(0), max(Fraction(0), y.upper / g.lower)
    tolerance = Fraction(1, 10**24)
    for _ in range(max_steps):
        if hi - lo <= tolerance * max(Fraction(1), hi):
            return Interval(lo, hi), "complete"
        mid = (lo + hi) / 2
        f = phi_interval(mid, g, aa)
        if f.lower == f.upper == y.lower == y.upper:
            return Interval(mid, mid), "complete"
        if f.upper <= y.lower:
            lo = mid
        elif f.lower >= y.upper:
            hi = mid
        else:
            # In the overlap region, monotonic slope >= g.lower provides
            # enclosure contraction without guessing a sign.
            new_lo = max(lo, mid - max(Fraction(0), f.upper - y.lower) / g.lower)
            new_hi = min(hi, mid + max(Fraction(0), y.upper - f.lower) / g.lower)
            if new_lo == lo and new_hi == hi:
                return Interval(lo, hi), "precision_limited"
            lo, hi = new_lo, new_hi
    return Interval(lo, hi), "iteration_budget_reached"


def ceil_fraction(q: Fraction) -> int:
    return -((-q.numerator) // q.denominator)
