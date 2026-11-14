# rcc-refcert

[![arXiv: 2509.18205](https://raw.githubusercontent.com/yeruciwenrou-dotcom/rcc-refcert/main/docs/assets/arxiv.svg)](https://arxiv.org/abs/2509.18205)
[![PyPI](https://img.shields.io/pypi/v/rcc-refcert.svg?label=PyPI)](https://pypi.org/project/rcc-refcert/)
[![0.2.0 DOI](https://img.shields.io/badge/0.2.0_DOI-10.5281%2Fzenodo.23625478-darkgreen)](https://doi.org/10.5281/zenodo.23625478)

`rcc-refcert` is a Python research toolkit for **structure-fair quantum circuit
complexity**.
It analyzes finite-control quantum models, verifies reference certificates,
and computes **quantum circuit complexity lower bounds** from exact target
spectra or predeclared measurement counts. Researchers can also compare
candidate preparations, study how structure is distributed across subsystems,
and share complete calculations for independent verification.

The toolkit implements selected parts of **Reference-Contingent Complexity
(RCC)**, introduced in
[*Structure-Fair Quantum Circuit Complexity: An Auditable Information-Theoretic Lower Bound*](https://arxiv.org/abs/2509.18205).

The same quantum state may be supplied by one physical background and require
entropy removal and control in another. **Structural fairness** makes this
distinction explicit: structure stably supplied by the background sets the
reference zero point, while the operations and resources that generate
additional target-directed structure are counted. Within an admissible model,
**RCC** proves a rigorous lower bound on universal optimal quantum circuit
complexity. Final-state information relative to the reference bounds the
cost of every successful preparation history, without reconstructing how the
state was produced.

## Start here

| What you have | What you can study | Start here |
|---|---|---|
| Channels, control rules and a reference state | Reference certificates and the resources of a finite quantum model | [Your own model](#work-with-your-own-model) |
| An exact target spectrum or predeclared measurement counts | A quantum circuit complexity lower bound in the declared model | [Spectra and counts](#target-spectra-and-measured-counts) |
| A complete target, a channel model and candidate programs | Target attainment and preparation-cost intervals for exact diagonal recipes | [Cost tasks](#cost-and-window-workflows) |
| Density matrices and subsystem labels | Entropy deficits, correlations and structure along a preparation | [State windows and probes](docs/COST_AND_WINDOWS.md#state-windows-and-probes) |
| A shared analysis bundle | Fresh calculations and their support for the saved results | [Reverify an analysis](#reverify-a-shared-analysis) |
| A calculation from the RCC paper | Its model, equations and reproducible example | [Paper-to-code map](docs/PAPER_MAP.md) · [Worked bound](#end-to-end-rcc-lower-bound-example) |

The 0.3 source series adds preparation-cost intervals and subsystem windows.
Editable reset and cooling tasks, three research probes and a workflow notebook
connect these calculations to complete analyses that can be shared and reverified.

For the physical motivation and how the bound works, see
[Why reference-contingent complexity](#why-reference-contingent-complexity).

You can also [read the reference results](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/results/reference_report.md)
without running code, or choose a [Jupyter tutorial](#jupyter-notebook).

## Quick start

Install the **0.3 source series** once, then choose a task below. The published
package and version DOI remain **0.2.0**; [install from PyPI](#install-from-pypi)
for its model, certificate and terminal-state tools.

The following commands obtain the source attached to
[the 0.3 workflow update](https://github.com/yeruciwenrou-dotcom/rcc-refcert/pull/40):

```bash
git clone https://github.com/yeruciwenrou-dotcom/rcc-refcert.git
cd rcc-refcert
git fetch origin pull/40/head
git checkout --detach FETCH_HEAD
python3 --version
python3 quickstart.py --reproduce-only
```

Python 3.10 or newer is required. On Windows, or where your interpreter is
named `python`, use `python` in place of `python3`. If you already have this
source checkout or a source ZIP, run the last two commands in the directory
containing `quickstart.py`.

For the frozen **0.2.0** examples, add `--branch v0.2.0` to the clone command
and omit the two pull-request fetch and checkout commands.
That release includes the model and terminal-state notebooks; the cost and
window notebook belongs to the 0.3 source series.

The script creates `.venv`, installs the locked verification dependencies,
checks the frozen reference evidence, and writes fresh results to
`generated_results/`. Expect three `MATCH` checks. Run `python3 quickstart.py`
to include the test suite. Later runs reuse the environment and refresh the
installation when the dependency lock or package metadata changes.

**For the examples below, stay in the checkout directory and use
`.venv/bin/python`.** On Windows, substitute `.venv\Scripts\python.exe`.
If you prefer your own active environment, install with
`python -m pip install .` and use that environment's interpreter throughout.
The module entry point accepts the same arguments as `rcc-refcert`.

To reproduce a particular source version, check out its full commit or release
tag before installation.

## Cost and window workflows

Use the environment created by the [source quickstart](#quick-start), then run
these commands from the checkout. On Windows, replace `.venv/bin/python` with
`.venv\Scripts\python.exe`:

```bash
.venv/bin/python -m rcc_refcert cost template cyclic-reset > task.json
.venv/bin/python -m rcc_refcert cost analyze task.json --bundle task.rccbundle
.venv/bin/python -m rcc_refcert bundle verify task.rccbundle
```

This exact recipe starts from a diagonal state and preserves diagonality.
The four-qubit reset task gives a rigorous **[5,5]** preparation-cost interval:
every successful program needs at least five atomic slots, and an executed
five-slot program reaches the target. The model charges halt as one slot.
Changing the tolerance gives **[4,4]** or **[4,5]**, showing when the evidence
determines the optimum and when a gap remains.

To examine state organization, export a probe and analyze its windows:

```bash
.venv/bin/python -m rcc_refcert probe export w1-quantum-organization > windows.json
.venv/bin/python -m rcc_refcert window analyze windows.json --bundle windows.rccbundle
```

Paired Bell states and a GHZ state have the same global spectrum. Their window
profiles locate that structure differently across the register. The other
probes compare phase-noise distributions and follow an algorithmic-cooling
trajectory. Each probe supplies editable inputs and a reference comparison.

The [workflow guide](docs/COST_AND_WINDOWS.md) covers changing the target and
tolerance, cooling, your own matrices, window probes, reports and independent
revalidation. [RCC_Workflows_Quickstart.ipynb](RCC_Workflows_Quickstart.ipynb)
provides the same path in a notebook.
The source installation also provides the model and terminal-state workflows
below. The next section offers the published package as a separate starting point.

## Install from PyPI

In a new working directory, use your Python 3.10 or newer environment to
install **0.2.0** and calculate a first bound:

```bash
python3 -m pip install "rcc-refcert==0.2.0"
python3 -m rcc_refcert bound template spectrum > spectrum.json
python3 -m rcc_refcert bound spectrum spectrum.json
```

Use `python` instead of `python3` when that is your interpreter's name.
The template supplies a complete exact spectrum for a four-dimensional target
and declared model parameters. Expect an integer lower bound of **one primitive
slot**: under those parameters, every successful preparation must incur at least
that cost. The [spectra and counts workflow](#target-spectra-and-measured-counts)
shows how to save a record and use measurement inputs; the
[terminal-state guide](docs/TERMINAL_BOUNDS.md)
explains how to supply your own task.

To list the bundled cases and reproduce the paper's reference calculations:

```bash
python3 -m rcc_refcert examples
python3 -m rcc_refcert reproduce --check
```

Expect three `MATCH` checks for the reference expectations, data, and report.
The [reference cases](#reference-cases) explain the deliberately failed
sufficient route and the nonhalting boundary among those expected results.

The API, CLI, templates, and frozen reference data work outside a source
checkout. The installed package also includes candidate preparation and bundle
verification. For the example scripts and notebooks, use the
[source quickstart](#quick-start).

## Work with your own model

You supply the model's channels, reference state, control language, and cost
assumptions, together with the target-state inputs for a bound calculation.
The package returns numerical checks and a reproducible record of the bound.
A complete analysis bundle also carries the model and proof arrays so another
researcher can reverify the calculation without the original modeling script.

After the [source installation](#quick-start), run these examples:

```bash
.venv/bin/python examples/custom_model_workflow.py --bundle alternating.rccbundle
.venv/bin/python examples/cyclic_reset_workflow.py --bundle cyclic-reset.rccbundle
```

The first builds an alternating qubit model and prepares a **Bellman–Choi
certificate (H.3)** for its reference-domination bound. Independent
verification passes even though a local sufficient test fails.
The second uses a **reference-potential certificate (H.4)** for a four-qubit
register, then computes bounds from an exact spectrum and synthetic counts.
Both bound paths for this register return **two primitive slots**. The new
[complete cost workflow](docs/COST_AND_WINDOWS.md#a-complete-cost-task) independently
verifies the five-slot optimum with gain exclusion and a matching program.

Each command saves a bundle containing the model, certificate and results.
Choose an unused filename. Follow the [custom-model guide](docs/CUSTOM_MODELS.md)
to replace the channels, states, control language and cost assumptions, then
verify your certificate and add a supported target-state task. The guide
explains the two certificate routes and their numerical limits.

## Reverify a shared analysis

Use the cyclic-reset certificate bundle above, or substitute a file you received:

```bash
.venv/bin/python -m rcc_refcert bundle inspect cyclic-reset.rccbundle
.venv/bin/python -m rcc_refcert bundle verify cyclic-reset.rccbundle --output cyclic-reset-verification.json
```

`inspect` checks the saved data for consistency. `verify` checks the model and
certificate matrices afresh, recomputes supported bounds, and compares them
with the saved results. Read **Fresh matrix verification** and
**Historical results supported** together: a passing matrix check can yield a
larger conservative constant and leave an earlier, stronger result unsupported.

The installed package and bundle are sufficient for verification; the sender's
model script is unnecessary. The original bundle is preserved, and `--output`
saves a separate report under an unused filename. The
[analysis-bundle guide](docs/ANALYSIS_BUNDLES.md) explains result comparisons,
exit codes and the original counts protocol. Exact historical scalar replay
uses the producer's package version. Cost and window bundles require the 0.3
reader and use the same commands; verification executes their saved requests
and compares the new scientific results with the author's evidence.

## Jupyter notebook

After the [source quickstart](#quick-start), install the optional notebook
dependencies and register its environment:

```bash
.venv/bin/python -m pip install -e ".[notebook]"
.venv/bin/python -m ipykernel install --user --name rcc-refcert --display-name "Python (rcc-refcert)"
.venv/bin/python -m jupyterlab
```

Choose a notebook for the task you want to explore:

| Notebook | Task |
|---|---|
| [RCC_Workflows_Quickstart.ipynb](RCC_Workflows_Quickstart.ipynb) | Preparation-cost intervals, subsystem windows, cooling and shared evidence |
| [RCC_Quickstart.ipynb](RCC_Quickstart.ipynb) | Finite-control models, reference certificates and paper calculations |
| [RCC_Bounds_Quickstart.ipynb](RCC_Bounds_Quickstart.ipynb) | Exact spectra, fixed-projector counts and scalar replay |

Select **Python (rcc-refcert)** as the kernel. Run all three commands with the
same interpreter; on Windows, use `.venv\Scripts\python.exe`. These dependencies
are optional and do not enter the runtime package.

## Target spectra and measured counts

Use the Python environment where you [installed the package](#install-from-pypi).
The following commands create an input template, calculate a bound, save its
record and replay it:

```bash
python3 -m rcc_refcert bound template spectrum > spectrum.json
python3 -m rcc_refcert bound spectrum spectrum.json
python3 -m rcc_refcert bound spectrum spectrum.json --format json > bound.json
python3 -m rcc_refcert bound replay bound.json
```

Use `python` instead of `python3` if that is your environment's interpreter.
In the [source quickstart](#quick-start) environment, stay in the checkout and
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
[terminal-state guide](docs/TERMINAL_BOUNDS.md)
explains the projector, sample-size and evidence requirements.

Both routes use a uniform reference on an ideal support and exact transcription.
The cost bound depends on the declared model premises; sampling coverage
describes the counts alone. These templates and commands are available directly
from the installed package.

## End-to-end RCC lower-bound example

The [paired-reset example](docs/END_TO_END_EXAMPLE.md) follows one qubit from
its physical model through reference certification to Theorem 3.1. Its
final-state information gap is

$$
D_{\max}^{0}(\lvert0\rangle\langle0\rvert\Vert I/2)
=1\ \mathrm{bit}
=1\thinspace\mathrm{st}_R.
$$

Appendix A's cost inversion gives
$C_{\mathrm{opt}}^{(0)}\ge1$ atomic resource slot under the model's stated
inputs. The permitted program `0` prepares the target in one slot, so the
optimum for this fixed model is exactly one.

Run it from the checkout:

```bash
.venv/bin/python examples/paired_reset_lower_bound.py
.venv/bin/python examples/paired_reset_lower_bound.py --json
```

The worked explanation connects the numerical checks, analytic model
arguments and matching feasible preparation.

## Reference cases

| Case | Scientific role | Intended result |
|---|---|---|
| `dephase-or-halt` | Transparent closed-form realization | Every supplied route passes |
| `multiblock-rectangular` | Direct-sum, rectangular-Kraus, and certificate diagnostic | H.1–H.4 pass; the original codewords fail H.70 as designed; H.76 supplies a passing re-encoding |
| `dark-nonhalting` | Least-fixed-point boundary with a recurrent nonhalting sector | The process remains valid; the linear inverse is unavailable and H.34 remains unevaluated |

The designed H.70 failure identifies codewords that do not meet that local
sufficient criterion. The same model passes the supplied H.3 and H.4 checks;
its original program prior can qualify through those routes.

## Python API

Audit a bundled model directly:

```python
from rcc_refcert import audit_case, get_case

result = audit_case(get_case("multiblock-rectangular"))
print(result.matches_expectations)
print(result.model_analysis.fixed_model_domination.constant)
print(result.gain_cost.outcome.value)
```

The values are `True`, `15/14` numerically, and `"fail"` for the deliberately
failed local test described above. The model still passes its supplied
Bellman–Choi and reference-potential certificate checks.

The [model guide](docs/MODEL_GUIDE.md) shows how to build a model with `Action`
and `FiniteControlModel`, audit it, and verify supplied certificates. For
target-state calculations, the [bounds guide](docs/TERMINAL_BOUNDS.md) covers
`bound_from_spectrum`, `bound_from_counts`, `prepare_protocol`,
`with_reference_certificate`, `validate_record` and `replay_record`.

## Results and scientific scope

Finite-control matrix and certificate checks report `pass`, `fail`, `inconclusive` or
`not_applicable`, with an explicit evidence level, currently `numerical`.
These outcomes describe finite-input and fixed-model checks. The
[scientific scope](docs/SCIENTIFIC_SCOPE.md) connects them to the RCC theorem
and its physical, transcription and family-uniformity requirements.

Terminal-state records distinguish the scalar calculation's enclosure,
numerical certificate evidence and sampling confidence. A completed zero lower
bound is a valid result; it does not establish zero preparation cost.
The [output contract](docs/OUTPUT_CONTRACT.md) explains fields and exit codes.

Exact diagonal recipes support rigorous model-specific cost intervals by combining
gain-based exclusion with an executed feasible program. Numerical matrix inputs
support candidate diagnostics and window profiles, with their numerical evidence
identified in the result. Window RCC values describe subsystem structure in the
declared reference scale; the full one-shot cost bound also uses the model and
accuracy corrections described below.

The explicit matrix and path algorithms target small finite models. Resource
budgets are checked before enumeration or dense matrix construction, and
unresolved precision is reported explicitly. The
[model guide](docs/MODEL_GUIDE.md#numerical-and-resource-limits)
describes limits and certificate error budgets.

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
distinct physical action classes per atomic slot. It gives the bandwidth-scaled
entropy deficit and the linear leading term of the lower bound under the
paper's regularity conditions. The full one-shot bound also retains spectral
skew, smoothing loss, and transcription and reference overheads. The
[scientific scope](docs/SCIENTIFIC_SCOPE.md#from-state-information-to-process-cost)
gives their precise relation and units.

With the model qualifications established and the measurement protocol fixed
in advance, endpoint statistics can thus certify a minimum cost without
reconstructing the preparation history.

The [paired-reset example](docs/END_TO_END_EXAMPLE.md)
makes the chain concrete. A qubit starts at the maximally mixed reference
$I/2$. Two reset directions, to $\lvert0\rangle$ and $\lvert1\rangle$, are
available before the target is chosen; their uniform average preserves the
reference. For the target $\lvert0\rangle$, the one-shot gap is one bit.
With the example's declared model constants and cost unit, the theorem gives
a lower bound of one atomic reset slot. A permitted one-slot preparation
supplies the matching upper bound, so the optimum is exactly one in this
fixed model.

The package exposes the model inputs, numerical certificate checks, and
scalar cost inversion that make such examples reproducible. The
[scientific scope](docs/SCIENTIFIC_SCOPE.md)
explains the evidence each calculation supplies; the
[paper-to-code map](docs/PAPER_MAP.md)
connects the implementation to the full model construction and lower-bound
theorem.

> **Manuscript alignment.** This source tree is aligned with version 4 of the
> [RCC manuscript](https://arxiv.org/abs/2509.18205)
> ([fixed V4](https://arxiv.org/abs/2509.18205v4)). Appendix labels and
> equation numbers refer to manuscript version 4.

## What this repository implements

| Area | Available calculations | Guide |
|---|---|---|
| Cost and state windows | Exact diagonal recipe-based cost intervals, complete program checks, subsystem organization and versioned probes | [Cost and windows](docs/COST_AND_WINDOWS.md) |
| Finite-control models | Code-weighted trajectories, terminating program semidensities, least fixed points and reference domination | [Model guide](docs/MODEL_GUIDE.md) |
| Reference certificates | Linear H.3 candidate preparation for stable finite models, independent H.3/H.4 verification, and local gain–cost checks with sufficient code completions | [Custom models](docs/CUSTOM_MODELS.md) |
| Terminal-state bounds | Exact-spectrum smoothing, fixed-projector counts, certificate binding and scalar cost inversion | [Terminal-state bounds](docs/TERMINAL_BOUNDS.md) |
| Reproducible evidence | Frozen Appendix F/H cases, scalar replay, and complete model, cost and window inputs for independent verification | [Analysis bundles](docs/ANALYSIS_BUNDLES.md) |

The [paper-to-code map](docs/PAPER_MAP.md) locates each implemented object in
the RCC argument. Together these tools let researchers examine the supplied
structure and generation costs of explicit quantum-complexity models.

## Further reading

| Question | Guide |
|---|---|
| What do the checks establish? | [Scientific scope](docs/SCIENTIFIC_SCOPE.md) |
| How do paper formulas map to code? | [Paper-to-code map](docs/PAPER_MAP.md) |
| How are numerical and tensor conventions fixed? | [Conventions](docs/CONVENTIONS.md) |
| How should I interpret result fields and exit codes? | [Output contract](docs/OUTPUT_CONTRACT.md) |
| How can I extend or contribute to the toolkit? | [Contributing](CONTRIBUTING.md) |

## Extending the research kernel

Contributions can add physical models, certificate constructions, stronger
numerical verification, terminal-state methods or interfaces for new research
tasks. The [contribution guide](CONTRIBUTING.md) explains the scientific
contracts, expected evidence and development checks for each kind of change.

## Repository structure

| Path | Contents |
|---|---|
| `src/rcc_refcert/` | Model, certificate, bound, cost and window APIs; CLI and evidence formats |
| `examples/` | Paired-reset, alternating-qubit, cyclic-register and numerical candidate workflows |
| `RCC_Quickstart.ipynb`, `RCC_Bounds_Quickstart.ipynb`, `RCC_Workflows_Quickstart.ipynb` | Executable model, bound, cost and window tutorials |
| `results/` | Frozen reference report and structured data |
| `generated_results/` | Local verification results generated by quickstart; ignored by Git |
| `docs/`, `tests/` | Detailed guides and scientific/interface regressions |

## Development, citation, and license

For development setup, tests, formatting and package builds, follow
[Contributing](CONTRIBUTING.md#local-verification).

Cite the software version used and the associated RCC paper.
[`CITATION.cff`](CITATION.cff) provides both citation records. The
[all-versions DOI](https://doi.org/10.5281/zenodo.22544967) identifies the
software archive across releases.

For a calculation made with the published 0.2.0 version, a copyable citation is:

> Liu, HongZheng; Tian, YiNuo; and Wu, Zhiyue. *rcc-refcert: a Python research
> toolkit for structure-fair quantum circuit complexity*. Version 0.2.0,
> 2026. https://doi.org/10.5281/zenodo.23625478

The GitHub **Cite this repository** button follows the paper preference in
`CITATION.cff`; include the software version citation as well when reporting a
calculation. Complete bundles can
[record the source revision](docs/ANALYSIS_BUNDLES.md#record-the-software-revision)
for both the author and the recipient.

For calculations made with a development checkout, record its full commit and
package version. The citation metadata and version DOI above identify the
published 0.2.0 release.

See the [Changelog](CHANGELOG.md) for release changes and subsequent updates. The source code
is available under the [MIT License](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/LICENSE).
