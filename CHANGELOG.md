# Changelog

## Unreleased

- Add conditional terminal-state cost bounds from complete exact spectra and
  predeclared fixed-projector counts, with conservative scalar enclosures.
- Add task-bound acquisition protocols, lossless JSON inputs, saved records,
  same-version replay, installed templates and a guided bounds notebook.
- Connect H.3/H.4 proof objects through fresh numerical verification and exact
  preservation of the propagated upper constant. Include an eight-output
  finite model with constructive one-slot witnesses.
- Refresh quickstart installations when the dynamic version changes. Require
  paired JSON/Markdown evidence at canonical report locations for both absolute
  and relative paths; custom Markdown-only reports remain supported.

Existing reference numbers and expected outcomes are unchanged. Reference
copies update only their producer version.

## 0.1.1 (2026-09-06)

- Fixed-point audits propagate matrix-assembly and solve errors to the output
  and reference-scaled constant. Unresolved precision returns `inconclusive`;
  H.34 estimates are distinguished from certificate upper constants.
- H.34 returns `inconclusive` when positive input uncertainty leaves reference
  support unresolved, including finite and infinite nominal constants.
- Model audits consistently use the caller's tolerance. Empty Kraus branches
  and codewords outside the supported numerical weight range are rejected.
- Explicit enumeration and dense matrix construction check configurable
  resource budgets before beginning expensive work.

The reference cases retain their numerical results and expected outcomes.

## 0.1.0 (2026-09-06)

Initial release of `rcc-refcert`, a Python research toolkit for finite-control
models and reference certificates in structure-fair quantum circuit complexity.
The implementation follows manuscript version 4; see the
[paper-to-code map](docs/PAPER_MAP.md) for its relation to the public paper.

### Models and certificates

- Define prefix-controlled quantum processes and compute their terminating
  program semidensities, with explicit treatment of nonhalting sectors.
- Check fixed-model reference domination, verify Bellman–Choi and
  reference-potential certificates, and analyze reference gain–cost assignments
  and sufficient prefix-code completions.
- Construct and audit new finite-control models through the public Python API.

### Examples and reproducibility

- Three reference cases cover a closed-form construction, a multiblock model
  with an intentional sufficient-route failure, and a recurrent nonhalting
  boundary.
- A complete paired-reset example connects a declared model and its reference
  certificate to an RCC lower bound of one slot, attained by an explicit
  one-slot preparation.
- The `examples`, `example`, and `reproduce` commands provide readable reports
  and versioned JSON. Packaged reference results support reproducibility checks
  from both source checkouts and installed distributions.
- A guided Jupyter notebook and model guide support a first run and the
  construction of new research inputs.

### Results and numerical conventions

- Reports identify check outcomes, evidence levels, numerical tolerances, and
  agreement with reference expectations.
- Certificate reports separate candidate constants from usable upper bounds
  that include numerical error corrections. Unresolved checks return
  `inconclusive` with no usable constant; valid certificates can remain
  unresolved for slowly halting dynamics.
- Gain–cost checks account for numerical uncertainty at the Kraft boundary,
  and suggested prefix codes use upper gain estimates. Unresolved linear
  outputs retain finite-depth evidence and return no domination constant.
- The [output contract](docs/OUTPUT_CONTRACT.md) and
  [numerical conventions](docs/CONVENTIONS.md) describe result fields, support
  diagnostics, and precision requirements.

### Installation

- Supports Python 3.10–3.14, with verified entry points on Linux, Windows, and
  macOS.
- A one-command quickstart creates an isolated environment with locked
  verification dependencies, runs the test suite, and reproduces the reference
  results. Fresh output is written separately from the reference files.
- Wheel and source distributions include the reference evidence and CLI.
