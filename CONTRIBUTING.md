# Contributing

RCC formulates universal optimal quantum circuit complexity relative to an
explicit physical generation model. Its structure-fairness principle places
the reference background, available dynamics, program description, and
resource cost in one common specification. Its scientific value can grow as
researchers test those choices, bring new physical models into the framework,
compare certificate methods, and sharpen the boundary between executable
evidence and analytic claims.

`rcc-refcert` provides a concrete research kernel for that work. We welcome
contributions across theory, algorithms, numerical verification, and
scientific communication. The bundled examples form an initial executable
basis rather than a closed catalogue, leaving room for new models, proof
objects, cost assignments, verification methods, and explanatory material.

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
the model or certificate object, the RCC claim layer it touches, and the
executable evidence it should produce. Bug and documentation forms collect the
narrower information needed for those changes.

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

The package directly produces the first two layers. A family-level or
theorem-level claim also needs its uniform analytic, physical, and transcription
arguments.

## Adding a model or certificate

A bundled model should expose a distinct physical mechanism, formula,
convention risk, or mathematical boundary. Document:

- the reference state, control spaces, actions, codewords, and intended
  physical interpretation;
- the Appendix F/H objects it exercises;
- the expected outcomes, including designed route failures or boundaries;
- the test that would fail under the most plausible incorrect implementation.

An expected H.70 failure records a cost shortfall along that sufficient route.
Family-uniform reference admissibility is established through the corresponding
uniform analytic argument.

Keep dependencies few and tied to a clear package responsibility. Add parameter
sweeps or user interfaces when they support a defined scientific use case and
preserve the minimal kernel.

## Local verification

Install the development environment and run the core checks:

```bash
python -m pip install -e ".[dev]"
ruff check src tests examples quickstart.py RCC_Quickstart.ipynb
ruff format --check src tests examples quickstart.py RCC_Quickstart.ipynb
python -W error -m pytest
rcc-refcert reproduce --check
python -m build
```

CI also executes the Notebook in its declared kernel, installs both distribution
formats outside the checkout, and checks the public entry points on Windows
and macOS. Certificate changes must preserve the distinction between a supplied
candidate and the returned upper constant, including near-critical and
nonhalting boundary regressions.

If the scientific output intentionally changes, explain why, update the
declared expectations, and regenerate both frozen reference files from the same
verified run.
