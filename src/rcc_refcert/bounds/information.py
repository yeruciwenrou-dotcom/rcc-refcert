"""Normalized trace-distance spectral cap and fixed-projector information."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

from .scalar import (
    BudgetError,
    InputError,
    Interval,
    Scalar,
    ln_interval,
    log2_interval,
    rational,
    require_int,
    sqrt_interval,
)


@dataclass(frozen=True)
class SpectralInformation:
    dimension: int
    epsilon: Fraction
    cap: Fraction
    saturation_radius: Fraction
    information: Interval
    relative_entropy: Interval
    spectral_skew: Interval
    smoothing_loss: Interval
    witness_rank: int | None
    witness_mass: Fraction | None

    def as_dict(self) -> dict:
        return {
            "kind": "declared_exact_spectrum",
            "information_semantics": "enclosure_of_exact_smooth_information",
            "dimension": self.dimension,
            "smoothing_radius": str(self.epsilon),
            "cap_exact": str(self.cap),
            "saturation_radius_exact": str(self.saturation_radius),
            "information_bits": self.information.strings(),
            "relative_entropy_bits": self.relative_entropy.strings(),
            "spectral_skew_bits": self.spectral_skew.strings(),
            "smoothing_loss_bits": self.smoothing_loss.strings(),
            "witness": None
            if self.witness_rank is None
            else {
                "rank": self.witness_rank,
                "target_mass_exact": str(self.witness_mass),
                "reference_response_exact": str(
                    Fraction(self.witness_rank, self.dimension)
                ),
                "operator_supplied": False,
                "selection_role": "mathematical_spectral_witness_not_experimental_predeclaration",
            },
        }


def spectral_information(
    values: Sequence[Scalar], dimension: int, epsilon: Scalar
) -> SpectralInformation:
    d = require_int(dimension, "dimension", 1)
    if d > 4096:
        raise BudgetError("reference spectrum dimension exceeds 4096")
    if (
        not isinstance(values, Sequence)
        or isinstance(values, (str, bytes))
        or len(values) != d
    ):
        raise InputError(
            "supply the complete declared reference-space spectrum, including zeros"
        )
    lam = sorted((rational(v, "spectrum") for v in values), reverse=True)
    if sum(v.denominator.bit_length() for v in lam) > 65536:
        raise BudgetError(
            "conservative denominator-bit preflight exceeds 65536; this is not the size of the exact result"
        )
    if any(v < 0 for v in lam) or sum(lam) != 1:
        raise InputError(
            "spectrum must be nonnegative and exactly normalized; no automatic clipping or normalization"
        )
    eps = rational(epsilon, "epsilon")
    if not 0 <= eps <= 1:
        raise InputError("epsilon must lie in [0,1]")
    cap = Fraction(1, d)
    saturation = sum((max(Fraction(0), v - cap) for v in lam), Fraction(0))
    cumulative = Fraction(0)
    rank, mass = None, None
    for k, value in enumerate(lam, 1):
        cumulative += value
        candidate = (cumulative - eps) / k
        if candidate > cap:
            cap, rank, mass = candidate, k, cumulative
    info = log2_interval(d * cap)
    entropy = Interval.point(0)
    for value in lam:
        if value:
            entropy = entropy - Interval(value, value) * log2_interval(value)
    hmin = Interval.point(0) - log2_interval(lam[0])
    return SpectralInformation(
        d,
        eps,
        cap,
        saturation,
        info,
        (log2_interval(Fraction(d)) - entropy).positive_part(),
        (entropy - hmin).positive_part(),
        log2_interval(lam[0] / cap),
        rank,
        mass,
    )


def hoeffding_lower(hits: int, samples: int, delta: Scalar) -> Interval:
    n = require_int(samples, "samples", 1)
    h = require_int(hits, "hits", 0)
    if n > 10**12:
        raise BudgetError("sample count exceeds calculation budget")
    if h > n:
        raise InputError("hits cannot exceed samples")
    failure = rational(delta, "delta_stat")
    if not 0 < failure < 1:
        raise InputError("delta_stat must lie in (0,1)")
    variance_scale = ln_interval(1 / failure) / Interval.point(2 * n)
    radius = Interval(
        sqrt_interval(variance_scale.lower).lower,
        sqrt_interval(variance_scale.upper).upper,
    )
    return (Interval.point(Fraction(h, n)) - radius).positive_part()


def projection_information(
    occupancy_lower: Scalar, rank: int, dimension: int, smoothing_radius: Scalar
) -> Interval:
    d = require_int(dimension, "dimension", 1)
    k = require_int(rank, "rank", 1)
    if k > d:
        raise InputError("projector rank cannot exceed reference dimension")
    p = rational(occupancy_lower, "occupancy_lower")
    eps = rational(smoothing_radius, "smoothing_radius")
    if not (0 <= p <= 1 and 0 <= eps <= 1):
        raise InputError("occupancy and radius must lie in [0,1]")
    if p <= eps:
        return Interval.point(0)
    return log2_interval((p - eps) * d / k).positive_part()
