# Analyze your own finite-control model

Start with the physical model: its reference state, allowed channels, control
language, initial state, and charged primitive. Once these choices are fixed,
`rcc-refcert` can prepare a candidate certificate, check it independently, and
preserve the complete finite input for another researcher to inspect.

This guide follows two executable examples. The first studies a reference
constant when a local sufficient condition fails. The second carries a model
through numerical certification, a conditional cost bound, and independent
reverification. Both use ordinary NumPy arrays and the public Python API.

Install this source tree into your active Python 3.10 or newer environment:

```bash
python -m pip install .
python examples/custom_model_workflow.py --bundle alternating.rccbundle
python -m rcc_refcert bundle verify alternating.rccbundle
```

The new candidate and bundle interfaces belong to this source version. The
published 0.1.3 release provides the underlying certificates and scalar bounds;
install the current source or the corresponding release candidate to use this
workflow. Choose a new output filename for each saved analysis.

## Declare the model

[`custom_model_workflow.py`](../examples/custom_model_workflow.py) constructs a
single qubit with two syntax phases. At either phase, `0` halts and `1`
continues. The continuing channel damps the qubit with probability $3/5$ in
phase A and pumps it with probability $1/5$ in phase B. The initial and reference
states are both $I/2$.

Each `Action` carries its physical, unweighted Kraus operators. The interpreter
applies the codeword weight once. Changing a successor changes the dynamics,
even if the resulting syntax graph remains structurally valid. The
[model guide](MODEL_GUIDE.md) gives the full construction rules, including
rectangular Kraus operators and direct-sum control blocks.

The alternating model has terminating semidensity
$\mathrm{diag}(29/46,17/46)$ and analytic minimum reference constant
$C_*=29/23$. The two local H.70 sums are $1.3$ and $1.1$, so this sufficient
route fails. A global H.3 certificate still passes. This makes the example a
useful way to distinguish a failed sufficient test from a failed model.

## Prepare and verify a candidate

`prepare_bellman_choi(model, tol=..., limits=...)` wraps the existing stable
full-space linear construction. It returns a `CandidatePreparation` with a
certificate, diagnostics, and a resource estimate. Its statuses describe what
happened during construction:

| Status | Meaning | Next step |
|---|---|---|
| `candidate_ready` | A finite H.3 candidate and its proposed constant were constructed | Run the independent verifier |
| `invalid_model` | The declared structure or channels failed validation | Correct the reported input |
| `not_applicable` | The full-space stable inverse does not apply | Supply a separately derived candidate or choose an applicable route |
| `inconclusive` | Numerical work did not resolve a usable candidate | Inspect the diagnostics and numerical conditioning |
| `resource_limit` | The request exceeds its declared computation budget | Reduce the problem or explicitly change the budget |

`resource_estimate` is diagnostic: counts through 256 bits remain integers;
larger counts are strings reporting their bit length and explicitly omitting
the decimal expansion. Admission checks still compare exact integers. Direct
verifiers raise `ResourceLimitError`, whose `estimate` and `limit` attributes
retain those exact integers, while its message uses the same bounded summary.

The central sequence in the example is:

```python
from examples.custom_model_workflow import build_model
from rcc_refcert.candidate import prepare_bellman_choi
from rcc_refcert import verify_bellman_choi

model = build_model()
prepared = prepare_bellman_choi(model)
if prepared.certificate is None:
    raise RuntimeError(prepared.diagnostics)
report = verify_bellman_choi(model, prepared.certificate)
print(report.outcome.value, report.constant)
```

Construction does not establish a certificate. `report.constant` becomes a
usable numerical upper constant only when the verifier passes. For this model,
the passing upper constant is approximately `1.26086956534`; the analytic
$29/23$ is a separate comparison. The saved bundle contains the actual candidate
and numerical inputs.

The helper covers full-space stable models. A recurrent nonhalting sector can
make that construction unavailable while a separately supplied H.3 or H.4
certificate still succeeds. A general automatic solver for those sectors is
outside this helper's scope.

## Cyclic noisy-reset register

Run the second example from the checkout:

