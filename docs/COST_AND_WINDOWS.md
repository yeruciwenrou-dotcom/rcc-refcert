# Preparation cost and state windows

The workflow API joins a complete target, a declared preparation model and
candidate programs in one reproducible task. A second entry analyzes subsystem
organization directly from state data. Both entries save complete inputs for
independent revalidation.

These commands belong to the 0.3 development series. Install this checkout in a
Python 3.10+ environment with `python -m pip install .`. The published 0.2.0
package provides the earlier model, certificate and terminal-bound workflows.

## A complete cost task

Run in a new directory with the environment where you installed this checkout:

```bash
python -m rcc_refcert cost template cyclic-reset > task.json
python -m rcc_refcert cost analyze task.json --bundle cost.rccbundle
python -m rcc_refcert bundle inspect cost.rccbundle
python -m rcc_refcert bundle verify cost.rccbundle --output verified.json
```

The default four-qubit reset model gives **[5,5] atomic slots**, including halt,
at trace-distance tolerance `1/10`. A verified reference-envelope certificate
excludes every smaller budget. The five-action candidate prepares the complete
target, so both endpoints refer to the same task.

The supplied four-action candidate misses this tolerance. Change `epsilon` to
`"9/20"` and it qualifies, giving **[4,4]**. At `"11/25"`, the result is
**[4,5]**: the supplied upper bound remains five and the exclusion reaches four.
A completed analysis can therefore report a failed candidate or an open gap.

Use exact integer, decimal-string or rational-string inputs. For example,
`"0.95"` and `"19/20"` denote the same exact reset probability; JSON `0.95`
does not declare that ideal parameter exactly. The preset accepts `qubits` and `p`;
try `qubits=3`, `p="9/10"`, `epsilon="1/10"` to obtain **[4,4]**.

To analyze several tolerances, set `epsilon_values` to
`["1/10", "9/20", "11/25"]`. The channel executions are reused, while each
point has its own request identity. Scan rows refer to the saved candidate
outputs and omit duplicate trajectory arrays.

```python
from rcc_refcert.workflows import (
    analyze_cost, compare_cost_results, load_workflow_template,
    render_workflow_result, save_workflow_bundle,
)

request = load_workflow_template("cyclic-reset")
result = analyze_cost(request)
print(render_workflow_result(result))
assert result["cost"]["interval_slots"] == [5, 5]
```

`result["effective_request"]` contains the full expanded recipe, target in its
original basis order, complete action words, costs, envelope and controls.
Export that object as JSON to edit the physical recipe directly. The recipe
supports `reset_product`, `basis_permutation`, `phase_z`, `classical_channel`
and identity `halt`. `classical_channel` uses a nonnegative column-stochastic
matrix and the declared measure-and-prepare quantum extension. Each action's
primitive composition is fixed before comparing costs.

An action costs one slot and halt costs one slot. The reference scale comes
from the declared physical action classes. Codeword length, reference gain and
this physical scale are recorded separately. Single-control-block exact
recipes are supported here; existing multiblock model APIs remain available.

## Cooling and the meaning of an open interval

```bash
python -m rcc_refcert cost template algorithmic-cooling > cooling.json
python -m rcc_refcert cost analyze cooling.json --format json --output cooling-result.json
```

The three-qubit model refreshes the two bath qubits at probability `9/10` and
compresses with the basis permutation exchanging `011` and `100`. The complete
target is produced by `R(CR)^3H`, with target-qubit probability `3078/3125`.
The supplied six-action word reaches tolerance `1/50`, giving **[6,6]**.
At tolerance `1/100`, the reported interval is **[6,8]**. The lower endpoint
comes from the verified gain relaxation; the eight-action witness supplies the
upper endpoint. The software preserves this distinction even when a separate
small-program enumeration can establish a sharper optimum.

The original information/transcription route stays available through
[`bound`](TERMINAL_BOUNDS.md) and the legacy certificate examples. Its fixed
constants and evidence are preserved. For example, the earlier cyclic-reset
example still returns two slots along that route. The gain-budget method does
not replace the physical scale by the logarithm of a local gain. H.70 checks
code-weighted sufficient inequalities; its failure does not invalidate an
independently verified unweighted gain certificate.

## Candidate comparisons

