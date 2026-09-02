from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np


class CheckOutcome(str, Enum):
    """Observed result of one check."""

    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"
    NOT_APPLICABLE = "not_applicable"


class EvidenceLevel(str, Enum):
    """Kind of evidence supporting a check outcome."""

    NUMERICAL = "numerical"


@dataclass(frozen=True)
class CheckResult:
    """One named condition with its observed outcome and evidence level."""

    name: str
    outcome: CheckOutcome
    message: str
    value: float | None = None
    tolerance: float | None = None
    residual: np.ndarray | None = field(default=None, repr=False, compare=False)
    evidence: EvidenceLevel = EvidenceLevel.NUMERICAL
