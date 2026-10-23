# rcc-refcert

[![arXiv: 2509.18205](https://raw.githubusercontent.com/yeruciwenrou-dotcom/rcc-refcert/main/docs/assets/arxiv.svg)](https://arxiv.org/abs/2509.18205)
[![PyPI](https://img.shields.io/pypi/v/rcc-refcert.svg?label=PyPI)](https://pypi.org/project/rcc-refcert/)
[![Archived 0.1.3 DOI](https://img.shields.io/badge/0.1.3_DOI-10.5281%2Fzenodo.22768920-blue)](https://doi.org/10.5281/zenodo.22768920)

`rcc-refcert` is a Python research toolkit for
**structure-fair quantum circuit complexity**: how much must be spent to
prepare a quantum state once the physical background, available operations,
and cost rules have been fixed?

Use it to build and audit small finite-control quantum models, verify
reference certificates, and compute conditional preparation-cost lower bounds
from exact target spectra or predeclared measurement counts. You supply the
model's channels, reference state, control language, and cost assumptions; the
package returns explicit numerical checks and reproducible bound records.
A complete analysis bundle also carries the model and proof arrays so another
researcher can reverify the calculation without the original modeling script.

The package implements selected parts of **Reference-Contingent Complexity
(RCC)**, introduced in
[*Structure-Fair Quantum Circuit Complexity: An Auditable Information-Theoretic Lower Bound*](https://arxiv.org/abs/2509.18205).
Within an RCC-admissible model, the theorem turns final-state information into
a cost floor shared by every successful preparation history. The toolkit makes
selected model checks and that cost inversion executable for declared finite
inputs.
The [conceptual introduction](#why-reference-contingent-complexity) explains
the research question; the [scientific scope](docs/SCIENTIFIC_SCOPE.md)
connects the implemented checks to the RCC framework.

> **Version.** This checkout is the **0.2.0rc1 development version**. Use the
> [source installation](#quick-start) for candidate preparation and complete
> analysis bundles. The published PyPI package and linked archive are **0.1.3**,
> with model audits, supplied-certificate verification, and scalar bounds.

## Start here

| Your task | What you obtain | Entry point |
|---|---|---|
| Reproduce the reference results | Model audits checked against frozen numerical evidence | [Published package](#install-from-pypi) or [current source](#quick-start) |
| Analyze your own finite-control model | Numerical certificate checks, conditional bounds, and shareable inputs | [Custom-model workflow](#work-with-your-own-model) |
| Reverify a shared analysis | Fresh matrix checks and a comparison with historical results | [Recipient workflow](#reverify-a-shared-analysis) |

For a target spectrum or predeclared counts alone, start with
[terminal-state bounds](#target-spectra-and-measured-counts).
You can also [read the reference results](results/reference_report.md)
without running code, or follow either [Jupyter notebook](#jupyter-notebook).

## Install from PyPI

For the published **0.1.3** capabilities, use a Python 3.10 or newer environment:

```bash
python3 -m pip install "rcc-refcert==0.1.3"
python3 -m rcc_refcert examples
python3 -m rcc_refcert reproduce --check
```

Use `python` instead of `python3` when that is your interpreter's name.
The API, CLI, and frozen reference data work outside a source checkout.
The check should report `MATCH` for the reference expectations, data, and report.
The [reference cases](#reference-cases) explain the deliberately failed
sufficient route and the nonhalting boundary among those expected results.

For the new candidate-preparation and complete-bundle workflows, install the
current source below.

## Quick start

For the **0.2.0rc1 development version**, clone this branch:

```bash
git clone --branch upgrade/complete-evidence-0.2.0rc1 https://github.com/yeruciwenrou-dotcom/rcc-refcert.git
cd rcc-refcert
python3 --version
python3 quickstart.py --reproduce-only
```

Python 3.10 or newer is required. On Windows, or where your interpreter is
named `python`, use `python` in place of `python3`. You can also select this
branch on GitHub, choose **Code → Download ZIP**, and run the last two commands
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
tag before installation. The published 0.1.3 source is tagged `v0.1.3`.

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
Choose an unused filename. Follow the [custom-model guide](docs/CUSTOM_MODELS.md)
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
[analysis-bundle guide](docs/ANALYSIS_BUNDLES.md) explains result comparisons,
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
[terminal-state guide](docs/TERMINAL_BOUNDS.md) explains the projector,
sample-size and evidence requirements.

Both routes use a uniform reference on an ideal support and exact transcription.
The cost bound depends on the declared model premises; sampling coverage
describes the counts alone. Templates are installed package resources, so
these commands also work outside the checkout when run with the installed
environment's interpreter.

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

Model and certificate checks report `pass`, `fail`, `inconclusive` or
`not_applicable`, with an explicit evidence level, currently `numerical`.
These outcomes describe finite-input and fixed-model checks. The
[scientific scope](docs/SCIENTIFIC_SCOPE.md) connects them to the RCC theorem
and its physical, transcription and family-uniformity requirements.

Terminal-state records distinguish the scalar calculation's enclosure,
numerical certificate evidence and sampling confidence. A completed zero lower
bound is a valid result; it does not establish zero preparation cost.
The [output contract](docs/OUTPUT_CONTRACT.md) explains fields and exit codes.

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

RCC's **principle of structural fairness** makes that dependence explicit.
Structure supplied as a fixed background is represented in the reference;
additional structure directed toward the target must be generated and counted.
The reference, allowed dynamics, control language and program prior, success
criterion, and atomic cost unit are fixed together before target selection.
This complete specification defines the physical generation model. Complexity
is therefore a relational physical quantity, measured relative to what the
model supplies and charges.

### What RCC measures

RCC is a structure-fair, model-relative framework for defining and
lower-bounding quantum circuit complexity.

For a fixed model, target, and accuracy $\epsilon$,
$C_{\rm opt}^{(\epsilon)}$ is the infimum of the declared cost over all
admissible successful preparation histories. It asks for the least cost
compatible with that model.

The paper constructs an admissible model family fixed before target selection,
whose size-indexed members can approximate arbitrary finite-dimensional pure
and mixed states to any positive tolerance. This is the universality claim.
The optimization is over preparation histories within a fixed member; the
reference and cost rules remain part of the declared problem.

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
| Finite-control models | Code-weighted trajectories, terminating program semidensities, least fixed points and reference domination | [Model guide](docs/MODEL_GUIDE.md) |
| Reference certificates | Stable Bellman–Choi candidate preparation, independent H.3/H.4 verification, and local gain–cost checks with sufficient code completions | [Custom models](docs/CUSTOM_MODELS.md) |
| Terminal-state bounds | Exact-spectrum smoothing, fixed-projector counts, certificate binding and scalar cost inversion | [Terminal-state bounds](docs/TERMINAL_BOUNDS.md) |
| Reproducible evidence | Frozen Appendix F/H cases, same-version scalar replay, and complete model/proof bundles for fresh verification | [Analysis bundles](docs/ANALYSIS_BUNDLES.md) |

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
| `src/rcc_refcert/` | Model, certificate and bounds APIs; CLI and evidence formats |
| `examples/` | Paired-reset, alternating-qubit and cyclic-register workflows |
| `RCC_Quickstart.ipynb`, `RCC_Bounds_Quickstart.ipynb` | Executable model and bounds tutorials |
| `results/` | Frozen reference report and structured data |
| `generated_results/` | Fresh local evidence written by the quickstart; ignored by Git |
| `docs/`, `tests/` | Detailed guides and scientific/interface regressions |

## Development, citation, and license

For development setup, tests, formatting and package builds, follow
[Contributing](CONTRIBUTING.md#local-verification).

Version 0.1.3 is archived on
[Zenodo](https://doi.org/10.5281/zenodo.22768920). Cite the version DOI of the
release you ran; the [all-versions DOI](https://doi.org/10.5281/zenodo.22544967)
identifies the project across releases. [`CITATION.cff`](CITATION.cff) provides
software and RCC-paper citation metadata.

See the [Changelog](CHANGELOG.md) for this version's changes. The source code
is available under the [MIT License](LICENSE).
