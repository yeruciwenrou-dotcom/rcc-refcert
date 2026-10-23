"""Prepare a full-space H.3 candidate for subsequent independent verification."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .bellman_choi import BellmanChoiCertificate
from .domination import minimum_domination_constant
from .fixed_point import linear_value_choi_envelopes
from .limits import (
    DEFAULT_LIMITS,
    ComputationLimits,
    ResourceLimitError,
    _resource_diagnostic,
    check_certificate_budget,
    check_matrix_budget,
    estimate_certificate_resources,
)
from .model import FiniteControlModel, ModelValidationError, require_valid_model
from .quantum import apply_choi_map
from .status import CheckOutcome


@dataclass(frozen=True)
class CandidatePreparation:
    """A candidate and preparation diagnostics, with no verification claim.

    ``status`` is one of ``candidate_ready``, ``invalid_model``,
    ``not_applicable``, ``inconclusive``, or ``resource_limit``. A ready
    certificate still requires ``verify_bellman_choi``. In particular its
    constant is a proposed value, not a verified numerical upper constant.
    Resource diagnostics above 256 bits use explicitly omitted decimal
    expansions; all admission comparisons still use the exact integers.
    """

    certificate: BellmanChoiCertificate | None
    status: str
    diagnostics: tuple[str, ...]
    resource_estimate: dict[str, int | str] = field(default_factory=dict)


def prepare_bellman_choi(
    model: FiniteControlModel,
    *,
    tol: float = 1e-10,
    limits: ComputationLimits = DEFAULT_LIMITS,
) -> CandidatePreparation:
    """Prepare the existing stable full-space linear H.3 candidate.

    Apply the constructed value maps to the initial state and obtain the
    proposed constant from that image and the declared reference. Independent
    verification supplies all error propagation and the accepted upper bound.
    The supplied tolerance is never increased. This helper does not construct
    candidates on general dark/recurrent subspaces or select an H.4 proof.
    """
    if not np.isfinite(tol) or tol <= 0:
        raise ValueError("tol must be finite and positive")
    estimate: dict[str, int | str] = {}
    try:
        empty = BellmanChoiCertificate({}, 0.0)
        planned = estimate_certificate_resources(model, empty)
        dimension = len(model.syntax_states) * sum(
            d * d for d in model.control_dims.values()
        )
        dense_elements = dimension * (dimension + model.output_dim**2)
        # The candidate adds one stored Choi family to the empty-proof estimate.
        certificate_elements = (
            planned["estimated_elements"] + planned["block_operator_elements"]
        )
        estimate = {
            "dense_matrix_elements": _resource_diagnostic(dense_elements),
            "certificate_matrix_elements": _resource_diagnostic(certificate_elements),
            "limit": _resource_diagnostic(limits.max_matrix_elements),
        }
        check_matrix_budget(model, limits)
        if certificate_elements > limits.max_matrix_elements:
            raise ResourceLimitError(
                "certificate_matrix_elements",
                certificate_elements,
                limits.max_matrix_elements,
            )
        require_valid_model(model, tol=tol)
    except ResourceLimitError as exc:
        return CandidatePreparation(None, "resource_limit", (str(exc),), estimate)
    except (ModelValidationError, TypeError, ValueError) as exc:
        return CandidatePreparation(None, "invalid_model", (str(exc),), estimate)

    try:
        envelopes = linear_value_choi_envelopes(model, tol=tol, limits=limits)
        image = np.zeros((model.output_dim, model.output_dim), dtype=complex)
        for control, initial in model.initial_blocks.items():
            image += apply_choi_map(
                envelopes[(model.start_syntax, control)],
                initial,
                input_dim=model.control_dims[control],
                output_dim=model.output_dim,
            )
        proposal = minimum_domination_constant(image, model.reference_state, tol=tol)
        if proposal.outcome is not CheckOutcome.PASS or proposal.constant is None:
            return CandidatePreparation(
                None,
                "inconclusive",
                ("candidate output scaling is unresolved: " + proposal.message,),
                estimate,
            )
        certificate = BellmanChoiCertificate(
            choi_envelopes=envelopes,
            constant=proposal.constant,
            name=f"{model.name}: linear H.3 candidate",
        )
        checked = check_certificate_budget(model, certificate, limits)
        estimate["certificate_matrix_elements"] = _resource_diagnostic(
            checked["estimated_elements"]
        )
    except ResourceLimitError as exc:
        return CandidatePreparation(None, "resource_limit", (str(exc),), estimate)
    except (np.linalg.LinAlgError, FloatingPointError, OverflowError) as exc:
        return CandidatePreparation(
            None,
            "inconclusive",
            ("linear candidate could not be resolved numerically: " + str(exc),),
            estimate,
        )
    except ValueError as exc:
        # The existing constructor expresses its full-space spectral gate using
        # this ValueError. Other numerical failures retain a distinct status.
        if "requires full transient spectral radius below one" in str(exc):
            return CandidatePreparation(
                None,
                "not_applicable",
                (
                    str(exc),
                    "a model-specific candidate may still be verified with H.3 or H.4",
                ),
                estimate,
            )
        return CandidatePreparation(None, "inconclusive", (str(exc),), estimate)
    return CandidatePreparation(
        certificate,
        "candidate_ready",
        (
            "constructed from the full-space linear value maps",
            "the proposed constant uses their initial image and the declared reference",
            "independent H.3 verification is required before using an upper constant",
        ),
        estimate,
    )