```bash
python examples/cyclic_reset_workflow.py --bundle cyclic-reset.rccbundle
python -m rcc_refcert bundle verify cyclic-reset.rccbundle --output cyclic-reset-verification.json
```

[`cyclic_reset_workflow.py`](../examples/cyclic_reset_workflow.py) declares four
qubits and four distinct physical channels: identity with halt, Pauli Z on the
first qubit, and two noisy resets of that qubit followed by a rotation that
moves it to the last position. The reset biases are $19/20$ and $1/20$. Each
instruction has a two-bit codeword and costs one declared primitive slot,
including halt. A reset together with its rotation is one primitive of this
model; a hardware gate decomposition would define a different cost problem.

The reference and initial state are $I/16$. The complementary resets have a
reference-preserving average. The weighted halting image is $\sigma/4$ and the
weighted continuation image is $3\sigma/4$. These relations supply the explicit
H.4 candidate used in the script. Its numerical verifier returns a conservative
upper constant close to `1.00000000010`.

The fixed model supplies the external premises recorded in the task:

- **RCon:** the reference and complete four-channel action set are fixed before
  the target. Their average preserves the reference.
- **TC:** every admitted instruction, including halt, is charged one slot and
  receives exactly two transcript bits; hence the program length is $2L$.
- **RA:** the explicit reference relations give terminal reference semidensity
  $\sigma$ for this finite model. The numerical task uses the independently
  verified upper constant. Any claim for a wider model family requires its own
  uniform argument.

The target is the fourfold product of $\mathrm{diag}(19/20,1/20)$ at trace
distance tolerance $1/10$. Its spectrum is supplied as exact rational numbers.
The counts path uses a clearly labelled synthetic fixture: 815 hits in 1000
trials for a rank-one projector, with statistical failure budget $0.01$. The
script binds the numerical constant before freezing that fixture's protocol.
Real data must retain the actual protocol fixed before acquisition.

Both paths produce an integer lower bound of **two primitive slots**. Four
reset-0 instructions followed by halt give a feasible five-slot program.
For this particular model, a separate structural argument proves five slots
are necessary: fewer than four resets leave a uniform qubit marginal whose
trace distance from the target marginal is $0.45$. The example demonstrates the
certificate-to-bound workflow; its general RCC bound is weaker than that
specialized structural argument.

## Read unresolved numerical results

The register's H.4 candidate passes with the default tolerance. Its full-space
H.3 candidate illustrates a different numerical behavior:

```bash
python examples/cyclic_reset_workflow.py --diagnose-h3
python examples/cyclic_reset_workflow.py --h3-tolerance 1e-8
```

The first command preserves the default H.3 `inconclusive` result. Local
checks pass, but the propagated error correction estimate, approximately
$6.6\times10^{-9}$, exceeds the default budget $10^{-10}$. The second command
additionally evaluates an explicitly chosen larger error budget. It retains
the default result and reports the new conservative constant separately.
Arithmetic remains binary64. Increasing a tolerance changes the accepted
error budget; it does not increase arithmetic precision.

The examples export the H.4 route for the register. A different route or
tolerance should be recorded as a distinct analysis with its own inputs.

## Choose a computation budget

`ComputationLimits` controls the explicit algorithms. H.3 and H.4 direct
verification and `with_reference_certificate` use a shared certificate
preflight. The full-space candidate constructor also checks its dense linear
system. Resource estimates describe the work counted by that route; they do
not predict total resident memory or elapsed time.

This distinction matters even for small registers: the default full-space
construction exceeds its budget at five qubits, while a compact H.4 candidate
can remain within its certificate budget. A resource refusal identifies the
requested calculation, not the validity of the model.

## Share the analysis

An analysis bundle carries the original model and proof arrays, control
settings, bound requests, and historical results. The recipient can verify it
with the installed package and the bundle alone. The alternating example
exports a certificate-only bundle; the register includes both terminal-state
requests. See [Analysis bundles](ANALYSIS_BUNDLES.md) for historical comparison,
counts handling, and the distinction between matrix revalidation and scalar
replay.
