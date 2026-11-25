# Share and reverify an analysis

An analysis bundle contains the inputs needed to recompute a result and the
author's saved evidence for comparison. A recipient can independently check
the calculation without the author's modeling script.

| Calculation | Bundle contents | Reader version |
|---|---|---|
| Model certificates and terminal-state bounds | Model and proof arrays, numerical controls, requests and historical results; container schema 1 | 0.2.0 or later |
| Preparation costs and subsystem complexity profiles | Requests, models, candidates, windows and historical results (container schema 2) | 0.3.0 or later for the original workflow fields. Requests that set `on_gain_failure` require 0.4.0 or later. |
| Fixed-effect target and reference counts | Raw histograms, frozen measurement and sampling plans, model premises and historical result (container schema 3) | 0.4.0 or later |
| Complete projective readouts | Frozen acquisitions, histogram counts, windows and result (container schema 4) | 0.4.0 or later |
| Cluster and cooling studies | Raw acquisitions, register layout, constraints, model and study result (container schema 5) | 0.4.0 or later |

Use a bundle when handing results to a collaborator, preserving a calculation
for review, or comparing numerical environments. The existing bound record
remains useful for exact scalar replay; it contains input hashes rather than
the complete model and proof arrays.

## Reverify a bundle you received

Use the producer version supplied with the `.rccbundle` file, or a compatible
reader from the table above. Install it from
[PyPI](../README.md#install-from-pypi) or the
[source quickstart](../README.md#install-from-source). Replace `received.rccbundle`
with your file's path:

```bash
python -m rcc_refcert bundle inspect received.rccbundle
python -m rcc_refcert bundle verify received.rccbundle --output received-verification.json
```

Use the interpreter from your active installation. Verification itself needs
only the installed package and bundle. Later examples in this guide use the
[source quickstart](../README.md#install-from-source) and `.venv/bin/python` from the
checkout root. On Windows, substitute `.venv\Scripts\python.exe`.

`inspect` checks stored data, object bindings and result consistency. `verify`
recomputes the analysis and compares fresh evidence with the saved history.
The bundle stays unchanged; `--output` writes a separate recipient report.

Workflow readers check numerical decisions against the saved candidate errors,
legal programs and numerical diagnostics before reporting a consistent record.
The recipient's resource limits apply before reconstructing matrices. Compound
workflow records have bounded storage for both original and effective inputs;
the [workflow guide](COST_AND_WINDOWS.md#reports-limits-and-revalidation) gives
their capacity and delivery rules.

For cost and window results, continue to
[complete cost and window workflows](#complete-cost-and-window-workflows).
The certificate examples and detailed contracts below concern schema 1.
For the cyclic-reset certificate example, a successful verification includes:

```text
Stored record consistency: pass
Fresh matrix verification: pass (numerical)
Fresh certificate constant: 1.0000000001000002
Historical certificate constant: 1.0000000001000002
Historical results supported: yes
```

The two request sections each report `scalar comparison match`,
`Same-version replay: match`, and `Integer lower bound: 2`. The decimal
constants may differ across numerical environments.

`inspect` checks the stored record and identifies its producer. `verify`
then checks the matrices afresh. Read **Fresh matrix verification** and
**Historical results supported** together: the first concerns the current
certificate check; the second asks whether that result supports the earlier
calculation. A different producer version can leave exact scalar replay
unavailable while fresh matrix verification remains possible.

Verification can also run from another directory: use the full path to the
installed environment's Python and to the bundle. Choose an unused report
filename. The original bundle remains unchanged, and `--output` saves the
full comparison report as JSON.

### Use the verified data in a new calculation

For a schema 2–5 bundle, verification writes the freshly calculated record
under `fresh_result`. The archive also contains the ordinary request used by
the command-line tools. From the directory containing the two files above,
run the following Python once for each new output directory:

```python
import json
from pathlib import Path
from zipfile import ZipFile

out = Path("received-analysis")
out.mkdir()
verification = json.loads(Path("received-verification.json").read_bytes())
with ZipFile("received.rccbundle") as archive:
    version = json.loads(archive.read("manifest.json"))["schema_version"]
    request = json.loads(archive.read("request.json"))
if version == 2:
    request = request["original"]
(out / "request.json").write_text(json.dumps(request, indent=2) + "\n", encoding="utf-8")
(out / "fresh.json").write_text(json.dumps(verification["fresh_result"], indent=2) + "\n", encoding="utf-8")
```

Choose the command for your calculation. For a cost task, `other-cost.json`
is a second result from `cost analyze --output`. For a study, set the new
search budget above the one reported by the first run. Plotting uses the
`plots` extra.

| Calculation received | Continue from the verified data |
|---|---|
| Schema 2, candidate costs | `python -m rcc_refcert cost compare received-analysis/fresh.json other-cost.json` |
| Schema 2, state windows or schema 4, projective counts | `python -m rcc_refcert window analyze received-analysis/request.json --csv received-analysis/windows.csv --plot received-analysis/windows.svg` |
| Schema 3, fixed-effect counts | `python -m rcc_refcert bound counts received-analysis/request.json --bundle received-analysis/counts.rccbundle` |
| Schema 5, cooling study | `python -m rcc_refcert study analyze received-analysis/request.json --max-dp-updates 2000000 --bundle received-analysis/extended.rccbundle` |

Schema 1 carries model and proof arrays. Use the matrix-verification workflow
below for those files.

## Export and check

To create a bundle of your own, use the same quickstart environment and run
the complete example from the checkout:

```bash
.venv/bin/python examples/cyclic_reset_workflow.py --bundle cyclic-reset.rccbundle
.venv/bin/python -m rcc_refcert bundle verify cyclic-reset.rccbundle --output cyclic-reset-verification.json
```

Use a new filename for each exported bundle and verification report. The
verification command preserves the original bundle and writes fresh evidence
separately. Send the bundle and its producer version to the recipient; pin the
same package version for exact historical scalar replay. The
[recipient workflow](#reverify-a-bundle-you-received) needs no example scripts.

For a Python workflow, `save_analysis_bundle(path, model, certificate,
requests=[...], tol=..., source=...)` saves one proof object and zero or more
bound requests. Each request has a `kind` of `spectrum` or `counts` and a
`request` containing the ordinary bound API input. Bind every task with
`with_reference_certificate` before creating the bundle. Freeze counts
protocols only after that task has been fixed.

For a certificate-only analysis, pass `requests=[]`. The bundle still contains
the full model, candidate, and numerical verification. This is useful when the
research question concerns reference domination without a terminal-state
target.

`verify_analysis_bundle(path, tol=None, limits=...)` exposes the same fresh
verification through Python. Omitting `tol` uses the recorded tolerance. An
explicit tolerance produces a new report; it never changes the saved controls
or historical result.

## Record the software revision

For an analysis made from a Git checkout, record the full commit alongside
the package version. After installing that checkout in the environment used
for the calculation, check that it has no uncommitted changes:

```bash
git status --short
git rev-parse HEAD
export RCC_REFCERT_SOURCE_REVISION="$(git rev-parse HEAD)"
```

Run the export or verification commands in that shell. In PowerShell, use
`$env:RCC_REFCERT_SOURCE_REVISION = git rev-parse HEAD`. If the working tree
has changes, commit the intended source and reinstall it before assigning
that revision; a commit ID alone cannot describe uncommitted edits.

For a model-certificate bundle (schema 1) or a preparation-cost or known-state
window bundle (schema 2), `producer.source_revision` records the author's supplied commit.
`inspect` preserves that identity, while the fresh verification report's
`producer.source_revision` records the recipient's supplied commit. Keep the
original bundle and fresh report together. Without the environment variable,
the field is `null`. The software validates the full 40-character Git ID but
does not infer it from the current directory or authenticate the declaration.

Fixed-effect counts, complete projective readouts and finite-data studies
(schemas 3–5) record the package name and version. For a source installation,
share the full output of `git rev-parse HEAD` alongside these bundles.

## Three questions, three answers

The verification report separates these questions:

| Question | Evidence |
|---|---|
| Are the stored inputs and results internally consistent? | Format, component digests, model/proof binding, and request/history checks |
| Does the old scalar calculation replay? | Same-producer-version replay from the original exact request |
| Does current numerical verification support the historical constant? | Fresh matrix verification and comparison with the saved constant |

These checks have different meanings. A digest establishes input identity. A
scalar replay recomputes the recorded arithmetic. Fresh certificate
verification checks the supplied matrices and error budget in the current
environment. The external model qualifications and sampling premises remain
visible alongside these results.

## Compare historical and fresh constants

Floating-point results can vary across environments. Historical support is
assessed using the unrounded conservative constants.

- If the fresh verification passes and its usable constant is no larger than
  the saved constant, the fresh numerical evidence supports the historical
  constant for the same input and declarations.
- If the fresh usable constant is larger, the fresh result supplies a new
  conservative bound and historical support is recorded as `no`.
- A failed or inconclusive verifier, or a resource refusal, is reported with
  the corresponding diagnostics.

For example, verifying the cyclic-reset bundle with the explicit tolerance
`1e-8` gives a fresh constant approximately `1.0000000100000002`, larger than
the historical `1.0000000001000002`. The matrix check passes, historical
support is `no`, and the integer bound remains **two**. The report gives the two
unrounded constants alongside the integer bounds. The command and its
separate output file appear [below](#format-and-numerical-identity).

For terminal-state tasks, comparison uses the same $C\ge1$ convention as the
certificate-binding adapter. A finite certificate may report a smaller
constant, but the bound task normalizes its usable constant to at least one.
The original candidate, report, and task remain in the bundle.

The bound record's producer-version restriction is retained. A version mismatch
can make historical scalar replay unavailable while the complete model and
proof still support a fresh analysis under the current software. The report
keeps those outcomes separate.

The `bundle verify` command uses these exit codes:

| Exit code | Result |
|---|---|
| `0` | Fresh matrix verification passes and the historical results are supported |
| `1` | Verification completed; a historical result is unsupported or unresolved, or matrix verification did not pass |
| `2` | Invalid input or an output-file error |
| `3` | The requested work exceeds the computation budget |

Exit `1` still produces a comparison report. Inspect its separate matrix,
historical-support, and scalar fields to understand the result. `bundle inspect`
checks stored consistency without matrix revalidation and exits `0` when that
inspection succeeds.

For exit `2`, read the input or output-path diagnostic; if the destination
already exists, keep it and choose a fresh filename. For exit `3`, review the
reported budget and the model size before explicitly changing the limit.

## Preserve the original counts event

A counts request binds a declared target, projector, fixed sample size,
statistical failure budget, and dataset to its original protocol. Revalidation
uses the original request and protocol digest.

When a new numerical certificate constant changes the bound, the verifier
reports a separate derived result linked to the original acquisition event.
The same supported probability statement is used for deterministic
post-processing with the fresh constant. The saved record identifies the acquisition
protocol used for both calculations.

The examples use synthetic counts. For experimental data, retain the
projector definition and dated acquisition and calibration records alongside
the bundle. They document the witness, the fixed sample size and sampling
assumptions, and the readout and support conditions. The embedded protocol
carries the witness ID and rank.

## Format and numerical identity

The `rcc-refcert.analysis-bundle` format has its own schema version, independent
of the bound-record schema. A bundle is a ZIP container with a JSON manifest
and numerical array payloads. It carries data rather than executable Python.
The loader reconstructs the supported finite model, Bellman–Choi certificates
(H.3), and reference-potential certificates (H.4).

Stored-history checks also compare the reported outcome with its individual
checks. A saved `pass` requires passing checks, finite nonnegative binary64
constants, and a reserved error consistent with the rounded subtraction of
the candidate from the usable constant. An H.3 candidate must match its stored
proof object. H.4's coefficient calculation is repeated by fresh verification.
See the [output contract](OUTPUT_CONTRACT.md#complete-analysis-bundles) for
the precise scope. Contradictory history is invalid input, even when container
digests match; both commands reject it before fresh matrix verification.
Consistent failed and inconclusive certificate-only analyses remain readable.

Array metadata retains shape, supported numeric dtype, and logical C-order
entries using a canonical little-endian representation. This preserves the
binary numerical inputs used by the existing certificate hashes. It does not
turn floating-point matrices into exact symbolic channels. Exact scalar
requests retain their rational values separately.

Import checks include container and element budgets, allowed members and
paths, array sizes and digests, model/proof type, and schema version. Unsupported
or incomplete data are rejected. Stored summaries cannot substitute for
missing matrix inputs.

The shared computation budget applies before certificate verification. A
different budget can be chosen explicitly:

```bash
.venv/bin/python -m rcc_refcert bundle verify cyclic-reset.rccbundle --max-matrix-elements 2097152
```

Raising the budget permits more work; it does not alter scientific validity or
improve numerical conditioning. A tolerance change is a separate choice:

```bash
.venv/bin/python -m rcc_refcert bundle verify cyclic-reset.rccbundle --tolerance 1e-8 --output cyclic-reset-tol-1e-8.json
```

For this example, the larger tolerance yields a larger conservative constant.
The command can therefore exit `1` with a valid fresh verification and a saved
comparison report: the new evidence does not support the smaller historical
constant, even though the fresh integer lower bound remains two.

Keep the original bundle and fresh report together when sharing that
comparison. The [custom-model guide](CUSTOM_MODELS.md) explains the two example
models, candidate preparation, and unresolved numerical states.

## Complete cost and window workflows

From the 0.3 quickstart environment, save a complete cost task and verify it:

```bash
.venv/bin/python -m rcc_refcert cost template cyclic-reset > task.json
.venv/bin/python -m rcc_refcert cost analyze task.json --bundle task.rccbundle
.venv/bin/python -m rcc_refcert bundle inspect task.rccbundle
.venv/bin/python -m rcc_refcert bundle verify task.rccbundle --output task-verification.json
```

Use the same `--bundle` option with `window analyze` for state-window inputs.
These schema-2 archives save the full effective request, including the model,
target basis and tensor labels, candidate words, reference scale, numerical
policy and computation controls. Verification reconstructs the request,
checks its evidence, executes candidates and recalculates windows.

If a 0.3.0 archive contains a fraction with repeated signs, reverify it with
0.3.0. For example, that version read `1/+-10` as `1/10`. The original request
preserves the spelling and the effective request records the value used. Use
the effective value when preparing a new request in 0.4.0.

Read `fresh_verification` and `historical_results_supported` in the recipient
report. Exact rational values are compared exactly. Numerical results use a
relative and absolute tolerance of `1e-10`. Same-version bitwise replay is
reported separately. For a tolerance scan, each point's request digest
includes that run's resource limits. The reader checks the author's digest,
then compares the cost, gain bound and candidate evidence at each tolerance.
Lower recipient limits can still reproduce every scientific result.

Roundoff-derived states can differ in their last bits across numerical
backends. Each saved state must match its own content digest, tensor layout
and numerical policy. Its correction must satisfy the declared density checks
and repair budget; the saved and fresh corrections are compared in trace norm
within the smaller of that budget and the state tolerance. Original input
identities remain exact. This permits supported scientific results alongside
a same-version bitwise replay mismatch.

When a correction exceeds its budget, no derived state is saved. Its reported
magnitude must be finite, nonnegative and greater than that budget. A fresh
attempt is compared at the declared numerical tolerance; the record remains
inconclusive and produces no cost interval or window value.

Verification uses the saved numerical policy. To study a different policy,
edit the request and run a new analysis. The original author result and the
recipient's fresh result retain separate identities. The schema-1 validation
path described above remains available; version 0.2.0 readers reject schema 2.
See the [workflow guide](COST_AND_WINDOWS.md#reports-limits-and-revalidation)
for analysis budgets, presentation options and examples.


### Fixed-effect counts

`bound counts request.json --bundle study.rccbundle` saves the original request and result. A recipient can run `bundle inspect study.rccbundle` to check archive integrity, data bindings, coverage identities and the conclusions implied by the stored endpoints. Run `bundle verify study.rccbundle` to compute the endpoints anew from the raw counts, apply the RCC routes and compare with the saved result. Its JSON report includes both records, historical support and a separate same-version replay comparison. A successful replay can reproduce a zero bound, information-only result or support conflict. The decision field states which conclusion the data support. [Worked example and acquisition format](TERMINAL_BOUNDS.md#target-and-reference-counts-for-the-same-effect)

### Complete projective readouts

Schema 4 saves the full window request, evidence and result. Use
`window analyze request.json --bundle result.rccbundle` to export it.
`bundle inspect` checks member integrity, the request identity and each
protocol and data digest. `bundle verify` rebuilds the confidence ledger,
clipped distributions, window bounds, retention and eligible costs from the
archived counts. It compares the fresh conclusions to the author's record
and reports same-version replay separately. The recipient needs only the
bundle and a version that supports schema 4. The physical measurement and
source declarations remain identified in the request.

### Finite-data research studies

For a cooling study, a recipient can have enough resources to verify the
archived cost interval before every candidate program has been replayed.
When the recipient's budget shortens that list, `candidate_replay` reports
the checked and expected counts and whether the fresh bounds establish the
historical interval. An overlapping but wider fresh interval leaves that
question unresolved. Full-record replay remains inconclusive until every
candidate has been checked. A contradiction in the checked evidence is
reported as a mismatch.

Schema 5 preserves the original count strings or ordered shots, register layout, acquisition protocols, model and result. Use `study analyze input.json --bundle study.rccbundle` and `bundle verify study.rccbundle` to recalculate the graph witness or cooling analysis. Inspection checks the data bindings. Verification repeats the decoding, confidence accounting, inference and model calculations. Study records use version 2. A recipient reading an earlier version-1 study record can reproduce the original calculation and see the current result separately. For example, a newly verified shorter cooling program can tighten the fresh upper bound while the original interval remains valid. See the [research studies](FINITE_DATA_STUDIES.md).
