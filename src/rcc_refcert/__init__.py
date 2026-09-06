"""Structure-fair analysis and reference certificates for quantum processes."""

from ._version import __version__
from .audit import (
    CaseAnalysis,
    DepthAgreement,
    ModelAnalysis,
    ReferenceSuite,
    audit_case,
    audit_model,
    audit_reference_suite,
)
from .bellman_choi import BellmanChoiCertificate, BellmanChoiReport, verify_bellman_choi
from .cases import CASES, CaseStudy, get_case
from .domination import DominationResult, minimum_domination_constant
from .fixed_point import linear_value_choi_envelopes
from .gain_cost import (
    ActionGainCost,
    GainCostReport,
    SyntaxGainCost,
    analyze_reference_gain_cost,
)
from .limits import ComputationLimits, ResourceLimitError
from .model import Action, FiniteControlModel, ModelValidationError, require_valid_model
from .reference_potential import (
    CertificateReport,
    ReferencePotentialCertificate,
    verify_reference_potential,
)
from .status import CheckOutcome, CheckResult, EvidenceLevel
from .weights import NumericalRangeError

__all__ = [
    "CASES",
    "Action",
    "ActionGainCost",
    "BellmanChoiCertificate",
    "BellmanChoiReport",
    "CaseAnalysis",
    "CaseStudy",
    "CertificateReport",
    "CheckOutcome",
    "CheckResult",
    "ComputationLimits",
    "DepthAgreement",
    "DominationResult",
    "EvidenceLevel",
    "FiniteControlModel",
    "GainCostReport",
    "ModelAnalysis",
    "ModelValidationError",
    "NumericalRangeError",
    "ReferencePotentialCertificate",
    "ReferenceSuite",
    "ResourceLimitError",
    "SyntaxGainCost",
    "__version__",
    "analyze_reference_gain_cost",
    "audit_case",
    "audit_model",
    "audit_reference_suite",
    "get_case",
    "linear_value_choi_envelopes",
    "minimum_domination_constant",
    "require_valid_model",
    "verify_bellman_choi",
    "verify_reference_potential",
]
