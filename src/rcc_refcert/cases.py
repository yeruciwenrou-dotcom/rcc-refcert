from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from .bellman_choi import BellmanChoiCertificate
from .examples import (
    make_dark_nonhalting_loop_model,
    make_dephase_bellman_choi_certificate,
    make_dephase_or_halt_model,
    make_dephase_reference_potential_certificates,
    make_multiblock_bellman_choi_certificate,
    make_multiblock_gain_cost_envelopes,
    make_multiblock_rectangular_model,
    make_multiblock_reference_potential_certificates,
    make_same_space_reference_envelopes,
)
from .model import BlockKey, FiniteControlModel
from .quantum import Array
from .reference_potential import ReferencePotentialCertificate
from .status import CheckOutcome

H1_REALIZATION = "h1_realization"
H2_LINEAR_FIXED_POINT = "h2_linear_fixed_point"
H34_DOMINATION = "h34_domination"
H3_BELLMAN_CHOI = "h3_bellman_choi"
H4_REFERENCE_POTENTIAL = "h4_reference_potential"
H6_GAIN_COST = "h6_gain_cost"

ModelFactory = Callable[[], FiniteControlModel]
BellmanFactory = Callable[[FiniteControlModel], BellmanChoiCertificate]
PotentialFactory = Callable[
    [FiniteControlModel], tuple[ReferencePotentialCertificate, ...]
]
EnvelopeFactory = Callable[[FiniteControlModel], dict[BlockKey, Array]]


class CaseKind(str, Enum):
    """Role of a bundled case in the reference suite."""

    DEMONSTRATION = "demonstration"
    DIAGNOSTIC = "diagnostic"
    BOUNDARY = "boundary"


@dataclass(frozen=True)
class CaseStudy:
    """One bundled model, its supplied proof objects, and expected outcomes."""

    name: str
    title: str
    purpose: str
    paper_references: tuple[str, ...]
    kind: CaseKind
    model_factory: ModelFactory
    expected_outcomes: tuple[tuple[str, CheckOutcome], ...]
    bellman_factory: BellmanFactory | None = None
    potential_factory: PotentialFactory | None = None
    envelope_factory: EnvelopeFactory | None = None
    interpretation: str | None = None

    def expected_outcome(self, check_name: str) -> CheckOutcome | None:
        return dict(self.expected_outcomes).get(check_name)


CASES: tuple[CaseStudy, ...] = (
    CaseStudy(
        name="dephase-or-halt",
        title="Dephase or halt",
        purpose=(
            "A transparent one-block model with a closed-form semidensity and "
            "tight reference certificates."
        ),
        paper_references=("H.1", "H.2", "H.3", "H.4", "H.6"),
        kind=CaseKind.DEMONSTRATION,
        model_factory=make_dephase_or_halt_model,
        bellman_factory=make_dephase_bellman_choi_certificate,
        potential_factory=make_dephase_reference_potential_certificates,
        envelope_factory=make_same_space_reference_envelopes,
        expected_outcomes=(
            (H1_REALIZATION, CheckOutcome.PASS),
            (H2_LINEAR_FIXED_POINT, CheckOutcome.PASS),
            (H34_DOMINATION, CheckOutcome.PASS),
            (H3_BELLMAN_CHOI, CheckOutcome.PASS),
            (H4_REFERENCE_POTENTIAL, CheckOutcome.PASS),
            (H6_GAIN_COST, CheckOutcome.PASS),
        ),
    ),
    CaseStudy(
        name="multiblock-rectangular",
        title="Multiblock rectangular process",
        purpose=(
            "Exercises direct-sum ordering, unequal block dimensions, rectangular "
            "Kraus maps, and nontrivial H.3–H.6 certificates."
        ),
        paper_references=("H.1", "H.2", "H.3", "H.4", "H.6"),
        kind=CaseKind.DIAGNOSTIC,
        model_factory=make_multiblock_rectangular_model,
        bellman_factory=make_multiblock_bellman_choi_certificate,
        potential_factory=make_multiblock_reference_potential_certificates,
        envelope_factory=make_multiblock_gain_cost_envelopes,
        expected_outcomes=(
            (H1_REALIZATION, CheckOutcome.PASS),
            (H2_LINEAR_FIXED_POINT, CheckOutcome.PASS),
            (H34_DOMINATION, CheckOutcome.PASS),
            (H3_BELLMAN_CHOI, CheckOutcome.PASS),
            (H4_REFERENCE_POTENTIAL, CheckOutcome.PASS),
            (H6_GAIN_COST, CheckOutcome.FAIL),
        ),
        interpretation=(
            "The original local codewords intentionally fail the sufficient "
            "condition in Eq. (H.70); Eq. (H.76) supplies a passing re-encoding."
        ),
    ),
    CaseStudy(
        name="dark-nonhalting",
        title="Dark nonhalting loop",
        purpose=(
            "Confirms that a valid nonhalting process keeps its least fixed-point "
            "meaning even when the linear inverse is unavailable."
        ),
        paper_references=("H.1", "H.2", "H.34"),
        kind=CaseKind.BOUNDARY,
        model_factory=make_dark_nonhalting_loop_model,
        expected_outcomes=(
            (H1_REALIZATION, CheckOutcome.PASS),
            (H2_LINEAR_FIXED_POINT, CheckOutcome.NOT_APPLICABLE),
            (H34_DOMINATION, CheckOutcome.INCONCLUSIVE),
        ),
        interpretation=(
            "The full transient spectral radius is one. The least fixed-point "
            "semantics remains valid, while the Neumann/linear-inverse route reaches "
            "its boundary. Eq. (H.34) therefore awaits the completed semidensity "
            "rather than using a finite truncation."
        ),
    ),
)


def get_case(name: str) -> CaseStudy:
    """Return a bundled case by its stable command-line name."""

    for case in CASES:
        if case.name == name:
            return case
    raise KeyError(name)


def case_names() -> tuple[str, ...]:
    return tuple(case.name for case in CASES)
