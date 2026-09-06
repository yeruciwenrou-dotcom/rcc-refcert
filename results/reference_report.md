# RCC RefCert reference report

This report presents executable evidence for RCC's finite-control model-qualification layer. It records declared processes, terminating program semidensities, and supplied proof objects, including diagnostics for whether action code lengths account for their reference gain. Paper references use RCC manuscript version 4.

## Run summary

Package: `rcc-refcert 0.1.0`  
Action depth: `1–8`  
Maximum transient continuations: `16`  
Numerical tolerance: `1.0e-10`

Residual diagnostics with absolute value at or below the numerical tolerance are shown as `0`. Certificate upper bounds and their error budgets round upward. Fresh CLI JSON retains the computed finite diagnostics.

| case | purpose | reference result |
|---|---|---|
| `dephase-or-halt` | A transparent one-block model with a closed-form semidensity and tight reference certificates. | pass |
| `multiblock-rectangular` | Exercises direct-sum ordering, unequal block dimensions, rectangular Kraus maps, and nontrivial H.3–H.6 certificates. | expected route failure |
| `dark-nonhalting` | Confirms that a valid nonhalting process keeps its least fixed-point meaning even when the linear inverse is unavailable. | expected boundary |
| Appendix F witnesses | Rank encoding, reference balance, nontrivial generation, and global reset | pass |

The summary reports agreement with the declared reference cases.

## Reading the outcomes

- `pass` means that a stated finite numerical condition holds at the displayed tolerance.
- `fail (expected)` marks the designed cost shortfall along a sufficient route.
- `inconclusive (expected)` marks a quantity left open by the current numerical route.
- `not applicable (expected)` marks a mathematical boundary where that calculation is unavailable.
- Matrix and certificate outcomes use floating-point numerical evidence at the displayed tolerance.

## Dephase or halt

A transparent one-block model with a closed-form semidensity and tight reference certificates.

RCC paper map: H.1, H.2, H.3, H.4, H.6.

| check | observed outcome | expected outcome | key value |
|---|---|---|---:|
| H.1 realization | pass | pass | max error 0 |
| H.2 linear fixed point | pass | pass | rho(T) = 0.5 |
| H.34 fixed-model domination | pass | pass | C* estimate = 1 |
| H.3 Bellman–Choi | pass | pass | C <= 1.00000000011; candidate 1; correction <= 1.01e-10 |
| H.4 reference potential | pass | pass | C <= 1.00000000011; candidate 1; correction <= 1.01e-10, C <= 2.00000000021; candidate 2; correction <= 2.01e-10 |
| H.6 gain–cost | pass | pass | s: 1 |

### Numerical diagnostics

- H.1 was checked at action depths 1–8; the maximum spectral-norm difference was `0`.
- The partial sum through 16 transient continuations has output trace `0.999992370605`.
- The linear solve has condition number `2.000e+00` and residual `0`.
- The full transient-space spectral radius is below one; numerical assembly and solve errors are propagated to the output.
- H.34: fixed-model minimum estimated from Appendix-H Eq. (H.34).
- `minimum Bellman–Choi value-map certificate` has minimum PSD residual eigenvalue `0`.
- `tight C=1 reference-potential certificate` has minimum scalar Bellman margin `0`.
- `positive-margin reference-potential certificate` has minimum scalar Bellman margin `0.5`.

### H.6 code-length diagnostic

| syntax | current H.70 sum | current route | H.76 sum | suggested codewords |
|---|---:|---|---:|---|
| `s` | 1 | passes | 1 | `dephase-and-continue=0`, `halt=1` |

## Multiblock rectangular process

Exercises direct-sum ordering, unequal block dimensions, rectangular Kraus maps, and nontrivial H.3–H.6 certificates.

RCC paper map: H.1, H.2, H.3, H.4, H.6.

| check | observed outcome | expected outcome | key value |
|---|---|---|---:|
| H.1 realization | pass | pass | max error 0 |
| H.2 linear fixed point | pass | pass | rho(T) = 0.353553390593 |
| H.34 fixed-model domination | pass | pass | C* estimate = 1.07142857143 |
| H.3 Bellman–Choi | pass | pass | C <= 1.07142857154; candidate 1.07142857143; correction <= 1.08e-10 |
| H.4 reference potential | pass | pass | C <= 1.33333333347; candidate 1.33333333333; correction <= 1.34e-10 |
| H.6 gain–cost | fail (expected) | fail | s0: 2, s1: 1.5 |

