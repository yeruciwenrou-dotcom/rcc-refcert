"""Exercise actual Qiskit V2 data containers and paired register shots."""

import json
from importlib.resources import files

import numpy as np
from qiskit.primitives import BitArray, DataBin, SamplerPubResult

from rcc_refcert.bounds import InputError, bound_from_counts, load_template
from rcc_refcert.workflows import import_readout, qiskit_readout


def main():
    data_dir = files("rcc_refcert.workflows").joinpath("data")
    vigo = json.loads(data_dir.joinpath("ibm_vigo_counts.json").read_bytes())["counts"]
    # Reconstruct a Qiskit histogram for q[i] measured into meas[i]. The archive prints Q0 first.
    native_counts = {outcome[::-1]: count for outcome, count in vigo.items()}
    pub = SamplerPubResult(
        DataBin(meas=BitArray.from_counts(native_counts, num_bits=5))
    )
    qubits = ["Q0", "Q1", "Q2", "Q3", "Q4"]
    layout = {"registers": [{"name": "meas", "bits_lsb_first": qubits}], "axes": qubits}
    assert import_readout(qiskit_readout(pub, layout), layout)["counts"] == vigo

    a = BitArray.from_samples(["01", "10", "01"], num_bits=2)
    b = BitArray.from_samples(["0", "1", "0"], num_bits=1)
    pub = SamplerPubResult(DataBin(a=a, b=b))
    layout = {
        "registers": [
            {"name": "b", "bits_lsb_first": ["qb"]},
            {"name": "a", "bits_lsb_first": ["q0", "q1"]},
        ],
        "axes": ["q0", "q1", "qb"],
    }
    assert import_readout(qiskit_readout(pub, layout), layout)["counts"] == {
        "100": 2,
        "011": 1,
    }
    one = {"registers": layout["registers"][1:], "axes": ["q0", "q1"]}
    assert import_readout(qiskit_readout(pub, one), one)["counts"] == {"10": 2, "01": 1}
    # Omitting the second coordinate used to produce a plausible but false
    # 1,000-shot histogram, changing the integer certificate from zero to one.
    shots = np.tile(np.array([1, 2, 3, 0], dtype=np.uint8), 250)
    grid = np.broadcast_to(shots, (1, 1000, 1000))[..., None]
    layout = {
        "registers": [{"name": "a", "bits_lsb_first": ["b0", "b1"]}],
        "axes": ["b1", "b0"],
    }
    pub = SamplerPubResult(DataBin(a=BitArray(grid, 2), shape=(1, 1000)))
    for loc in ((0, 0), (0, np.int64(999)), (-1, -1)):
        acquisition = import_readout(qiskit_readout(pub, layout, loc=loc), layout)
        assert acquisition["counts"] == dict.fromkeys(("00", "01", "10", "11"), 250)
        request = load_template("counts")
        assert request["protocol"]["samples"] == acquisition["samples"] == 1000
        request["data"]["hits"] = acquisition["counts"]["00"]
        assert bound_from_counts(request)["cost"]["integer_lower_bound_slots"] == 0
    for loc in (
        None,
        (),
        0,
        (0,),
        (0, 1000),
        (-2, 0),
        (0, 0, 0),
        (True, 2),
        (0, 1.0),
        (0, slice(None)),
    ):
        with np.testing.assert_raises(InputError):
            qiskit_readout(pub, layout, loc=loc)

    # Two settings with different cross-register correlations at the same margins.
    values = np.array([[[0], [1]], [[1], [0]]], dtype=np.uint8)
    a = BitArray(values, 1)
    b = BitArray(np.broadcast_to(values[:1], values.shape), 1)
    pub = SamplerPubResult(DataBin(a=a, b=b, shape=(2,)))
    layout = {
        "registers": [{"name": k, "bits_lsb_first": [k]} for k in ("a", "b")],
        "axes": ["a", "b"],
    }
    for loc, expected in ((0, {"00": 1, "11": 1}), ((-1,), {"10": 1, "01": 1})):
        assert (
            import_readout(qiskit_readout(pub, layout, loc=loc), layout)["counts"]
            == expected
        )
    a_grid = BitArray(values[None, ...], 1)
    b_grid = BitArray(np.broadcast_to(values[:1], values.shape)[None, ...], 1)
    pub = SamplerPubResult(DataBin(a=a_grid, b=b_grid, shape=(1, 2)))
    assert import_readout(qiskit_readout(pub, layout, loc=(0, 1)), layout)[
        "counts"
    ] == {"01": 1, "10": 1}
    with np.testing.assert_raises(InputError):
        qiskit_readout(pub, layout, loc=0)
    print(
        "Qiskit scalar, broadcast, paired-register and end-to-end certificate checks passed."
    )


if __name__ == "__main__":
    main()
