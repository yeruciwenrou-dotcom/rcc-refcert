<a id="preparation-cost-and-state-windows"></a>
<a id="preparation-costs-and-quantum-state-structure"></a>

# Preparation costs and complexity profiles

How much does a preparation cost in a specified model, and how does complexity
vary across its subsystems? The cost workflow bounds the optimum and checks
candidate programs against a complete target. The window workflow computes
subsystem RCC complexity profiles in pure and mixed states using a common
reference and control bandwidth. Entropy deficits and correlations supply the
information for these calibrated readings. You can analyze states directly or follow a
preparation step by step, and share either calculation for independent revalidation.

| Your question | Start here |
|---|---|
| Does a candidate reach my target, and how close is its cost to optimal? | [A complete cost task](#a-complete-cost-task) |
| How does changing the tolerance affect the result? | [Cost tasks](#a-complete-cost-task) and [candidate comparisons](#candidate-comparisons) |
| How do complexity profiles differ across subsystems or between states? | [Subsystem complexity profiles](#subsystem-complexity-profiles) |
| Can my counts resolve an RCC difference between two states in the same classical measurement window? | [Finite-sample windows](#finite-sample-windows) |
| How do I analyze my own state or model? | [Matrix inputs](#your-own-matrix-and-tensor-labels) and [numerical models](#numerical-models-and-candidate-diagnostics) |
| How do I save, share and verify the calculation? | [Reports and revalidation](#reports-limits-and-revalidation) |

Use **rcc-refcert 0.4.0 or later** with Python 3.10 or later to run all the
examples. Version 0.3.0 supports preparation costs and windows of known
states. Measured histograms and the `on_gain_failure` option require 0.4.0.
Install from
[PyPI](../README.md#install-from-pypi) or follow the
[source quickstart](../README.md#install-from-source), then activate that environment
or substitute its Python path in the commands below.

## A complete cost task

There are two routes through the four-qubit cyclic-reset example. The
[finite-control calculation](CUSTOM_MODELS.md#cyclic-noisy-reset-register)
verifies a reference-domination constant, then uses the final state to exclude
every program below two slots. The diagonal cost workflow below also bounds
the gain of the available actions and checks a five-slot program. Its lower
and upper endpoints meet at **[5, 5]** for the same complete target.

Run in a new directory with the environment where you installed the package:

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

The exact cost recipes start with a diagonal state and preserve diagonality.
They evaluate complete targets in their original basis. General matrix models
use the [numerical candidate workflow](#numerical-models-and-candidate-diagnostics);
the existing model and reference-certificate APIs also cover quantum CP maps.

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

In these recipes, each action costs one slot, including halt. The reference scale comes
from the declared physical action classes. Codeword length, reference gain and
this physical scale are recorded separately. Single-control-block exact
recipes are supported here; existing multiblock model APIs remain available.

You can combine independently established integer endpoints with the public
Python API. This example uses both endpoints of the cyclic-reset calculation.

```python
from rcc_refcert.workflows import analyze_cost, compose_interval, load_workflow_template

run = analyze_cost(load_workflow_template("cyclic-reset"))
core = run["digests"]["task_core"]
cost = run["cost"]
interval = compose_interval(cost["lower_bound_slots"], cost["upper_bound_slots"],
                            core_digest=core, lower_core=core, upper_core=core,
                            epsilon=cost["epsilon_exact"])
print(interval["interval_slots"])  # [5, 5]
```

For independently obtained evidence, pass each endpoint's actual task digest.
The model, initial state, complete target, metric and charging rules must
match. The upper endpoint needs a program verified to reach that target.
Supply `epsilon_upper <= epsilon <= epsilon_lower` when tolerances differ.
A lower endpoint obtained from counts retains its original sampling coverage.
The function composes supplied endpoints. External circuits need their own
feasibility and cost check.

### Build a half-erasure channel

The [complete one-qubit request](../examples/half_erasure.json) starts with a
uniform spin and targets the Z-basis populations (15/16, 1/16). Each column
of the channel matrix gives the output probabilities for one input, in the
order 0, 1. Its columns (1, 0) and (1/2, 1/2) leave 0 unchanged and halve the
excited population. Each application costs one atomic slot. Returning the
spin with `halt` costs one more.

```bash
.venv/bin/python -m rcc_refcert cost analyze examples/half_erasure.json --details
```

After one, two and three channel applications the excited populations are
1/4, 1/8 and 1/16. At tolerance 1/10 the two-application program reaches the
target and closes the interval at [3,3] slots. Remove that candidate from a
copy of the JSON and the supplied programs give [3,4]. Keep all candidates
and tighten `epsilon` to `"1/20"`: the interval is again [3,4]. Here the
reachable populations give an independent check. Four slots are necessary
at the tighter tolerance, while the computed lower bound is three.

## Cooling and the remaining optimality gap

```bash
python -m rcc_refcert cost template algorithmic-cooling > cooling.json
python -m rcc_refcert cost analyze cooling.json --format json --output cooling-result.json
```

Each refresh replaces both bath qubits with independent states whose
ground-state probability is `9/10`. Compression exchanges the basis states
`011` and `100`. The complete
target is produced by `R(CR)^3H`, with target-qubit probability `3078/3125`.
Here, R denotes bath refresh, C reversible compression, and H halt.

At tolerance `1/50`, the gain bound excludes costs below six and the supplied
six-action word reaches the target, giving **[6,6]**.
At tolerance `1/100`, the reported interval is **[6,8]**. The lower endpoint
comes from the verified gain relaxation; the eight-action witness supplies the
upper endpoint. The software preserves this distinction even when a separate
small-program enumeration can establish a sharper optimum.

The information/transcription route is available through
[`bound`](TERMINAL_BOUNDS.md) and the certificate examples. For example, the cyclic-reset
example still returns two slots along that route. The gain-budget method does
not replace the physical scale by the logarithm of a local gain. The
code-weighted gain–cost test (H.70) checks a sufficient local condition; its
failure does not invalidate an independently verified unweighted gain
certificate.

For an exact-cost request, omit `gain_certificate` or set it to `"auto"` to
verify the preset certificate (or a reference envelope for a custom model).
To test your own certificate, supply an object with an `envelopes` entry.
An empty object or a failed inequality returns a diagnostic for that input.
With 0.4.0 or later, set `"on_gain_failure": "auto"` to also try the automatic certificate.
The result retains the original diagnostic and names the verified certificate
that supports the lower bound in `gain_selection`.

To reuse a verified certificate with the same model, copy its input from the
effective request. The top-level `result["gain_certificate"]` also contains the
verification checks for the audit record.

```python
request["gain_certificate"] = result["effective_request"]["gain_certificate"]
```

## Candidate comparisons

Save machine results with `--format json --output result.json`, then use:

```bash
python -m rcc_refcert cost compare result-a.json result-b.json
```

Candidates can be ranked as improvements only for a common full task and
tolerance. Models, target directions, support, tensor axes and costs are bound
to the task identity. Equal spectra alone do not identify equal targets.
Different tasks are displayed separately.

For a reported interval `[L,U]`, L is the lower bound and U is the cost of the
best supplied feasible candidate. `U-L` bounds that candidate's additive
overhead relative to the optimum; `U/L` gives a multiplicative bound when `L>0`.
The multiplicative ratio requires a positive lower bound. A feasible program
supplies an upper bound. Crossed endpoints (`L>U`) signal conflicting evidence.

Use `cost compare --additive-gap 0` to test optimality, or supply
`criterion={"additive_gap": 0}` to the Python API. A closed interval such as
`[5,5]` certifies the optimum. With `[4,5]`, a five-slot program's optimality
remains unresolved. `criterion_status` records `certified` or `unresolved`,
and `meets_criterion` is respectively `true` or `null`. Positive additive
gaps and multiplicative factors use the same evidence rule. Shared results
can be reverified from their complete bundles.

<a id="state-windows-and-probes"></a>
<a id="subsystem-entropy-and-correlations"></a>

## Subsystem complexity profiles

A **subsystem window** selects the part of a quantum state to examine. In
this implementation, it retains a chosen set of tensor factors and traces out
the rest. The workflow evaluates the reduced state's RCC complexity using
the same reference and resource scale as the full state. For the uniform
product reference,

$$
C_{R,A}=\frac{\log_2 d_A-S(\rho_A)}{g_R},\qquad g_R=\log_2\Gamma_R.
$$

The entropy deficit supplies the information numerator; the control bandwidth
converts it to a complexity reading in R-structons, with
$1\thinspace\mathrm{st}_R = g_R$ bits. Keeping the reference and bandwidth fixed makes
these readings comparable across subsystems and preparation steps. Bipartitions
also separate local and correlation contributions to this state-side complexity.
The [scientific scope](SCIENTIFIC_SCOPE.md#from-state-information-to-process-cost)
connects these subsystem reductions to RCC's reference-compatible windows.

Start with a probe whose question matches the complexity profile you want to study.
Each installed probe pairs a physical question with explicit states or a
preparation, selected windows and comparison controls. Export its request to
inspect the assumptions, change parameters or use the same windows on your
own data.

```bash
python -m rcc_refcert probe list
python -m rcc_refcert probe show w1-quantum-organization
python -m rcc_refcert probe export w1-quantum-organization > windows.json
python -m rcc_refcert window analyze windows.json --bundle windows.rccbundle
```

`probe show` displays the question, parameters, expected default results and
comparison controls. Use `probe show ID --format json` for the complete probe
record, or `probe export ID` for its executable request.

For a retained subsystem A, the uniform product reference gives
`deficit_bits = log2(d_A) - S(rho_A)` and
`rcc_main_term = deficit_bits / log2(Gamma)`, in `st_R`. Both units and the source of Gamma
remain in the result. `keep` names the systems retained by a partial trace.
Tensor axes follow the input order, with the leftmost axis most significant.
An empty window has zero deficit; the full window gives the global quantity.

`entropy_bits` is the entropy of the reduced state `rho_A`. The corresponding
reference-preserving effective state on the full space is
`rho_A ⊗ I_B/d_B`, whose entropy is `S(rho_A) + log2(d_B)`. Its full-space
entropy deficit equals the reported subsystem deficit.

### Choose a probe

| Probe | Physical question | What to inspect |
|---|---|---|
| W1 · Quantum organization | How do paired Bell modules and a GHZ state differ in subsystem complexity at the same global RCC value? | At Gamma=4, windows 12/13/34 give (1,0,1) versus (1/2,1/2,1/2) st_R. |
| W2 · Noise distribution | How does phase-noise distribution change subsystem complexity at a fixed global RCC value? | Both states have entropy 1 bit and global C=3/2 st_R; module values are (1/2,1) versus (3/4,3/4) st_R, with the cross window as a null control. |
| W3 · Cooling trajectory | How do bath refresh and reversible compression change local and correlation contributions to complexity? | Follow target and bath RCC values and the scaled correlation along the same candidate; Gamma=3 comes from its model. |

Use `probe list` to see their command IDs: `w1-quantum-organization`,
`w2-noise-distribution` and `w3-cooling-trajectory`, respectively.

The values in the table use the default parameters, with Gamma=4 for W1 and
W2. That Gamma is a declared comparison scale; W3 derives Gamma=3 from its
physical action classes. W1's common mixing parameter preserves the equality
of the two global spectra while changing their purity. Recompute the values
after changing parameters.

The W2 distributed-noise probability is solved numerically, and its root
residual is saved with the result. Its two states have matched entropy but
different spectra, so their one-shot information can differ too. All window
entropy values are numerical.

Exported requests are complete editable inputs. `export_probe(...,
parameters={...})` regenerates a parameterized instance and its identity; use
`mixing` or `gamma` for W1, `concentrated_probability` or `gamma` for W2, and
`p` or `cycles` for W3. The instance digest identifies the declared probe
parameters; the separate request digest identifies the actual edited inputs.

### Follow a preparation trajectory

W3 is a preparation task, so send its request to **`cost analyze`**:

```bash
python -m rcc_refcert probe export w3-cooling-trajectory > trajectory.json
python -m rcc_refcert cost analyze trajectory.json --details --bundle trajectory.rccbundle --csv trajectory.csv --plot trajectory.svg
```

The CSV and figure show the global reading, subsystem readings and the partition correlation for each program step. Figures require the `plots` extra. The Python entry point is `rcc_refcert.workflows.export_window_files`.

Its window profiles use the states produced by each candidate, with the step,
action and cumulative cost recorded together. Set `windows.steps` to a list
of step numbers to retain a selection. Halt advances charged cost and leaves
the state unchanged.

With the Python API, read the same stored trajectory directly:

```python
from rcc_refcert.workflows import analyze_cost, export_probe, render_workflow_result

cooling = analyze_cost(export_probe("w3-cooling-trajectory"))
print(render_workflow_result(cooling["windows"]))
```

The eight-action program defines the full target. The six-action candidate
reaches it within the default tolerance and attains the model's lower bound.
To see what a paid operation does, compare the first refresh with the
compression that follows it. Compression permutes the eight populations,
so the global entropy and global RCC stay fixed. The target qubit becomes
more polarized and the target and bath become correlated. The operation
costs one slot even though the change in global RCC is zero. The next
refresh replaces the bath and removes those correlations.

Changing `p` changes the bath model, and changing `cycles` changes the
target construction. Keep the model, target and tolerance fixed when
comparing candidate costs.

### Read local and correlation contributions

A declared bipartition A|B reports
`C_global = C_A + C_B + I(A:B)/g` and a numerical decomposition residual.
All three contributions are in `st_R`: `I(A:B)` is in bits, and division by
the same control bandwidth gives its contribution to complexity. For mixed
states, I is total correlation; for a pure bipartite state, it equals twice
the reduced-state entropy. This identity separates the local and correlation
contributions to state-side RCC complexity.
A full finite-accuracy preparation-cost bound additionally uses the model
inputs and one-shot corrections described in the
[scientific scope](SCIENTIFIC_SCOPE.md#from-state-information-to-process-cost).
Overlapping windows do not sum to the global quantity. Windows distinguish
subsystem complexity profiles even when global spectra coincide; a known full
spectrum already fixes its global Dmax bound.

## Finite-sample windows

A prespecified binary event or a small set of coarse outcome bins can be
analyzed directly from counts, without reconstructing a density matrix. A
complete computational-basis measurement on $n$ qubits can have $2^n$
outcomes. This PVM interface supports up to 256 declared outcomes. The sample
size needed to resolve a rare event and the resources needed to qualify a
preparation model are separate costs. The Python interface is
`rcc_refcert.workflows.analyze_pvm_windows`.

From a complete histogram of an ideal projective measurement, you can bound
RCC in the measured classical window. Measure two states in that same window
to bound their RCC difference in R-structons. The calculation uses the block
ranks, the uniform reference on the declared support and the control bandwidth
`g_R = log2(atomic_action_classes)`. You can study a window without giving
a preparation model. These installed examples use synthetic counts.

| Template | Question answered |
|---|---|
| `bell-ghz-counts` | Can one Bell-basis measurement distinguish the window RCC of a Bell pair and the reduced pair of a GHZ state? |
| `pvm-counts` | Which group of outcomes certifies the strongest one-shot information floor at the requested tolerance, and what preparation budget does it exclude? |
| `product-counts` | How much of the joint computational-basis reading comes from the two marginals and how much from correlations? |
| `retained-counts` | What window information survives a projection, and how much remains after weighting by the probability of retention? |

```bash
python -m rcc_refcert window template bell-ghz-counts > pair.json
python -m rcc_refcert window analyze pair.json --csv pair.csv --bundle pair.rccbundle
python -m rcc_refcert bundle verify pair.rccbundle
```

Each state contributes 20,000 shots. The Bell pair puts all of them in
$\Phi^+$, and the GHZ reduced pair splits evenly between $\Phi^+$ and
$\Phi^-$. The Bell lower endpoint exceeds the GHZ upper endpoint by at least
0.37086784 R-structons at 99% joint coverage. This compares the two states
on the **same Bell-basis classical window**. With `window_scope` set to
`containing_quantum`, the measurement supplies a lower bound for the larger
window. Its upper endpoint and the corresponding ordering remain open.

For your own experiment, replace the acquisition fields in a template. Before
sampling, save the bare object at `batches[0].protocol` to `protocol.json`
and run:

```bash
python -m rcc_refcert window prepare-protocol protocol.json > frozen.json
```

The [installed request schema](../src/rcc_refcert/workflows/data/pvm_request.schema.json) describes the fields. Keep the returned protocol and SHA-256 digest with the dataset. Specify the
state, reference, setting and projector source, every outcome and its positive
rank, the fixed IID trial count, and the failure budget. For observed data set
`data.origin` to `observed_counts`, copy the dataset identity and protocol
digest, and supply integer counts for the declared outcomes. Missing histogram
entries count as zero once the total reconciles with the fixed trial count.
The declared ranks must sum to the reference dimension. The experiment
supplies the evidence for the physical readout, support and reference.

Every tolerance and deterministic regrouping of one acquisition uses the same
coverage event. Add `coarse_windows` to an entry to map **each** outcome of
its parent measurement to a group. To obtain local windows, declare the two
product axes, their block ranks and the joint outcome-to-coordinate map as in
`product-counts`. For outcomes $X$ and $Y$ on the two subsystems, the
correlation interval bounds their contribution $I(X:Y)/g_R$ to the measured
window's RCC, in R-structons. Its lower endpoint also gives a lower bound on
the quantum mutual-information contribution of those subsystems on the same scale.

The `pvm-counts` example has counts (9600, 9400, 600, 400). At trace-distance
tolerance 0.3, pooling outcomes 0 and 1 gives at least **0.34832863 one-shot
bits** at 99% coverage. The supplied eight-action model converts this to at
least one integer slot. Supply model qualifications for the target state to
obtain a cost. Different settings may strengthen the same task by taking the
largest valid floor. The request reports each task and its tolerance separately.

For a projected branch, include all discarded trials. The retained outcomes
estimate the normalized projected state's window, using the retained sample
size. A separate one-sided retention endpoint (Hoeffding or Clopper–Pearson)
or a supplied known retention probability weights the state-side lower bound.
Zero retained observations leave the conditional window undetermined. A known
zero retention probability gives an exactly zero weighted contribution.
The parent preparation's unconditional process cost needs additional evidence.
See the [paper-to-code derivation](PAPER_MAP.md#finite-histogram-calculation)
and [bundle verification](ANALYSIS_BUNDLES.md#complete-projective-readouts).

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

## Numerical models and candidate diagnostics

The complete [numerical cost example](../examples/numerical_cost_workflow.py)
adapts the two-action model from the [model guide](MODEL_GUIDE.md#a-complete-two-action-model).
Run it from the checkout with your installed environment:

```bash
python examples/numerical_cost_workflow.py --bundle numerical-cost.rccbundle
python -m rcc_refcert bundle verify numerical-cost.rccbundle
```

Its `make_request()` function constructs the model, exports its matrices,
declares the reference and atomic costs, supplies the complete target and
provides two candidate words. Both candidates leave the supplied `I/2` state
unchanged. Their trace distance from `diag(0.6, 0.4)` is numerically 0.1, within
the declared tolerance `1/5`; their costs are one and two slots, including halt.
The result is `numerical_analysis`, with numerical candidate evidence and empty
rigorous cost endpoints. The saved bundle is independently reverified.

Use this request as a starting point for your own channels, initial state,
target, action words and resource declarations. The source keeps each part
explicit so the full task can be checked and shared.

`serialize_numeric_model(model, subsystem_dims=..., subsystem_labels=...,
reference=..., cost=...)` exports an existing `FiniteControlModel` as data-only
complex matrices. Use that document in a `mode="numerical"` cost request with
a complete target and candidate words. The reference and cost fields have the
same form as an expanded exact recipe. Model validation uses its saved
`validation_tolerance`.

Numeric-model schema 2 names each continuation edge by its physical `source`
and `destination`. Its Kraus matrices have destination rows and source columns,
including transitions between control blocks of different dimensions. In the
Python model these keys are `(source, destination)`.

Schema-1 numeric models with only self-edges remain readable. Cross-control
records from the first development build have ambiguous edge directions:
re-export the original `FiniteControlModel` with the current serializer and
rerun the task. Changing a schema number alone does not resolve that ambiguity.
This model format is separate from the analysis-bundle container version.

Numerical candidate execution uses the existing unweighted physical channel
semantics. The actual trace distance is computed against the original target;
roundoff-derived targets remain separate diagnostic objects. Results near the
requested tolerance are unresolved within the declared comparison tolerance.
Such results do not produce a strict feasible upper bound, including at zero
tolerance. Numerical tolerance comparisons use separately identified requests.
Numerical multiblock outputs are supported; intermediate window
trajectories require one compatible control-block layout.

## Reports, limits and revalidation

### Export reports and plots

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
For complete projective readouts, each CSV row identifies the dataset and
sampling event. When two acquisitions share a state and window, their plot
labels also show the dataset. Each horizontal row corresponds to one CSV
data row. Exceptionally long labels include its row number. A dot and an
end cap mark a two-sided interval. A right-pointing triangle marks a
one-sided lower bound.
Missing optional plotting dependencies preserve the computed scientific result
and mark the presentation step partial. Output files are exclusive by default;
`--overwrite` explicitly selects atomic replacement. Inputs and output paths
must remain distinct.

### Computation budgets

| Budget | Default |
|---|---:|
| Dynamic programming (DP) cells / updates | 100,000 / 1,000,000 |
| Rational numerator or denominator bits | 65,536 |
| Total candidate actions | 10,000 |
| Saved trajectory states / window evaluations | 256 / 256 |
| Matrix or vector working elements | 1,048,576 |
| JSON nodes per task or state / compound record | 200,000 / 2,000,000 |
| UTF-8 bytes per JSON input or bundle data member | 32 MiB |

Compound records retain original and effective inputs, outputs and diagnostics,
so they have a larger aggregate capacity than a single task. Readers and writers
use the same limits for each role; JSON nesting is limited to 40 levels and
string content to 16 MiB. A bundle member's byte limit applies separately.

Checks precede dense allocations and optional trajectory storage. These are
work bounds, not runtime guarantees. Exact DP uses syntax states and budgets,
without enumerating programs. A completed budget prefix remains a valid lower
bound if arithmetic or update limits stop further exclusion. Optional window
limits preserve already established cost endpoints. Execution state and
scientific decision are separate fields.

Trajectory windows distinguish resource limits from unresolved numerical
states. A numerical failure identifies the affected state diagnostics;
increasing the resource budget does not resolve it. If the main cost analysis
is already partial, it retains its original reason and the window result
reports its own status separately.

### Execution status

Cost and window analyses exit 0 on completion, 1 for a partial result, 2 for
input errors, 3 for a preflight resource limit and 130 on interruption. With
the default certificate policy, a failed inequality returns `certificate_failed`
(exit 1) and a malformed certificate returns `invalid_input` (exit 2).
Each result or failure carries a run identifier.
An unresolved numerical input or tolerance comparison returns a partial result
and exit 1. A definite numerical candidate miss remains a completed analysis.
If bundle saving fails after calculation, the CLI still delivers the scientific
result, records the delivery error and exits 1.

### Share and reverify a workflow

Preparation-cost and known-state window bundles use container schema 2.
`inspect` checks archive integrity,
object bindings and stored-result consistency; it does not rerun the physical
model. `verify` rebuilds the recipe, checks evidence, executes candidates and
recalculates windows from the saved effective inputs. It preserves author
history and writes a separate recipient result. Numerical semantic comparison
uses a 1e-10 relative/absolute scale; exact rational strings remain exact.
Bitwise same-version replay is reported separately. Different producer versions
can still have matching newly computed scientific results.

Stored numerical decisions, candidate status and diagnostics must agree before
inspection succeeds. A numerically unresolved state has empty global,
window and partition readouts. Numeric evidence retains empty rigorous cost endpoints.
The recipient's resource ceilings constrain the first reconstruction as well as
fresh calculation; the author's saved limits and input identity remain intact.

A changed numerical policy defines a new task, so schema-2 verification uses
the saved policy. Schema-1 model and certificate bundles, including their
spectrum and projector-count requests, remain readable from 0.2.0.

Finite-sample projective readouts use **container schema 4** and require
0.4.0 or later. `inspect` checks the archive and its acquisition bindings.
`verify` starts from the saved counts and recomputes the sampling coverage,
window bounds, retention contributions and any eligible preparation-cost
bounds. The [bundle guide](ANALYSIS_BUNDLES.md) lists the reader for each format.
