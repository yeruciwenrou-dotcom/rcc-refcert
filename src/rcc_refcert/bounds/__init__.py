"""Conditional terminal-state cost bounds and replayable records."""

from .._version import __version__
from .api import bound_from_counts, bound_from_spectrum, render_record, replay_record
from .certificates import with_reference_certificate
from .cli import load_template
from .contracts import Task, prepare_protocol
from .information import hoeffding_lower, projection_information, spectral_information
from .records import validate_record
from .scalar import BudgetError, InputError, UnsupportedContract

__all__ = [
    "BudgetError",
    "InputError",
    "Task",
    "UnsupportedContract",
    "__version__",
    "bound_from_counts",
    "bound_from_spectrum",
    "hoeffding_lower",
    "load_template",
    "prepare_protocol",
    "projection_information",
    "render_record",
    "replay_record",
    "spectral_information",
    "validate_record",
    "with_reference_certificate",
]
