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
```

Alternatively, select `upgrade/complete-evidence-0.2.0rc1` on GitHub and choose
**Code → Download ZIP**, then extract the archive. Run the following commands
from the directory containing `quickstart.py`. Python 3.10 or newer is required;
on macOS and most Linux systems:

```bash
python3 --version
python3 quickstart.py --reproduce-only
```

On Windows, or where your interpreter is named `python`, use
`python quickstart.py --reproduce-only`.
The script creates `.venv`, installs the locked verification dependencies,
checks the frozen reference evidence, and writes fresh results to
`generated_results/`. Expect three `MATCH` checks. To include the independent
test suite, run `python3 quickstart.py` (or `python quickstart.py`). Later runs
reuse the installation and refresh it when package metadata, the dependency
lock, or the package version changes.

The commands below use `.venv/bin/python`, the quickstart interpreter on macOS
and Linux. On Windows, substitute `.venv\Scripts\python.exe`. To use an
existing active environment, install this checkout with
`python -m pip install .` and use that environment's interpreter throughout.
The module entry point accepts the same arguments as `rcc-refcert`.

To reproduce a specific source version, check out its full commit or release
tag before installation. The published 0.1.3 source is tagged `v0.1.3`.

## Work with your own model

After the [source installation](#quick-start), run these two examples from the
checkout. They use ordinary NumPy arrays and the public model and certificate
APIs:

```bash
.venv/bin/python examples/custom_model_workflow.py --bundle alternating.rccbundle
.venv/bin/python examples/cyclic_reset_workflow.py --bundle cyclic-reset.rccbundle
```

The alternating qubit example prepares and independently verifies an H.3
certificate even though a local sufficient condition fails. The cyclic-reset
example verifies a supplied H.4 certificate and computes bounds from an exact
spectrum and synthetic counts. Both bound paths return **two primitive slots**
for its declared task; the guide distinguishes this general lower bound from
the example's separately established five-slot optimum.

Each command saves an analysis bundle. Choose an unused output filename;
existing evidence is preserved. To adapt the workflow, follow the
[custom-model guide](docs/CUSTOM_MODELS.md): declare your channels, initial and
reference states, control language, and cost premises; prepare or supply a
certificate; verify it; then add a supported target-state task.
The [model guide](docs/MODEL_GUIDE.md) gives the construction rules, and
[terminal-state bounds](docs/TERMINAL_BOUNDS.md) specifies spectrum and counts
inputs. Candidate preparation covers the stable full-space linear route;
other models can use separately supplied H.3/H.4 proof objects.

## Reverify a shared analysis

Install the current source as above, then run the following commands on the
bundle produced by the cyclic-reset example, or replace the filename with a
bundle you received:

```bash
.venv/bin/python -m rcc_refcert bundle inspect cyclic-reset.rccbundle
.venv/bin/python -m rcc_refcert bundle verify cyclic-reset.rccbundle --output cyclic-reset-verification.json
```

`inspect` checks stored consistency. `verify` checks the model and certificate
matrices afresh, recomputes supported bounds, and compares the fresh evidence
with the historical results. The installed package and bundle are sufficient;
the sender's model script is unnecessary. The original bundle is preserved,
and `--output` saves a separate report under an unused filename.

A successful fresh matrix check can still leave a historical result
unsupported if the new conservative constant is larger. The
[analysis-bundle guide](docs/ANALYSIS_BUNDLES.md) explains that comparison,
the separate scalar-replay result, exit codes, and preservation of the original
counts protocol. For exact historical scalar replay, use the bundle producer's
package version.

## Jupyter notebook

The notebook dependencies are optional and do not enter the runtime package.
After the quickstart has created `.venv`, macOS and Linux users can run:

```bash
.venv/bin/python -m pip install -e ".[notebook]"
.venv/bin/python -m ipykernel install --user --name rcc-refcert --display-name "Python (rcc-refcert)"
.venv/bin/python -m jupyterlab
```

Open `RCC_Quickstart.ipynb` for the reference-model audits or
`RCC_Bounds_Quickstart.ipynb` for spectra, fixed-projector counts, and replay.
Select **Python (rcc-refcert)** as the kernel. The `ipykernel install` command
registers this name; installing the notebook dependencies alone does not.
If you use another environment, run all three commands with that environment's
Python interpreter. On Windows, use `.venv\Scripts\python.exe` in the same
commands.

## Target spectra and measured counts

With the package installed, run the spectrum example:

```bash
python -m rcc_refcert bound template spectrum > spectrum.json
python -m rcc_refcert bound spectrum spectrum.json
python -m rcc_refcert bound spectrum spectrum.json --format json > bound.json
python -m rcc_refcert bound replay bound.json
```

The template declares a fixed four-dimensional model and a complete exact
spectrum. Its integer-slot lower bound is one. A second template provides a
synthetic fixed-projector example with 550 hits in 1000 trials:

```bash
python -m rcc_refcert bound template counts > counts.json
python -m rcc_refcert bound counts counts.json
```

For real measurements, prepare the protocol before collecting data using
`bound prepare-protocol`, then preserve its digest with the dataset. The
[counts guide](docs/TERMINAL_BOUNDS.md#fixed-projector-counts)
explains the fixed-projector, fixed-sample-size contract.

Use the interpreter of the environment where you installed the package.
After the source quickstart, this is `.venv/bin/python` on macOS and Linux,
or `.venv\Scripts\python.exe` on Windows.
Templates are included in the installed package and work outside the checkout.
Both routes use a uniform reference on an ideal support and exact transcription.
Their preparation-cost bounds are conditional on the declared model premises;
sampling coverage describes the counts alone.
See the [guide](docs/TERMINAL_BOUNDS.md)
and [bounds notebook](RCC_Bounds_Quickstart.ipynb)
for inputs, units, zero results and limitations.

## End-to-end RCC lower-bound example

A fixed one-qubit paired-reset model connects the finite-control qualification
layer to the paper's main lower-bound theorem in Section III, Theorem 3.1. It
constructs the complete program semidensity, checks the fixed-model reference
conditions, and evaluates the endpoint gap

$$
D_{\max}^{0}(\lvert0\rangle\langle0\rvert\Vert I/2)
=1\ \mathrm{bit}
=1\thinspace\mathrm{st}_R.
$$

Appendix A's canonical cost inversion then gives

$$
C_{\mathrm{opt}}^{(0)}\ge1
\quad\text{atomic resource slot}
$$

under the model's stated analytic inputs.

The admissible program `0` prepares the target exactly in one slot, giving the
matching upper bound. Thus the transparent fixed model satisfies

$$
C_{\mathrm{opt}}^{(0)}=1
$$

atomic resource slot. The displayed feasible program establishes tightness for
this fixed model.

From the repository root, use the quickstart environment:

```bash
.venv/bin/python examples/paired_reset_lower_bound.py
.venv/bin/python examples/paired_reset_lower_bound.py --json
```

On Windows, use `.venv\Scripts\python.exe` in these commands. If you installed
into another environment, use that environment's Python interpreter.

The [worked explanation](docs/END_TO_END_EXAMPLE.md) separates software
checks, analytic model obligations, and the theorem-level consequence. The
example states all model inputs explicitly.

## Reference cases

| Case | Scientific role | Intended result |
|---|---|---|
| `dephase-or-halt` | Transparent closed-form realization | Every supplied route passes |
| `multiblock-rectangular` | Direct-sum, rectangular-Kraus, and certificate diagnostic | H.1–H.4 pass; the original codewords fail H.70 as designed; H.76 supplies a passing re-encoding |
| `dark-nonhalting` | Least-fixed-point boundary with a recurrent nonhalting sector | The process remains valid; the linear inverse is unavailable and H.34 remains unevaluated |

The designed H.70 failure is a successful diagnostic: it identifies codewords
whose description cost falls short of their reference gain.

## Python API

The case API gives the shortest route from a bundled model to its complete
audit:

```python
from rcc_refcert import audit_case, get_case

