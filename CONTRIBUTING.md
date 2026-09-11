# Contributing

RCC studies quantum circuit complexity under an explicit physical generation
model. Its structure-fairness principle accounts for the structure supplied by
the reference background, available dynamics, and program description, together
with the resources spent on generation.

`rcc-refcert` makes finite models and certificate methods available for
researchers to test and extend. Contributions can bring new physical models
into the framework, compare certificate constructions, improve numerical
reliability, or help readers reproduce and understand the results.
The terminal-state interfaces also support exact-spectrum and fixed-projector
calculations with explicit model assumptions, sampling contracts, and replay.

Contributions can address one layer at a time:

- **physical models:** new finite-control examples, resource assignments,
  nonhalting mechanisms, or controlled counterexamples;
- **certificate methods:** Bellman–Choi or reference-potential construction,
  gain–cost encodings, negative witnesses, or family-scaling diagnostics;
- **numerical reliability:** interval bounds, exact arithmetic, conditioning
  diagnostics, solver integrations, or independent realizations;
- **interfaces:** model serialization, larger simulation backends, and stable
  machine-readable outputs;
- **explanation and reproduction:** clearer derivations, examples, notebooks,
  tests, and RCC paper-to-code maps.

For a substantial scientific change, open a **Scientific proposal** describing
the model or certificate object, the RCC result it affects, and the evidence
needed to assess it. Use the bug or documentation issue form for a specific
problem, with a reproducible input or a link to the affected passage.

## Scientific contract

Read [`docs/SCIENTIFIC_SCOPE.md`](docs/SCIENTIFIC_SCOPE.md) and
[`docs/CONVENTIONS.md`](docs/CONVENTIONS.md) before changing the mathematical
core. Changes to code weighting, Kraus composition, direct-sum order,
vectorization, Choi tensor order, support handling, or fixed-point gates must
explain their mathematical effect and include a focused regression.

A convention or certificate change normally needs both:

- a positive example that exercises the intended path;
- a controlled negative or boundary example that catches the likely wrong
  convention.

Keep the claim layers visible in code, tests, and prose:

1. a floating-point outcome for one finite input;
2. a fixed-model semidensity, domination, or certificate statement;
3. a model-family statement requiring a uniform argument;
4. the RCC theorem under its complete physical and transcription hypotheses.

The finite-control kernel directly produces the first two layers. The
terminal-state calculator evaluates a cost lower bound conditionally on the
declared model arguments. Changes to that route must preserve the exact-input,
one-sided arithmetic, sampling, and cost-unit contracts in
[`docs/TERMINAL_BOUNDS.md`](docs/TERMINAL_BOUNDS.md). A family-level or
theorem-level claim also needs its uniform analytic, physical, and transcription
arguments; scalar replay does not discharge those obligations.

## Adding a model or certificate

A bundled model should expose a distinct physical mechanism, formula,
convention risk, or mathematical boundary. Document:

- the reference state, control spaces, actions, codewords, and intended
  physical interpretation;
- the RCC objects and formulas it exercises;
- the expected outcomes, including designed route failures or boundaries;
- the test that would fail under the most plausible incorrect implementation.

An expected H.70 failure records a code-length shortfall along that sufficient
route. An `inconclusive` result records an unresolved numerical condition. Check
the other certificate routes for the original model; adopting suggested
codewords changes its program weights and defines a re-encoded model.
Family-uniform reference admissibility needs the corresponding uniform analytic
argument.

Keep dependencies few and tied to a clear package responsibility. Add parameter
sweeps or user interfaces when they support a defined scientific use case and
preserve the minimal kernel.

## Local verification

Install the development environment and run the core checks:

```bash
python -m pip install -e ".[dev]"
ruff check src tests examples quickstart.py RCC_Quickstart.ipynb RCC_Bounds_Quickstart.ipynb
ruff format --check src tests examples quickstart.py RCC_Quickstart.ipynb RCC_Bounds_Quickstart.ipynb
python -W error -m pytest
rcc-refcert reproduce --check
python -m build
```

CI also executes both notebooks in their declared kernel, installs both distribution
formats outside the checkout, and checks the public entry points on Windows
and macOS. Certificate changes must preserve the distinction between a supplied
candidate and the returned upper constant, including near-critical and
nonhalting boundary regressions.

If the scientific output intentionally changes, explain why, update the
declared expectations, and regenerate both frozen reference files from the same
verified run.