Save machine results with `--format json --output result.json`, then use:

```bash
python -m rcc_refcert cost compare result-a.json result-b.json
```

Candidates can be ranked as improvements only for a common full task and
tolerance. Models, target directions, support, tensor axes and costs are bound
to the task identity. Equal spectra alone do not identify equal targets.
Different tasks are displayed separately.

`U-L` bounds the best supplied candidate's additive overhead relative to the
optimum; `U/L` gives a multiplicative bound when `L>0`. A zero lower bound has
no multiplicative ratio. A missing upper bound is not a proof of
unreachability. `L>U` is an evidence conflict and produces no valid interval.
The comparison API accepts an explicit `criterion={"additive_gap": 1}` or
`criterion={"multiplicative_factor": "3/2"}`; it attaches the requested decision
to each eligible row. Comparisons read supplied result records; shared evidence
can be reverified using its complete bundle.

## State windows and probes

```bash
python -m rcc_refcert probe list
python -m rcc_refcert probe show w1-quantum-organization
python -m rcc_refcert probe export w1-quantum-organization > windows.json
python -m rcc_refcert window analyze windows.json --bundle windows.rccbundle
```

For a retained subsystem A, the uniform product reference gives
`deficit_bits = log2(d_A) - S(rho_A)` and
`rcc_main_term = deficit_bits / log2(Gamma)`. Both units and the source of Gamma
remain in the result. `keep` names the systems retained by a partial trace.
Tensor axes follow the input order, with the leftmost axis most significant.
An empty window has zero deficit; the full window gives the global quantity.

| Probe | Question and control |
|---|---|
| `w1-quantum-organization` | Paired Bell modules versus GHZ: identical pure spectra, different subsystem organization. At Gamma=4, windows 12/13/34 give (1,0,1) versus (1/2,1/2,1/2). Global fidelity can also distinguish these states. |
| `w2-noise-distribution` | Concentrated versus distributed phase noise: entropy 1 bit and global C=3/2 for both, but module values (1/2,1) versus (3/4,3/4). The cross window is a null control. The distributed probability is solved numerically, with its root residual retained. |
| `w3-cooling-trajectory` | One exact cooling trajectory: refresh removes bath entropy and correlation; reversible compression redistributes them. Gamma=3 comes from the model, so g=log2(3). The diagonal correlations are classical. |

Exported requests are complete editable inputs. `export_probe(...,
parameters={...})` regenerates a parameterized instance and its identity; use
`mixing` or `gamma` for W1, `concentrated_probability` or `gamma` for W2, and
`p` or `cycles` for W3. The instance digest identifies the declared probe
parameters; the separate request digest identifies the actual edited inputs.

For W3, send the exported request to **`cost analyze`**. Its window profiles use
the states already produced by each candidate, including step, action and
cumulative cost. Set `windows.steps` to a list of step numbers to retain a
selection. Halt advances charged cost but leaves the state unchanged.

A declared bipartition A|B reports
`C_global = C_A + C_B + I(A:B)/g` and a numerical decomposition residual.
For mixed states, I is total correlation. Overlapping windows do not sum to
the global quantity. Global entropy and window entropy provide different
information; known full spectra do not automatically acquire a stronger
global Dmax bound through windowing.

## Your own matrix and tensor labels

```python
from rcc_refcert.workflows import StateInput, analyze_windows, load_workflow_template

state = StateInput.numeric(
    [[0.8, 0.0], [0.0, 0.2]], (2,), ("spin",),
    policy={"mode": "roundoff_only", "tolerance": 1e-10, "repair_budget": 1e-10},
)
request = load_workflow_template("window-state")
request["states"] = [{"id": "measured-model-state", "state": state.as_dict()}]
request["windows"] = [{"id": "spin", "keep": ["spin"]}]
result = analyze_windows(request)
```

Supply full density matrices, explicit dimensions, physical labels and support.
JSON complex entries are `[real, imaginary]`. Direct Python input accepts
complex NumPy matrices. Probability sorting is confined to a derived spectral
calculation; it never changes the complete target's basis positions.

Qiskit qubit 0 is the least significant axis. For a qubit density matrix `dm`,
keep its array and name axes from highest qubit index to zero:

```python
state = StateInput.numeric(dm.data, (2,) * n,
                           tuple(f"q{i}" for i in reversed(range(n))))
```

