# Contributing

RCC studies quantum circuit complexity under an explicit physical generation
model. Its principle of structural fairness accounts for the structure supplied by
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
- **terminal-state bounds:** spectrum or measurement-based methods, cost
  inversion, and connections to finite-control reference certificates;
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

1. a finite-input computation, with numerical or scalar-enclosure evidence;
2. a fixed-model semidensity, domination, certificate, or conditional cost-bound
   statement;
3. a model-family statement requiring a uniform argument;
4. the RCC theorem under its complete physical and transcription hypotheses.

The finite-control kernel produces numerical evidence for finite-input and
fixed-model checks. The terminal-state calculator encloses the scalar cost
inversion under declared model arguments; it records matrix-certificate
evidence and sampling confidence separately. A family-level or theorem-level
claim also needs its uniform analytic, physical, and transcription arguments;
scalar replay does not discharge those obligations.

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

## Changing terminal-state calculations

Read the exact-input, sampling, and cost-unit contracts in
[`docs/TERMINAL_BOUNDS.md`](docs/TERMINAL_BOUNDS.md). A new method should explain
which information bound it computes, how it enters cost inversion, and which
model or measurement assumptions justify that path.

Preserve exact scalar inputs and conservative rounding through calculation,
serialization, and replay. Test the lower-bound direction against a case with
an independently known result, including a relevant zero or boundary case.
An integer-slot bound requires the declared integer cost domain; the upper
endpoint of a calculator enclosure is not a physical upper bound on cost.

Measurement changes must keep the task, projector, fixed sample size, failure
budget, and acquisition digest consistent. New sampling or readout models need
their own justified contracts. The H.3/H.4 adapter must verify the supplied
proof object on the actual model and use the returned upper constant, while
retaining the numerical evidence level and the external model premises.

If inputs or outputs change, update the templates, record validation, replay,
and schema documentation together. Keep the guide and bounds notebook runnable;
describe any compatibility effect in the changelog. A saved record identifies
its package version, so replay behavior must be assessed for that version.

## Local verification

From the repository root, use the environment created by the
[source quickstart](README.md#quick-start), which already includes development
dependencies. On macOS and Linux:

```bash
.venv/bin/python -m ruff check src tests examples quickstart.py RCC_Quickstart.ipynb RCC_Bounds_Quickstart.ipynb
.venv/bin/python -m ruff format --check src tests examples quickstart.py RCC_Quickstart.ipynb RCC_Bounds_Quickstart.ipynb
.venv/bin/python -W error -m pytest
.venv/bin/python -m rcc_refcert reproduce --check
.venv/bin/python -m build
```

On Windows, substitute `.venv\Scripts\python.exe`. For an environment you
manage yourself, install with `python -m pip install -e ".[dev]"` and replace
`.venv/bin/python` with that environment's Python interpreter in every command.

CI also executes both notebooks in their declared kernel, installs both distribution
formats outside the checkout, and checks the public entry points on Windows
and macOS. Certificate changes must preserve the distinction between a supplied
candidate and the returned upper constant, including near-critical and
nonhalting boundary regressions.

If the scientific output intentionally changes, explain why, update the
declared expectations, and regenerate both frozen reference files from the same
verified run.