result = audit_case(get_case("multiblock-rectangular"))

print(result.matches_expectations)
print(result.model_analysis.fixed_model_domination.constant)
print(result.gain_cost.outcome.value)
```

The corresponding values are `True`, `15/14` numerically, and `"fail"`. The
last value is the deliberately failed sufficient condition H.70 described
above.

For a new model, use `Action`, `FiniteControlModel`, `require_valid_model`, and
`audit_model`. Supplied proof objects can be checked with
`verify_bellman_choi`, `verify_reference_potential`, and
`analyze_reference_gain_cost`. The [model guide](docs/MODEL_GUIDE.md) contains a
complete minimal example.

For target-state calculations, `rcc_refcert.bounds` exposes
`bound_from_spectrum`, `bound_from_counts`, `prepare_protocol`, and
`replay_record`. Use `with_reference_certificate` to connect an H.3 or H.4
proof object to the declared task, and `validate_record` to check a saved
record's consistency. The [input guide](docs/TERMINAL_BOUNDS.md)
contains a runnable API example and the evidence and replay contracts.

## Results and scientific scope

Finite-control checks report an `outcome`—`pass`, `fail`, `inconclusive`, or
`not_applicable`—separately from its `evidence`, currently `numerical`. The
package establishes finite-input and fixed-model statements. The complete
framework—including physical reference consistency, faithful transcription,
family-uniform admissibility, and the RCC lower-bound theorem—is developed in
the accompanying RCC manuscript. The [paper map](docs/PAPER_MAP.md) records
the implemented objects and manuscript-version alignment.

Terminal-state records separately identify the scalar enclosure, any numerical
reference-certificate evidence, and any sampling confidence. The calculator
evaluates the RCC cost inversion under the supplied hypotheses. A completed
zero lower bound is a valid result; it does not establish zero preparation cost.

See [Scientific scope](docs/SCIENTIFIC_SCOPE.md) for how these results connect
to the RCC theorem, [Output contract](docs/OUTPUT_CONTRACT.md) for result fields
and exit codes, and [Conventions](docs/CONVENTIONS.md) for the numerical and
tensor definitions.

The explicit matrix and path algorithms target small finite models. Audits
check resource budgets before enumeration or dense matrix construction and
report unresolved numerical precision explicitly. H.34 gives a minimum-constant
estimate; passing H.3 and H.4 reports provide numerical upper constants with
error budgets. See the [model guide](docs/MODEL_GUIDE.md#numerical-and-resource-limits)
for input limits and budget settings.

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
RCC quantifies the target's one-shot information gap relative to the reference
and converts it into a cost lower bound using the model's atomic control
bandwidth and transcription rules. Under the theorem's reference-consistency,
faithful-transcription, and reference-admissibility hypotheses, this bound
applies to every admissible preparation history and hence to their optimum.
An endpoint measurement can thus certify a minimum cost without reconstructing
the preparation history.

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
> [RCC manuscript](https://arxiv.org/abs/2509.18205). Appendix labels and
> equation numbers refer to manuscript version 4.

## What this repository implements

The bundled cases reproduce selected finite constructions from the RCC paper,
while the package also accepts new finite-control models and supplied proof
objects. It can:

- construct a prefix-controlled quantum-process model and compute its
  terminating program semidensity;
- audit independent trajectory and block-superoperator realizations while
  preserving least-fixed-point semantics in nonhalting sectors;
- verify Bellman–Choi and reference-potential certificates, and evaluate
  fixed-model domination constants;
- identify operations whose code length understates their reference gain and
  obtain a sufficient prefix-code completion;
- compute conditional preparation-cost lower bounds from complete exact
  spectra or predeclared fixed-projector counts, with explicit tolerance,
  sampling coverage, and atomic-slot units;
- connect freshly verified H.3 or H.4 proof objects to a declared target-state
  task while retaining their numerical evidence level;
- prepare H.3 candidates for stable finite models, with separate construction
  diagnostics and independent verification;
- save calculation inputs and results in a versioned record and replay the
  scalar calculation with the same package version;
- export complete model and proof inputs in an analysis bundle, reverify them
  in another environment, and compare fresh evidence with historical constants;
- reproduce the Appendix F/H reference cases and follow a worked fixed-model
  chain from a physical declaration to a one-shot RCC lower bound.

This makes `rcc-refcert` a compact research testbed for a foundational task:
turning quantum-complexity models into explicit objects whose supplied
structure and generation costs can be examined.

## Further reading

| Question | Guide |
|---|---|
| What do the checks establish? | [Scientific scope](docs/SCIENTIFIC_SCOPE.md) |
| How do paper formulas map to code? | [Paper-to-code map](docs/PAPER_MAP.md) |
| How are numerical and tensor conventions fixed? | [Conventions](docs/CONVENTIONS.md) |
| How should I interpret result fields and exit codes? | [Output contract](docs/OUTPUT_CONTRACT.md) |
| How can I extend or contribute to the toolkit? | [Contributing](CONTRIBUTING.md) |

## Extending the research kernel

The public model and certificate interfaces support research beyond the
bundled reference cases. Extensions are most useful when they enlarge the class of
auditable structure-fair models, strengthen the certificate layer, or make its
evidence more rigorous. Examples include:

- finite-control models with new physical resources or boundary behavior;
- Bellman–Choi or reference-potential search beyond the stable linear route;
- rigorous matrix-interval or exact-matrix certificate verification;
- family-uniform certificate constructions and scaling diagnostics;
- alternative reference gain–cost encodings and negative witnesses;
- terminal-state bound methods with explicit reference, transcription, and
  sampling assumptions;
- additional input formats, solvers, and larger-state-space backends.

Contributions are welcome across scientific models, algorithms, numerical
reliability, documentation, and examples. See
[Contributing](CONTRIBUTING.md) for how to propose and verify a change.

## Repository structure

| Path | Purpose |
|---|---|
| `src/rcc_refcert/` | Finite-control models, simulation, certificates, terminal-state bounds, CLI, and report rendering |
| [`examples/paired_reset_lower_bound.py`](examples/paired_reset_lower_bound.py) | Fixed model-to-lower-bound executable example |
| [`examples/custom_model_workflow.py`](examples/custom_model_workflow.py) | New-model candidate preparation, independent verification, and export |
| [`examples/cyclic_reset_workflow.py`](examples/cyclic_reset_workflow.py) | H.4 certificate, exact-spectrum and synthetic-counts bounds, and complete-input export |
| `tests/` | Scientific regressions and public-interface tests |
| [`quickstart.py`](quickstart.py) | Environment setup, independent tests, and reference reproduction |
| [`RCC_Quickstart.ipynb`](RCC_Quickstart.ipynb) | Guided run through the three reference cases |
| [`RCC_Bounds_Quickstart.ipynb`](RCC_Bounds_Quickstart.ipynb) | Guided exact-spectrum and fixed-projector calculations |
| [`results/reference_report.md`](results/reference_report.md) | Frozen human-readable reference evidence |
| [`results/reference_suite.json`](results/reference_suite.json) | Frozen normalized structured evidence |
| `generated_results/` | Fresh locally generated evidence; ignored by Git |
| `docs/` | Scientific scope, RCC paper map, conventions, model and terminal-state guides, and output contract |

## Development, citation, and license

In an active Python 3.10 or newer environment, run these checks from the
repository root. See [Contributing](CONTRIBUTING.md)
for quickstart-environment commands and guidance on scientific changes.

```bash
python -m pip install -e ".[dev]"
python -m ruff check src tests examples quickstart.py RCC_Quickstart.ipynb RCC_Bounds_Quickstart.ipynb
python -m ruff format --check src tests examples quickstart.py RCC_Quickstart.ipynb RCC_Bounds_Quickstart.ipynb
python -W error -m pytest
python -m rcc_refcert reproduce --check
python -m build
```

Version 0.1.3 is archived on
[Zenodo](https://doi.org/10.5281/zenodo.22768920).
For reproducible citations, use the version DOI of the release you ran. The
[all-versions DOI](https://doi.org/10.5281/zenodo.22544967) represents the project
across releases.

See the [Changelog](CHANGELOG.md) for the capabilities included in this version.
Citation metadata for the software and associated RCC paper are provided in
[`CITATION.cff`](CITATION.cff). The source code is available under the
[MIT License](LICENSE).
