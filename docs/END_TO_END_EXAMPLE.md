# From model qualification to an RCC lower bound

The paired-reset example gives one minimal, reproducible path from a declared
physical model to a numerical lower bound on
$C_{\rm opt}^{(\epsilon)}$. It is intentionally fixed rather than generic:
every state, channel, codeword, cost constant, and theorem input is visible in
one small construction.

The existing `dephase-or-halt` case is the shortest closed-form demonstration
of the finite-control qualification machinery. Starting from $I/2$, however,
both dephasing and identity preserve the reference and therefore do not produce
a target with a nonzero reference information gap. The paired-reset model uses
the reset pair from Appendix F to retain the same transparency while producing
a one-bit, nontrivial endpoint.

## Run the example

After installing the package in the active Python environment, run:

```bash
python examples/paired_reset_lower_bound.py
```

The same fixed result is available as structured JSON:

```bash
python examples/paired_reset_lower_bound.py --json
```

The implementation is in
[`paired_reset_example.py`](../src/rcc_refcert/paired_reset_example.py), and
the executable entry point is
[`examples/paired_reset_lower_bound.py`](../examples/paired_reset_lower_bound.py).

## Declared model

| Input | Fixed value | Role |
|---|---|---|
| Hilbert space | one qubit | common input and output space |
| Reference state | $\sigma_R=I/2$ | structural vacuum and initial state |
| Physical actions | reset to $\lvert0\rangle$ or $\lvert1\rangle$ | Appendix-F paired non-unital dynamics |
| Program domain | `0`, `1` | complete prefix-free domain for this terminal model |
| Target state | $\rho=\lvert0\rangle\langle0\rvert$ | endpoint whose information gap is audited |
| Generation tolerance | $\epsilon=0$ | exact one-shot branch |
| Cost unit | one terminal reset slot | legal cost set for the example |
| Control bandwidth | $\Gamma_R=2$, $g_R=\log_2\Gamma_R=1$ | one bit per atomic choice |
| RCC reporting unit | $1\,{\rm st}_R=g_R=1$ bit | one R-structon per atomic control bandwidth |
| Transcription | $\Lambda_R(L)=\Phi_{1,0}(L)=L$ | $a=0$ and $\gamma=0$ |

The two reset directions are both present before the target is selected. Their
uniform control average preserves the declared reference:

$$
\frac{1}{2}\left[\mathcal R_0(\sigma_R)+\mathcal R_1(\sigma_R)\right]
=\sigma_R.
$$

This is the one-qubit, one-step terminal restriction of the construction in
Appendix F, Eqs. (F.41)–(F.44).

## Executed chain

The complete program semidensity is

$$
M_U
=2^{-1}\lvert0\rangle\langle0\rvert+2^{-1}\lvert1\rangle\langle1\rvert
=\frac{I}{2}
=\sigma_R.
$$

The software independently constructs this operator through the finite-control
semantics and obtains:

| Computed quantity | Fixed result |
|---|---|
| program semidensity | $I/2$ |
| trace | $1$ |
| nonhalting mass | $0$ |
| transient spectral radius | $0$ |
| minimum fixed-model constant $C^\star$ in $M_U\preceq C^\star\sigma_R$ | $1$ |
| supplied H.3 Bellman–Choi certificate | pass, constant $1$ |
| supplied H.4 reference-potential certificate | pass, constant $1$ |
| H.77 aggregate-balance residual | $0$ |

Identifying the enumerated programs as the complete domain gives the semantic
reference constant $C_U=1$, hence $\chi_U=\log_2C_U=0$. This identification
is part of the fixed model declaration; the matrix computation supplies the
finite operator identity it uses.

For the target state,

$$
\lvert0\rangle\langle0\rvert\preceq 2\sigma_R,
\qquad
D_{\max}^{0}(\rho\Vert\sigma_R)=\log_2 2=1.
$$

Definition 2.6 identifies this one-bit state-side gap with
$1\,{\rm st}_R$. The reporting unit records the gap after calibration by the
same atomic control bandwidth; the process-side cost remains expressed in
resource slots.

With $\beta_U=\gamma+\chi_U=0$, the main lower-bound theorem in Section III,
Theorem 3.1 and Eq. (3.1), together with the canonical inversion in Appendix A,
Eqs. (A.45)–(A.46), gives

$$
C_{\rm opt}^{(0)}(\rho;\mathfrak M_R)
\ge
F_{1,0}(1)
=1.
$$

The legal program `0` also supplies the matching upper-bound witness: one reset
slot prepares the target exactly. Consequently,

$$
C_{\rm opt}^{(0)}(\rho;\mathfrak M_R)=1
$$

for this declared fixed model. The lower bound is therefore tight here; this
equality uses an explicit feasible program, not an automated optimizer.

## Evidence and proof responsibilities

| Layer | Responsibility in this example |
|---|---|
| Software calculation | constructs $M_U$; checks trajectory/superoperator agreement, trace, nonhalting mass, spectral radius, fixed-model domination, supplied H.3/H.4 proof objects, H.77 balance, and the exact $D_{\max}^{0}$ input; verifies that program `0` prepares the target in one slot |
| Analytic model declaration | fixes the physical reference and resource meaning (`RCon`), identifies all legal histories and their exact prefix-free transcription (`TC`), and identifies the enumerated set as the complete program domain used by `RA` |
| RCC theorem and explicit witness | the theorem converts the one-bit, one R-structon (`st_R`) endpoint gap and fixed model constants into the lower bound through Section III, Theorem 3.1; Appendix A supplies the canonical inversion; the one-slot target-preparation program supplies the matching upper bound |

The result is the exact optimum for this declared fixed model because its
theorem-level lower bound and explicit upper-bound witness coincide. The
example does not automate general RCC optimization or establish uniformity for
a growing model family.

## How the H.70 diagnostic relates to the final inference

Each directed reset has reference gain $2$. With the original one-bit local
codewords, the sufficient H.70 sum is

$$
2^{-1}\!\times2+2^{-1}\!\times2=2,
$$

so that local sufficient route fails. H.76 suggests two-bit codewords and
reduces its diagnostic sum to $1$. The final lower-bound chain does not use
that re-encoding: it uses the exact complete-domain identity
$M_U=\sigma_R$ and the aggregate H.77 balance of the paired actions. This is
the intended distinction between a failed sufficient route and failure of
reference admissibility itself.

## Paper map

| Step | RCC paper location |
|---|---|
| maximally mixed reference and paired reset construction | Appendix F, Eqs. (F.41)–(F.44) |
| finite-control semidensity and supplied certificates | Appendix H, H.1–H.4 |
| local gain, H.70 diagnostic, H.76 re-encoding, and H.77 aggregate balance | Appendix H, Eqs. (H.67)–(H.77) |
| max-relative entropy input | Appendix A, Eqs. (A.6)–(A.7) |
| R-structon reporting unit | Section II, Definition 2.6 |
| main universal-optimum lower bound | Section III, Theorem 3.1 and Eq. (3.1) |
| generalized inverse and canonical slot inversion | Appendix A, Eqs. (A.45)–(A.46) |