For a QuTiP density operator `rho`, preserve tensor order:

```python
state = StateInput.numeric(rho.full(), tuple(rho.dims[0]), tuple(labels))
```

Check imported axes with an asymmetric product state before interpreting a
window. These are array conversion recipes; neither library is required.
See the official [Qiskit bit-order guide](https://quantum.cloud.ibm.com/docs/en/qiskit/bit-ordering)
and [QuTiP quantum-object documentation](https://qutip.readthedocs.io/en/stable/apidoc/quantumobject.html).

Numerical input defaults to no repair. An unresolved Hermiticity, trace or PSD
residual returns `numerical_unresolved`. Explicit `roundoff_only` allows small
corrections within both the check tolerance and repair budget. Results retain
the original input, derived state and perturbation. Entropies use binary64
logarithms, including for exact probabilities; they are numerical quantities.

## Numerical candidate migration

`serialize_numeric_model(model, subsystem_dims=..., subsystem_labels=...,
reference=..., cost=...)` exports an existing `FiniteControlModel` as data-only
complex matrices. Use that document in a `mode="numerical"` cost request with
a complete target and candidate words. The reference and cost fields have the
same form as an expanded exact recipe. Model validation uses its saved
`validation_tolerance`.

Numerical candidate execution uses the existing unweighted physical channel
semantics. The actual trace distance is computed against the original target;
roundoff-derived targets remain separate diagnostic objects. Results near the
requested tolerance are unresolved within the declared comparison tolerance.
Such results do not produce a strict feasible upper bound, including at zero
tolerance. Numerical tolerance comparisons use separately identified requests.
Numerical multiblock outputs are supported; intermediate window
trajectories require one compatible control-block layout.

## Reports, limits and revalidation

Text, JSON and Markdown present the same stored result. Text wraps at 80
columns by default; `--width 120` changes presentation only. Optional graphics
and CSV come from saved window quantities:

```bash
python -m pip install ".[plots]"
python -m rcc_refcert window analyze windows.json --csv profile.csv --plot profile.svg
python -m rcc_refcert window analyze windows.json --format markdown --output report.md
```

Install `.[plots]` from this checkout; ordinary analysis only needs NumPy.
Plotting supports SVG, PNG and PDF and is limited to 128 displayed rows.
Missing optional plotting dependencies preserve the computed scientific result
and mark the presentation step partial. Output files are exclusive by default;
`--overwrite` explicitly selects atomic replacement. Inputs and output paths
must remain distinct.

| Budget | Default |
|---|---:|
| DP cells / updates | 100,000 / 1,000,000 |
| Rational numerator or denominator bits | 65,536 |
| Total candidate actions | 10,000 |
| Saved trajectory states / window evaluations | 256 / 256 |
| Matrix or vector working elements | 1,048,576 |

Checks precede dense allocations and optional trajectory storage. These are
work bounds, not runtime guarantees. Exact DP uses syntax states and budgets,
without enumerating programs. A completed budget prefix remains a valid lower
bound if arithmetic or update limits stop further exclusion. Optional window
limits preserve already established cost endpoints. Execution state and
scientific decision are separate fields.

New CLI analysis exits: 0 completed, 1 partial, 2 invalid or unsupported input,
3 preflight resource limit, 130 interrupted. A fresh run identifier accompanies
each result or failure. A failed candidate alone does not mean failed execution.

Workflow bundles use container schema 2. `inspect` checks archive integrity,
object bindings and stored-result consistency; it does not rerun the physical
model. `verify` rebuilds the recipe, checks evidence, executes candidates and
recalculates windows from the saved effective inputs. It preserves author
history and writes a separate recipient result. Numerical semantic comparison
uses a 1e-10 relative/absolute scale; exact rational strings remain exact.
Bitwise same-version replay is reported separately. Different producer versions
can still have matching newly computed scientific results.

Schema-1 model/certificate/spectrum/counts bundles from 0.2.0 retain their
existing validation path. A 0.2 reader rejects schema 2; recipients need the
new workflow version. A changed numerical policy constitutes a new task,
so workflow verification uses the saved policy. See
[bundle semantics](ANALYSIS_BUNDLES.md) for the original evidence contracts.
