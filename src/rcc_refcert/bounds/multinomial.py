"""Weighted classical windows and smooth one-shot floors on a joint TV ball."""

from fractions import Fraction as F

from .scalar import Interval, ln_interval, log2_interval, sqrt_interval


def tv_radius(m, n, failure):
    """Outward radius from D.32 for a predeclared complete alphabet."""
    if m == 1:
        return F(0)
    factor = ln_interval(F((1 << m) - 2) / failure).upper
    return min(F(1), sqrt_interval(factor / (2 * n)).upper)


def _point(x):
    return Interval(x, x)


def _threshold(p, u, order, shift):
    """Fill low ratios (positive shift) or drain high ratios (negative shift)."""
    mass = weight = F(0)
    for j, i in enumerate(order):
        mass += p[i]
        weight += u[i]
        level = (mass + shift) / weight
        if j + 1 == len(order):
            return level
        k = order[j + 1]
        next_ratio = p[k] / u[k]
        if (shift > 0 and level <= next_ratio) or (shift <= 0 and level >= next_ratio):
            return level


def _kl(p, u):
    result = Interval.point(0)
    for x, y in zip(p, u):
        if x:
            result += _point(x) * log2_interval(x / y)
    return result.positive_part()


def _entropy_term(x):
    return (_point(x) * log2_interval(1 / x)).upper if x else F(0)


class HistogramRegion:
    """Exact frequencies and rank weights, sorted once for all requested radii."""

    def __init__(self, counts, ranks, radius):
        total, dimension = sum(counts), sum(ranks)
        self.p = [F(c, total) for c in counts]
        self.u = [F(r, dimension) for r in ranks]
        self.order = sorted(range(len(counts)), key=lambda i: self.p[i] / self.u[i])
        self.distance = sum((max(F(0), x - y) for x, y in zip(self.p, self.u)), F(0))
        self.radius = radius

    def classical(self, bandwidth):
        p, u, t = self.p, self.u, self.radius
        if t >= self.distance:
            q = u
        elif t == 0:
            q = p
        else:
            floor = _threshold(p, u, self.order, t)
            cap = _threshold(p, u, self.order[::-1], -t)
            q = [min(max(x, floor * y), cap * y) for x, y in zip(p, u)]
        lower = _kl(q, u).lower
        m = len(p)
        upper = F(0)
        if m > 1:
            v = min(t, F(m - 1, m))
            continuity = (
                _entropy_term(v)
                + _entropy_term(1 - v)
                + v * log2_interval(F(m - 1)).upper
            )
            cross_term = t * log2_interval(max(u) / min(u)).upper
            upper = min(
                log2_interval(1 / min(u)).upper,
                _kl(p, u).upper + continuity + cross_term,
            )
        return Interval(lower, upper) / bandwidth, q

    def smooth_floor(self, epsilon):
        s = min(F(1), self.radius + epsilon)
        if s >= self.distance:
            return Interval.point(0), F(1), []
        cap = _threshold(self.p, self.u, self.order[::-1], -s)
        # At s=0 include the maximal-ratio outcomes as a witness.
        group = [i for i in range(len(self.p)) if self.p[i] >= cap * self.u[i]]
        return log2_interval(cap), cap, group
