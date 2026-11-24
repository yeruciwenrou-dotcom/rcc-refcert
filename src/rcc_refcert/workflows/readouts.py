"""Lossless conversion of native and Qiskit readouts to named RCC axes."""

from collections import Counter
from numbers import Integral

from ..bounds.contracts import keys, text
from ..bounds.scalar import InputError, require_int


def _positions(layout):
    keys(layout, {"registers", "axes"}, "readout layout")
    registers, axes = layout["registers"], layout["axes"]
    if not isinstance(registers, list) or not 1 <= len(registers) <= 32:
        raise InputError("declare the registers in displayed left-to-right order")
    names, displayed, widths = [], [], []
    for reg in registers:
        keys(reg, {"name", "bits_lsb_first"}, "classical register")
        names.append(text(reg["name"], "register name"))
        bits = reg["bits_lsb_first"]
        if not isinstance(bits, list) or not 1 <= len(bits) <= 64:
            raise InputError(
                "declare the measured wire at each classical bit, low bit first"
            )
        displayed.extend(text(x, "measured wire") for x in reversed(bits))
        widths.append(len(bits))
    if len(set(names)) != len(names) or len(set(displayed)) != len(displayed):
        raise InputError("register names and measured wire identities must be unique")
    if not isinstance(axes, list) or not axes or len(axes) > 64:
        raise InputError("declare one to 64 output axes in tensor order")
    for axis in axes:
        text(axis, "output axis")
    if len(set(axes)) != len(axes) or not set(axes) <= set(displayed):
        raise InputError("each output axis must identify one measured wire")
    return widths, [displayed.index(axis) for axis in axes]


def import_readout(data, layout):
    """Decode a histogram or paired per-shot strings, preserving the explicit layout."""
    widths, positions = _positions(layout)
    if isinstance(data, list):
        data = {"bitstrings": data}
    elif (
        isinstance(data, dict) and data and not ({"counts", "bitstrings"} & data.keys())
    ):
        data = {"counts": data}
    if not isinstance(data, dict) or set(data) not in ({"counts"}, {"bitstrings"}):
        raise InputError("supply counts or bitstrings from a single joint acquisition")
    if "bitstrings" in data:
        shots = data["bitstrings"]
        if (
            not isinstance(shots, list)
            or not shots
            or any(not isinstance(s, str) for s in shots)
        ):
            raise InputError("bitstrings must be a nonempty list of joint shot strings")
        raw = Counter(shots)
    else:
        raw = data["counts"]
    if not isinstance(raw, dict) or not raw:
        raise InputError("counts must be a nonempty joint histogram")
    bins = Counter()
    for label, count in raw.items():
        if not isinstance(label, str):
            raise InputError("expected a binary register string")
        blocks = label.split(" ")
        if list(map(len, blocks)) != widths or any(
            ch not in "01" for block in blocks for ch in block
        ):
            raise InputError(
                "outcome disagrees with declared register widths or binary alphabet"
            )
        bits = "".join(blocks)
        bins["".join(bits[i] for i in positions)] += require_int(count, "outcome count")
    return {
        "layout": layout,
        "counts": dict(sorted(bins.items())),
        "samples": sum(bins.values()),
    }


def qiskit_readout(pub_result, layout, *, loc=None):
    """Extract one parameter location of one SamplerPubResult, keeping joint shots paired."""
    _positions(layout)
    registers = [getattr(pub_result.data, r["name"]) for r in layout["registers"]]
    shape = tuple(registers[0].shape)
    for reg, spec in zip(registers, layout["registers"]):
        if reg.num_bits != len(spec["bits_lsb_first"]):
            raise InputError("the BitArray width disagrees with the declared register")
        if tuple(reg.shape) != shape:
            raise InputError("joint registers must have the same parameter shape")
    coordinates = () if loc is None else loc
    if not isinstance(coordinates, tuple):
        coordinates = (coordinates,)
    if len(coordinates) != len(shape) or any(
        isinstance(i, bool) or not isinstance(i, Integral) or not -n <= i < n
        for i, n in zip(coordinates, shape)
    ):
        raise InputError(
            f"choose one complete parameter location for shape {shape}, "
            "with one in-range integer per dimension"
        )
    # A scalar selects a position on a one-dimensional grid. Never pass a
    # partial index to the SDK, which can interpret another parameter as shots.
    indices = tuple(int(i) % n for i, n in zip(coordinates, shape))
    loc = indices[0] if len(indices) == 1 else indices or None
    if len(registers) == 1:
        data = {"counts": registers[0].get_counts(loc)}
    else:
        records = [reg.get_bitstrings(loc) for reg in registers]
        if len({len(s) for s in records}) != 1:
            raise InputError("registers in a joint acquisition need equal shot counts")
        data = {"counts": dict(Counter(" ".join(row) for row in zip(*records)))}
    selected = import_readout(data, layout)["samples"]
    if any(getattr(reg, "num_shots", selected) != selected for reg in registers):
        raise InputError("the selected location disagrees with the register shot count")
    return data
