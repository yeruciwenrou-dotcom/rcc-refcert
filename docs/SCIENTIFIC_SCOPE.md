# Scientific scope

## Repository identity

RCC makes the reference dependence of quantum circuit complexity explicit.
Its principle of structural fairness guides the construction of physical
generation models: structure already supplied by the background enters the
reference, and additional target-directed structure is generated and charged
in the same resource coordinates. The reference background, allowed dynamics,
control interface, program semantics, output convention, and cost unit must
form a consistent physical and resource description.

The reference has an independent physical origin, identified before target
selection. Together, the reference and generation model determine the
structural zero point and resource scale. A change of reference requires a
corresponding model specification; cross-model cost comparisons also account
for the resources needed to translate between the models (Appendix A.10).

Appendix F constructs an admissible qubit model family with universal
pure- and mixed-state generation to arbitrary positive tolerance. At each
size, the same member serves every target of that size. Appendix H supplies
finite-control realizations and certificate methods. These constructions give
the Section II framework explicit models and operational content.

For a target state $\rho$ in a specified admissible model, the process-side object
$C_{\rm opt}^{(\epsilon)}$ is the infimum of the declared cost over every
admissible history that prepares the target within accuracy $\epsilon$.
The reference and resource rules are held fixed across those histories.
This optimization defines a relational physical quantity, specified jointly
by the target, reference background, admissible processes, error semantics,
and cost scale. The main RCC theorem proves a rigorous lower bound on universal
optimal quantum circuit complexity by converting the target's one-shot structural
gap relative to the reference into a lower bound on this process optimum.

`rcc-refcert` implements finite-control qualification machinery for this model
class. Given prefix-coded quantum operations and a reference state, it
constructs the terminating program
semidensity, verifies reference certificates, evaluates the reference gain of
individual actions, and tests the corresponding code-length allocation.
Its terminal-state calculator then accepts declared model inputs and a target's
exact spectrum, fixed-effect counts or complete projective readout to evaluate
a quantum circuit complexity lower bound in that model's atomic resource units.

The preparation-cost workflow combines exact reference-envelope exclusions
with executed candidate programs to bound a complete target's cost in a
declared finite model. The window workflow evaluates state-side RCC complexity
across subsystems, either directly from states or along a candidate's trajectory.
Entropy deficits supply information relative to the reference; division by the
control bandwidth expresses it in complexity units. These calculations connect
optimal preparation costs with complexity profiles at a chosen subsystem resolution.

The implementation fixes program-semidensity and certificate conventions and
reproduces selected constructions from Appendices F and H of RCC manuscript
version 4. The [paper map](PAPER_MAP.md) locates the implemented objects and
checks in the RCC manuscript.

The RCC paper develops the complete framework,
including physical reference consistency, faithful transcription,
windowed RCC, cross-reference compilation, the Complexity Window
Thermodynamics (CWT) interfaces, and the lower-bound theorem.

Section IV and Appendices B–D connect finite measurements to a one-shot
information bound and, in a qualified model, a lower bound on preparation
cost. The software accepts complete exact spectra, fixed-projector counts,
and the responses of a predeclared effect on the target and reference. The
fixed-effect workflow uses one-sided Hoeffding or Clopper–Pearson endpoints
with fixed-size iid counts. It can propagate a known binary readout channel
by taking the preimage of the observed confidence interval (D.38).
For a complete projective measurement, block ranks give the reference
weights on the declared uniform support. One joint histogram region bounds
all requested windows and tolerances. A prespecified projected branch can
also report a retention-weighted state-side contribution.

Process certificates use the model's declared support, error and cost rules.
Results from several routes can be combined when they concern the same task
and their sampling events have joint coverage. In the paper, finite calibration
of an uncertain channel (D.40) and general leakage corrections require
additional evidence. The [measurement guide](TERMINAL_BOUNDS.md) and the
[finite-data studies](FINITE_DATA_STUDIES.md) show the implemented cases.

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
Hilbert-space dimension alone does not determine it. The reference fixes the
structural zero point, and $g_R$ calibrates information against the model's
atomic resource scale. Thus $C_R$ is a state-side complexity reading in
R-structons ($\mathrm{st}_R$), with $1\thinspace\mathrm{st}_R = g_R$ bits. The
model counts preparation cost in atomic resource slots. "State-side" identifies
where the reading is obtained. Its complexity meaning comes from this physical
calibration and its relation to the process optimum through the RCC theorem.

Under the exact-transcription hypotheses of Theorem 3.1, the common lower
bound for every admissible successful history is

$$
C_{\rm opt}^{(\epsilon)}(\rho;\mathfrak M_R)
\ge F_{g_R,a}\left[D_{\max}^{\epsilon}(\rho\Vert\sigma_R)
-\beta_U\right],\qquad \beta_U=\gamma+\log_2 C_U.
$$

$D_{\max}^{\epsilon}$ uses normalized states within
$T(\tau,\rho)=\frac{1}{2}\Vert\tau-\rho\Vert_1\le\epsilon$ of the target, with
$0\le\epsilon\le1$. The reference constant satisfies $C_U\ge1$.
$F_{g_R,a}$ inverts
$g_R L+a\log_2\max\lbrace1,L\rbrace$ and returns zero for nonpositive inputs.
The full information input decomposes as

