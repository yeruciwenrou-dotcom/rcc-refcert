# Mathematical and tensor conventions

These conventions determine every numerical result. A change here requires the
convention tests, the multiblock regression, the negative certificate tests, and
the frozen report to be rerun.

## Spaces, support, and block order

A transient block is indexed by `x = (syntax_state, control_state)` and carries
an operator on the Hilbert space declared by that control state. Matrix
realizations use the canonical lexicographic order of syntax labels and then
control labels. Declaration or dictionary insertion order has no mathematical
effect.

The output space is the declared support of the reference. `FiniteControlModel`
requires `sigma_R` to be numerically certifiable as full rank on that space. A
rank-deficient reference in a larger ambient space must be reduced to its
support before model construction. The lower-level
`minimum_domination_constant` function also exposes explicit
support-compatibility diagnostics for Eq. (H.34).

## Program weight and physical weight

Kraus operators in an `Action` are unweighted physical operators. A codeword of
length $\ell$ contributes $2^{-\ell}$ exactly once in the syntax layer.
Equivalently, a composed program carries $2^{-|p|}$.

The trace of each CP branch supplies the Born weight; code length supplies the
syntax weight, exactly once. Each declared action is a total quantum operation
across all its physical outcome branches; continuation versus halt is a
syntax-level choice.

## Halting and subnormalization

The terminating output is a positive semidefinite semidensity with trace at most
one. Missing trace is nonhalting code mass. The semidensity remains
unnormalized, preserving both that mass and its Appendix H domination constant.

## Vectorization

Column-major vectorization is used:

$$
\mathrm{vec}(X)=(X_{11},X_{21},\ldots,X_{d1},X_{12},\ldots)^T,
$$

so

$$
\mathrm{vec}(KXK^\dagger)
=(\overline K\otimes K)\mathrm{vec}(X).
$$

The small-model transient and halt matrices are built by applying maps to matrix
units. This is slower than relying on a single Kronecker expression, but makes
direct-sum and rectangular-Kraus conventions easier to audit.

## Choi convention

The frozen convention is

$$
J(\Phi)=\sum_{ij}|i\rangle\langle j|_{\rm in}\otimes
\Phi(|i\rangle\langle j|)_{\rm out},
$$

with tensor order $\mathrm{input}\otimes\mathrm{output}$. Therefore

$$
J(\mathbb W_y\circ\mathbb T_{y\leftarrow x})
=\sum_\mu(K_\mu^T\otimes I)X_y(\overline K_\mu\otimes I).
$$

The code factor is absorbed once as $2^{-\ell/2}$ into the transition Kraus
operators used for this composition. A complex nonsymmetric regression
distinguishes this formula from the common but incorrect
adjoint/no-conjugation alternative.

## Composition order

For actions $a_1,\ldots,a_m$, $a_1$ acts first. The corresponding channel is
$\Phi_{a_m}\circ\cdots\circ\Phi_{a_1}$.

## Fixed point

The least-fixed-point series is primary. `linear_fixed_point` solves with
$(I-\mathbb T)^{-1}$ only if the spectral radius of the entire transient
superoperator matrix is below $1-\mathrm{tol}$. The spectral-radius gate is evaluated on that entire
matrix.

## Numerical outcomes and residuals

Floating-point matrix inequalities use the smallest eigenvalue of the Hermitian
symmetrization. Each result records the observed `outcome` separately from its
`evidence`; the current evidence level is `numerical`. Certificate checks retain
the tested residual matrix as well as its scalar diagnostic. A numerical pass
certifies the stated floating-point condition at its recorded tolerance; the
evidence level remains `numerical`.
