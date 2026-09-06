# rcc-refcert

`rcc-refcert` is the reference implementation and research kernel for the
finite-control qualification layer of **Reference-Contingent Complexity
(RCC)**, introduced in
[*Structure-Fair Quantum Circuit Complexity: An Auditable Information-Theoretic Lower Bound*](https://arxiv.org/abs/2509.18205).

> **Manuscript alignment.** This source tree is aligned with version 4 of the
> RCC manuscript, currently being prepared as the next arXiv revision. The
> publicly available paper is presently
> [arXiv:2509.18205v3](https://arxiv.org/abs/2509.18205v3); appendix labels and
> equation numbers in this repository therefore refer to manuscript version 4.
> The repository provides executable finite-model evidence for selected
> constructions; the paper remains responsible for the analytic and
> model-family arguments.

RCC is a structure-fair, model-relative framework for defining and
lower-bounding quantum circuit complexity. Within a declared physical
generation model, it defines $C_{\rm opt}^{(\epsilon)}$ as the infimum of the
declared cost over all admissible histories that prepare the target within
accuracy $\epsilon$. The main RCC theorem converts the target's one-shot
structural gap relative to the reference into a rigorous lower bound on this
global process optimum and supports auditable conservative certificates from
final-state evidence.

This repository turns the framework's finite-control qualification machinery
into objects that can be constructed, inspected, and audited. It reproduces
selected finite constructions from the paper and gives researchers a concrete
basis for developing new structure-fair model classes, certificate methods,
and gain–cost assignments.

## Start here

| Goal | Entry point |
|---|---|
| Inspect the recorded evidence without running code | [`results/reference_report.md`](results/reference_report.md) |
| Set up the package and reproduce the reference results | [`quickstart.py`](quickstart.py) |
| Follow a guided first run in Jupyter | [`RCC_Quickstart.ipynb`](RCC_Quickstart.ipynb) |
| Run the minimal qualification-to-lower-bound chain | [`docs/END_TO_END_EXAMPLE.md`](docs/END_TO_END_EXAMPLE.md) |
| Understand exactly what the numerical results establish | [`docs/SCIENTIFIC_SCOPE.md`](docs/SCIENTIFIC_SCOPE.md) |
| Trace RCC paper formulas to implementation | [`docs/PAPER_MAP.md`](docs/PAPER_MAP.md) |
| Construct or audit a new finite-control model | [`docs/MODEL_GUIDE.md`](docs/MODEL_GUIDE.md) |

## Why reference-contingent complexity

A target quantum state specifies the structure that every successful
preparation must realize. Its optimal preparation cost becomes physically
comparable only after the generation background and resource scale are fixed.
The reference background, available operations, control language, supplied
ancillas, success semantics, and unit of cost determine which structure is
already supplied and how the remainder is counted. A reset channel or a short
control macro can itself contain structure that shortens the route to a target;
when that advantage remains implicit, changing the description layer can make
generation responsibility appear to disappear.

RCC fixes the reference background, allowed dynamics, control interface,
program prior, success semantics, and cost unit in one generation model. Its
**structure-fairness principle** requires supplied structure to be represented
in the reference or charged through the dynamics and resource coordinates.
Complexity is therefore a relational physical quantity: the target specifies
what must be generated, while the declared model fixes what is already
supplied, which histories are admissible, and how their cost is measured. RCC
also defines a state-side complexity readout from the target and the fixed
model data. Optimality takes the infimum over all admissible preparation
histories within a declared model. Universality concerns the joint target
generation coverage of the admissible model class. Under reference
consistency, faithful transcription, and reference
admissibility, the one-shot refinement bounds every admissible preparation
path before the infimum is taken. This makes an otherwise inaccessible global
circuit optimum auditable from information in the final state.

Section II of the RCC paper formulates this physical model. Appendix F proves
that the model class is nonempty and constructs an admissible qubit model family
that can approximate arbitrary pure and mixed states; Appendix H supplies
constructive finite-control qualification routes. This repository implements
selected finite-control constructions from that chain, while Section III states
the main lower-bound theorem. The package tests whether a declared process
semantics, program semidensity, reference certificate, and description-cost
assignment fit together as claimed.

## What this repository implements

The bundled cases reproduce selected finite constructions from the RCC paper,
while the package also accepts new finite-control models and supplied proof
objects. It can:

- reproduce the Appendix F/H reference cases and their numerical evidence;
- follow one complete fixed-model chain from a physical declaration and
  program semidensity to a numerical one-shot RCC lower bound;
- construct a prefix-controlled quantum-process model and compute its
  terminating program semidensity;
- audit independent trajectory and block-superoperator realizations while
  preserving least-fixed-point semantics in nonhalting sectors;
- test Bellman–Choi, reference-potential, and fixed-model domination
  certificates;
- identify operations whose code length understates their reference gain and
  obtain a sufficient prefix-code completion;
- develop new structure-fair model classes, certificate methods, cost
  assignments, and rigorous-verification backends.

This makes `rcc-refcert` a compact research testbed for a foundational task:
turning quantum-complexity models into explicit objects whose supplied
structure and generation costs can be examined.

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
reuse the environment unless the package metadata or dependency lock changes.
The three reference cases should all report `MATCH`; the designed route failure
and nonhalting boundary are described in the reference-case table below.

To regenerate and compare the scientific evidence without running the
independent tests:

```bash
python3 quickstart.py --reproduce-only
```

To install into an environment you already manage:

```bash
python3 -m pip install .
rcc-refcert examples
rcc-refcert example dephase-or-halt
rcc-refcert reproduce --check
```

The default check uses the frozen Markdown and normalized JSON installed with
the package, so it also works from outside a repository checkout. Pass an
explicit report path to compare another evidence pair.

The equivalent module entry point is `python3 -m rcc_refcert`. Substitute
`python` when it names a supported Python 3 interpreter. Use `--details`
for residuals, margins, and proposed codewords, or `--format json` for the
versioned machine-readable result:

```bash
rcc-refcert example multiblock-rectangular --details
rcc-refcert reproduce --format json
```

To write a new report, choose the destination explicitly:

```bash
rcc-refcert reproduce --output reference_report.md
```

### Jupyter notebook

The notebook dependencies are optional and do not enter the runtime package.
After the quickstart has created `.venv`, macOS and Linux users can run:

```bash
.venv/bin/python -m pip install -e ".[notebook]"
.venv/bin/python -m ipykernel install --user --name rcc-refcert --display-name "Python (rcc-refcert)"
.venv/bin/python -m jupyterlab
```

Open `RCC_Quickstart.ipynb` and select **Python (rcc-refcert)** as its kernel.
On Windows, use `.venv\Scripts\python` in the same commands.

## End-to-end RCC lower-bound example

A fixed one-qubit paired-reset model connects the finite-control qualification
layer to the paper's main lower-bound theorem in Section III, Theorem 3.1. It
constructs the complete program semidensity, checks the fixed-model reference
conditions, and evaluates the endpoint gap

$$
D_{\max}^{0}(\lvert0\rangle\langle0\rvert\Vert I/2)
=1\ \mathrm{bit}
=1\,\mathrm{st}_R.
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

After installing the package in the active environment, run:

```bash
python3 examples/paired_reset_lower_bound.py
python3 examples/paired_reset_lower_bound.py --json
```

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

## Scientific boundary

The package is a compact research reference implementation of RCC's
finite-control qualification layer. It constructs finite-model program
semidensities and verifies supplied reference certificates and gain–cost
assignments; every supported calculation has an explicit RCC paper map,
numerical contract, and regression.

Every check reports an `outcome`—`pass`, `fail`, `inconclusive`, or
`not_applicable`—separately from its `evidence`, currently `numerical`. The
package establishes finite-input and fixed-model statements. The complete
framework—including physical reference consistency, faithful transcription,
family-uniform admissibility, and the RCC lower-bound theorem—is developed in
the [RCC paper](https://arxiv.org/abs/2509.18205).

The exact claim ladder is documented in
[`docs/SCIENTIFIC_SCOPE.md`](docs/SCIENTIFIC_SCOPE.md), and numerical and tensor
conventions are fixed in [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md).

## Extending the research kernel

The package exposes a research object that can grow independently of the
bundled reference cases. Extensions are most useful when they enlarge the class of
auditable structure-fair models, strengthen the certificate layer, or make its
evidence more rigorous. Examples include:

- finite-control models with new physical resources or boundary behavior;
- automated Bellman–Choi or reference-potential certificate search;
- rigorous interval or exact-arithmetic verification;
- family-uniform certificate constructions and scaling diagnostics;
- alternative reference gain–cost encodings and negative witnesses;
- serialization, solver, and larger-state-space backends.

Contributions are welcome across scientific models, algorithms, numerical
reliability, documentation, and examples. See
[`CONTRIBUTING.md`](CONTRIBUTING.md) for the project-specific workflow and the
claims each change must protect.

## Repository structure

| Path | Purpose |
|---|---|
| `src/rcc_refcert/` | Finite-control models, simulation, certificates, CLI, and report rendering |
| [`examples/paired_reset_lower_bound.py`](examples/paired_reset_lower_bound.py) | Fixed model-to-lower-bound executable example |
| `tests/` | Scientific regressions and public-interface tests |
| [`quickstart.py`](quickstart.py) | Environment setup, independent tests, and reference reproduction |
| [`RCC_Quickstart.ipynb`](RCC_Quickstart.ipynb) | Guided run through the three reference cases |
| [`results/reference_report.md`](results/reference_report.md) | Frozen human-readable reference evidence |
| [`results/reference_suite.json`](results/reference_suite.json) | Frozen normalized structured evidence |
| `generated_results/` | Fresh locally generated evidence; ignored by Git |
| `docs/` | Scientific scope, RCC paper map, conventions, model guide, and output contract |

## Development, citation, and license

```bash
python -m pip install -e ".[dev]"
ruff check src tests examples quickstart.py RCC_Quickstart.ipynb
ruff format --check src tests examples quickstart.py RCC_Quickstart.ipynb
python -W error -m pytest
python -m build
```

The source code is released under the MIT License. Citation metadata for the
software and associated RCC paper are provided in
[`CITATION.cff`](CITATION.cff).
