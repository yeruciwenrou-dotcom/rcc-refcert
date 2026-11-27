"""Installed, synthetic PVM acquisitions for the finite-window workflow."""

from .pvm import REQUEST, prepare_pvm_protocol


def pvm_template(name):
    from ..bounds.cli import load_template

    bell = name == "bell-ghz-counts"
    scale = 4 if bell else 8
    labels = ["Phi+", "Phi-", "Psi+", "Psi-"] if bell else ["0", "1", "2", "3"]
    measurement = {
        "id": "bell-pvm" if bell else "four-outcome-pvm",
        "setting": "Bell basis of the selected two qubits"
        if bell
        else "Rank-one projectors in a basis with squared overlaps (0.48,0.47,0.03,0.02) with pure-0",
        "ranks": dict.fromkeys(labels, 1),
        "readout": "ideal",
        "window_scope": "classical_blocks",
        "window": "Bell-basis blocks" if bell else "measurement blocks",
        "source": "Declared complete orthogonal basis of the four-dimensional ideal space",
    }
    cases = (
        [("Bell pair", [20000, 0, 0, 0]), ("GHZ reduced pair", [10000, 10000, 0, 0])]
        if bell
        else [("pure-0", [9600, 9400, 600, 400])]
    )
    request = {
        "schema": REQUEST,
        "schema_version": 1,
        "atomic_action_classes": scale,
        "batches": [],
        "tolerances": ["3/10"],
    }
    for state, counts in cases:
        event = state + " sampling"
        protocol = {
            "event_id": event,
            "dataset_id": state + " synthetic shots",
            "state_id": state,
            "reference_id": "uniform-C4",
            "dimension": 4,
            "reference_treatment": "uniform_on_support",
            "support": "no_leakage",
            "measurement": measurement,
            "samples": sum(counts),
            "delta": "1/200" if bell else "1/100",
            "sampling": "fixed_n_iid",
            "selection": "predeclared",
        }
        frozen = prepare_pvm_protocol(protocol)
        request["batches"].append(
            {
                "protocol": frozen["protocol"],
                "data": {
                    "protocol_sha256": frozen["protocol_sha256"],
                    "dataset_id": protocol["dataset_id"],
                    "origin": "synthetic_fixture",
                    "counts": dict(zip(labels, counts)),
                },
            }
        )
    if bell:
        request["comparisons"] = [
            [x["protocol"]["event_id"] for x in request["batches"]]
        ]
    else:
        request["models"] = {"pure-0": load_template("counts")["task"]["model"]}
    if name in ("product-counts", "retained-counts"):
        request.pop("models")
        request["atomic_action_classes"] = 4
        entry = request["batches"][0]
        protocol = entry["protocol"]
        protocol.update(
            state_id="correlated pair",
            event_id="joint Z sampling",
            dataset_id="joint Z shots",
        )
        measurement = protocol["measurement"]
        bits = ["00", "01", "10", "11"]
        measurement.update(
            id="Z tensor Z",
            setting="Computational basis readout of qubits A and B",
            window="computational blocks",
            ranks=dict.fromkeys(bits, 1),
        )
        measurement["product"] = {
            "axes": [{"label": axis, "ranks": {"0": 1, "1": 1}} for axis in ("A", "B")],
            "coordinates": {bit: list(bit) for bit in bits},
            "source": "Declared local computational projectors on A tensor B",
        }
        entry["data"].update(
            dataset_id=protocol["dataset_id"], counts={"00": 10000, "11": 10000}
        )
        if name == "retained-counts":
            protocol["samples"] = 25000
            protocol["support"] = "projected_branch"
            protocol["retention"] = {
                "state": "normalized_projected",
                "method": "hoeffding",
                "event_id": "retention sampling",
                "delta": "1/200",
                "source": "Ideal projective support flag followed by Z tensor Z on each accepted pair",
            }
            protocol["delta"] = "1/200"
            entry["data"]["discarded"] = 5000
        entry["data"]["protocol_sha256"] = prepare_pvm_protocol(protocol)[
            "protocol_sha256"
        ]
    return request
