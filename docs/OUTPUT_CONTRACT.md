# Output contract

## Terminal and JSON modes

Every command defaults to reader-facing text. `--format json` selects a stable
machine-facing document:

| command | schema |
|---|---|
| `rcc-refcert examples --format json` | `rcc-refcert.case-list` |
| `rcc-refcert example NAME --format json` | `rcc-refcert.case-audit` |
| `rcc-refcert reproduce --format json` | `rcc-refcert.reference-suite` |

Each document carries `schema_version: 2`. Additive fields may appear within a
version; removing a field or changing its meaning requires a new version.

The standalone `examples/paired_reset_lower_bound.py --json` document uses
schema `rcc-refcert.paired-reset-lower-bound`, version `3`. It reports the
model declaration, endpoint gap, lower bound, feasible preparation, exact
fixed-model optimum, and certificate constants described below.

Schema versions identify output formats independently of the package version.

## Producer and source provenance

Every machine-facing document carries a top-level `producer` object with the
software name and package version. A fresh command or fixed-example result also
carries `provenance.repository` and `provenance.tested_revision` when
`RCC_REFCERT_SOURCE_REVISION` supplies a full 40-character Git commit. CI sets
that variable to the exact tree tested by the workflow. Local runs without a
verified source revision omit `provenance` rather than guessing from the
current directory.

Canonical frozen evidence retains the stable `producer` identity but omits a
commit field. Its containing repository commit or release tag supplies that
version anchor without introducing a self-referential commit claim into the
tracked JSON.

## Artifact roles

The top-level `artifact_role` distinguishes a newly computed result from the
canonical normalized evidence checked into the repository:

| artifact | `artifact_role` | purpose |
|---|---|---|
| CLI JSON and `generated_results/reference_suite.json` | `fresh-run-evidence` | complete numerical detail from the current execution |
| `results/reference_suite.json` and its installed package-resource copy | `canonical-frozen-evidence` | normalized regression evidence committed with the source tree and shipped in distributions |

The two files retain the same descriptive filename because they represent the
same scientific suite. Their schemas and `artifact_role` values make their
different evidentiary roles explicit to readers and automated consumers.

## Reader-facing reference results

The first summary line for a bundled case describes its declared case-level
reference role:

| label | meaning |
|---|---|
| `PASS` | every named check in the case is expected to pass and does pass |
| `EXPECTED ROUTE FAILURE` | a declared sufficient route fails as designed, while the case matches its reference expectations |
| `EXPECTED BOUNDARY` | the case reaches a declared mathematical boundary and matches its reference expectations |
| `MISMATCH` | at least one observed outcome differs from the declared reference outcome |

Individual check lines remain authoritative for what passed, failed, was
inconclusive, or was not applicable.

## Outcomes and expectations

Checks report `outcome` and `evidence` separately. A bundled case also records
`expected_outcome` and `matches_expectation`. This is how an intentional H.70
failure remains machine-distinguishable from an unexpected regression.

The complete case or suite result is summarized by
`matches_reference_expectations`. Consumers should use that field for the
bundled regression decision and retain individual outcomes for interpretation.

## Numerical values

JSON represents unavailable or non-finite scalars as `null`; fields such as
`constant_is_infinite` preserve the mathematical distinction where it matters.
Tolerances and residuals are carried either in the run parameters or alongside
their individual check.

H.3 and H.4 reports carry these fields in both summary and detailed JSON:

| field | meaning |
|---|---|
| `candidate_constant` | the supplied H.3 constant or the original H.4 sum of initial coefficients times potentials |
| `constant` | the usable numerical upper constant, including its error budget; `null` unless the certificate passes |
| `constant_error_bound` | the reserved correction in a passing result; the estimated required correction for an inconclusive result when available |

The `constant-error-budget` check propagates one-sided local residuals through
the continuation dynamics. Its acceptance budget is `tol * max(1, candidate)`.
When a positive correction is needed, the returned constant reserves that
budget and rounds upward by one floating-point step. Matrix checks can pass
while this final check remains `inconclusive`. Consumers must inspect `outcome`
and use `constant` for a passing bound. See [CONVENTIONS.md](CONVENTIONS.md)
for the propagation method and its numerical evidence level.

H.34 additionally reports `reference_rank`, `reference_condition_number`, and
`message`. The rank counts eigenvalues resolved above the numerical threshold.
If a small positive eigenvalue leaves support unresolved, `constant`,
`support_compatible`, and `constant_is_infinite` are all `null`. An infinite
constant requires a positive-mass witness in an established exact kernel.

The machine-facing JSON returned by the command retains computed finite
diagnostics. In the frozen structured result and Markdown report, a diagnostic
whose absolute value is at or below its stated tolerance is represented as
zero; the remaining finite scalars are stored to twelve significant digits.
Certificate upper constants and their error bounds instead round toward
positive infinity and are never discarded as sub-tolerance residuals. The
tolerance remains part of the result, and the command JSON supplies the
underlying computed values.

`--details` preserves each outcome while adding per-depth checks, certificate
residual summaries, control-wise gains, and suggested codewords.

## Exit codes

| code | meaning |
|---:|---|
| `0` | bundled expectations and every requested frozen comparison match |
| `1` | a scientific expectation or requested frozen comparison differs |
| `2` | command-line input is invalid or a requested comparison file is missing |

`reproduce --check` compares the normalized suite structure and rendered
Markdown with the frozen evidence installed as package resources, so the
default check works outside a repository checkout. `reproduce --check PATH`
compares with another report and also checks a sibling `reference_suite.json`
when one is present. The quickstart and source-tree CI pass the checked-in
`results/reference_report.md` explicitly, keeping the repository copies under
direct regression. Both check forms are read-only. `reproduce --output PATH`
writes only to the explicit destination.