$$
D_{\max}^{\epsilon}(\rho\Vert\sigma_R)
=g_R C_R(\rho)+\Delta_{\rm spec}(\rho)-\delta_{\rm sm}(\rho,\epsilon),
$$

where $H_{\min}(\rho)=-\log_2\Vert\rho\Vert_\infty$,
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
The paper's reference-compatible windows describe RCC complexity at a chosen
observation resolution (Section V and Appendix E). They retain the reference
and resource scale while changing the accessible object. The window workflow
implements explicit
subsystem reductions and finite projective observations against their declared
reference. A measured window gives a state-side reading. A process lower bound
also requires a one-shot witness for the same target and qualified model.
An exact optimum additionally needs a matching feasible preparation, as in
the paired-reset example and the closed intervals in the cost workflow.

## Preparation-cost intervals and window profiles

For exact diagonal-preserving finite recipes with diagonal initial states,
a verified reference-envelope certificate
and a budget calculation rule out cheaper preparations. Candidate programs
are then executed against the complete target in its original basis. A
candidate that meets the trace-distance tolerance supplies an upper bound.
Equal endpoints establish the optimum in that declared model; distinct
endpoints record the remaining optimality gap. This unweighted gain calculation is
distinct from the code-weighted H.70 certificate route.

Numerically supplied models support candidate execution and trace-distance
diagnostics with recorded precision policies. Those diagnostics retain their
numerical status and supply no strict feasible upper endpoint. The exact
recipe route and the numerical route therefore expose different evidence.

For a subsystem $A$, the window workflow evaluates
$C_{R,A}=(\log_2 d_A-S(\rho_A))/g_R$, in $\mathrm{st}_R$.
This is the state-side complexity reading and RCC main term; the
full finite-accuracy cost bound also uses the one-shot corrections and model
inputs above. Entropies are numerical, including when the input probabilities
are exact. For a complete bipartition, the decomposition is
$C_{R,AB}=C_{R,A}+C_{R,B}+I(A:B)/g_R$. The same bandwidth converts the
mutual information into a correlation contribution to complexity, in the same
units as the local terms. On mixed states, $I(A:B)$ measures total correlation,
including classical correlation in the cooling examples; on pure bipartite
states it equals twice the reduced-state entropy. This identity decomposes
state-side RCC complexity; the optimum over full preparation histories is
bounded using the model and one-shot terms above.

The same subsystem quantities enter the fixed-reference entropy balance
in Proposition 6.2 of the [RCC paper](https://arxiv.org/html/2509.18205v4#S6).
For a subsystem of dimension $d_A$ with uniform reference, its entropy in
bits and its calibrated complexity satisfy $S(\rho_A)+g_R C_{R,A}=\log_2 d_A$.
In the cooling trajectory a reversible compression preserves global entropy
while changing the target, bath and correlation contributions. A bath
refresh supplies fresh polarized qubits. The trajectory records the cost
spent on each step alongside the structure visible through each window.

The [preparation costs and complexity profiles guide](COST_AND_WINDOWS.md) gives editable reset and
cooling tasks, state comparisons and trajectory probes. The model's reference,
transcription and family conditions retain their roles in the universal
complexity argument.

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
C^\star=\left\Vert\sigma_R^{-1/2}M\sigma_R^{-1/2}\right\Vert_\infty
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
model and a given $C$. For each supplied candidate, the numerical verifier reports the local checks and the resulting constant.

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

Cost and window results record `execution` separately from the scientific
`decision`. Exact cost evidence uses rational arithmetic; window entropies
and numerical candidate diagnostics carry their numerical evidence level.
An executed candidate may miss the target tolerance while the analysis
itself completes successfully. See the [output contract](OUTPUT_CONTRACT.md#workflow-results).

## How the results connect to RCC

The executable evidence connects to the RCC results in a precise order:

1. finite numerical agreement for a declared input and tolerance;
2. a fixed-model semidensity, domination constant, or supplied certificate;
3. reference admissibility for a model family after its uniform analytic
   obligations are discharged;
4. the RCC lower bound after every theorem hypothesis, including transcription
   and resource conditions, is established.

The finite-control kernel produces levels one and two. The terminal-state
calculator evaluates the level-four cost inversion for the declared model using
its analytic and transcription inputs. For a model family, the same domination
constant must cover every member.

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
preparation tolerance, sampling budgets, and model overhead change the quantum
circuit complexity lower bound for a declared model. Saved exact inputs and replayable scalar records make those
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

## Target-state bounds

The fixed eight-output example has a complete finite program domain and
one-slot witnesses for its named pure and mixed targets. It illustrates both
the continuous bound and the stronger rounding available for declared integer
atomic-slot costs. In this example the inputs are a complete exact spectrum or
fixed-sample projector counts with ideal readout on the declared support.
[Terminal-state bounds](TERMINAL_BOUNDS.md) also develops the target/reference
measurement route. The [cluster and cooling studies](FINITE_DATA_STUDIES.md)
apply the measurement and process calculations to complete research tasks.
