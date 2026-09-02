# Changelog

## 0.1.0 (unreleased)

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
  agreement, fixed-point convergence, and fixed-model domination constants;
- retained explicit claim boundaries: finite proof-object and numerical checks
  do not replace physical reference consistency, faithful transcription,
  model-family uniformity, or the paper's analytic lower-bound proof.

### Research interface and documentation

- established the `examples`, `example`, and `reproduce` CLI commands with
  readable output and a versioned JSON contract;
- exposed public finite-control model, audit, certificate-verification, and
  reference gain-cost interfaces for new research inputs;
- added the RCC overview, scientific scope, paper map, tensor and numerical
  conventions, model guide, output contract, and a complete fixed-model
  lower-bound walkthrough;
- added a guided Jupyter first run with stable cell identities and direct views
  of the semidensity and H.70/H.76 diagnostics;
- documented the source tree's exact manuscript-version alignment while
  preserving the boundary between executable finite-model evidence and the
  paper's analytic and model-family arguments.

### Reproducibility and distribution

- added a one-command quickstart that creates an isolated environment with
  locked verification dependencies, runs the independent suite, checks frozen
  evidence, and writes fresh results without overwriting the reference files;
- shipped the canonical Markdown report and normalized JSON as package
  resources so `reproduce --check` works outside a source checkout;
- distinguished fresh and frozen evidence with explicit artifact roles and
  recorded producer-version and optional tested-revision provenance while
  keeping the frozen evidence deterministic;
- included the complete test support required by source distributions and
  verified clean installations of both wheel and source archives outside the
  repository;
- supported Python 3.10 through 3.14, exercised NumPy 1.26 and current NumPy 2,
  executed the native Notebook kernel, ran the full public quickstart on
  Windows, and retained the public reproduction entry check on macOS.

### Validation and repository governance

- made warnings-as-errors tests, Ruff checks, frozen-evidence reproduction,
  native Notebook execution, distribution builds, and cross-platform public
  entry checks part of one aggregate required CI gate;
- pinned official GitHub Actions to reviewed full commit SHAs and added an
  explicit manual workflow entry for independent reruns and release validation;
- preserved the existing public API, runtime dependency set, and frozen
  scientific results throughout the validation work.
