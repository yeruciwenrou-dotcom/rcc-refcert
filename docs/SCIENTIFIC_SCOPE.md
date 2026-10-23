# Scientific scope

## Repository identity

RCC is a structure-fair, model-relative framework for defining and
lower-bounding quantum circuit complexity. For a target state $\rho$ within a
declared physical generation model, its process-side object
$C_{\rm opt}^{(\epsilon)}$ is the infimum of the declared cost over every
admissible history that prepares the target within accuracy $\epsilon$. The
main RCC theorem converts the target's one-shot structural gap relative to the
reference into a rigorous lower bound on this global process optimum. The
resulting complexity is a relational physical quantity fixed jointly by the
target, reference background, admissible processes, error semantics, and cost
scale.

The target specifies the structure that every successful preparation must
realize; the model fixes the reference background, available operations,
control interface, program semantics, and resource unit that determine what is
already supplied and how the remaining generation responsibility is measured.
Structural fairness requires target-shortening resources to be represented in
those same coordinates. `rcc-refcert` implements the finite-control
qualification machinery for this model class. Given prefix-coded quantum
operations and a reference state, it constructs the terminating program
semidensity, verifies reference certificates, evaluates the reference gain of
individual actions, and tests the corresponding code-length allocation.
Its terminal-state calculator then accepts declared model inputs and a target's
exact spectrum or fixed-projector counts to evaluate a conditional lower bound
on preparation cost.

The implementation fixes program-semidensity and certificate conventions and
reproduces selected constructions from Appendices F and H of RCC manuscript
version 4. The [paper map](PAPER_MAP.md) locates the implemented objects and
checks in the RCC manuscript.

Appendix F proves that the model class is nonempty and constructs an admissible
qubit model family with approximately universal pure- and mixed-state
generation. Appendix H supplies finite-control realization and certificate
machinery. Together they make the Section II model an explicit, auditable
construction. Section III uses the qualified model hypotheses in the RCC lower
bound.

`rcc-refcert` connects finite-control qualification to selected terminal-state
lower-bound calculations. The RCC paper develops the complete framework,
including physical reference consistency, faithful transcription,
windowed RCC, cross-reference compilation, the Complexity Window
Thermodynamics (CWT) interfaces, and the lower-bound theorem.

Section IV and Appendices B–D develop the finite-sample terminal-state audit:
support treatment, confidence construction, readout calibration, one-shot
conversion, and multi-path certificate synthesis. The implemented subset uses
a uniform reference on an ideal support, exact transcription, complete exact
spectra, or one predeclared projector with fixed-N iid counts. It computes the
one-sided Hoeffding endpoint, converts the information lower bound through the
canonical cost inverse, and saves the calculation for replay. Support
uncertainty, readout/leakage corrections, and multi-path synthesis require the
broader contracts developed in the paper.

## From state information to process cost

The paper distinguishes the state-side RCC value from the optimum over
preparation histories. On the unbiased reference support,

$$
\sigma_R=\Pi_R/d_R,\qquad g_R=\log_2\Gamma_R,\qquad
C_R(\rho)=\frac{D(\rho\Vert\sigma_R)}{g_R}
=\frac{\log_2 d_R-S(\rho)}{g_R}.
$$

Here $\Gamma_R$ counts operationally distinct physical actions in one declared
atomic slot, including the applicable addressing and resource semantics.
It is determined by the control interface. A count of syntax labels or the
Hilbert-space dimension alone does not determine it. One R-structon
($\mathrm{st}_R$) represents $g_R$ bits of state-side information; preparation
cost is counted in atomic resource slots.

Under the exact-transcription hypotheses of Theorem 3.1, the common lower
bound for every admissible successful history is

$$
C_{\rm opt}^{(\epsilon)}(\rho;\mathfrak M_R)
\ge F_{g_R,a}\left[D_{\max}^{\epsilon}(\rho\Vert\sigma_R)
-\beta_U\right],\qquad \beta_U=\gamma+\log_2 C_U.
$$

$D_{\max}^{\epsilon}$ uses normalized states within
$T(\tau,\rho)=\tfrac12\|\tau-\rho\|_1\le\epsilon$ of the target, with
$0\le\epsilon\le1$. The reference constant satisfies $C_U\ge1$.
$F_{g_R,a}$ inverts
$g_R L+a\log_2\max\{1,L\}$ and returns zero for nonpositive inputs.
The full information input decomposes as

