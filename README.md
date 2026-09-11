# rcc-refcert

[![PyPI](https://img.shields.io/pypi/v/rcc-refcert.svg?label=PyPI)](https://pypi.org/project/rcc-refcert/)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.22712591-blue)](https://doi.org/10.5281/zenodo.22712591)

`rcc-refcert` is a Python research toolkit for
**structure-fair quantum circuit complexity**.
It helps researchers build and audit quantum generation models, verify
reference certificates, and compute conditional lower bounds on quantum
circuit complexity from terminal-state information.

Each model specifies the supplied resources, allowed quantum processes, and
rules for counting description and generation costs. You can examine reference
gain–cost assignments and develop new model and certificate constructions.
The terminal-state tools apply this framework to quantum state preparation,
using exact spectra or fixed-projector counts. Bundled examples provide
reproducible numerical evidence,
including a worked chain from a declared model to a lower bound on quantum
state preparation cost.

The toolkit implements finite-control models, reference-certificate methods,
and conditional target-state bounds from **Reference-Contingent Complexity
(RCC)**, introduced in
[*Structure-Fair Quantum Circuit Complexity: An Auditable Information-Theoretic Lower Bound*](https://arxiv.org/abs/2509.18205).

Install from [PyPI](#install-from-pypi) to use the model audits and terminal-state
bounds. The [source quickstart](#quick-start) also runs the verification suite
and provides the notebooks and worked examples.

## Start here

| Goal | Entry point |
|---|---|
| Inspect the recorded evidence without running code | [Reference results](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/results/reference_report.md) |
| Install the package and reproduce the reference results | [Install from PyPI](#install-from-pypi) |
| Compute a bound from a target spectrum or fixed-projector counts | [Terminal-state bounds](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/docs/TERMINAL_BOUNDS.md) |
| Install the current source and run its tests | [Quick start](#quick-start) |
| Follow model audits or target-state calculations in Jupyter | [Notebook setup and selection](#jupyter-notebook) |
| Follow a model from qualification to a lower bound | [Worked example](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/docs/END_TO_END_EXAMPLE.md) |
| Understand what the numerical results establish | [Scientific scope](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/docs/SCIENTIFIC_SCOPE.md) |
| Trace RCC paper formulas to implementation | [Paper-to-code map](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/docs/PAPER_MAP.md) |
| Construct or audit a new finite-control model | [Model guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/docs/MODEL_GUIDE.md) |

> **Manuscript alignment.** This source tree is aligned with version 4 of the
> RCC manuscript, currently being prepared as the next arXiv revision. The
> publicly available paper is presently
> [arXiv:2509.18205v3](https://arxiv.org/abs/2509.18205v3); appendix labels and
> equation numbers in this repository therefore refer to manuscript version 4.

## Why reference-contingent complexity

RCC is a structure-fair, model-relative framework for defining and
lower-bounding quantum circuit complexity. It asks how much of a target's
structure must be generated when the physical background and available
resources are fixed.

The same target state can have different preparation costs under different
backgrounds. A reset channel, a supplied ancilla, or a short control macro may
already carry structure that makes the target easier to prepare. RCC's
**structure-fairness principle** requires this supplied structure to be
represented in the reference or charged through the dynamics and resource
coordinates. The generation model fixes the reference background, allowed
operations, control language, program prior, success semantics, and cost unit
together. Complexity is therefore a relational physical quantity, measured
relative to that complete specification.

Within a declared model, $C_{\rm opt}^{(\epsilon)}$ is the infimum of the cost
over all admissible histories that prepare the target within accuracy
$\epsilon$. Universality concerns the joint target-generation coverage of the
admissible model class; optimality concerns all legal histories within a given
member. Under the theorem's hypotheses, including reference consistency,
faithful transcription, and reference admissibility, RCC converts the target's
one-shot structural gap into a lower bound on every such history and hence on
the global process optimum. Final-state evidence can thus bound the minimum
cost without identifying an optimal preparation path.

Section II of the RCC paper formulates this physical model. Appendix F proves
that the model class is nonempty and constructs an admissible qubit model family
that can approximate arbitrary pure and mixed states; Appendix H supplies
constructive finite-control qualification routes. This repository implements
selected finite-control constructions from that chain, while Section III states
the main lower-bound theorem. Researchers can use the package to check how a
model's quantum dynamics, program weights, reference certificates, and
description costs fit together.

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
- save calculation inputs and results in a versioned record and replay the
  scalar calculation with the same package version;
- reproduce the Appendix F/H reference cases and follow a worked fixed-model
  chain from a physical declaration to a one-shot RCC lower bound.

This makes `rcc-refcert` a compact research testbed for a foundational task:
turning quantum-complexity models into explicit objects whose supplied
structure and generation costs can be examined.

## Install from PyPI

In a Python 3.10 or newer environment, install the package and check the
bundled reference results:

```bash
python3 -m pip install --upgrade rcc-refcert
python3 -m rcc_refcert examples
python3 -m rcc_refcert reproduce --check
```

Use `python` instead of `python3` when that is the interpreter name in your
environment. The command-line tool and Python API work outside a source
checkout; the frozen reference data are included in the installed package.
For an exact version, install `rcc-refcert==0.1.2`.

The source quickstart below installs the code and runs the independent test
suite. The checkout also provides both notebooks, worked examples, and the full
documentation.

## Quick start

Obtain the source and enter the repository directory:

```bash
git clone https://github.com/yeruciwenrou-dotcom/rcc-refcert.git
cd rcc-refcert
```

Alternatively, download and extract the repository ZIP, then open a terminal
in the extracted directory containing `quickstart.py`.

Python 3.10 or newer is required. On macOS and most Linux systems, use:

```bash
python3 --version
python3 quickstart.py
```

If your environment exposes Python 3.10 or newer as `python`, the equivalent is:

```bash
python quickstart.py
```

On its first run, the script creates a local `.venv`, installs the locked
verification dependencies, runs the independent test suite, checks both frozen
reference files, and writes fresh evidence to `generated_results/`. Later runs
reuse the installation, refreshing it when the package metadata, dependency
lock, or package version changes.
The three reference cases should all report `MATCH`; the designed route failure
and nonhalting boundary are described in the reference-case table below.

To regenerate and compare the scientific evidence without running the
independent tests:

```bash
python3 quickstart.py --reproduce-only
```

To run individual commands in the environment created by the quickstart, use
its Python interpreter. On macOS and Linux:

```bash
.venv/bin/python -m rcc_refcert examples
```

On Windows:

```powershell
.venv\Scripts\python.exe -m rcc_refcert examples
```

Use the same interpreter for Python scripts and API examples. The module entry
point accepts the same arguments as the `rcc-refcert` command.

If you prefer an environment you already manage, install the package there:

```bash
python3 -m pip install .
python3 -m rcc_refcert examples
python3 -m rcc_refcert example dephase-or-halt
python3 -m rcc_refcert reproduce --check
```

The default check uses the frozen Markdown and normalized JSON installed with
the package, so it also works from outside a repository checkout. Pass an
explicit report path to compare another evidence pair.

The following commands use the quickstart interpreter on macOS and Linux.
On Windows, substitute `.venv\Scripts\python.exe`; for another environment,
use its Python interpreter. Add `--details` for residuals, margins, and proposed
codewords, or `--format json` for the versioned machine-readable result:

```bash
.venv/bin/python -m rcc_refcert example multiblock-rectangular --details
.venv/bin/python -m rcc_refcert reproduce --format json
```

To write a new report, choose the destination explicitly:

```bash
.venv/bin/python -m rcc_refcert reproduce --output reference_report.md
```

### Jupyter notebook

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
[counts guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/docs/TERMINAL_BOUNDS.md#fixed-projector-counts)
explains the fixed-projector, fixed-sample-size contract.

Use the interpreter of the environment where you installed the package.
After the source quickstart, this is `.venv/bin/python` on macOS and Linux,
or `.venv\Scripts\python.exe` on Windows.
Templates are included in the installed package and work outside the checkout.
Both routes use a uniform reference on an ideal support and exact transcription.
Their preparation-cost bounds are conditional on the declared model premises;
sampling coverage describes the counts alone.
See the [guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/docs/TERMINAL_BOUNDS.md)
and [bounds notebook](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/RCC_Bounds_Quickstart.ipynb)
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

The legal program `0` prepares the target exactly in one slot, giving the
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

The [worked explanation](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/docs/END_TO_END_EXAMPLE.md) separates software
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
`analyze_reference_gain_cost`. The [model guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/docs/MODEL_GUIDE.md) contains a
complete minimal example.

For target-state calculations, `rcc_refcert.bounds` exposes
`bound_from_spectrum`, `bound_from_counts`, `prepare_protocol`, and
`replay_record`. Use `with_reference_certificate` to connect an H.3 or H.4
proof object to the declared task, and `validate_record` to check a saved
record's consistency. The [input guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/docs/TERMINAL_BOUNDS.md)
contains a runnable API example and the evidence and replay contracts.

## Results and scientific scope

Finite-control checks report an `outcome`—`pass`, `fail`, `inconclusive`, or
`not_applicable`—separately from its `evidence`, currently `numerical`. The
package establishes finite-input and fixed-model statements. The complete
framework—including physical reference consistency, faithful transcription,
family-uniform admissibility, and the RCC lower-bound theorem—is developed in
the accompanying RCC manuscript. The [paper map](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/docs/PAPER_MAP.md) records
the implemented objects and manuscript-version alignment.

Terminal-state records separately identify the scalar enclosure, any numerical
reference-certificate evidence, and any sampling confidence. The calculator
evaluates the RCC cost inversion under the supplied hypotheses. A completed
zero lower bound is a valid result; it does not establish zero preparation cost.

See [Scientific scope](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/docs/SCIENTIFIC_SCOPE.md) for how these results connect
to the RCC theorem, [Output contract](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/docs/OUTPUT_CONTRACT.md) for result fields
and exit codes, and [Conventions](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/docs/CONVENTIONS.md) for the numerical and
tensor definitions.

The explicit matrix and path algorithms target small finite models. Audits
check resource budgets before enumeration or dense matrix construction and
report unresolved numerical precision explicitly. H.34 gives a minimum-constant
estimate; passing H.3 and H.4 reports provide numerical upper constants with
error budgets. See the [model guide](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/docs/MODEL_GUIDE.md#numerical-and-resource-limits)
for input limits and budget settings.

## Extending the research kernel

The public model and certificate interfaces support research beyond the
bundled reference cases. Extensions are most useful when they enlarge the class of
auditable structure-fair models, strengthen the certificate layer, or make its
evidence more rigorous. Examples include:

- finite-control models with new physical resources or boundary behavior;
- automated Bellman–Choi or reference-potential certificate search;
- rigorous matrix-interval or exact-matrix certificate verification;
- family-uniform certificate constructions and scaling diagnostics;
- alternative reference gain–cost encodings and negative witnesses;
- terminal-state bound methods with explicit reference, transcription, and
  sampling assumptions;
- serialization, solver, and larger-state-space backends.

Contributions are welcome across scientific models, algorithms, numerical
reliability, documentation, and examples. See
[Contributing](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/CONTRIBUTING.md) for how to propose and verify a change.

## Repository structure

| Path | Purpose |
|---|---|
| `src/rcc_refcert/` | Finite-control models, simulation, certificates, terminal-state bounds, CLI, and report rendering |
| [`examples/paired_reset_lower_bound.py`](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/examples/paired_reset_lower_bound.py) | Fixed model-to-lower-bound executable example |
| `tests/` | Scientific regressions and public-interface tests |
| [`quickstart.py`](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/quickstart.py) | Environment setup, independent tests, and reference reproduction |
| [`RCC_Quickstart.ipynb`](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/RCC_Quickstart.ipynb) | Guided run through the three reference cases |
| [`RCC_Bounds_Quickstart.ipynb`](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/RCC_Bounds_Quickstart.ipynb) | Guided exact-spectrum and fixed-projector calculations |
| [`results/reference_report.md`](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/results/reference_report.md) | Frozen human-readable reference evidence |
| [`results/reference_suite.json`](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/results/reference_suite.json) | Frozen normalized structured evidence |
| `generated_results/` | Fresh locally generated evidence; ignored by Git |
| `docs/` | Scientific scope, RCC paper map, conventions, model and terminal-state guides, and output contract |

## Development, citation, and license

In an active Python 3.10 or newer environment, run these checks from the
repository root. See [Contributing](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/CONTRIBUTING.md)
for quickstart-environment commands and guidance on scientific changes.

```bash
python -m pip install -e ".[dev]"
python -m ruff check src tests examples quickstart.py RCC_Quickstart.ipynb RCC_Bounds_Quickstart.ipynb
python -m ruff format --check src tests examples quickstart.py RCC_Quickstart.ipynb RCC_Bounds_Quickstart.ipynb
python -W error -m pytest
python -m rcc_refcert reproduce --check
python -m build
```

Version 0.1.2 is archived on
[Zenodo](https://doi.org/10.5281/zenodo.22712591).
For reproducible citations, use the version DOI of the release you ran. The
[all-versions DOI](https://doi.org/10.5281/zenodo.22544967) represents the project
across releases.

See the [Changelog](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/CHANGELOG.md) for the capabilities included in this version.
Citation metadata for the software and associated RCC paper are provided in
[`CITATION.cff`](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/CITATION.cff). The source code is available under the
[MIT License](https://github.com/yeruciwenrou-dotcom/rcc-refcert/blob/main/LICENSE).
