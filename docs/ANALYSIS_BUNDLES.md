# Share and reverify an analysis

An analysis bundle lets a recipient check a calculation from its saved
numerical inputs. It contains the finite model, a Bellman–Choi (H.3) or
reference-potential (H.4) proof object, raw arrays, numerical controls, and any
supported terminal-state requests. It also keeps the original verification
and bound records for comparison. The recipient can check the matrices and
recompute the results without the author's model script.

Use a bundle when handing results to a collaborator, preserving a calculation
for review, or comparing numerical environments. The existing bound record
remains useful for exact scalar replay; it contains input hashes rather than
the complete model and proof arrays.

## Reverify a bundle you received

You need the installed package and the `.rccbundle` file. Follow the
[0.2.0rc1 source quickstart](../README.md#quick-start) and run the commands
below from the checkout root. On Windows, substitute
`.venv\Scripts\python.exe`. For your own active installation, use its
interpreter instead. The `bundle` interfaces require 0.2.0rc1.

Replace `received.rccbundle` with the path to your file:

```bash
.venv/bin/python -m rcc_refcert bundle inspect received.rccbundle
.venv/bin/python -m rcc_refcert bundle verify received.rccbundle --output received-verification.json
```

For the cyclic-reset example below, a successful verification includes:

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

The bundle's `producer.source_revision` records the author's supplied commit.
`inspect` preserves that identity, while the fresh verification report's
`producer.source_revision` records the recipient's supplied commit. Keep the
original bundle and fresh report together. Without the environment variable,
the field is `null`. The software validates the full 40-character Git ID but
does not infer it from the current directory or authenticate the declaration.

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
therefore assessed using the actual conservative constants, rather than
requiring byte-for-byte equality of matrix reports.

- If the fresh verification passes and its usable constant is no larger than
  the saved constant, the fresh numerical evidence supports the historical
  constant for the same input and declarations.
- If the fresh usable constant is larger, the fresh result supplies a new
  conservative bound. Its passing status alone does not support the stronger
  historical constant.
- A failed or inconclusive verifier, or a resource refusal, is reported with
  its own diagnostics. It does not become a successful historical check.

For example, verifying the cyclic-reset bundle with the explicit tolerance
`1e-8` gives a fresh constant approximately `1.0000000100000002`, larger than
the historical `1.0000000001000002`. The matrix check passes, historical
support is `no`, and the integer bound remains **two**. The report shows the
constant comparison and explains that rounding to the same integer does not
establish support for the smaller historical constant. The command and its
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
preserves that request and its protocol digest. It never relabels a changed
task as the original pre-acquisition declaration.

When a new numerical certificate constant changes the bound, the verifier
reports a separate derived result linked to the original acquisition event.
The same supported probability statement is used for deterministic
post-processing with the fresh constant. The original protocol, data, and
historical record remain unchanged. This mechanism does not authorize choosing
a new witness after viewing data, changing the sample rule, or substituting
different measurements.

The example counts are synthetic. For experimental results, acquisition
chronology, fixed-N iid sampling, ideal readout, support assumptions, and the
physical meaning of the witness remain external obligations. Storing their
declarations does not establish them.
The embedded protocol carries a witness ID and rank. Preserve the actual
projector definition and acquisition records alongside the bundle; its model
and proof arrays do not include the experimental measurement operator.

## Format and numerical identity

The `rcc-refcert.analysis-bundle` format has its own schema version, independent
of the bound-record schema. A bundle is a ZIP container with a JSON manifest
and numerical array payloads. It carries data rather than executable Python.
The loader reconstructs only the supported finite model and H.3/H.4 types.

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