$$
D_{\max}^{\epsilon}(\rho\Vert\sigma_R)
=g_R C_R(\rho)+\Delta_{\rm spec}(\rho)-\delta_{\rm sm}(\rho,\epsilon),
$$

where $H_{\min}(\rho)=-\log_2\|\rho\|_\infty$,
$\Delta_{\rm spec}=S(\rho)-H_{\min}(\rho)$ is the spectral correction,
and $\delta_{\rm sm}=D_{\max}-D_{\max}^{\epsilon}$ is the smoothing loss.
$C_R$ is the linear leading term; the stated smoothing regularity and uniform
constants give the compact form of Corollary 3.1. The calculator uses the full
nonrecursive inversion, so it retains these corrections and model overheads.

The all-path guarantee comes from the model qualifications. `RCon` places the
reference, outputs and costs in the same physical problem. `TC` covers every
admissible history with a program whose length is controlled by its cost.
`RA` bounds the semidensity of the full program domain by $C_U\sigma_R$.
Each successful program contributes a positive term to that semidensity;
the resulting bound on its output gap holds for every successful history
and survives taking the infimum of their costs.

At a fixed uniform reference and tolerance, identical target spectra yield
the same global information bound. In particular, all pure targets share
this state-side value, while their optimal preparation costs can differ.
The paper's reference-compatible windows resolve task-relevant internal
structure (Section V and Appendix E). Window calculations are part of the
broader framework; the implemented scalar routes use the declared global
support or one predeclared projector. An exact optimum additionally needs a
matching feasible preparation, as in the paired-reset example.

## From programs to the terminating output

For a fixed finite model, let $\Omega_0$ be the transient block state,
$\mathbb T$ the code-weighted continuation map, and $\mathbb H$ the
code-weighted halt map. At action depth $m$, H.1 identifies

$$
\mathbb H\mathbb T^{m-1}(\Omega_0)=\sum_{p:\thinspace\mathrm{depth}(p)=m}2^{-|p|}\rho_p.
$$

The two sides are implemented independently. Their agreement is a direct check
of the realization conventions rather than a comparison of two views of the
same array.

The terminating program semidensity is the least fixed-point series

$$
M=\sum_{m\ge 1}\mathbb H\mathbb T^{m-1}(\Omega_0).
$$

Its trace is the total Kraft weight of accepted terminating programs. The
deficit $1-\mathrm{Tr}M$ also includes unused code space when a local
prefix code is incomplete; it cannot in general be attributed entirely to
infinite execution. For a finite partial sum, the deficit additionally
includes programs that halt beyond the truncation. If
the spectral radius of the full transient superoperator is strictly below one
at the stated tolerance, the package also evaluates the linear form
$\mathbb H(I-\mathbb T)^{-1}(\Omega_0)$. At spectral radius one, the least
fixed-point series remains the defining semantics and the report marks the
linear branch as a boundary.

For one declared reference state $\sigma_R$, Eq. (H.34) gives the minimum
domination constant

$$
C^\star=\left\|\sigma_R^{-1/2}M\sigma_R^{-1/2}\right\|_\infty
$$

on compatible support. Positive mass in the kernel of the reference makes the
constant infinite. Numerically unresolved small eigenvalues are reported as
inconclusive, with no finite or infinite constant asserted. This is the
fixed-model level of the calculation; a model
family additionally asks for a uniform bound
$\sup_n C_n^\star<\infty$.

The linear audit propagates working-precision estimates for assembly, solution,
and output error, then includes reference scaling in the H.34 precision check.
Unresolved precision produces an inconclusive result. H.34 remains a numerical
point estimate; H.3 and H.4 provide the separate upper-constant certificate
interfaces. Explicit matrices and path enumeration have configurable preflight
budgets for the supported small-model setting.

## Three certificate interfaces

The package keeps three logically different constructions separate:

| interface | code checks | logical role |
|---|---|---|
| H.3 Bellman–Choi | Choi PSD, Bellman residuals, output domination, propagated constant correction | numerical verification of the fixed-model CP-supersolution conditions |
| H.4 reference potential | local matrix domination, scalar Bellman inequalities, propagated constant correction | constructive sufficient certificate |
| H.6 gain–cost | unweighted local reference gains, actual H.70 sums, fixed-model H.72 coefficients, H.76 completion | sufficient route connecting reference growth to code length |

