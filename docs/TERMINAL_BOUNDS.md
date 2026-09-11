# Terminal-state cost bounds

The `bound` command and `rcc_refcert.bounds` API turn a declared target and
model into a conditional lower bound on preparation cost in atomic slots.
They accept a complete exact spectrum or counts from one fixed projector.
Reference consistency (`RCon`), faithful transcription (`TC`), and reference
admissibility (`RA`) remain separately supplied model arguments.

## First calculation

Install this source tree with `python -m pip install .`, then run:

```bash
rcc-refcert bound template spectrum > spectrum.json
rcc-refcert bound spectrum spectrum.json
rcc-refcert bound spectrum spectrum.json --format json > bound.json
rcc-refcert bound replay bound.json
```

Templates are installed package resources, so these commands also work outside
the checkout. The equivalent Python interface is:

```python
from rcc_refcert.bounds import load_template, bound_from_spectrum, render_record

request = load_template("spectrum")
result = bound_from_spectrum(request)
print(render_record(result))
```

[RCC_Bounds_Quickstart.ipynb](../RCC_Bounds_Quickstart.ipynb) walks through
tolerance changes, a pure target, protocol declaration, counts and replay.
Follow the [Jupyter setup](../README.md#jupyter-notebook) to install the
optional dependencies and register **Python (rcc-refcert)** with the same
interpreter that runs the package.

## Model and exact-input contract

Declare the reference dimension, the number of distinct physical atomic
action classes, exact-transcription constants, a reference-domination upper
constant and their sources. Counting syntax actions alone does not establish
the physical action count. The initial implementation uses a uniform reference
on the declared ideal support and normalized trace distance. Approximate
transcription, uncertain support, nonuniform references and readout corrections
need different contracts and are not accepted here.

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

The input budgets include 4096 eigenvalues, a 65536-bit aggregate denominator
estimate before spectrum arithmetic, 8192-bit rational inputs, bounded exact
decimal exponents, 32 levels of JSON nesting, and a 2 MB CLI input. Counts
are limited to $10^{12}$ samples. The dense H.3/H.4 adapter checks a reference
dimension limit of 1024 before allocation; the matrix kernel's own budgets
also apply. Scalar strings allow 512 characters for decimal notation and 5000
for integer or fraction notation; all forms share the rational bit budget.
Inputs beyond these budgets fail explicitly.

## Fixed-projector counts

Before collecting data, prepare and preserve an acquisition protocol:

```bash
rcc-refcert bound template protocol > protocol-input.json
rcc-refcert bound prepare-protocol protocol-input.json > frozen-protocol.json
```

The protocol binds the task, witness ID, projector rank, fixed sample size and
statistical failure budget. Preserve its full digest with the dataset. The
calculator supports a predeclared projector, fixed-N iid sampling, ideal
readout and no leakage. It does not support choosing the projector on the same
data, optional stopping, correlated samples or post hoc changes to the failure
budget. Hashes check identity, not the chronology or truth of those premises.

For $h$ hits in $N$ trials, the one-sided Hoeffding endpoint is

$$
p_L=\max\left\lbrace 0,\frac{h}{N}-\sqrt{\frac{\ln(1/\delta)}{2N}}\right\rbrace.
$$

Its conservative lower endpoint enters
$\max\lbrace 0,\log_2((p_L-\epsilon)d_R/k)\rbrace$ when $p_L>\epsilon$;
otherwise the information lower bound is zero. Coverage at least $1-\delta$
refers to this sampling event under the declared sampling model, not to the
probability that the complete physical model is correct.

`bound template counts` provides a **synthetic** 550-of-1000 illustration
that already references its protocol. Real datasets must carry their original
acquisition metadata. Never regenerate a digest merely to attach existing
counts to a revised protocol. This protocol version also binds tolerance and
source labels as part of the task. Even deterministic tolerance changes require
the declared task to match; this is an interface restriction, not a claim that
the Hoeffding event mathematically depends on the tolerance.

## Fixed eight-output model

`rcc_refcert.bounds.terminal_model.build_terminal_model()` constructs one
four-dimensional model. Its eight distinct terminal reset channels produce
four basis pure states and four cyclic permutations of
$(11/20,3/10,1/10,1/20)$. Each Kraus family has entries
$K_{ij}=\sqrt{p_i}\lvert i\rangle\langle j\rvert$, so the physical channel is
trace preserving and resets every normalized input to the named diagonal state.
The eight length-three codewords exhaust its complete program domain. Their
Kraft sum is one, and their equal-weight output sum is exactly $I/4$.

Each legal process is a single terminal action costing one atomic slot; no
zero-action program terminates. Exact transcription therefore uses $a=0$ and
$\gamma=0$ with bandwidth $g=3$ bits per slot. Reference domination has
$C_U=1$ by the exact equal-weight sum. Distinctness follows from the different
reset outputs. These statements qualify this finite declared domain; they
do not establish a universal state generator or a uniform model-family result.

The mixed target at tolerance $0.1$ has a continuous lower bound of about
$0.282666$ slots and integer bound one. At this tolerance, the spectral cap is
$0.45$. The information bound reaches zero at the saturation radius $0.35$.
A pure target at zero tolerance has continuous bound $2/3$ and integer
bound one. Every named target has a constructive one-slot upper witness, but
the calculator does not infer reachability for arbitrary user targets.

## Connect an H.3 or H.4 proof object

`with_reference_certificate(task, model, certificate, source=...)` verifies
the supplied `BellmanChoiCertificate` or `ReferencePotentialCertificate` on
that actual finite-control model. The task model ID must match the model name,
the dimensions must match, and the reference matrix must be the nominal uniform
state. The returned task records hashes of the actual binary model and proof
object, the numerical evidence level, tolerance, method and source.

Only a passing report's propagated `constant` is used. Its exact binary value
is preserved as a rational number, with the nonnegative-overhead convention
$\max(1,C)$. A candidate constant, an inconclusive report or an H.34 point
estimate cannot enter through this adapter. Scalar enclosure does not upgrade
the matrix verifier into a rigorous interval-matrix backend, and the adapter
leaves the external RCon, TC and RA declarations intact.

Use the returned task before freezing a measurement protocol. Saved evidence
hashes can identify the proof inputs but do not contain or reverify those inputs;
preserve the proof objects separately with their source.

## Records, zero results and replay

The independent `rcc-refcert.bound-record` schema, version 2, leaves the existing
reference-suite and paired-reset schemas unchanged. Each record includes the
model, qualification, path, parameters, calibration, reference treatment,
flags, exact input snapshot, hash and producer version. The installed JSON
Schema checks shape; `validate_record` checks cross-field consistency;
`replay_record` recomputes and compares the entire same-version scalar record.
Neither validates external physics, source claims or acquisition chronology.

A completed zero result exits successfully and explains whether smoothing,
sampling margin, reference contrast or model overhead exhausted the bound.
It does not establish zero preparation cost. CLI completion exits 0; invalid
input, unsupported contracts, exhausted budgets and partial numerical results
exit 2. Replay mismatch is a rejected input record and exits 2. The existing
`reproduce` command continues to use exit 1 for reference mismatches.