### Numerical diagnostics

- H.1 was checked at action depths 1–8; the maximum spectral-norm difference was `0`.
- The partial sum through 16 transient continuations has output trace `0.857142835855`.
- The linear solve has condition number `2.541e+00` and residual `0`.
- The full transient-space spectral radius is below one; numerical assembly and solve errors are propagated to the output.
- H.34: fixed-model minimum estimated from Appendix-H Eq. (H.34).
- `multiblock minimum value-map certificate` has minimum PSD residual eigenvalue `0`.
- `multiblock rectangular reference-potential certificate` has minimum scalar Bellman margin `0`.

### H.6 code-length diagnostic

| syntax | current H.70 sum | current route | H.76 sum | suggested codewords |
|---|---:|---|---:|---|
| `s0` | 2 | fails | 1 | `compress-and-continue=00`, `halt-from-s0=01` |
| `s1` | 1.5 | fails | 1 | `expand-and-continue=00`, `halt-from-s1=01` |

Interpretation: The original local codewords intentionally fail the sufficient condition in Eq. (H.70); Eq. (H.76) supplies a passing re-encoding.

## Dark nonhalting loop

Confirms that a valid nonhalting process keeps its least fixed-point meaning even when the linear inverse is unavailable.

RCC paper map: H.1, H.2, H.34.

| check | observed outcome | expected outcome | key value |
|---|---|---|---:|
| H.1 realization | pass | pass | max error 0 |
| H.2 linear fixed point | not applicable (expected) | not applicable | rho(T) = 1 |
| H.34 fixed-model domination | inconclusive (expected) | inconclusive | not evaluated |

### Numerical diagnostics

- H.1 was checked at action depths 1–8; the maximum spectral-norm difference was `0`.
- The partial sum through 16 transient continuations has output trace `0`.
- The full transient spectral radius lies at the linear-inverse boundary; the least fixed-point series remains the defining semantics.

Interpretation: The full transient spectral radius is one. The least fixed-point semantics remains valid, while the Neumann/linear-inverse route reaches its boundary. Eq. (H.34) therefore awaits the completed semidensity rather than using a finite truncation.

## Appendix F executable witnesses

- F.3 whole-word rank decoder: all `781` words over a `Gamma=5` alphabet at lengths 0–4, including the empty word, with `0` round-trip failures.
- `Gamma=5` reference-balance error: `0`.
- Word-average errors for lengths 1–5: `0, 0, 0, 0, 0`.
- Partial program Kraft mass over lengths 0–5: `0.749214172363`.
- F.5 two-qubit witness: reset-pair balance error `0`, Bell-state generation error `0`, and purity `0.25 → 1.00`.
- Natural fixed-model `C>1`: `1.398804068566732894`, inside a decimal interval of width `3.944E-31`.
- Global-reset fixed-size constants: n=1: 2, n=2: 4, n=3: 8, n=4: 16, n=5: 32, n=6: 64, n=7: 128, n=8: 256.

### Global-reset H.6 diagnostic

| model | current H.70 sum | current route | H.76 sum | suggested halt length |
|---|---:|---|---:|---:|
| `global-reset-loop-n=1` | 1.5 | fails as expected | 1 | 2 |
| `global-reset-loop-n=2` | 2.5 | fails as expected | 1 | 3 |
| `global-reset-loop-n=3` | 4.5 | fails as expected | 1 | 4 |
| `global-reset-loop-n=4` | 8.5 | fails as expected | 1 | 5 |

## Scientific scope

The calculations above establish finite-input and fixed-model numerical statements for the declared processes and supplied proof objects. They make the Appendix F/H constructions inspectable. The RCC paper supplies the physical reference-consistency, faithful-transcription (`TC`), and uniform model-family arguments used by the lower bound. An H.70 failure identifies a cost shortfall along that sufficient gain–cost route.
