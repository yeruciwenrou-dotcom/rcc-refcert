# RCC RefCert

[![arXiv: 2509.18205](https://raw.githubusercontent.com/yeruciwenrou-dotcom/rcc-refcert/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/assets/arxiv.svg)](https://arxiv.org/abs/2509.18205)
[![PyPI](https://img.shields.io/pypi/v/rcc-refcert)](https://pypi.org/project/rcc-refcert/)
[![Software DOI (all versions)](https://img.shields.io/badge/DOI%20%28all%20versions%29-10.5281%2Fzenodo.22544967-darkgreen)](https://doi.org/10.5281/zenodo.22544967)

**RCC RefCert** is an open-source toolkit for studying quantum circuit complexity.
Given the parameters of your preparation model, you can compute a **rigorous
lower bound on optimal quantum circuit complexity** from final-state data.
Use the target state's exact spectrum or counts collected under a
prespecified measurement protocol.

You can verify reference bounds for models with measurement, feed-forward and
reset. In exact diagonal-preserving models, a successful program is optimal
when its cost meets the lower bound. An open gap limits how many slots a
better program could save. Window RCC maps complexity across subsystems from
the density matrix of a pure or mixed state. Complete outcome histograms give
confidence bounds on the RCC difference between two states in the same
classical measurement window. A colleague can independently recompute the
results from one bundle.

The toolkit is based on **Reference-Contingent Complexity (RCC)**, introduced by
Liu, Tian and Wu in
[*Structure-Fair Quantum Circuit Complexity: An Auditable Information-Theoretic Lower Bound*](https://arxiv.org/abs/2509.18205).

## Features of reference-contingent complexity

<a id="structural-fairness"></a>
<a id="structural-fairness-gives-complexity-comparisons-a-physical-basis"></a>

### Structural fairness makes circuit complexity comparable across physical settings

Quantum circuit complexity is often measured by the minimum number of gates needed
to prepare a target state from a fixed initial state. Counting starts once the
inputs are ready, so equal gate counts can conceal different physical costs. For
example, one device may supply a pure ancillary qubit, while another must first
reset a qubit in a mixed state to obtain one. RCC takes structural fairness as
a physical postulate, using the structure reliably supplied by the background
as the reference zero point and fixing the available controls and their costs
before the target is chosen. It counts only
the resources used to generate additional structure and measures them on a
common calibrated scale, making quantum circuit complexity comparable across
physical settings.

<a id="auditable-complexity-lower-bounds"></a>
<a id="final-state-data-certify-a-lower-bound-on-optimal-complexity"></a>

### Final-state data give a rigorous lower bound on optimal circuit complexity

With the model, cost rules and required accuracy fixed, optimal quantum circuit
complexity is the infimum of the costs of all circuits that successfully prepare
the target. Each such circuit must generate the structure the target requires
beyond what the reference already supplies. Although this global optimum is
often hard to compute directly, RCC can certify a rigorous lower bound from
final-state data alone. The auditable certificate can use the exact target
spectrum or counts showing that a prespecified measurement outcome is common in
the target and rare under the reference.

<a id="start-here"></a>
<a id="what-this-repository-implements"></a>
<a id="what-you-can-do"></a>

## Research tasks

| Research task | What you can do |
|---|---|
| [Build a finite-control model for RCC certification](#work-with-your-own-model) | Specify what structure the background supplies and which operations incur a cost. Encode the reference state, quantum channels and allowed controls in a model you can submit for certification. |
| [Verify a model's reference bound](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/CUSTOM_MODELS.md#prepare-and-verify-a-candidate) | Check a certificate you already have or, for a stable model, generate and verify a numerical candidate. You can reuse the verified reference bound to calculate complexity lower bounds for different targets in the same model. |
| [Certify a lower bound on optimal circuit complexity](#target-spectra-and-measured-counts) | An exact target spectrum gives a cost below which no circuit in the model can prepare the target within tolerance. For an experiment, [plan how many shots to take](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/TERMINAL_BOUNDS.md#plan-a-fixed-sample-size) and use target and reference counts to certify a bound at the chosen confidence level. The [graph-state example](#graph-state-and-cooling-studies) shows how the choice of measurement affects that bound. |
| [Compare preparation strategies](#preparation-costs-and-complexity-profiles) | Find which programs reach the target within tolerance and compare their costs. In an exact diagonal-preserving model, a successful program is optimal when its cost matches the lower bound. A better program could save at most the gap between that cost and the lower bound. The [cooling study](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/FINITE_DATA_STUDIES.md#three-qubit-algorithmic-cooling) proves that six slots are optimal for the full three-qubit target at trace-distance tolerance 1/50. |
| [Measure pure-state complexity with window RCC](#compare-subsystem-complexity) | Subsystem profiles show how complexity is distributed within a pure state and where two states differ, even when their global RCC readings agree. For pure or mixed states, use [your own density matrix](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/COST_AND_WINDOWS.md#your-own-matrix-and-tensor-labels) to [separate the contributions of local structure and correlations between subsystems](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/COST_AND_WINDOWS.md#read-local-and-correlation-contributions) and track both during preparation. With outcome counts, [bound the RCC difference between two states in the same classical measurement window](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/COST_AND_WINDOWS.md#finite-sample-windows). |
| [Share a calculation for independent verification](#reverify-a-shared-analysis) | Share the original inputs and results in a single bundle. A colleague can use it to recompute the result independently. |
| [Reproduce the paper's reference calculations](#reference-cases) | Rerun the bundled cases and compare the outputs with the frozen reference results. The [paper-to-code map](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/PAPER_MAP.md) links each calculation to the corresponding equations. |

> **New in 0.4.0**
>
> Plan a fixed sample size for a preparation-cost threshold and certify a lower
> bound from target and reference counts, accounting for known binary readout
> errors.
> Full outcome histograms give finite-sample intervals for RCC in the measured
> classical window and for the difference between two states measured there.
> The release adds [Qiskit readout import](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/FINITE_DATA_STUDIES.md#your-counts-and-qiskit-registers)
> with an [IBM hardware example](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/FINITE_DATA_STUDIES.md#check-the-mapping-on-a-hardware-file),
> finite-data studies of a noisy six-qubit cluster state and three-qubit
> algorithmic cooling, and a [half-erasure benchmark with an analytic optimum](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/COST_AND_WINDOWS.md#build-a-half-erasure-channel).
> [Full release notes](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/CHANGELOG.md#040).

## Quick start

### Install from PyPI

With Python 3.10 or newer, run this spectrum example in a new working directory.
For the finite-data workflows, use the [0.4.0 source installation](#install-from-source)
or an installed 0.4.0 release.
On Windows you can use Command Prompt. Substitute `python` for `python3`
if that is your interpreter's name.

```bash
python3 -m pip install rcc-refcert
python3 -m rcc_refcert bound template spectrum > spectrum.json
python3 -m rcc_refcert bound spectrum spectrum.json
```

In Windows PowerShell 5.1, use this command for the template step to save
`spectrum.json` as ASCII:

```powershell
python -m rcc_refcert bound template spectrum | Out-File -Encoding ascii -FilePath spectrum.json
```

The template supplies a four-dimensional target spectrum and the model
parameters. The integer lower bound is **one atomic slot**. Every circuit
that prepares this target to the stated accuracy must use at least one slot.
To run your own calculation, replace the spectrum and model parameters in
`spectrum.json`, or follow the [measurement protocol](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/TERMINAL_BOUNDS.md#fixed-projector-counts)
for projector counts. The [terminal-state guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/TERMINAL_BOUNDS.md)
describes the input fields. To see an optimal cost, follow the [five-slot cyclic reset](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/COST_AND_WINDOWS.md#a-complete-cost-task). To compare pure states, start with [Bell and GHZ subsystem profiles](#compare-subsystem-complexity).

The installed package includes the [Python API](#python-api), command-line
tools and reference cases. The source checkout also includes example scripts,
[Jupyter notebooks](#jupyter-notebook) and the verification suite.

### Install from source

The [source archive for the 0.4.0 examples](https://github.com/yeruciwenrou-dotcom/rcc-refcert/archive/867c064e5f9134c48bc58eedfccb2df5487421a1.zip)
contains the code used below. Extract it and open the directory containing
`quickstart.py`. With Git, you can get the same source revision by running:

```bash
git clone https://github.com/yeruciwenrou-dotcom/rcc-refcert.git
cd rcc-refcert
git switch --detach 867c064e5f9134c48bc58eedfccb2df5487421a1
```

From that directory, run the frozen reference calculations:

```bash
python3 --version
python3 quickstart.py --reproduce-only
```

The script creates `.venv`, installs the locked verification dependencies,
checks the frozen reference evidence, and writes fresh results to
`generated_results/`. Expect three `MATCH` checks. Run `python3 quickstart.py`
to include the test suite. Later runs reuse the environment and refresh the
installation when the dependency lock or package metadata changes.

For source examples, stay in the checkout directory and use its interpreter:

- **macOS / Linux:** `.venv/bin/python`
- **Windows:** `.venv\Scripts\python.exe`

Long shell commands use `\` to continue on the next line. On Windows, join
those lines into one command and omit the trailing `\`.

If you prefer your own active environment, install with
`python -m pip install .` and use that environment's interpreter throughout.
The module entry point accepts the same arguments as `rcc-refcert`.

## Research workflows

### Work with your own model

You supply the model's channels, reference state, control language, and cost
assumptions, together with the target-state inputs for a bound calculation.
The package returns numerical checks and a reproducible record of the bound.
A complete analysis bundle also carries the model and proof arrays so another
researcher can reverify the calculation without the original modeling script.

After the [source installation](#install-from-source), run these examples:

```bash
.venv/bin/python examples/custom_model_workflow.py --bundle alternating.rccbundle
.venv/bin/python examples/cyclic_reset_workflow.py --bundle cyclic-reset.rccbundle
```

The first builds an alternating qubit model and prepares a **Bellman–Choi
certificate (H.3)** for its reference-domination bound. Independent
verification passes even though the local gain–cost sufficient test fails.
The second uses a **reference-potential certificate (H.4)** for a four-qubit
register, then computes bounds from an exact spectrum and synthetic counts.
Both bound paths for this register return **two atomic slots**. The
[complete cost workflow](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/COST_AND_WINDOWS.md#a-complete-cost-task) independently
verifies the five-slot optimum with gain exclusion and a matching program.

Each command saves a bundle containing the model, certificate and results.
Choose an unused filename. Follow the [custom-model guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/CUSTOM_MODELS.md)
to replace the channels, states, control language and cost assumptions, then
verify your certificate and add a supported target-state task. The guide
explains the two certificate routes and their numerical limits.

### Target spectra and measured counts

Use either [installation above](#quick-start).
The following commands create an input template, calculate a bound, save its
record and replay it:

```bash
python3 -m rcc_refcert bound template spectrum > spectrum.json
python3 -m rcc_refcert bound spectrum spectrum.json
python3 -m rcc_refcert bound spectrum spectrum.json --format json > bound.json
python3 -m rcc_refcert bound replay bound.json
```

Use `python` instead of `python3` if that is your environment's interpreter.
In the [source quickstart](#install-from-source) environment, stay in the checkout and
use `.venv/bin/python` on macOS/Linux or `.venv\Scripts\python.exe` on Windows.
Use unused filenames for your own input files and saved results.

The template declares a four-dimensional model and a complete exact spectrum.
Expect an integer-slot lower bound of **one**. To try synthetic measurement
counts with 550 hits in 1000 trials:

```bash
python3 -m rcc_refcert bound template counts > counts.json
python3 -m rcc_refcert bound counts counts.json
```

For real measurements, fix the protocol **before collecting data** with
`bound prepare-protocol` and preserve its digest with the dataset. The
[terminal-state guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/TERMINAL_BOUNDS.md)
explains the projector, sample-size and evidence requirements.

Both routes use a uniform reference on an ideal support and exact transcription.
The cost bound depends on the declared model premises; sampling coverage
describes the counts alone. These templates and commands are available directly
from the installed package.

You can also measure the reference. Apply the same binary measurement to the
target and reference, then use both hit counts to bound the preparation cost.
In the [worked example](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/TERMINAL_BOUNDS.md#target-and-reference-counts-for-the-same-effect),
550 target hits and 250 reference hits in 1,000 shots each certify at least
one slot in the specified model, with at least 95% joint coverage.

With counts for **all outcomes of one measurement**, you can also compare the
window RCC of two states. Measure a Bell pair and a reduced GHZ pair in the
same Bell basis. With 20,000 synthetic shots per state, the Bell pair exceeds
the GHZ pair by at least 0.37086784 R-structons **in that classical measurement
window**, with at least 99% joint coverage. For the containing quantum window
the same counts give a lower bound for each state and leave their ordering open. See [finite-sample windows](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/COST_AND_WINDOWS.md#finite-sample-windows)
for the commands, protocol and example with your own counts.

<a id="finite-data-studies"></a>

### Graph-state and cooling studies

Compare the preparation-cost bounds that two measurement strategies give for
the same noisy cluster state. The two alternating X/Z settings together use
the same total number of shots as the Z-basis measurement.

Use the [source quickstart](#install-from-source) or an active 0.4.0
installation. The commands below save the counts for independent verification.
On Windows use `.venv\Scripts\python.exe`, or use `python` in your active
installation.

```bash
.venv/bin/python -m rcc_refcert study template cluster > cluster.json
.venv/bin/python -m rcc_refcert study analyze cluster.json --bundle cluster.rccbundle
.venv/bin/python -m rcc_refcert bundle verify cluster.rccbundle
```

With the default synthetic counts, each color alone certifies at least one slot.
Together they certify at least two slots. The noisy graph state has the same
Z-basis populations as the uniform reference, so 20,000 Z-basis shots give
a zero lower bound in this example. The alternating X/Z settings reveal
stabilizer correlations that the Z-basis populations miss.

Use `study template cooling` to ask whether another cooling cycle is needed.
In the default model, a six-slot program reaches the full three-qubit target
within trace distance 1/50, and the model rules out every cheaper program.
The final refresh preserves the target qubit's polarization and erases its
correlations with the bath. Joint counts let you examine both effects.
To supply your own measurements, follow the register
layouts and acquisition steps in the [finite-data guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/FINITE_DATA_STUDIES.md).

<a id="cost-and-window-workflows"></a>
<a id="preparation-costs-and-subsystem-structure"></a>

### Preparation costs and complexity profiles

Use the Python environment where you installed the package. This example
creates an editable preparation task, analyzes the candidates and verifies the
saved result:

```bash
python3 -m rcc_refcert cost template cyclic-reset > task.json
python3 -m rcc_refcert cost analyze task.json --bundle task.rccbundle
python3 -m rcc_refcert bundle verify task.rccbundle
```

At the default trace-distance tolerance of `1/10`, the four-qubit reset task
returns **[5,5] atomic slots**, including halt. The
[worked calculation](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/COST_AND_WINDOWS.md#a-complete-cost-task)
shows how the model excludes shorter programs and how a five-slot program
meets the target. For a model supplied as matrices, the
[numerical workflow](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/COST_AND_WINDOWS.md#numerical-models-and-candidate-diagnostics)
reports each candidate's cost and distance from the target.

<a id="compare-state-organization"></a>

#### Compare subsystem complexity

To compare subsystem complexity in a pure or mixed state, choose the subsystems
to examine. Each selected subsystem is a **subsystem window**: the analysis traces
out the remaining systems and evaluates the reduced state relative to the
declared reference and control scale. For the uniform product reference, the
window RCC value is $C_{R,A}=[\log_2 d_A-S(\rho_A)]/g_R$. The control bandwidth
$g_R=\log_2\Gamma_R$ converts the entropy deficit into a complexity reading in
R-structons ($\mathrm{st}_R$). For a complete bipartition, the global reading is the sum of
the two local readings and the contribution from correlations between them.

To try an editable state comparison in the same environment:

```bash
python3 -m rcc_refcert probe export w1-quantum-organization > windows.json
python3 -m rcc_refcert window analyze windows.json --bundle windows.rccbundle
```

At fixed dimension and control bandwidth, all pure states have the same global
RCC reading for a uniform reference. Here two Bell pairs and a four-qubit GHZ
state both give 2 R-structons. For the Bell pairs, a two-qubit window reads 1
when it contains a whole pair and 0 when it contains one qubit from each pair.
The corresponding GHZ windows both read 1/2.

The [window guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/COST_AND_WINDOWS.md#subsystem-complexity-profiles)
works through the local and correlation contributions on that common scale. To use [your own density matrix](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/COST_AND_WINDOWS.md#your-own-matrix-and-tensor-labels),
supply the matrix, its tensor dimensions and the subsystems to compare.
The [workflow notebook](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/RCC_Workflows_Quickstart.ipynb)
follows both the preparation and window calculations.

### Reverify a shared analysis

Use the cyclic-reset certificate bundle from the [model example](#work-with-your-own-model),
or substitute a bundle you received.

```bash
python3 -m rcc_refcert bundle inspect cyclic-reset.rccbundle
python3 -m rcc_refcert bundle verify cyclic-reset.rccbundle \
  --output cyclic-reset-verification.json
```

`inspect` checks the saved data for consistency. `verify` recomputes the
analysis from its saved inputs and compares it with the original result.
For the cyclic-reset certificate, read **Fresh matrix verification** and
**Historical results supported** together. A fresh matrix check can pass with
a larger conservative constant and leave the stronger historical constant
unsupported, even when both calculations give the same integer cost bound.

A colleague needs only the bundle and a compatible installation of RCC RefCert
to recompute the result. Use `--output` to save the verification report under
a new filename. The
[analysis-bundle guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/ANALYSIS_BUNDLES.md) explains result comparisons,
exit codes and which versions can verify each bundle. Exact historical scalar
replay uses the producer's package version.

## Notebooks and Python API

### Jupyter notebook

After the [source quickstart](#install-from-source), install the optional notebook
dependencies and register its environment:

```bash
.venv/bin/python -m pip install -e ".[notebook]"
.venv/bin/python -m ipykernel install --user \
  --name rcc-refcert --display-name "Python (rcc-refcert)"
.venv/bin/python -m jupyterlab
```

Choose a notebook for the task you want to explore:

| Tutorial | What you will do |
|---|---|
| [Models and certificates](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/RCC_Quickstart.ipynb) | Analyze finite-control models, verify reference certificates and reproduce paper calculations. |
| [Terminal-state bounds](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/RCC_Bounds_Quickstart.ipynb) | Calculate bounds from exact spectra or fixed-projector counts, then save and replay the result. |
| [Preparation costs and complexity profiles](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/RCC_Workflows_Quickstart.ipynb) | Compare preparation costs, use window RCC to study states and cooling trajectories, and share complete evidence. |

Select **Python (rcc-refcert)** as the kernel. Run all three commands with the
same interpreter; on Windows, use `.venv\Scripts\python.exe`. These dependencies
are optional and do not enter the runtime package.

### Python API

Audit a bundled model directly:

```python
from rcc_refcert import audit_case, get_case

result = audit_case(get_case("multiblock-rectangular"))
print(result.matches_expectations)
print(result.model_analysis.fixed_model_domination.constant)
print(result.gain_cost.outcome.value)
```

The values are `True`, `15/14` numerically, and `"fail"` for the deliberately
failed local gain–cost test in the [reference cases](#reference-cases). The model
still passes its supplied Bellman–Choi and reference-potential certificate checks.

The [model guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/MODEL_GUIDE.md) shows how to build a model with `Action`
and `FiniteControlModel`, audit it, and verify supplied certificates. For
target-state calculations, the [bounds guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/TERMINAL_BOUNDS.md) covers
`bound_from_spectrum`, `bound_from_counts`, `prepare_protocol`,
`with_reference_certificate`, `validate_record` and `replay_record`.

For preparation costs and subsystem complexity profiles, import from
`rcc_refcert.workflows`.
The [workflow guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/COST_AND_WINDOWS.md) introduces
`analyze_cost`, `compare_cost_results`, `analyze_windows`, `export_probe` and
`save_workflow_bundle` with executable examples.

## Why reference-contingent complexity

RCC treats quantum circuit complexity as a **reference-dependent physical
quantity**. Its **principle of structural fairness** requires the structure
supplied by the background to be represented in the reference, and additional
target-directed structure to be generated and counted. This principle guides
the construction of a complete physical generation model: the reference,
allowed dynamics, control language and program prior, success criterion, and
atomic cost unit must account consistently for the resources supplied and used.

The reference has an independent physical origin, such as a conservation law,
an encoding structure, or a control architecture. The reference and generation
model jointly set the structural zero point and resource scale of this
relational physical quantity. A change of reference can shift part of the
target structure into the background.
Comparing circuit complexity across the two settings then requires specifying
how that background structure is physically supplied.

### What RCC measures

RCC is a structure-fair, model-relative framework for defining and
lower-bounding quantum circuit complexity.

Within this framework, the paper constructs an admissible qubit model family
whose members, at each size, can approximate every pure and mixed state of
that size to any positive tolerance. The family is specified before target
selection, so the same physical rules apply across target choices.

For a specified admissible model, target, and accuracy $\epsilon$,
$C_{\rm opt}^{(\epsilon)}$ is the infimum of the declared cost over all
admissible successful preparation histories. It asks for the least cost
compatible with that model. The reference, allowed processes, and cost rules
remain the same across all histories in this optimization.

### How the final state gives a lower bound

Every successful history must leave the required structure in its final state.
Faithful transcription bounds that history's program length by its physical
cost. Reference admissibility bounds the program's output gap relative to the
structured vacuum by the same description length plus a fixed calibration
constant. The gap that remains throughout the target's error neighborhood
therefore imposes a common cost floor. Taking the infimum over successful
histories carries this bound to $C_{\rm opt}^{(\epsilon)}$.

For a finite controller with measurement, feed-forward and synchronous loops,
a reference certificate bounds the combined output of all halting paths
relative to the reference. The sum includes each program's weight and the
probabilities of its measurement branches, so any bias the controller
introduces toward particular outputs enters the bound.

For the unbiased reference $\sigma_R=\Pi_R/d_R$, the state-side RCC value is
$C_R(\rho)=[\log_2 d_R-S(\rho)]/\log_2\Gamma_R$, where $\Gamma_R$ counts
distinct physical action classes per atomic slot. The reference sets the
structural zero point, and the control bandwidth $g_R=\log_2\Gamma_R$ sets the
resource scale. The entropy deficit divided by this bandwidth is a complexity
reading in R-structons ($\mathrm{st}_R$), with
$1\thinspace\mathrm{st}_R = g_R$ bits. It is the linear leading term of the
lower bound under the paper's regularity conditions.

Two mixed states with the same entropy have the same global RCC reading at
this reference and control scale. If one has a larger maximum eigenvalue, its
spectral skew, $\Delta_{\rm spec}(\rho)=S(\rho)-H_{\min}(\rho)\geq 0$,
is greater. This term adds to the entropy deficit before smoothing and can
tighten the one-shot lower bound on circuit complexity. The
[scientific scope](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/SCIENTIFIC_SCOPE.md#from-state-information-to-process-cost)
gives the full cost bound, including the smoothing loss at the chosen
tolerance and the transcription and reference overheads.

With the model qualifications established and the measurement protocol fixed
in advance, endpoint statistics can thus certify a lower bound on optimal circuit
complexity without reconstructing the preparation history.

The package exposes the model inputs, numerical certificate checks, and
scalar cost inversion that make such examples reproducible. The
[scientific scope](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/SCIENTIFIC_SCOPE.md)
explains the evidence each calculation supplies; the
[paper-to-code map](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/PAPER_MAP.md)
connects the implementation to the full model construction and lower-bound
theorem.

> **Manuscript alignment.** This source tree is aligned with version 4 of the
> [RCC manuscript](https://arxiv.org/abs/2509.18205)
> ([fixed V4](https://arxiv.org/abs/2509.18205v4)). Appendix labels and
> equation numbers refer to manuscript version 4.

<a id="end-to-end-rcc-lower-bound-example"></a>

The [worked lower-bound example](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/END_TO_END_EXAMPLE.md)
follows Theorem 3.1 from the physical model and its terminal-state certificate
through the cost inversion in Appendix A to a matching preparation.

### Reference cases

| Case | Scientific role | Intended result |
|---|---|---|
| `dephase-or-halt` | Transparent closed-form realization | Every supplied route passes |
| `multiblock-rectangular` | Direct-sum, rectangular-Kraus, and certificate diagnostic | Realization, fixed-point and reference-certificate checks pass. The original codewords fail the local gain–cost test; the suggested prefix code meets it. |
| `dark-nonhalting` | Least-fixed-point boundary with a recurrent nonhalting sector | The process remains valid. The linear-inverse method is unavailable, so this method leaves the minimum reference-domination constant unevaluated. |

The multiblock example deliberately violates the local gain–cost sufficient
condition with its original codewords. Its supplied Bellman–Choi and
reference-potential certificates still pass their numerical checks. Adopting
the suggested prefix code changes the program weights and defines a separately
re-encoded model.

To reproduce the reference calculations, run this command in the environment
where you installed the toolkit:

```bash
python3 -m rcc_refcert reproduce --check
```

Expect three `MATCH` checks for the reference expectations, data and report.
The [paper-to-code map](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/PAPER_MAP.md)
locates the corresponding definitions and equations.

## Results and scientific scope

Finite-control matrix and certificate checks report `pass`, `fail`, `inconclusive` or
`not_applicable`, with an explicit evidence level, currently `numerical`.
These outcomes describe finite-input and fixed-model checks. The
[scientific scope](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/SCIENTIFIC_SCOPE.md) connects them to the RCC theorem
and its physical, transcription and family-uniformity requirements.

Terminal-state records distinguish the scalar calculation's enclosure,
numerical certificate evidence and sampling confidence. A zero lower bound on its own leaves the optimum open.
The report explains which input or measurement led to that result.
The [output contract](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/OUTPUT_CONTRACT.md) explains fields and exit codes.

Exact diagonal recipes support rigorous model-specific cost intervals by combining
gain-based exclusion with an executed feasible program. Numerical matrix inputs
support candidate diagnostics and window profiles, with their numerical evidence
identified in the result. Window RCC compares state-side complexity across
subsystems in the declared reference and resource scale; the full one-shot cost
bound also uses the model and
accuracy corrections in the [RCC explanation](#how-the-final-state-gives-a-lower-bound).

The explicit matrix and path algorithms target small finite models. Resource
budgets are checked before enumeration or dense matrix construction, and
unresolved precision is reported explicitly. The
[model guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/MODEL_GUIDE.md#numerical-and-resource-limits)
describes limits and certificate error budgets.

## Further reading

The [version 0.3.0 source tree](https://github.com/yeruciwenrou-dotcom/rcc-refcert/tree/v0.3.0)
preserves the documentation shipped with that release. The
[0.3.0 release notes](https://github.com/yeruciwenrou-dotcom/rcc-refcert/releases/tag/v0.3.0) describe the original cost and window workflows.

- [Scientific scope](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/SCIENTIFIC_SCOPE.md): what each calculation establishes and how it connects to RCC.
- [Paper-to-code map](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/PAPER_MAP.md): implemented objects, equations and worked examples.
- [Conventions](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/CONVENTIONS.md): numerical, tensor and exact-input conventions.
- [Output contract](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/OUTPUT_CONTRACT.md): result fields, evidence levels and exit codes.
- [Section VII.B of the paper](https://arxiv.org/pdf/2509.18205v4#page=26) discusses how RCC relates to other physical notions of complexity, including the holographic CV and CA proposals.

### Extending the research kernel

Use [GitHub Issues](https://github.com/yeruciwenrou-dotcom/rcc-refcert/issues)
to report a problem, suggest a scientific extension or improve an explanation.

Contributions can add physical models, certificate constructions, stronger
numerical verification, terminal-state methods or interfaces for new research
tasks. The [contribution guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/CONTRIBUTING.md) explains the scientific
contracts, expected evidence and development checks for each kind of change.

For development setup, tests, formatting and package builds, follow
[local verification](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/CONTRIBUTING.md#local-verification).

### Repository structure

| Path | Contents |
|---|---|
| `src/rcc_refcert/` | Model, certificate, bound, cost and window APIs, command-line tools including `study` for finite-data research, and evidence formats |
| `examples/` | Paired-reset, alternating-qubit, cyclic-register and numerical candidate workflows, the `half_erasure.json` benchmark, and IBM Sherbrooke hardware counts and register layout in `readouts/` |
| `RCC*Quickstart.ipynb` | Executable model, bound, cost and window tutorials |
| `results/` | Frozen reference report and structured data |
| `generated_results/` | Local verification results generated by quickstart; ignored by Git |
| `docs/`, `tests/` | Detailed guides and scientific/interface regressions |

<a id="development-citation-and-license"></a>

## Citation and license

Cite the software version used and the associated RCC paper.
[`CITATION.cff`](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/CITATION.cff) provides both citation records. The
[all-versions DOI](https://doi.org/10.5281/zenodo.22544967) identifies the
software archive across releases.

The following citation identifies the 0.4.0 source revision used in the examples above.

> Liu, HongZheng; Tian, YiNuo; and Wu, Zhiyue. *RCC RefCert: A Research Toolkit
> for Structure-Fair Quantum Circuit Complexity*. Version 0.4.0, 2026.
> [Source revision `867c064`](https://github.com/yeruciwenrou-dotcom/rcc-refcert/commit/867c064e5f9134c48bc58eedfccb2df5487421a1).

The GitHub **Cite this repository** button follows the paper preference in
`CITATION.cff`; include the software version citation as well when reporting a
calculation. Complete bundles can
[record the source revision](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/docs/ANALYSIS_BUNDLES.md#record-the-software-revision)
for both the author and the recipient.

For calculations made with a source checkout, record its full commit and
package version. To reproduce a source version, check out that commit or a
release tag before installation. The software archive provides a separate DOI
for each archived release as well as the all-versions DOI above.

See the [Changelog](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/CHANGELOG.md) for release changes and subsequent updates. The source code
is available under the [MIT License](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/867c064e5f9134c48bc58eedfccb2df5487421a1/LICENSE).
