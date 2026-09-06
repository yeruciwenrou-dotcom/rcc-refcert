# Changelog

## 0.1.0 (unreleased)

Initial release of the finite-control model, reference-certificate, and
gain-cost research interfaces.

### Numerical correctness

- propagated H.3 and H.4 residuals to the final domination constant, including
  slowly halting dynamics and zero-deficit nonhalting sectors;
- distinguished unresolved small positive reference eigenvalues from exact
  kernel witnesses in fixed-model domination diagnostics;
- computed Elias header lengths with integer arithmetic across large binary
  boundaries.

### Result interpretation and compatibility

- H.3 and H.4 reports retain the original value as `candidate_constant` and
  return a usable `constant` only when `outcome` is `pass`. The returned upper
  constant includes the correction reported by `constant_error_bound`;
- unresolved error budgets return `inconclusive` with `constant: null`.
  Conservative error propagation can leave a mathematically valid certificate
  unresolved, especially for slowly halting dynamics;
- result JSON uses schema version 2; the paired-reset example uses version 3.
  Programs consuming earlier output must handle nullable constants and support
  diagnostics and use the passing upper constant for subsequent bounds. See
  [the output contract](docs/OUTPUT_CONTRACT.md);
- frozen certificate upper bounds round upward to preserve their correction.
  The three reference-case outcomes, semidensities, H.34 domination values,
  and exact one-slot optimum of the paired-reset example are preserved.

### Scientific scope and executable evidence

- established three declared finite-control reference cases: a transparent
  closed-form construction, a multiblock certificate diagnostic with an
  intentional sufficient-route failure, and a recurrent nonhalting boundary;
- unified the implemented Appendix F witnesses and H.1, H.2, H.34, H.3, H.4,
  H.6, H.70, and H.76 checks in deterministic audit results;
- added a fixed paired-reset example that connects model declaration, program
  semidensity, an exact one-shot information gap, the RCC lower-bound theorem,
  and cost inversion to a one-slot lower bound, together with the matching
  one-slot preparation witness that proves tightness for that declared model;
- exposed the one-shot gap in bits and in the Section-II R-structon reporting
  unit while keeping continuous inversion and the discrete slot floor
  distinct;
- separated observed outcomes from evidence levels and kept software checks,
  analytic model obligations, and theorem-level consequences distinct in
  readable and structured output;
- added representation-invariance and deterministic generated-model checks
  for Kraus freedom, basis covariance, complete relabeling, path/block
  agreement, fixed-point convergence, and fixed-model domination constants.

### Research interface and documentation

- established the `examples`, `example`, and `reproduce` CLI commands with
  readable output and a versioned JSON contract;
- exposed public finite-control model, audit, certificate-verification, and
  reference gain-cost interfaces for new research inputs;
- added the RCC overview, scientific scope, paper map, tensor and numerical
  conventions, model guide, output contract, and a complete fixed-model
  lower-bound walkthrough;
- added a guided Jupyter first run with direct views of the semidensity and
  H.70/H.76 diagnostics;
- documented the source tree's manuscript-version alignment.

### Reproducibility and distribution

- added a one-command quickstart that creates an isolated environment with
  locked verification dependencies, runs the independent suite, checks frozen
  evidence, and writes fresh results without overwriting the reference files;
- shipped the canonical Markdown report and normalized JSON as package
  resources so `reproduce --check` works outside a source checkout;
- distinguished fresh and frozen evidence with explicit artifact roles and
  recorded producer-version and optional tested-revision provenance while
  keeping the frozen evidence deterministic;
- made both wheel and source archives independently installable and able to
  reproduce the packaged reference evidence outside the repository;
- supported Python 3.10 through 3.14, exercised NumPy 1.26 and current NumPy 2,
  verified native Notebook execution and the full public quickstart on
  Windows, and checked public reference reproduction on macOS.
