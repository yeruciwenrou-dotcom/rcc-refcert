# Changelog

## 0.4.0

You can now plan a measurement around the preparation cost you want to rule
out and bound differences in RCC between states measured in the same classical
window.

- **Design a measurement and certify a lower bound.** Given a response or
  cost threshold and an expected hit rate, find the number of shots to take
  and the number of hits needed to pass. Use the same binary measurement on
  the target and reference, or supply a known reference response. The
  calculation can account for known false-positive and false-negative rates.
- **Compare window RCC from counts.** Use the counts for every outcome of a
  projective measurement to put confidence bounds on RCC in the measured
  classical window. Two states measured in that same window can be ordered
  when their intervals separate. For a containing quantum window, the
  measurement gives a lower bound for each state. If a projection selects only part of the sample, you can also
  weight its contribution by the probability of retaining a shot.
- **Compare measurement settings and preparation programs.** For the same
  noisy six-qubit cluster state, either local setting alone certifies at least
  one slot in the default example. Combining the two raises the lower bound to
  two slots. In the cooling study, a six-slot program is optimal for the full
  three-qubit target at trace-distance tolerance 1/50. Joint counts track the
  target and bath before and after the final refresh. Both studies accept raw
  counts or joint Qiskit readouts and can be recomputed from a shared bundle. The
  [IBM Vigo example](docs/FINITE_DATA_STUDIES.md#check-the-mapping-on-a-hardware-file)
  uses archived five-qubit counts to check which bit belongs to each qubit.
- **See which gain certificate supports a cost bound.** An empty or invalid
  certificate now gives a diagnostic for the submitted input. To try the
  automatic certificate as well, set `on_gain_failure` to `"auto"`. The
  report records the original diagnostic and the certificate actually used.
  Cost requests reject exact numbers with repeated signs. Terminal-state
  requests identify normalized trace distance as the required error measure.

Terminal reports give the circuit lower bound in atomic slots and the
calibrated one-shot reading in R-structons. For exact spectra they show how
spectral skew raises the unsmoothed information and how much smoothing removes. Exact binomial
analysis accepts up to 4,096 observations per sampled arm. Cooling reports
give target, bath, joint and correlation intervals at each stage. Window
exports now include global readings, partition correlations and the lower
bound after accounting for discarded shots. Use `cost analyze --plot` or
`--csv` on a trajectory. On `bound spectrum` and `bound counts`, use `--output`
to save the report.

Cost comparisons now identify the model, complete target, tolerance and maximum
remaining saving for the program attaining the upper endpoint. In the
[half-erasure benchmark](docs/COST_AND_WINDOWS.md#build-a-half-erasure-channel),
the reachable states give an independent check on the optimal cost. Window reports
give the uniform reference, number of action classes and conversion to
R-structons. State-window and numerical-model inputs now require an integer
action-class count of at least two. Shared cost and state-window bundles
identify the software that calculated the saved result across versions.

Use 0.4.0 or later to verify the new finite-data bundles and cost requests that
specify `on_gain_failure`. The [compatibility table](docs/ANALYSIS_BUNDLES.md)
lists the earliest reader for each bundle.

## 0.3.0 (2026-11-15)

This release adds preparation-cost intervals and subsystem RCC complexity
profiles. It also extends the existing evidence-sharing tools to these new
workflows.

### New research capabilities

- **Bound the optimal preparation cost.** For exact diagonal-preserving models,
  combine a rigorous lower bound with the cost of a successful candidate
  program. Compare candidates for the same target and scan the allowed error.
  The reset and cooling examples show both matching bounds and open gaps;
  the cost includes the halt operation.
- **Compare subsystem complexity in pure and mixed states.** Use window RCC
  under a common reference and control bandwidth to compare states, separate
  local and correlation contributions, or follow a preparation step by step.
- **Adapt complete research examples.** Editable reset and cooling tasks and
  three state probes connect physical questions to calculations. The new
  workflow notebook, readable reports, CSV exports and optional plots support
  comparison and reuse. Matrix models can also be supplied for numerical
  candidate diagnostics.
- **Share and reverify the new workflows.** Save cost and window requests,
  inputs and results in complete analysis bundles. A recipient can recompute
  them and compare fresh evidence with the saved results, including numerical
  diagnostics and unresolved outcomes.

Start with the [cost and window guide](docs/COST_AND_WINDOWS.md) or the
[workflow notebook](RCC_Workflows_Quickstart.ipynb).

### Compatibility

- Existing model, reference-certificate and terminal-state interfaces remain
  available. Existing model/certificate bundles (container schema 1) remain
  readable and verifiable.
- New cost/window bundles use container schema 2. Recipients need **0.3.0 or
  later**; see the [recipient guide](docs/ANALYSIS_BUNDLES.md).
- **Early development exports only:** numerical models with transitions between
  control blocks must be re-exported from the original `FiniteControlModel`
  if they use the ambiguous schema-1 format from the first development build.
  The numerical-model format is separate from the bundle container;
  [migration details](docs/COST_AND_WINDOWS.md#numerical-models-and-candidate-diagnostics)
  explain the distinction.

The existing terminal-state bound route and frozen reference values retain
their meaning. The new cost workflow uses additional model and candidate
information to bound the preparation optimum. Reference-file producer metadata
now identifies version 0.3.0.

## 0.2.0 (2026-10-25)

This release connects custom-model certificate preparation, terminal-state
bounds and complete evidence sharing.

### Added

- **Certificate preparation.** Construct numerical Bellman–Choi (H.3)
  candidates for custom finite-control models, then verify them independently.
  Report unsupported, unresolved and resource-limited attempts explicitly.
- **Complete analysis bundles.** Save original model matrices, proof objects,
  numerical controls and bound requests. Inspect or reverify the bundle through
  the Python API or `rcc-refcert bundle` commands.
- **Fresh-versus-saved evidence.** Show recomputed constants beside historical
  results and explain whether the earlier result is still supported. Counts
  retain their original acquisition protocol and statistical event.
- **Editable examples.** Add alternating damping/pumping and cyclic noisy-reset
  workflows, guides and notebook steps for adapting and sharing calculations.

### Reliability and compatibility

- Apply resource checks before certificate verification, task binding and
  bundle import; keep diagnostics usable even for extreme resource requests.
- Check saved verification summaries against their proof objects and numerical
  controls. Preserve consistent failed or inconclusive results for diagnosis.
- Preserve existing output files and provide recovery hints for file errors.
  Explain the state-side RCC term, the full one-shot lower bound and the
  preparation optimum as distinct quantities.

Frozen reference values and bound-record v2 retain their numerical meaning.
Use the original package version for exact scalar replay of an older record;
complete bundles also support fresh model/certificate verification.

## 0.1.3 (2026-09-15)

Align the guides and worked examples with RCC manuscript version 4.

- Update the paired-reset explanation for Eq. (III.1) and the audit-record
  requirements in Appendix D.6.
- Add a runnable Bellman–Choi (H.3) certificate-to-bound example to the
  terminal-state guide and notebook.
- Clarify reference-dependent resource accounting, model qualifications and
  expected reference-check outcomes.

Numerical algorithms, calculated bounds and record schemas are unchanged.
Use 0.1.2 for exact scalar replay of records produced by that release.

## 0.1.2 (2026-09-12)

Add terminal-state complexity bounds from target spectra and measurement counts.

### Added

- Calculate cost lower bounds from complete exact spectra or predeclared
  fixed-projector counts, with conservative scalar enclosures.
- Bind counts to acquisition protocols; provide lossless JSON inputs, saved
  records, same-version replay, installed templates and a bounds notebook.
- Connect verified Bellman–Choi (H.3) and reference-potential (H.4)
  certificates to the bound calculator. Include an eight-output finite model
  with constructive one-slot witnesses.

### Reliability

- Refresh quickstart installations when the package version changes and keep
  canonical JSON/Markdown reports paired.
- Bind certificate matrices to records with a versioned numeric format and
  check matrix budgets before verification.
- Avoid an unused continuation after the last requested halting term, and
  preserve record generation and replay for extreme accepted exact inputs.

Existing reference values and expected outcomes are unchanged; reference
copies update their producer version.

## 0.1.1 (2026-09-06)

Improve numerical error accounting, support diagnostics and resource checks.

- Propagate matrix-assembly and solve errors into fixed-point audit results
  and reference-scaled constants. Distinguish fixed-model domination estimates
  from certificate upper bounds.
- Return `inconclusive` when precision or reference support is unresolved,
  rather than reporting a usable constant.
- Apply the caller's tolerance consistently; reject empty Kraus branches and
  codewords outside the supported numerical weight range.
- Check resource budgets before explicit enumeration or dense matrix assembly.

Reference values and expected outcomes are unchanged.

## 0.1.0 (2026-09-06)

Initial release: finite-control models and reference certificates for
structure-fair quantum circuit complexity.

- Define prefix-controlled quantum processes and compute code-weighted sums
  of terminating outputs, including models with nonhalting sectors.
- Check reference domination, verify Bellman–Choi and reference-potential
  certificates, and analyze local gain–cost conditions and prefix codes.
- Construct custom models through the Python API. Explore three reference
  cases and a paired-reset example with a one-slot RCC lower bound attained
  by an explicit preparation.
- Use readable reports and versioned JSON, frozen reference evidence, a guided
  notebook and a one-command quickstart. Reports identify numerical evidence,
  tolerances and unresolved checks.
- Install from a wheel or source distribution with Python 3.10–3.14;
  entry points are verified on Linux, Windows and macOS.

The [paper-to-code map](docs/PAPER_MAP.md) locates the implemented objects.
The [output contract](docs/OUTPUT_CONTRACT.md) and
[numerical conventions](docs/CONVENTIONS.md) describe how to read the results.
