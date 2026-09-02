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
Structure fairness requires target-shortening resources to be represented in
those same coordinates. `rcc-refcert` implements the finite-control
qualification machinery for this model class. Given prefix-coded quantum
operations and a reference state, it constructs the terminating program
semidensity, verifies reference certificates, evaluates the reference gain of
individual actions, and tests the corresponding code-length allocation.

Its roles form a deliberate hierarchy:

1. a research implementation of the finite-control qualification machinery
   arising from the physical model in Section II of
   [the RCC paper](https://arxiv.org/abs/2509.18205);
2. a reference implementation of program-semidensity and certificate
   conventions for that model class;
3. an executable reproduction of the selected constructions in Appendices F
   and H.

Appendix F proves that the model class is nonempty and constructs an admissible
qubit model family with approximately universal pure- and mixed-state
generation. Appendix H supplies finite-control realization and certificate
machinery. Together they make the Section II model an explicit, auditable
construction. Section III uses the qualified model hypotheses in the RCC lower
bound.

`rcc-refcert` concentrates on the finite-control qualification layer. The RCC
paper develops the complete framework, including physical reference
consistency, faithful transcription, finite-sample terminal-state auditing,
windowed RCC, cross-reference compilation, the Complexity-Windowed
Thermodynamics (CWT) interfaces, and the lower-bound theorem.

Section IV and Appendices B–D develop the finite-sample terminal-state audit:
support treatment, confidence construction, readout calibration, one-shot
conversion, and multi-path certificate synthesis. The current kernel supplies
qualified-model inputs, a deterministic endpoint example, and structured
evidence roles for that layer. The paper provides its finite-sample statistical
and calibration framework.

## Executable mathematical spine

For a fixed finite model, let $\Omega_0$ be the transient block state,
$\mathbb T$ the code-weighted continuation map, and $\mathbb H$ the
code-weighted halt map. At action depth $m$, H.1 identifies

$$
\mathbb H\mathbb T^{m-1}(\Omega_0)=\sum_{p:\,\mathrm{depth}(p)=m}2^{-|p|}\rho_p.
$$

The two sides are implemented independently. Their agreement is a direct check
of the realization conventions rather than a comparison of two views of the
same array.

The terminating program semidensity is the least fixed-point series

$$
M=\sum_{m\ge 1}\mathbb H\mathbb T^{m-1}(\Omega_0).
$$

It is subnormalized, and its trace deficit records nonhalting program mass. If
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
constant infinite. This is the fixed-model level of the calculation; a model
family additionally asks for a uniform bound
$\sup_n C_n^\star<\infty$.

## Three certificate interfaces

The package keeps three logically different constructions separate:

| interface | code checks | logical role |
|---|---|---|
| H.3 Bellman–Choi | Choi PSD, Bellman residuals, output domination | exact fixed finite-model characterization for a supplied candidate $C$ |
| H.4 reference potential | local matrix domination and scalar Bellman inequalities | constructive sufficient certificate |
| H.6 gain–cost | unweighted local reference gains, actual H.70 sums, fixed-model H.72 coefficients, H.76 completion | sufficient route connecting reference growth to code length |

The linear branch can construct the minimum H.3 value-map candidate from
$\mathbb H(I-\mathbb T)^{-1}$ and pass it through the independent verifier.
Candidates obtained by other analytic or numerical methods can be supplied to
the same verifier.

A failed H.70 result rejects that supplied sufficient route. H.76 then gives a
deterministic local prefix-code witness at sufficient lengths. The corresponding
RCC analysis supplies its target-independent transcription calibration.

## Outcome and evidence

Results use two axes:

| field | values | meaning |
|---|---|---|
| `outcome` | `pass`, `fail`, `inconclusive`, `not_applicable` | what happened to the named condition |
| `evidence` | `numerical` | how that outcome was established |

`not_applicable` is used for a genuine mathematical boundary, such as the
linear inverse at spectral radius one. `inconclusive` records a quantity for
which the available numerical evidence supports neither pass nor fail.

## Claim ladder

The executable evidence connects to the RCC results in a precise order:

1. finite numerical agreement for a declared input and tolerance;
2. a fixed-model semidensity, domination constant, or supplied certificate;
3. reference admissibility for a model family after its uniform analytic
   obligations are discharged;
4. the RCC lower bound after every theorem hypothesis, including transcription
   and resource conditions, is established.

The package produces levels one and two. Levels three and four combine those
outputs with the uniform analytic and transcription arguments developed in the
RCC paper.

The [paired-reset end-to-end example](END_TO_END_EXAMPLE.md) makes this handoff
executable for one fixed finite model. It computes the program semidensity and
one-shot endpoint gap, while separately declaring the physical reference,
complete program domain, exact transcription, and fixed-family scope needed to
invoke the RCC theorem. Its numerical cost floor is therefore a worked
theorem consequence under declared inputs. Program `0` supplies a matching
one-slot upper-bound witness, so the optimum is exactly one slot for this fixed
model. Automated general optimization and `RCon`, `TC`, or family-uniform `RA`
certification remain outside the example.

## Independent research use

The kernel also supports research on finite-control processes. A researcher can
compute a terminating program semidensity, compare independent realizations,
test supplied proof objects, and locate operations whose description cost is
too small for their reference gain. These tasks make the repository a testbed
for model design, cost assignment, negative witnesses, and rigorous certificate
verification.

## Extension points

The current kernel accepts Python-declared finite synchronous models and
supplied certificate candidates. Its public model, verifier, and JSON result
interfaces provide natural extension points for model serialization, automated
certificate search, interval PSD verification, broader control semantics,
family-uniform diagnostics, and larger simulation backends. These interfaces
define the package's current extension directions.
