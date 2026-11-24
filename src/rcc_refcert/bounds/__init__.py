"""Quantum circuit complexity bounds from terminal states and replayable records."""

from .._version import __version__
from .api import bound_from_counts, bound_from_spectrum, render_record, replay_record
from .binomial import clopper_pearson_lower, clopper_pearson_upper
from .certificates import with_reference_certificate
from .cli import load_template
from .contracts import Task, prepare_protocol
from .effects import binary_readout_preimage, prepare_effect_protocol
from .information import (
    fixed_effect_information,
    hoeffding_lower,
    hoeffding_upper,
    projection_information,
    spectral_information,
)
from .planning import plan_counts
from .records import validate_record
from .scalar import BudgetError, InputError, UnsupportedContract

__all__ = [
    "BudgetError",
    "InputError",
    "Task",
    "UnsupportedContract",
    "__version__",
    "binary_readout_preimage",
    "bound_from_counts",
    "bound_from_spectrum",
    "clopper_pearson_lower",
    "clopper_pearson_upper",
    "fixed_effect_information",
    "hoeffding_lower",
    "hoeffding_upper",
    "load_template",
    "plan_counts",
    "prepare_effect_protocol",
    "prepare_protocol",
    "projection_information",
    "render_record",
    "replay_record",
    "spectral_information",
    "validate_record",
    "with_reference_certificate",
]
