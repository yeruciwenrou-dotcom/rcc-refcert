# rcc-refcert

[![arXiv: 2509.18205](https://raw.githubusercontent.com/yeruciwenrou-dotcom/rcc-refcert/main/docs/assets/arxiv.svg)](https://arxiv.org/abs/2509.18205)
[![PyPI](https://img.shields.io/pypi/v/rcc-refcert.svg?label=PyPI)](https://pypi.org/project/rcc-refcert/)
[![0.2.0 DOI](https://img.shields.io/badge/0.2.0_DOI-10.5281%2Fzenodo.23625478-darkgreen)](https://doi.org/10.5281/zenodo.23625478)

`rcc-refcert` is a Python research toolkit for **structure-fair quantum circuit
complexity**.
It audits small finite-control quantum models, verifies reference certificates,
and computes **conditional lower bounds on state-preparation cost** from exact
target spectra or predeclared measurement counts.

The toolkit implements selected parts of **Reference-Contingent Complexity
(RCC)**, introduced in
[*Structure-Fair Quantum Circuit Complexity: An Auditable Information-Theoretic Lower Bound*](https://arxiv.org/abs/2509.18205).

The same quantum state may be supplied by one physical background and require
entropy removal and control in another. **Structural fairness** makes this
distinction explicit: structure stably supplied by the background sets the
reference zero point, while the operations and resources that generate
additional target-directed structure are counted. Within an admissible model,
**RCC** uses final-state information relative to that reference to bound the
cost of every successful preparation process, without reconstructing how the
state was produced.

For example, the [paired-reset model](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/END_TO_END_EXAMPLE.md) has an
integer lower bound of **one primitive slot**, attained by an explicit
one-slot preparation. The [four-qubit workflow](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/CUSTOM_MODELS.md#cyclic-noisy-reset-register)
gives a lower bound of **two slots**, while its separately established optimum
is five. A lower bound need not equal the cost of the best process.

You supply the model's channels, reference state, control language, and cost
assumptions, together with the target-state inputs for a bound calculation.
The package returns numerical checks and a reproducible record of the bound.
A complete analysis bundle also carries the model and proof arrays so another
researcher can reverify the calculation without the original modeling script.

The [conceptual introduction](#why-reference-contingent-complexity) explains
the research question; the [scientific scope](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/SCIENTIFIC_SCOPE.md)
connects the implemented checks to the RCC framework.

## Start here

| Your task | What you obtain | Entry point |
|---|---|---|
| Reproduce the reference results | Model audits checked against frozen numerical evidence | [Published package](#install-from-pypi) or [current source](#quick-start) |
| Calculate a preparation-cost lower bound | A bound from an exact target spectrum or predeclared measurement counts | [Terminal-state workflow](#target-spectra-and-measured-counts) |
| Analyze your own finite-control model | Numerical certificate checks, conditional bounds, and shareable inputs | [Custom-model workflow](#work-with-your-own-model) |
| Reverify a shared analysis | Fresh matrix checks and a comparison with historical results | [Recipient workflow](#reverify-a-shared-analysis) |

You can also [read the reference results](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/results/reference_report.md)
without running code, or follow either [Jupyter notebook](#jupyter-notebook).

## Install from PyPI

Use a Python 3.10 or newer environment:

```bash
python3 -m pip install "rcc-refcert==0.2.0"
python3 -m rcc_refcert examples
python3 -m rcc_refcert reproduce --check
```

Use `python` instead of `python3` when that is your interpreter's name.
The API, CLI, and frozen reference data work outside a source checkout.
The check should report `MATCH` for the reference expectations, data, and report.
The [reference cases](#reference-cases) explain the deliberately failed
sufficient route and the nonhalting boundary among those expected results.

The installed package includes candidate preparation and bundle verification.
For the example scripts and notebooks, use the source quickstart below.

## Quick start

To run the example scripts and notebooks for **0.2.0**, clone its release tag:

```bash
git clone --branch v0.2.0 https://github.com/yeruciwenrou-dotcom/rcc-refcert.git
cd rcc-refcert
python3 --version
python3 quickstart.py --reproduce-only
```

Python 3.10 or newer is required. On Windows, or where your interpreter is
named `python`, use `python` in place of `python3`. You can also select the `v0.2.0`
tag on GitHub, choose **Code → Download ZIP**, and run the last two commands
from the extracted directory containing `quickstart.py`.

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

## Work with your own model

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
Both bound paths for this register return **two primitive slots**; a separate
analysis establishes its five-slot optimum.

Each command saves a bundle containing the model, certificate and results.
Choose an unused filename. Follow the [custom-model guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/CUSTOM_MODELS.md)
to replace the channels, states, control language and cost assumptions, then
verify your certificate and add a supported target-state task. The guide
explains the two certificate routes and their numerical limits.

## Reverify a shared analysis

Use the cyclic-reset bundle above, or substitute a file you received:

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
[analysis-bundle guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/ANALYSIS_BUNDLES.md) explains result comparisons,
exit codes and the original counts protocol. Exact historical scalar replay
uses the producer's package version.

## Jupyter notebook

After the [source quickstart](#quick-start), install the optional notebook
dependencies and register its environment:

```bash
.venv/bin/python -m pip install -e ".[notebook]"
.venv/bin/python -m ipykernel install --user --name rcc-refcert --display-name "Python (rcc-refcert)"
.venv/bin/python -m jupyterlab
```

Open `RCC_Quickstart.ipynb` for reference-model audits or
`RCC_Bounds_Quickstart.ipynb` for spectra, fixed-projector counts and replay.
Select **Python (rcc-refcert)** as the kernel. Run all three commands with the
same interpreter; on Windows, use `.venv\Scripts\python.exe`. These dependencies
are optional and do not enter the runtime package.

## Target spectra and measured counts

After the [source quickstart](#quick-start), create an input template, calculate
a bound, save its record and replay it:

```bash
.venv/bin/python -m rcc_refcert bound template spectrum > spectrum.json
.venv/bin/python -m rcc_refcert bound spectrum spectrum.json
.venv/bin/python -m rcc_refcert bound spectrum spectrum.json --format json > bound.json
.venv/bin/python -m rcc_refcert bound replay bound.json
```

The template declares a four-dimensional model and a complete exact spectrum.
Expect an integer-slot lower bound of **one**. To try synthetic measurement
counts with 550 hits in 1000 trials:

```bash
.venv/bin/python -m rcc_refcert bound template counts > counts.json
.venv/bin/python -m rcc_refcert bound counts counts.json
```

For real measurements, fix the protocol **before collecting data** with
`bound prepare-protocol` and preserve its digest with the dataset. The
[terminal-state guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/TERMINAL_BOUNDS.md) explains the projector,
sample-size and evidence requirements.

Both routes use a uniform reference on an ideal support and exact transcription.
The cost bound depends on the declared model premises; sampling coverage
describes the counts alone. Templates are installed package resources, so
these commands also work outside the checkout when run with the installed
environment's interpreter.

## End-to-end RCC lower-bound example

The [paired-reset example](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/END_TO_END_EXAMPLE.md) follows one qubit from
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

The [model guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/MODEL_GUIDE.md) shows how to build a model with `Action`
and `FiniteControlModel`, audit it, and verify supplied certificates. For
target-state calculations, the [bounds guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/TERMINAL_BOUNDS.md) covers
`bound_from_spectrum`, `bound_from_counts`, `prepare_protocol`,
`with_reference_certificate`, `validate_record` and `replay_record`.

## Results and scientific scope

Model and certificate checks report `pass`, `fail`, `inconclusive` or
`not_applicable`, with an explicit evidence level, currently `numerical`.
These outcomes describe finite-input and fixed-model checks. The
[scientific scope](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/SCIENTIFIC_SCOPE.md) connects them to the RCC theorem
and its physical, transcription and family-uniformity requirements.

Terminal-state records distinguish the scalar calculation's enclosure,
numerical certificate evidence and sampling confidence. A completed zero lower
bound is a valid result; it does not establish zero preparation cost.
The [output contract](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/OUTPUT_CONTRACT.md) explains fields and exit codes.

The explicit matrix and path algorithms target small finite models. Resource
budgets are checked before enumeration or dense matrix construction, and
unresolved precision is reported explicitly. The
[model guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/MODEL_GUIDE.md#numerical-and-resource-limits)
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
[scientific scope](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/SCIENTIFIC_SCOPE.md#from-state-information-to-process-cost)
gives their precise relation and units.

With the model qualifications established and the measurement protocol fixed
in advance, endpoint statistics can thus certify a minimum cost without
reconstructing the preparation history.

The [paired-reset example](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/END_TO_END_EXAMPLE.md)
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
[scientific scope](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/SCIENTIFIC_SCOPE.md)
explains the evidence each calculation supplies; the
[paper-to-code map](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/PAPER_MAP.md)
connects the implementation to the full model construction and lower-bound
theorem.

> **Manuscript alignment.** This source tree is aligned with version 4 of the
> [RCC manuscript](https://arxiv.org/abs/2509.18205)
> ([fixed V4](https://arxiv.org/abs/2509.18205v4)). Appendix labels and
> equation numbers refer to manuscript version 4.

## What this repository implements

| Area | Available calculations | Guide |
|---|---|---|
| Finite-control models | Code-weighted trajectories, terminating program semidensities, least fixed points and reference domination | [Model guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/MODEL_GUIDE.md) |
| Reference certificates | Linear H.3 candidate preparation for stable finite models, independent H.3/H.4 verification, and local gain–cost checks with sufficient code completions | [Custom models](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/CUSTOM_MODELS.md) |
| Terminal-state bounds | Exact-spectrum smoothing, fixed-projector counts, certificate binding and scalar cost inversion | [Terminal-state bounds](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/TERMINAL_BOUNDS.md) |
| Reproducible evidence | Frozen Appendix F/H cases, same-version scalar replay, and complete model/proof bundles for fresh verification | [Analysis bundles](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/ANALYSIS_BUNDLES.md) |

The [paper-to-code map](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/PAPER_MAP.md) locates each implemented object in
the RCC argument. Together these tools let researchers examine the supplied
structure and generation costs of explicit quantum-complexity models.

## Further reading

| Question | Guide |
|---|---|
| What do the checks establish? | [Scientific scope](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/SCIENTIFIC_SCOPE.md) |
| How do paper formulas map to code? | [Paper-to-code map](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/PAPER_MAP.md) |
| How are numerical and tensor conventions fixed? | [Conventions](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/CONVENTIONS.md) |
| How should I interpret result fields and exit codes? | [Output contract](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/OUTPUT_CONTRACT.md) |
| How can I extend or contribute to the toolkit? | [Contributing](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/CONTRIBUTING.md) |

## Extending the research kernel

Contributions can add physical models, certificate constructions, stronger
numerical verification, terminal-state methods or interfaces for new research
tasks. The [contribution guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/CONTRIBUTING.md) explains the scientific
contracts, expected evidence and development checks for each kind of change.

## Repository structure

| Path | Contents |
|---|---|
| `src/rcc_refcert/` | Model, certificate and bounds APIs; CLI and evidence formats |
| `examples/` | Paired-reset, alternating-qubit and cyclic-register workflows |
| `RCC_Quickstart.ipynb`, `RCC_Bounds_Quickstart.ipynb` | Executable model and bounds tutorials |
| `results/` | Frozen reference report and structured data |
| `generated_results/` | Local verification results generated by quickstart; ignored by Git |
| `docs/`, `tests/` | Detailed guides and scientific/interface regressions |

## Development, citation, and license

For development setup, tests, formatting and package builds, follow
[Contributing](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/CONTRIBUTING.md#local-verification).

Cite the software version used and the associated RCC paper.
[`CITATION.cff`](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/CITATION.cff) provides both citation records. The
[all-versions DOI](https://doi.org/10.5281/zenodo.22544967) identifies the
software archive across releases.

For a calculation made with this version, a copyable citation is:

> Liu, HongZheng; Tian, YiNuo; and Wu, Zhiyue. *rcc-refcert: a Python research
> toolkit for structure-fair quantum circuit complexity*. Version 0.2.0,
> 2026. https://doi.org/10.5281/zenodo.23625478

The GitHub **Cite this repository** button follows the paper preference in
`CITATION.cff`; include the software version citation as well when reporting a
calculation. Complete bundles can
[record the source revision](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/docs/ANALYSIS_BUNDLES.md#record-the-software-revision)
for both the author and the recipient.

See the [Changelog](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/CHANGELOG.md) for this version's changes. The source code
is available under the [MIT License](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/v0.2.0/LICENSE).