The linear branch can construct the minimum H.3 value-map candidate from
$\mathbb H(I-\mathbb T)^{-1}$ and pass it through the independent verifier.
Candidates obtained by other analytic or numerical methods can be supplied to
the same verifier.

In exact mathematics, Theorem H.3 is a necessary and sufficient
CP-supersolution characterization of $M\preceq C\sigma_R$ for a fixed finite
model and a given $C$. The software checks a supplied candidate numerically;
a failed candidate does not establish infeasibility of all such certificates.

A failed H.70 result rejects that supplied sufficient route. Paired actions
can satisfy aggregate reference balance even when their separate worst-case
gain sums fail H.70. H.76 supplies a deterministic prefix code meeting the
local criterion, with new weights and a new program semidensity. Applying a
cost bound to that re-encoded model also requires its own target-independent
transcription calibration.

## Outcome and evidence

Finite-control checks use two axes:

| field | values | meaning |
|---|---|---|
| `outcome` | `pass`, `fail`, `inconclusive`, `not_applicable` | what happened to the named condition |
| `evidence` | `numerical` | how that outcome was established |

`not_applicable` is used for a genuine mathematical boundary, such as the
linear inverse at spectral radius one. `inconclusive` records a quantity for
which the available numerical evidence supports neither pass nor fail.
A passing H.3 or H.4 result returns the candidate plus a reserved numerical
error budget. The candidate, usable upper constant, and correction are separate
fields; a rejected or inconclusive certificate has no usable constant.

Terminal-state records separately describe exact scalar input and enclosure,
any numerical reference-certificate evidence, and the sampling confidence of
the counts route. None of these fields verifies the external physical and
transcription premises. See [Terminal-state bounds](TERMINAL_BOUNDS.md) for
their input and replay semantics.

## How the results connect to RCC

The executable evidence connects to the RCC results in a precise order:

1. finite numerical agreement for a declared input and tolerance;
2. a fixed-model semidensity, domination constant, or supplied certificate;
3. reference admissibility for a model family after its uniform analytic
   obligations are discharged;
4. the RCC lower bound after every theorem hypothesis, including transcription
   and resource conditions, is established.

The finite-control kernel produces levels one and two. The terminal-state
calculator evaluates the level-four cost inversion conditionally on supplied
model hypotheses, including the required analytic and transcription arguments.
A finite calculation alone does not establish the uniform model-family step.

The [paired-reset example](END_TO_END_EXAMPLE.md) follows this connection for
one fixed finite model. It computes the program semidensity and one-shot
endpoint gap, then combines those results with the declared physical
reference, complete program domain, exact transcription, and fixed-family
scope to apply the RCC theorem. Program `0` supplies a matching one-slot
upper bound, establishing an optimum of one slot in that model. The physical
and family-level premises are supplied analytically; the software computes the
finite-model quantities and checks the explicit preparation.

## Independent research use

The kernel also supports research on finite-control processes. A researcher can
compute a terminating program semidensity, compare independent realizations,
test supplied proof objects, and compare local reference gains with the
code-length allocation required by a chosen sufficient route. These tasks
make the repository a testbed for model design, cost assignment, negative
witnesses, and numerical
verification of supplied certificates.

The terminal-state interfaces also let researchers study how target spectra,
preparation tolerance, sampling budgets, and model overhead change a conditional
cost lower bound. Saved exact inputs and replayable scalar records make those
comparisons inspectable independently of the bundled models.

## Extension points

The current kernel accepts Python-declared finite synchronous models, prepares
candidates through the stable full-space linear route, and verifies supplied
H.3/H.4 proof objects. Analysis bundles serialize the supported model and proof
inputs for independent revalidation. The public model, verifier, bundle, and
JSON interfaces support further work on broader certificate search, additional
input formats, interval PSD verification, broader control semantics,
family-uniform diagnostics, and larger simulation backends. The
[custom-model guide](CUSTOM_MODELS.md) and
[bundle guide](ANALYSIS_BUNDLES.md) describe the implemented workflows.

## Conditional target-state bounds

The fixed eight-output example has a complete finite program domain and
one-slot witnesses for its named pure and mixed targets. It illustrates both
the continuous bound and the stronger rounding available for declared integer
atomic-slot costs. These fixed-model witnesses do not establish large-system
scaling or reachability of arbitrary user targets. Matrix spectral
certification, approximate transcription, optional stopping, and
readout/leakage corrections are outside the implemented contract. See
[Terminal-state bounds](TERMINAL_BOUNDS.md).
