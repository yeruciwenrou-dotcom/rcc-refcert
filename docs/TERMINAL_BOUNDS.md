# Quantum circuit complexity bounds from terminal states

The `bound` command and `rcc_refcert.bounds` API calculate a quantum circuit
complexity lower bound for state preparation, measured in atomic resource
slots. Supply a complete exact spectrum or counts from one projector selected
before measurement, together with the
model's reference and cost assumptions. The
[scientific scope](SCIENTIFIC_SCOPE.md#from-state-information-to-process-cost)
explains how reference consistency, faithful transcription and reference
admissibility qualify the resulting cost bound.

To check a complete preparation program and combine exclusion with a feasible
upper endpoint, use the [cost workflow](COST_AND_WINDOWS.md#a-complete-cost-task).
The spectrum and counts routes in this guide provide lower bounds from
terminal-state evidence.

## First calculation

Follow the [source quickstart](../README.md#install-from-source), then run these
commands from the checkout root. On Windows, use `.venv\Scripts\python.exe`.
If your shell is Windows PowerShell 5.1, run the `>` examples in Command Prompt.
These commands also work outside a checkout with the
[PyPI package](../README.md#install-from-pypi). Use the interpreter from your
active installation.

```bash
.venv/bin/python -m rcc_refcert bound template spectrum > spectrum.json
.venv/bin/python -m rcc_refcert bound spectrum spectrum.json
.venv/bin/python -m rcc_refcert bound spectrum spectrum.json --format json > bound.json
.venv/bin/python -m rcc_refcert bound replay bound.json
```

The template gives an integer-slot lower bound of **one**. The JSON file
preserves the inputs and result for the final replay command. Templates are
installed package resources; to work outside the checkout, use the full path
to the installed interpreter. The equivalent Python interface is:

```python
from rcc_refcert.bounds import load_template, bound_from_spectrum, render_record

request = load_template("spectrum")
result = bound_from_spectrum(request)
print(render_record(result))
```

[RCC_Bounds_Quickstart.ipynb](../RCC_Bounds_Quickstart.ipynb) walks through
tolerance changes, a pure target, certificate binding, protocol declaration,
counts and replay.
Follow the [Jupyter setup](../README.md#jupyter-notebook) to install the
optional dependencies and register **Python (rcc-refcert)** with the same
interpreter that runs the package.

## Model and exact-input contract

Declare the reference dimension, the number of distinct physical atomic
action classes, exact-transcription constants, a reference-domination upper
constant and their sources. Counting syntax actions alone does not establish
the physical action count. The calculator uses a uniform reference
on the declared ideal support and normalized trace distance. Process bounds use
exact transcription. The fixed-effect acquisition can include a known binary
readout channel as described below.

Use integers, decimal or rational strings, `fractions.Fraction`, or
`decimal.Decimal`. Python binary floats are rejected by the scalar input API.
JSON decimal tokens are parsed directly as `Decimal`, preserving their written
value. Duplicate keys, nonfinite values and unknown fields are rejected.
Supply exactly the declared number of eigenvalues, including zeros; the
spectrum must be nonnegative and sum to one exactly. No normalization or
uncertified matrix eigensolver is silently inserted.

For decreasing eigenvalues and cumulative sums $S_k$, the normalized
trace-distance smoothing problem has cap

$$
t_\epsilon=\max\left\lbrace \frac{1}{d_R},
\max_{1\le k\le d_R}\frac{S_k-\epsilon}{k}\right\rbrace,
\qquad I_\epsilon=\log_2(d_R t_\epsilon).
$$

The implementation solves this scalar problem with exact rational arithmetic.
It also returns an active prefix rank and mass, the relative entropy,
the skew and smoothing loss. The direct information value drives the bound;
subtracting nearly equal displayed diagnostics does not drive the calculation.
This is Theorem A.1 of the
[V4 paper](https://arxiv.org/abs/2509.18205v4), with normalized-state
trace-distance smoothing. The
[state-to-cost explanation](SCIENTIFIC_SCOPE.md#from-state-information-to-process-cost)
relates this one-shot value to the state-side RCC leading term and the
all-path preparation-cost guarantee.

Let $g=\log_2\Gamma$, $\beta=\gamma+\log_2 C_U$ with $C_U\ge1$, and

$$
\Phi(L)=gL+a\log_2\max\lbrace 1,L\rbrace.
$$

The conservative endpoint of the inverse at $I_\epsilon-\beta$ gives the
continuous cost lower bound. The reporting unit $\mathrm{st}_R$ contains
$g$ bits; it does not remove the overhead or nonlinear inversion. Taking
the ceiling is justified only for a declared integer atomic-slot cost domain.
An unspecified cost domain returns no integer bound.

Logarithms use 64-digit Decimal enclosures and rational endpoints. Square
roots and inversion preserve the lower-bound direction. Serialized interval
endpoints round outward; the short display rounds down. The upper endpoint
of `calculator_enclosure_slots` encloses the calculation and is **not** a
physical upper bound on the optimum cost. Partial inversion results retain a
conservative endpoint and report their numerical status.

See [Numerical and input limits](#numerical-and-input-limits) for accepted
input sizes and certificate budgets.

## Fixed-projector counts

Before collecting data, prepare and preserve an acquisition protocol:

```bash
.venv/bin/python -m rcc_refcert bound template protocol > protocol-input.json
.venv/bin/python -m rcc_refcert bound prepare-protocol protocol-input.json > frozen-protocol.json
```

The protocol binds the task, witness ID, projector rank, fixed sample size and
statistical failure budget. Preserve its full digest with the dataset. The
calculator supports a predeclared projector, independent and identically
distributed sampling with a fixed sample size, ideal readout and no leakage.
Keep the projector definition and dated acquisition records with the data.
The digest identifies the protocol and the rank sets the uniform-reference
baseline $k/d_R$. When $k=d_R$ the projector covers the entire support.
Under ideal readout every trial then gives a hit. A smaller count is a mismatch
between the data and the protocol.

For $h$ hits in $N$ trials, the one-sided Hoeffding endpoint is

$$
p_L=\max\left\lbrace 0,\frac{h}{N}-\sqrt{\frac{\ln(1/\delta)}{2N}}\right\rbrace.
$$

Its conservative lower endpoint enters
$\max\lbrace 0,\log_2((p_L-\epsilon)d_R/k)\rbrace$ when $p_L>\epsilon$;
otherwise the information lower bound is zero. Coverage at least $1-\delta$
refers to this event under the declared sampling model.

To try the full path, generate the example dataset of 550 hits in 1,000 trials:

```bash
.venv/bin/python -m rcc_refcert bound template counts > projector-counts.json
.venv/bin/python -m rcc_refcert bound counts projector-counts.json --format json > projector-result.json
.venv/bin/python -m rcc_refcert bound replay projector-result.json
```

For your own acquisition, copy `task` from `protocol-input.json` and
`protocol` from `frozen-protocol.json` into the counts request.
Set `data.protocol_id` to the frozen
protocol's `id` and `data.protocol_sha256` to the saved digest. Enter the
fixed sample size, observed hits, dataset ID and origin in `data`. Save this
request and its result under new names to keep the example available for comparison.

### Target and reference counts for the same effect

Apply the same predeclared binary measurement to a target preparation and to the model's reference state. The two observed acceptance rates bound how much structure the preparation must generate. Run the complete synthetic example with version 0.4.0 or later:

```bash
.venv/bin/python -m rcc_refcert bound template effect-counts > effect.json
.venv/bin/python -m rcc_refcert bound counts effect.json --bundle effect.rccbundle
.venv/bin/python -m rcc_refcert bundle verify effect.rccbundle
```

The example accepts basis state 0 and pools the other three outcomes into `no`. Of 1,000 shots on each preparation, 550 target shots and 250 reference shots give `yes`. One-sided Hoeffding endpoints with failure budget 1/40 per arm give a target response above 0.50705 and a reference response below 0.29295, jointly with at least 95% coverage. At generation tolerance 0.1 the direct route certifies at least 0.47457747 bits. In the eight-output model below this gives at least 0.15819249 atomic slots, or **at least one slot** for integer costs. The hypothesis-testing route at η = 1/2 certifies 0.44936061 bits on those same two events. The stronger valid route determines the reported bound.

On the declared ideal support, $\sigma_R=I/d_R$ gives $p_\rho\leq d_R b_U$ for the same effect. A target lower endpoint above this ceiling signals inconsistent inputs. This check also applies to state-only analyses with a declared support. For a known exact reference response $b$, applying the inequality to the complementary effect gives $p_\rho\geq 1-d_R(1-b)$, which constrains the alternatives used for planning.

To use your own data, freeze the settings before collecting either batch:

```bash
.venv/bin/python -m rcc_refcert bound template effect-protocol > effect-protocol.json
# Edit the two state IDs, measurement, exhaustive labels, batch IDs, budgets and shot counts.
.venv/bin/python -m rcc_refcert bound prepare-protocol effect-protocol.json > frozen-effect.json
```

Use the normalized `protocol` from `frozen-effect.json` in your request.
Each arm's `arm_sha256` binds its acquisition settings. Keep it and the
`dataset_id` with that batch. Enter both raw bin counts, including any zero,
and set `data.<arm>.origin` to `observed_counts` or `simulation`. The result
records a separate `data_sha256` for the supplied data.

Each sample consists of fixed-size IID trials for the declared state and
measurement. Both state identities must agree with the task. Keep the
physical readout definition, sampling dates and model premises with the study.

- To try different synthetic counts, copy the example request to `effect-low.json`
  and set its target histogram to `{"yes":300,"no":700}`. Run
  `.venv/bin/python -m rcc_refcert bound counts effect-low.json --bundle effect-low.rccbundle`.
  At this tolerance the contrast gives a zero lower bound, and the target
  acceptance falls below the hypothesis test's threshold.
- For a **known reference response**, set `protocol.reference` to `{"kind":"exact","state_id":"uniform-C4","response":"1/4","source":"rank-one projector evaluated on I/4"}` and remove `data.reference`. A deterministic upper bound uses `upper_bound` with its supporting source. The target batch keeps its acquisition identity. A sampled reference with zero hits still contributes its statistical upper endpoint. A deterministic zero response on a full-rank uniform reference forces a zero effect on that support. Any target hits then give a support conflict.
- To compute **state-side information alone**, omit `task`. A declared task missing one of RCon, TC or RA retains the information and lists the missing process premise. A smoothing radius can cover several smaller generation tolerances. Changing the task tolerance produces a new derivation from the original sampling events.

In Python, pass the same request to `rcc_refcert.bounds.bound_from_counts`. `prepare_effect_protocol` freezes a declaration, and `hoeffding_lower`, `hoeffding_upper` and `fixed_effect_information` expose the conservative scalar operations. Use `rcc_refcert.workflows.save_effect_bundle(path, request, result)` to share a Python calculation. The installed input schema is `bounds/data/fixed_effect_counts.schema.json`. The JSON result includes the exact endpoints, sampling ledger, each route's eligibility, the model qualifications in the input snapshot and the selected cost bound. [Bundle format and verification](ANALYSIS_BUNDLES.md#fixed-effect-counts)

### Plan a fixed sample size

How many trials give a 90% chance of certifying that the ideal target acceptance exceeds 0.8, if its true value is 0.9? Version 0.4.0 includes this example with a one-sided sampling failure budget of 0.05:

```bash
.venv/bin/python -m rcc_refcert bound template sample-plan > plan.json
.venv/bin/python -m rcc_refcert bound plan plan.json --counts-request planned-counts.json
```

| Target endpoint method | Minimum fixed trials | Minimum accepted outcomes | Design power |
|---|---:|---:|---:|
| Clopper–Pearson | 112 | 97 | 0.907795 |
| Hoeffding | 253 | 222 | 0.900303 |

Use `protocol.target.method` to choose `clopper_pearson` or `hoeffding` before acquisition. The response goal uses a strict inequality; both endpoints and the hit threshold respect that choice. The design searches every smaller integer sample size. Power can fall when the required hit count rises. Use `fixed_samples` in place of `max_samples` to evaluate an existing budget. An `expected_response` range such as `["0.89","0.91"]` gives the worst power over that interval and the two endpoint powers. If a calibration or support constraint limits the highest compatible hit count, the report also gives that count. Trials beyond the feasible interval do not contribute to power.

For a **preparation-cost goal**, supply your qualified `task`, match the target and reference IDs in the protocol, and set `goal` to e.g. `{"cost_above_slots":"0"}`. The planner uses the same smoothing radius, reference upper response and cost inversion as the counts report. A known ideal reference response or upper bound needs its source. For a sampled reference, use its original frozen arm and attach its bound raw batch as `reference_data`. The target sample is then a new, fixed-size IID acquisition conditional on the prior reference data. The output retains that reference event and its share of the joint failure budget.

In a `max_samples` search, the planner writes `planned-counts.json` when it
finds a design with the requested power. Choose an unused output name. If the
search reaches its limit first, the report gives the largest sample size
checked and leaves the counts request empty. You can increase the limit or
revise the goal before acquisition.

With a prespecified `fixed_samples` budget, a result marked
`fixed_n_below_power` includes a fillable request for that budget and reports
the power it actually achieves.

After collecting the planned target batch, enter both counts and their
origin in `planned-counts.json`. For a second acquisition, choose new request
and bundle names. The design power refers to the assumed response. The
following commands calculate and verify the certificate for the observed counts:

```bash
.venv/bin/python -m rcc_refcert bound counts planned-counts.json --bundle planned-study.rccbundle
.venv/bin/python -m rcc_refcert bundle verify planned-study.rccbundle
```

For an immediate **25-shot example**, generate a completed synthetic request with `bound template binomial-counts` and analyze it with `bound counts`. With 14 acceptances, known reference 1/4 and radius 0.1, the one-sided 95% Clopper–Pearson lower endpoint exceeds 0.3786. This certifies one integer slot in the eight-output model. The same observations under a prespecified Hoeffding analysis give zero slots. Choose the endpoint method during design. Both methods bind to their own frozen acquisition identities.

### Calibrate a known binary readout

For ideal acceptance probability $p$, a known false-positive rate $f$ and false-negative rate $h$ give observed acceptance $y=f+(1-f-h)p$. Supply the known rates and their evidence in the shared measurement description before freezing the protocol:

```json
"calibration": {
  "kind": "known_binary",
  "false_positive": "1/10",
  "false_negative": "1/5",
  "source": "Exact readout channel specified for this simulation."
}
```

Raw counts describe the observed readout. Each arm's response refers to the ideal binary effect. A sampled arm uses the one-sided observed interval appropriate to its role and the sign of the slope. The calculator intersects its inverse image with $[0,1]$. A constant readout can leave the full interval feasible. An empty intersection gives a readout conflict and no process cost. A deterministic reference response already refers to the ideal effect. With a negative slope the planning report counts the observed **reject** label as favourable evidence. The record retains the observed endpoint, its direction, and the inferred ideal interval. A matrix inferred with finite calibration uncertainty requires a different feasible-set calculation.

**Arithmetic and scale.** Clopper–Pearson uses integer binomial-tail comparisons to enclose the endpoint on a grid of spacing $2^{-48}$, up to 2,048 observations per sampled arm. Power planning supports up to 1,024 target trials with observed design probabilities of at most 128 denominator bits. Exact comparisons determine design power against the requested level. Text and JSON display conservative rounded power values. Python callers can use `plan_counts`, `clopper_pearson_lower`, `clopper_pearson_upper` and `binary_readout_preimage` from `rcc_refcert.bounds`. [Paper-to-code map](PAPER_MAP.md#terminal-state-calculation-interfaces)

## Fixed eight-output model

`rcc_refcert.bounds.terminal_model.build_terminal_model()` constructs one
four-dimensional model. Its eight distinct terminal reset channels produce
four basis pure states and four cyclic permutations of
$(11/20,3/10,1/10,1/20)$. Each Kraus family has entries
$K_{ij}=\sqrt{p_i}\lvert i\rangle\langle j\rvert$, so the physical channel is
trace preserving and resets every normalized input to the named diagonal state.
The eight length-three codewords exhaust its complete program domain. Their
Kraft sum is one, and their equal-weight output sum is exactly $I/4$.

Each admissible process is a single terminal action costing one atomic slot; no
zero-action program terminates. Exact transcription therefore uses $a=0$ and
$\gamma=0$ with bandwidth $g=3$ bits per slot. Reference domination has
$C_U=1$ by the exact equal-weight sum. Distinctness follows from the different
reset outputs. These conditions qualify the declared eight-program domain.

The mixed target at tolerance $0.1$ has a continuous lower bound of about
$0.282666$ slots and integer bound one. At this tolerance, the spectral cap is
$0.45$. The information bound reaches zero at the saturation radius $0.35$.
A pure target at zero tolerance has continuous bound $2/3$ and integer
bound one. Each of the eight named targets has an explicit one-slot preparation.

<a id="connect-an-h3-or-h4-proof-object"></a>

## Use a reference certificate in a bound calculation

`with_reference_certificate(task, model, certificate, source=...)` checks a
Bellman–Choi certificate (H.3) or reference-potential certificate (H.4) against
the supplied finite-control model. These are represented by
`BellmanChoiCertificate` and `ReferencePotentialCertificate`, respectively.
The task model ID must match the model name,
the dimensions must match, and the reference matrix must be the nominal uniform
state. The returned task records hashes of the actual binary model and proof
object, the numerical evidence level, tolerance, method and source.

The fixed eight-output model supplies a small runnable example. Build a
Bellman–Choi candidate from its linear value map, then let the adapter verify
it and bind the resulting upper constant to a new spectrum task:

```python
from rcc_refcert import BellmanChoiCertificate, linear_value_choi_envelopes
from rcc_refcert.bounds import (
    bound_from_spectrum,
    load_template,
    replay_record,
    with_reference_certificate,
)
from rcc_refcert.bounds.terminal_model import build_terminal_model

model = build_terminal_model()
certificate = BellmanChoiCertificate(linear_value_choi_envelopes(model), 1.0)
certified_request = load_template("spectrum")
analytic_result = bound_from_spectrum(certified_request)
certified_request["task"] = with_reference_certificate(
    certified_request["task"],
    model,
    certificate,
    source="H.3 value-map candidate for the fixed eight-output model",
)
reference = certified_request["task"]["model"]["reference_domination"]
certified_result = bound_from_spectrum(certified_request)
print("Reference evidence:", reference["evidence"]["level"])
print("Propagated C upper bound:", reference["upper_constant"])
print("Analytic-model lower bound:", analytic_result["cost"]["lower_bound_slots"])
print("Certificate-based lower bound:", certified_result["cost"]["lower_bound_slots"])
print("Integer lower bound:", certified_result["cost"]["integer_lower_bound_slots"])
print("Scalar replay matches:", replay_record(certified_result)["matches"])
```

The template's analytic declaration uses $C_U=1$. The adapter includes the
matrix verifier's correction budget in its upper constant, so the continuous
lower bound is slightly smaller: about $0.28266563547$ slots instead of
$0.28266563552$. Both calculations give integer lower bound one, and the
certificate evidence remains `numerical`. An H.4 reference-potential candidate
uses the same adapter entry point.

New bindings identify their `input_hash_format` as
`rcc-refcert.matrix-bytes.v1`. Arrays are hashed in bounded C-order chunks,
with shape, numeric dtype and little-endian representation recorded in the
snapshot. Equivalent memory layouts and byte orders give the same digest;
shape, dtype and entry changes remain distinguishable. Supported array types
are NumPy booleans, integers through 64 bits, floats through 64 bits and
complex numbers through 128 bits. Earlier declarations without a format field
remain readable; their hashes describe the earlier value-list snapshots.
Replay continues to require the recorded producer version.

Only a passing report's propagated `constant` is used. Its exact binary value
is preserved as a rational number, with the nonnegative-overhead convention
$\max(1,C)$. A candidate constant, an inconclusive report or an H.34 point
estimate cannot enter through this adapter. Scalar enclosure does not upgrade
the matrix verifier into a rigorous interval-matrix backend, and the adapter
leaves the external RCon, TC and RA declarations intact.

Use the returned task before freezing a measurement protocol. Saved evidence
hashes in a bound record identify the proof inputs; the record does not contain
the original matrices. An [analysis bundle](ANALYSIS_BUNDLES.md) preserves the
complete model, proof object, numerical controls, bound requests, and historical
results for independent revalidation. The
[cyclic-register example](CUSTOM_MODELS.md#cyclic-noisy-reset-register) shows
this workflow for both exact spectra and synthetic counts.

The bundle verifier compares the fresh conservative constant with the saved
one. A passing matrix result with a larger constant produces a fresh bound and
does not by itself support the historical bound. For counts, any changed bound
is reported as a separate derivation from the original acquisition event;
the protocol and dataset remain unchanged.

## Numerical and input limits

The input budgets include 4096 eigenvalues, a 65536-bit aggregate denominator
estimate before spectrum arithmetic, 8192-bit rational inputs, bounded exact
decimal exponents, 32 levels of JSON nesting, and a 2 MB CLI input. Counts
are limited to $10^{12}$ samples. Scalar strings allow 512 characters for decimal notation and 5000
for integer or fraction notation; all forms share the rational bit budget.
User decimals have an absolute exponent limit of 2048. Serialized result
decimals have a separate 512-character and absolute exponent limit of 8192,
allowing outward-rounded endpoints to represent accepted exact inputs.
Inputs and records beyond their respective budgets fail explicitly.

Before reference allocation, hashing or verification, the H.3/H.4 adapter
checks an output-dimension limit of 1024 and a matrix-element estimate. The
estimate sums numeric input entries, one family of Choi blocks (H.3) or control
matrices (H.4), the output matrix, and the block-level correction system.
Its default limit is 1048576 elements; pass `limits=ComputationLimits(...)`
from `rcc_refcert` to adjust `max_matrix_elements`. This is an algorithm
preflight estimate, not a peak-memory or execution-time bound. Direct H.3/H.4
verification, task binding, and bundle verification share the certificate
matrix preflight. The 1024 output-dimension cap is specific to task binding.

## Records, zero results and replay

The spectrum and fixed-projector routes use `rcc-refcert.bound-record`, version 2.
Target/reference effect counts use `rcc-refcert.fixed-effect-record`, version 1. Each record includes the
model, qualification, path, parameters, calibration, reference treatment,
flags, exact input snapshot, hash and producer version. The installed JSON
Schema checks shape; `validate_record` checks cross-field consistency;
`replay_record` recomputes and compares the entire same-version scalar record.

A completed zero result exits successfully and explains whether smoothing,
sampling margin, reference contrast or model overhead exhausted the bound.
CLI completion exits 0. Invalid
input, unsupported contracts, exhausted budgets and partial numerical results
exit 2. Replay mismatch is a rejected input record and exits 2. The existing
`reproduce` command continues to use exit 1 for reference mismatches.
