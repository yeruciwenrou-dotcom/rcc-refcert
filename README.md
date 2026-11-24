# RCC RefCert

[![arXiv: 2509.18205](https://raw.githubusercontent.com/yeruciwenrou-dotcom/rcc-refcert/main/docs/assets/arxiv.svg)](https://arxiv.org/abs/2509.18205)
[![PyPI](https://img.shields.io/pypi/v/rcc-refcert)](https://pypi.org/project/rcc-refcert/)
[![Software 0.3.0 DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.24248347-darkgreen)](https://doi.org/10.5281/zenodo.24248347)

**RCC RefCert** is an open-source toolkit for studying quantum circuit complexity.
How cheaply can a circuit prepare your target state? For a specified model and
preparation tolerance, RCC RefCert uses final-state data to give a **rigorous
lower bound on optimal quantum circuit complexity**. Supply an exact target
spectrum or counts from a measurement chosen before data collection.

You can build your own quantum models and compare preparation strategies. With a
density matrix, window RCC shows how much structure is visible in each subsystem
and how much comes from correlations in a pure or mixed state. Share the model,
inputs and results for independent verification.

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
reset a qubit in a mixed state to obtain one. Structural fairness is RCC's
physical postulate for making this distinction. Before choosing the target,
fix what the background supplies, the available controls, their costs and the
weights assigned to control programs. The background sets the reference zero
point. A preparation pays for the resources it uses, even for a step that
preserves global entropy. To carry a bound from one setting to another, account
for the change of reference and the cost and accuracy of translating the controls.

<a id="auditable-complexity-lower-bounds"></a>
<a id="final-state-data-certify-a-lower-bound-on-optimal-complexity"></a>

### Final-state data give a rigorous lower bound on optimal circuit complexity

With the model, cost rules and required accuracy fixed, optimal quantum circuit
complexity is the infimum of the costs of all circuits that successfully prepare
the target. Why can a measurement on the target rule out cheaper circuits?
The model's transcription bound gives every low-cost circuit a short control
description. Short descriptions carry greater weight in the mixture of program
outputs, and the reference certificate bounds that whole mixture. An outcome
that is common in the target yet rare under the reference can therefore rule
out every circuit below a calculable cost, even after allowing for preparation
error.

<a id="start-here"></a>
<a id="what-this-repository-implements"></a>
<a id="what-you-can-do"></a>

## Research tasks

| Research task | What you can do |
|---|---|
| [Study graph-state noise or algorithmic cooling with finite data](#finite-data-studies) | See which local measurements give the strongest lower bound on the cost of preparing a noisy graph state. For cooling, find which programs reach the full target within tolerance and use joint counts to track polarization and target–bath correlations. Supply your own counts or Qiskit shots and share a replayable analysis. |
| [Build a finite-control model for RCC certification](#work-with-your-own-model) | Specify what structure the background supplies and which operations incur a cost. Encode the reference state, quantum channels and allowed controls in a model you can submit for certification. |
| [Verify a model's reference bound](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/1fbdfd03aa2df3ad45081098477dc974dc002084/docs/CUSTOM_MODELS.md#prepare-and-verify-a-candidate) | Check a certificate you already have or, for a stable model, generate and verify a numerical candidate. You can reuse the verified reference bound to calculate complexity lower bounds for different targets in the same model. |
| [Certify a lower bound on optimal circuit complexity](#target-spectra-and-measured-counts) | Use the exact target spectrum to find a cost below which no circuit in your model can prepare the target within tolerance. [Fixed-projector measurement counts](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c5ecafef6f80c0c4519db1dba19b9ca093268dc0/docs/TERMINAL_BOUNDS.md#fixed-projector-counts) give a lower bound at a prespecified confidence level. |
| [Plan a measurement and certify a cost from counts](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c5ecafef6f80c0c4519db1dba19b9ca093268dc0/docs/TERMINAL_BOUNDS.md#plan-a-fixed-sample-size) | Choose a sample size for the response or cost threshold you want to certify. Apply the [same binary measurement to target and reference](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c5ecafef6f80c0c4519db1dba19b9ca093268dc0/docs/TERMINAL_BOUNDS.md#target-and-reference-counts-for-the-same-effect) and use the two histograms to bound the target’s preparation cost. |
| [Compare preparation strategies](#cost-and-window-workflows) | Find which programs reach the target within tolerance and compare their costs. In exact diagonal-preserving models, you can prove a program is optimal, as in [cyclic reset](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c0a9eecd8fa5ce082b29bb30608acfb8c7b24ffe/docs/COST_AND_WINDOWS.md#a-complete-cost-task), or bound how much a better program could save, as in [algorithmic cooling](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c0a9eecd8fa5ce082b29bb30608acfb8c7b24ffe/docs/COST_AND_WINDOWS.md#cooling-and-the-remaining-optimality-gap). |
| [Analyze pure-state complexity with window RCC](#compare-subsystem-complexity) | Distinguish pure states with the same global RCC value by the structure visible in their subsystems and correlations. For pure and mixed states alike, use [your own density matrices](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c0a9eecd8fa5ce082b29bb30608acfb8c7b24ffe/docs/COST_AND_WINDOWS.md#your-own-matrix-and-tensor-labels) to separate [the contributions of local structure and correlations between subsystems](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c0a9eecd8fa5ce082b29bb30608acfb8c7b24ffe/docs/COST_AND_WINDOWS.md#read-local-and-correlation-contributions) and track how each changes during preparation. |
| [Share a calculation for independent verification](#reverify-a-shared-analysis) | Share the original inputs and results in a single bundle. A colleague can use it to recompute the result independently. |
| [Reproduce the paper's reference calculations](#reference-cases) | Rerun the bundled cases and compare the outputs with the frozen reference results. The [paper-to-code map](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/1fbdfd03aa2df3ad45081098477dc974dc002084/docs/PAPER_MAP.md) links each calculation to the corresponding equations. |

## Quick start

### Install from PyPI

With Python 3.10 or newer, run these commands in a new working directory.
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
parameters. The integer lower bound is **one primitive slot**. Every circuit
that prepares this target to the stated accuracy must use at least one slot.
To run your own calculation, replace the spectrum and model parameters in
`spectrum.json`, or follow the [measurement protocol](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c5ecafef6f80c0c4519db1dba19b9ca093268dc0/docs/TERMINAL_BOUNDS.md#fixed-projector-counts)
for projector counts. The [terminal-state guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c5ecafef6f80c0c4519db1dba19b9ca093268dc0/docs/TERMINAL_BOUNDS.md)
describes the input fields.

The installed package includes the [Python API](#python-api), command-line
tools and reference cases. The source checkout also includes example scripts,
[Jupyter notebooks](#jupyter-notebook) and the verification suite.

### Install from source

The [source archive for the 0.4.0 examples](https://github.com/yeruciwenrou-dotcom/rcc-refcert/archive/9929c34b1a585b3b64505e33b31bbafb03067ad3.zip)
contains the code used below. Extract it and open the directory containing
`quickstart.py`. With Git, you can get the same source revision by running:

```bash
git clone https://github.com/yeruciwenrou-dotcom/rcc-refcert.git
cd rcc-refcert
git switch --detach 9929c34b1a585b3b64505e33b31bbafb03067ad3
```

From that directory, run the frozen reference calculations:

```bash
python3 --version
python3 quickstart.py --reproduce-only
```

On Windows, or where your interpreter is named `python`, use `python` in place
of `python3`.

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
Both bound paths for this register return **two primitive slots**. The
[complete cost workflow](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c0a9eecd8fa5ce082b29bb30608acfb8c7b24ffe/docs/COST_AND_WINDOWS.md#a-complete-cost-task) independently
verifies the five-slot optimum with gain exclusion and a matching program.

Each command saves a bundle containing the model, certificate and results.
Choose an unused filename. Follow the [custom-model guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/1fbdfd03aa2df3ad45081098477dc974dc002084/docs/CUSTOM_MODELS.md)
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
[terminal-state guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c5ecafef6f80c0c4519db1dba19b9ca093268dc0/docs/TERMINAL_BOUNDS.md)
explains the projector, sample-size and evidence requirements.

Both routes use a uniform reference on an ideal support and exact transcription.
The cost bound depends on the declared model premises; sampling coverage
describes the counts alone. These templates and commands are available directly
from the installed package.

With counts for **all outcomes of one measurement**, you can also compare the
window RCC of two states. The Bell/GHZ example uses the same two-qubit
readout on both preparations. From 20,000 synthetic shots per state it
certifies a gap of at least 0.37086784 R-structons in the measured window
at 99% joint coverage. See [finite-sample windows](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c0a9eecd8fa5ce082b29bb30608acfb8c7b24ffe/docs/COST_AND_WINDOWS.md#finite-sample-windows)
for the commands, protocol and example with your own counts.

<a id="finite-data-studies"></a>

### Graph-state and cooling studies

Use the [source quickstart](#install-from-source) or an active 0.4.0
installation. The example uses the quickstart interpreter on macOS/Linux.
On Windows use `.venv\Scripts\python.exe`, or use `python` in your active
installation. Compare two measurement settings on the same noisy cluster
state and save the counts for independent verification:

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
layouts and acquisition steps in the [finite-data guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/9929c34b1a585b3b64505e33b31bbafb03067ad3/docs/FINITE_DATA_STUDIES.md).

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
[worked calculation](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c0a9eecd8fa5ce082b29bb30608acfb8c7b24ffe/docs/COST_AND_WINDOWS.md#a-complete-cost-task)
shows how the model excludes shorter programs and how a five-slot program
meets the target. For a model supplied as matrices, the
[numerical workflow](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c0a9eecd8fa5ce082b29bb30608acfb8c7b24ffe/docs/COST_AND_WINDOWS.md#numerical-models-and-candidate-diagnostics)
reports each candidate's cost and distance from the target.

<a id="compare-state-organization"></a>

#### Compare subsystem complexity

To compare subsystem complexity in a pure or mixed state, choose the subsystems
to examine. Each selected subsystem is a **subsystem window**: the analysis traces
out the remaining systems and evaluates the reduced state relative to the
declared reference and control scale. For the uniform product reference, the
window RCC value is $C_{R,A}=[\log_2 d_A-S(\rho_A)]/g_R$. The control bandwidth
$g_R=\log_2\Gamma_R$ converts the entropy deficit into a complexity reading in
R-structons ($\mathrm{st}_R$). A bipartition separates its local and correlation
contributions.

To try an editable state comparison in the same environment:

```bash
python3 -m rcc_refcert probe export w1-quantum-organization > windows.json
python3 -m rcc_refcert window analyze windows.json --bundle windows.rccbundle
```

On this four-qubit reference, two Bell pairs and a GHZ state both give a global
reading of 2 R-structons. Within one Bell pair the reading is 1, and across
the two pairs it is 0. In the GHZ state either pair retains one shared
classical bit, giving a reading of 1/2. The windows locate structure that a
single global reading leaves unresolved.

The [window guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c0a9eecd8fa5ce082b29bb30608acfb8c7b24ffe/docs/COST_AND_WINDOWS.md#subsystem-complexity-profiles)
works through the local and correlation contributions on that common scale. To use [your own density matrix](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c0a9eecd8fa5ce082b29bb30608acfb8c7b24ffe/docs/COST_AND_WINDOWS.md#your-own-matrix-and-tensor-labels),
supply the matrix, its tensor dimensions and the subsystems to compare.
The [workflow notebook](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c5ecafef6f80c0c4519db1dba19b9ca093268dc0/RCC_Workflows_Quickstart.ipynb)
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
**Historical results supported** together. A fresh matrix check can pass
with a larger conservative constant than the one used in the original bound.

A colleague can verify the bundle with the installed package. Use `--output`
to save the verification report under a new filename. The
[analysis-bundle guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c5ecafef6f80c0c4519db1dba19b9ca093268dc0/docs/ANALYSIS_BUNDLES.md) explains result comparisons,
exit codes and the original counts protocol. Exact historical scalar replay
uses the producer's package version. Preparation-cost and known-state window
bundles are readable from 0.3.0
(0.4.0 for requests using `on_gain_failure`). Use 0.4.0 or later for
fixed-effect counts, measured windows and finite-data studies. The same
verification command recomputes their results from the archived inputs.

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
| [Models and certificates](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/1fbdfd03aa2df3ad45081098477dc974dc002084/RCC_Quickstart.ipynb) | Analyze finite-control models, verify reference certificates and reproduce paper calculations. |
| [Terminal-state bounds](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/1fbdfd03aa2df3ad45081098477dc974dc002084/RCC_Bounds_Quickstart.ipynb) | Calculate bounds from exact spectra or fixed-projector counts, then save and replay the result. |
| [Preparation costs and complexity profiles](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c5ecafef6f80c0c4519db1dba19b9ca093268dc0/RCC_Workflows_Quickstart.ipynb) | Compare preparation costs, use window RCC to study states and cooling trajectories, and share complete evidence. |

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

The [model guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/1fbdfd03aa2df3ad45081098477dc974dc002084/docs/MODEL_GUIDE.md) shows how to build a model with `Action`
and `FiniteControlModel`, audit it, and verify supplied certificates. For
target-state calculations, the [bounds guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c5ecafef6f80c0c4519db1dba19b9ca093268dc0/docs/TERMINAL_BOUNDS.md) covers
`bound_from_spectrum`, `bound_from_counts`, `prepare_protocol`,
`with_reference_certificate`, `validate_record` and `replay_record`.

For preparation costs and subsystem complexity profiles, import from
`rcc_refcert.workflows`.
The [workflow guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c0a9eecd8fa5ce082b29bb30608acfb8c7b24ffe/docs/COST_AND_WINDOWS.md) introduces
`analyze_cost`, `compare_cost_results`, `analyze_windows`, `export_probe` and
`save_workflow_bundle` with executable examples.

## Why reference-contingent complexity

Preparing a pure qubit illustrates why the resource accounting matters.
A reset operation can produce $\lvert0\rangle$ in a single step, but the
physical process that removes entropy may be absent from a gate count.
Likewise, a supplied pure ancilla already contains structure that a
preparation procedure can use. The same target can therefore have different
costs depending on what the background supplies and which operations are
charged.

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
relational physical quantity. Changing the reference calls for a corresponding
update of the physical model.

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

For the unbiased reference $\sigma_R=\Pi_R/d_R$, the state-side RCC value is
$C_R(\rho)=[\log_2 d_R-S(\rho)]/\log_2\Gamma_R$, where $\Gamma_R$ counts
distinct physical action classes per atomic slot. The reference sets the
structural zero point, and the control bandwidth $g_R=\log_2\Gamma_R$ sets the
resource scale. The entropy deficit divided by this bandwidth is a complexity
reading in R-structons
($\mathrm{st}_R$), with $1 \mathrm{st}_R=g_R$ bits. It is the linear leading term
of the lower bound under the paper's regularity conditions. The full one-shot
bound also retains spectral
skew, smoothing loss, and transcription and reference overheads. The
[scientific scope](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c5ecafef6f80c0c4519db1dba19b9ca093268dc0/docs/SCIENTIFIC_SCOPE.md#from-state-information-to-process-cost)
gives their precise relation and units.

With the model qualifications established and the measurement protocol fixed
in advance, endpoint statistics can thus certify a minimum cost without
reconstructing the preparation history.

The package exposes the model inputs, numerical certificate checks, and
scalar cost inversion that make such examples reproducible. The
[scientific scope](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c5ecafef6f80c0c4519db1dba19b9ca093268dc0/docs/SCIENTIFIC_SCOPE.md)
explains the evidence each calculation supplies; the
[paper-to-code map](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/1fbdfd03aa2df3ad45081098477dc974dc002084/docs/PAPER_MAP.md)
connects the implementation to the full model construction and lower-bound
theorem.

> **Manuscript alignment.** This source tree is aligned with version 4 of the
> [RCC manuscript](https://arxiv.org/abs/2509.18205)
> ([fixed V4](https://arxiv.org/abs/2509.18205v4)). Appendix labels and
> equation numbers refer to manuscript version 4.

<a id="end-to-end-rcc-lower-bound-example"></a>

The [worked lower-bound example](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/1fbdfd03aa2df3ad45081098477dc974dc002084/docs/END_TO_END_EXAMPLE.md)
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
The [paper-to-code map](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/1fbdfd03aa2df3ad45081098477dc974dc002084/docs/PAPER_MAP.md)
locates the corresponding definitions and equations.

## Results and scientific scope

Finite-control matrix and certificate checks report `pass`, `fail`, `inconclusive` or
`not_applicable`, with an explicit evidence level, currently `numerical`.
These outcomes describe finite-input and fixed-model checks. The
[scientific scope](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c5ecafef6f80c0c4519db1dba19b9ca093268dc0/docs/SCIENTIFIC_SCOPE.md) connects them to the RCC theorem
and its physical, transcription and family-uniformity requirements.

Terminal-state records distinguish the scalar calculation's enclosure,
numerical certificate evidence and sampling confidence. A zero lower bound on its own leaves the optimum open.
The report explains which input or measurement led to that result.
The [output contract](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c5ecafef6f80c0c4519db1dba19b9ca093268dc0/docs/OUTPUT_CONTRACT.md) explains fields and exit codes.

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
[model guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/1fbdfd03aa2df3ad45081098477dc974dc002084/docs/MODEL_GUIDE.md#numerical-and-resource-limits)
describes limits and certificate error budgets.

## Further reading

The guides include current explanations. The
[version 0.3.0 source tree](https://github.com/yeruciwenrou-dotcom/rcc-refcert/tree/v0.3.0)
preserves the documentation shipped with that release. The
[0.3.0 release notes](https://github.com/yeruciwenrou-dotcom/rcc-refcert/releases/tag/v0.3.0) describe the earlier cost and subsystem workflows. The [0.4.0 research studies](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/9929c34b1a585b3b64505e33b31bbafb03067ad3/docs/FINITE_DATA_STUDIES.md) add raw counts, local measurement settings and hardware register mapping.

- [Scientific scope](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c5ecafef6f80c0c4519db1dba19b9ca093268dc0/docs/SCIENTIFIC_SCOPE.md): what each calculation establishes and how it connects to RCC.
- [Paper-to-code map](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/1fbdfd03aa2df3ad45081098477dc974dc002084/docs/PAPER_MAP.md): implemented objects, equations and worked examples.
- [Conventions](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/1fbdfd03aa2df3ad45081098477dc974dc002084/docs/CONVENTIONS.md): numerical, tensor and exact-input conventions.
- [Output contract](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c5ecafef6f80c0c4519db1dba19b9ca093268dc0/docs/OUTPUT_CONTRACT.md): result fields, evidence levels and exit codes.
- [Section VII.B of the paper](https://arxiv.org/pdf/2509.18205v4#page=26) discusses how RCC relates to other physical notions of complexity, including the holographic CV and CA proposals.

### Extending the research kernel

Use [GitHub Issues](https://github.com/yeruciwenrou-dotcom/rcc-refcert/issues)
to report a problem, suggest a scientific extension or improve an explanation.

Contributions can add physical models, certificate constructions, stronger
numerical verification, terminal-state methods or interfaces for new research
tasks. The [contribution guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c5ecafef6f80c0c4519db1dba19b9ca093268dc0/CONTRIBUTING.md) explains the scientific
contracts, expected evidence and development checks for each kind of change.

For development setup, tests, formatting and package builds, follow
[local verification](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c5ecafef6f80c0c4519db1dba19b9ca093268dc0/CONTRIBUTING.md#local-verification).

### Repository structure

| Path | Contents |
|---|---|
| `src/rcc_refcert/` | Model, certificate, bound, cost and window APIs; CLI and evidence formats |
| `examples/` | Paired-reset, alternating-qubit, cyclic-register and numerical candidate workflows |
| `RCC*Quickstart.ipynb` | Executable model, bound, cost and window tutorials |
| `results/` | Frozen reference report and structured data |
| `generated_results/` | Local verification results generated by quickstart; ignored by Git |
| `docs/`, `tests/` | Detailed guides and scientific/interface regressions |

<a id="development-citation-and-license"></a>

## Citation and license

Cite the software version used and the associated RCC paper.
[`CITATION.cff`](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/1fbdfd03aa2df3ad45081098477dc974dc002084/CITATION.cff) provides both citation records. The
[all-versions DOI](https://doi.org/10.5281/zenodo.22544967) identifies the
software archive across releases.

For a calculation made with version 0.3.0, a copyable citation is:

> Liu, HongZheng; Tian, YiNuo; and Wu, Zhiyue. *RCC RefCert: A Research Toolkit
> for Structure-Fair Quantum Circuit Complexity*. Version 0.3.0,
> 2026. https://doi.org/10.5281/zenodo.24248347

The GitHub **Cite this repository** button follows the paper preference in
`CITATION.cff`; include the software version citation as well when reporting a
calculation. Complete bundles can
[record the source revision](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c5ecafef6f80c0c4519db1dba19b9ca093268dc0/docs/ANALYSIS_BUNDLES.md#record-the-software-revision)
for both the author and the recipient.

For calculations made with a source checkout, record its full commit and
package version. To reproduce a source version, check out that commit or a
release tag before installation. The software archive provides a separate DOI
for each archived release as well as the all-versions DOI above.

See the [Changelog](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/c5ecafef6f80c0c4519db1dba19b9ca093268dc0/CHANGELOG.md) for release changes and subsequent updates. The source code
is available under the [MIT License](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.3.0/LICENSE).
