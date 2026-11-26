# Research with finite measurement data

Use graph-state measurements to bound the cost of preparing a six-qubit
cluster. In the cooling study, test whether a shorter program reaches the
full three-qubit target and use joint counts to track the effect of the last
bath refresh.

With an active installation, run the commands below with its Python. After the
[source quickstart](../README.md#install-from-source), run them from the
checkout root with `.venv/bin/python` on macOS or Linux, or
`.venv\Scripts\python.exe` on Windows. Use a fresh output name when saving a
second analysis.

## Six-qubit cluster state

After independent phase noise, which measurements rule out cheaper
preparations of the cluster state? Compare two alternating X/Z settings with
a computational-basis measurement at the same total shot count.

```sh
python -m rcc_refcert study template cluster --noise 1/20 --shots 10000 > cluster.json
python -m rcc_refcert study analyze cluster.json --csv cluster.csv --bundle cluster.rccbundle
python -m rcc_refcert bundle verify cluster.rccbundle
```

In each color setting, 8,574 of the 10,000 synthetic shots pass the stabilizer
test. Either setting certifies a preparation cost of **at least one slot**
in the cluster model. Combining both settings raises the lower bound to **two
slots**. The noisy graph state and the uniform reference have identical
computational-basis populations. More Z-basis shots can estimate those
populations more precisely, but the two states still look the same in that
basis. The alternating X/Z settings test the graph's stabilizer parities,
where the states differ. Repeat with ten shots per color to see which bounds
survive:

```sh
python -m rcc_refcert study template cluster --noise 1/20 --shots 10 > cluster-10.json
python -m rcc_refcert study analyze cluster-10.json --csv cluster-10.csv --bundle cluster-10.rccbundle
```

With edges 01, 12, 34, 45, 03, 14, 25, the stabilizers are
$K_i=X_i\prod_{j\sim i}Z_j$. Read X on sites 0, 2, 4 for A and on
sites 1, 3, 5 for B, reading Z on the other sites. An outcome passes if
each measured stabilizer has even parity. The color projectors commute.
Their product is the rank-one graph projector, so its occupation is at
least $\max(0,p_{A,L}+p_{B,L}-1)$. Both endpoints refer to the same prepared
state. Applying the paper's fixed-effect bound to this occupation and its
reference response $1/64$ gives at least 5.33856 one-shot bits at tolerance
0.05. The witness uses the same two statistical events as the color tests.
[Paper, IV.2–IV.4](https://arxiv.org/html/2509.18205v4)
· [Graph-state coloring measurements](https://arxiv.org/abs/1806.05565)

The two predeclared binary tests have 99% joint coverage by default.
The complete color histograms form a second 99% analysis from the same
counts, and the separate Z acquisition forms a third 99% analysis.
A simultaneous statement covering all three strategies has coverage at least
97% by the union bound, without assuming statistical independence. The
model predicts color and graph occupations of $(1-q)^3$ and $(1-q)^6$.
The templates round the predicted outcome frequencies to integer counts.

At noise `1/4`, each color still certifies at least one slot, while their
intersection no longer resolves a positive lower bound. The report credits
both colors. In JSON, `strongest_bounds.binary_colors` gives the strongest
binary witness at 99% joint coverage. `strongest_bounds.all_measurements`
includes the full histograms at 97%. The CSV lists the same witnesses and events.

### Cluster model

The declared input and reference are $I/64$. At each slot the controller
selects from twelve addressed resets to 0 or 1, six H gates, seven CZ gates
on the grid, six addressed phase-flip channels with declared probability
$q>0$, and one halt. Each costs one slot. The code uses five bits per slot
and stops at the first halt. The two reset directions together preserve twice
the reference. The other continuing actions are unital. Their code-weighted
sum sends the reference to $31\sigma/32$, and halt contributes
$\sigma/32$. Summing the stopping series gives exactly $\sigma$. The
transcription is exact with zero overhead and domination constant one.

Six resets, six H gates, seven CZ gates, six noise operations and halt
prepare the example target in 26 slots. The uniform reference on 64 states
limits the terminal-state information to six bits. At five bits per slot,
even perfect knowledge of the final state yields an integer lower bound of
at most two slots by this route. At the default noise and tolerance, the
two-color witness reaches that limit. The 26-slot construction supplies a
feasible upper bound on the same preparation cost. At zero noise the six
phase-flip operations coincide and the template uses only the five-bit
observation scale.

## Three-qubit algorithmic cooling

How much polarization does a further cycle buy, and is that cycle necessary
to prepare the specified full target? A refresh replaces both bath qubits.
Compression swaps 011 with 100. Halt returns the full register and costs one
slot. Observe the target qubit jointly with the bath immediately after the
last compression as well as after the final refresh.

```sh
python -m rcc_refcert study template cooling --bath 9/10 --cycles 3 > cooling.json
python -m rcc_refcert study analyze cooling.json --format json --output cooling-report.json --bundle cooling.rccbundle
python -m rcc_refcert bundle verify cooling.rccbundle
```

At trace-distance tolerance $1/50$, the eight-slot target program reaches
the target exactly. The shorter six-slot program reaches trace distance
$81/6250$ and the exact model rules out lower costs. The resulting model
interval is **[6, 6]**.

Why measure the bath as well as the target qubit? In the default model the
target's ground-state probability is exactly $3078/3125$ both just before
and just after the final refresh. The refresh replaces the bath and removes
its correlations with the target. The two full states are a trace distance
$4779/312500$ apart. A polarization measurement alone would give them the
same ideal reading.

The `finite_windows` record reports what the joint counts resolve about the
target, bath and their classical correlations. The `observed_polarizations`
intervals bound $2p(q_1=0)-1$. Each of three preparations
uses a separate joint histogram. A fourth acquisition observes the target
qubit with known binary readout errors; the example uses a 2% false positive
and 4% false negative probability for recording 0. An empty inverse image
is reported as a calibration conflict. These four experiments together have
99% coverage. See `analytic_control` for the full predicted populations.

The prospective sampling plan concerns a new **ideal** target-qubit readout.
It asks how many shots are needed to certify $p(q_1=0)>0.8$ at the requested
failure rate with at least 90% power, using the model forecast rounded down
to two decimal places. With the default bath and target, the forecast is 0.98.
Plan for 39 shots. Observing 0 on at least 37 of them certifies a ground-state
probability above 0.8 at 99% confidence.

Changing the bath changes the model. Changing the cycle count changes the
target. Within each task, all candidates share the full target and tolerance.
The study tests earlier cycle programs within the candidate budget. For
a twelve-cycle target at the same bath and tolerance, the two-cycle program
R–C–R–C–R–H ends about 0.0158 from the full target and attains the six-slot
lower bound.

The text report identifies the origin of each acquisition. Add `--details` to
show the dataset IDs and the digests binding each protocol to its readout.
In the CSV, `evidence_origin` identifies rows derived from counts and rows
calculated in the preparation model. Rows that use the generation tolerance
carry `generation_epsilon`.

If the cost search reaches its update limit, the report gives the interval
obtained so far. To continue the search, rerun `study analyze` on the same
input with `--max-dp-updates` set above the limit shown in that report.
Save the extended search under a new name such as `cooling-extended.rccbundle`. The first bundle retains the original interval and search budget.

## Your counts and Qiskit registers

For cluster measurements, keep the [cluster model](#cluster-model) when
its controls, reference and slot costs describe the preparation you want to
study. To report state-side information from the counts alone, set
`process_model` to `null`. The cooling study compares programs in the
declared refresh/compression model. To use different controls or cost units,
supply your model's reference and qualifications in the
[fixed-effect](TERMINAL_BOUNDS.md#target-and-reference-counts-for-the-same-effect)
or [measured-window workflow](COST_AND_WINDOWS.md#finite-sample-windows).
The [model guide](CUSTOM_MODELS.md) shows how to construct the model.

A request contains the raw counts, their origin, a source, and each
acquisition's protocol. Specify the fixed shot count and measurement before
sampling. Generate templates at other budgets with `--shots`. To change
wiring or dataset names, edit the protocol, keeping the expected measurement,
physical axes and prepared state, then freeze the bare object:

```sh
python -m rcc_refcert study prepare-protocol protocol.json > frozen.json
```

Use a common `preparation_id` and data origin for settings measured on the same physical preparation. Keep the returned digest with the dataset. Set `data.dataset_id` to the
protocol's ID, `data.origin` to `observed_counts` or `simulation`, and
`data.source` to the run and measurement record. Replace `data.outcomes`
with a count dictionary or list of joint shot strings (optionally wrapped in
`{"counts": {...}}` or `{"bitstrings": [...]}`) and preserve
`data.protocol_sha256`.

Register groups in a count string follow the **displayed left-to-right**
order in `layout.registers`. Within each register, `bits_lsb_first` lists
the wire measured into each classical bit starting at bit zero. Use
`axes` to choose the RCC output order or a marginal. Keep the laboratory
wire-to-classical-bit assignment with the source. With multiple registers,
pass joint keys such as `"10 1"` or the aligned records from the same shots.
Separately aggregated register counts lose their joint information.

```python
from rcc_refcert.workflows import (
    import_readout, prepare_study_protocol, qiskit_readout, study_template,
)

study = study_template("cluster")
entry = study["acquisitions"]["A"]
protocol = entry["protocol"]
# For a circuit that measures q[i] into meas[i], fix the assignment before acquisition.
protocol["layout"]["registers"][0]["bits_lsb_first"] = [f"q{i}" for i in range(6)]
protocol["dataset_id"] = "run-17/color-A"
frozen = prepare_study_protocol(protocol)

# pub_result is one SamplerPubResult from that acquisition.
raw = qiskit_readout(pub_result, protocol["layout"])
decoded = import_readout(raw, protocol["layout"])
entry["data"] = dict(dataset_id=protocol["dataset_id"], source="run-17/color-A",
                     origin="observed_counts", protocol_sha256=frozen["protocol_sha256"],
                     outcomes=raw)
# Supply the matching color-B and Z acquisitions from the same preparation.
```

Select one parameter point on every broadcast axis. For a two-dimensional grid pass `loc=(i, j)`. On a one-dimensional grid an integer is sufficient. All registers must describe the same grid and the same shots. For large JSON acquisitions, store the joint histogram in `data.outcomes.counts`, with one dictionary per setting and parameter point. This preserves shot correlations in a compact file. Plain JSON can be read directly.
[IBM bit ordering](https://quantum.cloud.ibm.com/docs/en/qiskit/bit-ordering)
· [IBM BitArray API](https://quantum.cloud.ibm.com/docs/en/api/qiskit/qiskit.primitives.BitArray)

### Check the mapping on a hardware file

From the source checkout, run:

```sh
python -m rcc_refcert study import-counts examples/readouts/sherbrooke_counts.json examples/readouts/sherbrooke_layout.json
```

These are 1,024 published shots from register `c_reg` on IBM Sherbrooke.
Displaying classical axes in order c0, c1, c2, c3 yields 524 ones on c0
and 291 on c3. Both bit orders preserve the shot total. This example
checks the archived register data and makes no assumption about its physical
preparation cost.
[Original hardware counts](https://github.com/TriumDesigns/emergent-spacetime-quantum-circuits/blob/68850e5e7ae94f1e90200b6e4d764eff8d33a932/Emergence-quantum-exp/exp-1-4-qubit-emergence/run_emergence_ibm%20%20raw%20result%20counts%20and%20data.txt)

## References

- **Graph-state measurements.** Huangjun Zhu and Masahito Hayashi,
  [Efficient Verification of Hypergraph States](https://doi.org/10.1103/PhysRevApplied.12.054047),
  *Physical Review Applied* **12**, 054047 (2019).
- **Asymptotic limits of heat-bath algorithmic cooling.** Sadegh Raeisi and Michele Mosca,
  [Asymptotic Bound for Heat-Bath Algorithmic Cooling](https://doi.org/10.1103/PhysRevLett.114.100404),
  *Physical Review Letters* **114**, 100404 (2015).
- **IBM Sherbrooke counts.** Ankitkumar Patel,
  [Emergent Spacetime Signatures from Minimal Quantum Circuits: Entanglement, Entropy, and Real-Hardware Evidence](https://github.com/TriumDesigns/emergent-spacetime-quantum-circuits/blob/68850e5e7ae94f1e90200b6e4d764eff8d33a932/Emergent%20spacetime%20signatures%20on%20IBM%20quantum%20computer.pdf)
  (2025). The 1,024 shots used to check register order come from the four-qubit experiment.
