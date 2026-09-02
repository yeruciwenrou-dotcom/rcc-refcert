# RCC paper-to-code map

This map locates the repository inside the argument of
[the RCC paper](https://arxiv.org/abs/2509.18205) and connects the implemented
mathematical objects to executable checks.

> **Manuscript alignment.** This source tree is aligned with version 4 of the
> RCC manuscript, currently being prepared as the next arXiv revision. The
> publicly available paper is presently
> [arXiv:2509.18205v3](https://arxiv.org/abs/2509.18205v3); appendix labels and
> equation numbers in this repository therefore refer to manuscript version 4.
> The repository provides executable finite-model evidence for selected
> constructions; the paper remains responsible for the analytic and
> model-family arguments.

## Theory-to-software chain

| paper layer | role in RCC | repository responsibility |
|---|---|---|
| Section II | declares the reference-contingent, structure-fair physical generation model and its qualification conditions | represents a finite-control instance with explicit references, controls, channels, codewords, and halting semantics |
| Appendix F | constructs admissible native models, including an approximately universal qubit state-generation family, and proves the class is nonempty and nontrivial | reproduces rank coding, reference balance, selected nontrivial-generation constructions, and global-reset witnesses |
| Appendix H | develops finite-control semidensities and sufficient reference-certificate routes | implements H.1–H.6 realization, fixed-point, domination, certificate, and gain–cost checks |
| Section III | derives the RCC lower bound from the complete model hypotheses | the fixed paired-reset example evaluates the exact epsilon-zero endpoint and cost inversion after its analytic model inputs are stated; the RCC paper supplies the general theorem |
| Section IV and Appendices B–D | convert finite terminal-state evidence, support treatment, calibration, and multiple audit paths into one-sided RCC lower-bound certificates | supplies qualified-model inputs, a deterministic endpoint example, and structured evidence roles; the paper supplies the finite-sample statistical and calibration layer |

The code therefore provides executable evidence for a qualified finite model.
The RCC theorem additionally depends on the physical and analytic premises
established in the RCC paper.

## Implemented objects

| paper object | implementation | executable responsibility |
|---|---|---|
| finite syntax states $S$ | `FiniteControlModel.syntax_states` | finite parser and control graph |
| physical controls $Q$, spaces $K_q$ | `FiniteControlModel.control_dims` | heterogeneous direct-sum blocks |
| codeword $c_{s,a}$, length $\ell_{s,a}$ | `Action.codeword` | prefix check and the single code-weight insertion |
| successor $\nu(s,a)$ | `Action.successor` | deterministic continue or halt transition |
| continuing CP branches | `Action.continue_kraus[(q,r)]` | unweighted physical branches, including rectangular maps |
| terminating CP map | `Action.halt_kraus[q]` | unconditional output channel |
| initial state $\Omega_0$ | `FiniteControlModel.initial_blocks` | normalized transient start state |
| transient map $\mathbb T$ | `apply_transient_map`, `transient_matrix` | code-weighted continuation |
| halt map $\mathbb H$ | `apply_halt_map`, `halt_matrix` | code-weighted terminating output |
| H.1 realization identity | `depth_contribution_by_maps`, `depth_contribution_by_enumeration` | independent depth-by-depth regression |
| H.2 least fixed point | `truncated_semidensity` | monotone finite partial sum |
| H.2 linear branch | `linear_fixed_point` | full-transient spectral-radius gate and solve |
| H.3 minimum value-map candidate | `linear_value_choi_envelopes` | constructs $\mathbb H(I-\mathbb T)^{-1}$ blocks after the same gate |
| H.3 proof object $X_x=J(\mathbb W_x)$ | `BellmanChoiCertificate`, `verify_bellman_choi` | supplied Choi, Bellman, and output-domination checks |
| H.34 minimum constant | `minimum_domination_constant` | support test and generalized-eigenvalue calculation |
| H.4 envelopes and coefficients | `ReferencePotentialCertificate`, `verify_reference_potential` | supplied local domination and scalar Bellman checks |
| H.67–H.70 local gain–cost | `analyze_reference_gain_cost` | unweighted gains and actual weighted Kraft sums |
| H.72 initial coefficients | `GainCostReport.initial_coefficients` | fixed-instance values; family supremum remains analytic |
| H.76 completion | `suggested_code_length`, `suggested_codeword` | deterministic prefix-code witness without model mutation |
| H.28 Choi composition | `precompose_choi_with_kraus` | transpose/conjugate convention |
| F.3 rank code and occupancy | `encode_word`, `decode_word`, `occupancy_factor` | exact whole-word domain and unused-rank rejection |
| F.4 natural $C>1$ example | `natural_c_gt_one_interval` | certified decimal truncation interval |
| F.5 nontrivial generation | `make_f5_two_qubit_witness` | maximally mixed reference to reset state to Bell state |
| global-reset family | `global_reset_family_constants` | fixed-size $C_n^\star=2^n$ values and non-uniformity witness |
| one finite model | `audit_model`, `ModelAnalysis` | H.1, H.2, and H.34 kept as separate outcomes |
| bundled case | `CaseStudy`, `audit_case` | model, supplied proof objects, and declared expectations |
| complete finite-control reference evidence | `audit_reference_suite`, CLI `reproduce` | deterministic structured result and Markdown report |
| fixed end-to-end bridge | `paired_reset_example`, `examples/paired_reset_lower_bound.py` | one declared model from program semidensity through $D_{\max}^{0}$ and Theorem 3.1 to a tight one-slot result, using Appendix A's canonical inversion and an explicit feasible program |

## From executable evidence to RCC results

| RCC element | connection to the package |
|---|---|
| resource condition `RCon` | the RCC paper supplies the physical interpretation of the declared reference, controls, and resources |
| faithful transcription `TC` | the transcription argument connects an external computation to the declared finite-control model |
| family-level reference admissibility `RA` | H.4 and H.6 provide family-facing certificate interfaces; the RCC paper supplies their uniform analytic realization |
| $\sup_n C_n^\star<\infty$ | fixed-size calculations become a family result through a uniform bound in the scale parameter |
| main RCC lower bound | combines `RCon`, `TC`, and `RA` with the remaining theorem hypotheses |

## Worked end-to-end bridge

The [paired-reset example](END_TO_END_EXAMPLE.md) instantiates one fixed,
transparent chain without changing the responsibility split above:

| stage | executable value | paper connection |
|---|---|---|
| physical model | $\sigma_R=I/2$, paired terminal resets, codewords `0` and `1` | Appendix F, Eqs. (F.41)–(F.44) |
| program semidensity | $M_U=I/2$, trace $1$, nonhalting mass $0$ | Appendix H, H.1–H.2 |
| fixed-model qualification | $C^\star=1$; supplied H.3/H.4 candidates pass; H.77 residual $0$ | Appendix H, H.3–H.4 and Eqs. (H.67)–(H.77) |
| endpoint gap | $D_{\max}^{0}(\lvert0\rangle\langle0\rvert\Vert I/2)=1$ bit | Appendix A, Eqs. (A.6)–(A.7) |
| RCC reporting unit | $1\,{\rm st}_R=g_R=1$ bit | Section II, Definition 2.6 |
| main lower bound and cost inversion | $g_R=1$, $a=\gamma=\chi_U=0$, hence $C_{\rm opt}^{(0)}\ge1$ slot | Section III, Theorem 3.1 and Eq. (3.1); Appendix A, Eqs. (A.45)–(A.46) |
| matching upper-bound witness | program `0` prepares the target exactly in one slot, hence $C_{\rm opt}^{(0)}\le1$ and the fixed-model value is $1$ | declared paired-reset model and executable program semantics |

The software computes the finite matrices and checks supplied proof objects.
The physical reference meaning, complete-domain identification, exact
transcription, and fixed-family scope remain explicit analytic inputs. Their
combination with the RCC theorem yields the lower bound; the separately
verified one-slot program makes that bound tight for this fixed model. This is
not a general RCC optimizer or a model-family uniformity proof.

## Complete framework

`rcc-refcert` implements the finite-control qualification layer mapped above.
The [RCC paper](https://arxiv.org/abs/2509.18205) presents the complete physical
model and lower-bound framework, including transcription, family-level
arguments, finite-sample auditing, windowed RCC, dynamical witnesses, and the
Complexity-Windowed Thermodynamics (CWT) interfaces.
