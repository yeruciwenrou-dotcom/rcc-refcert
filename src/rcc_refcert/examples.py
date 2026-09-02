from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from decimal import Decimal, localcontext

import numpy as np

from .bellman_choi import BellmanChoiCertificate
from .fixed_point import linear_value_choi_envelopes
from .model import Action, FiniteControlModel
from .prefix import elias_header_length
from .quantum import (
    Array,
    apply_kraus,
    choi_from_kraus,
    dephasing_kraus_qubit,
    identity_kraus,
    reset_kraus_qubit,
)
from .rank_encoding import occupancy_factor, partial_program_kraft_mass
from .reference_potential import ReferencePotentialCertificate


@dataclass(frozen=True)
class F5QubitWitness:
    """Two-qubit executable witness for the nontrivial construction in F.5."""

    reference_state: Array
    after_resets: Array
    generated_state: Array
    target_state: Array
    reset_pair_balance_errors: tuple[float, float]

    @property
    def generation_error(self) -> float:
        return float(np.linalg.norm(self.generated_state - self.target_state, ord=2))

    @property
    def initial_purity(self) -> float:
        return float(np.trace(self.reference_state @ self.reference_state).real)

    @property
    def final_purity(self) -> float:
        return float(np.trace(self.generated_state @ self.generated_state).real)


@dataclass(frozen=True)
class Gamma5Summary:
    """Executable balance and coding quantities for the five-channel alphabet."""

    reference_balance_error: float
    word_average_errors: tuple[float, ...]
    partial_kraft_mass: float
    occupancy_factors: tuple[float, ...]


def make_dephase_or_halt_model() -> FiniteControlModel:
    sigma = np.eye(2, dtype=complex) / 2.0
    continue_action = Action(
        name="dephase-and-continue",
        codeword="1",
        successor="s",
        continue_kraus={("q", "q"): dephasing_kraus_qubit()},
    )
    halt_action = Action(
        name="halt",
        codeword="0",
        successor=None,
        halt_kraus={"q": identity_kraus(2)},
    )
    return FiniteControlModel(
        syntax_states=("s",),
        control_dims={"q": 2},
        actions_by_syntax={"s": (continue_action, halt_action)},
        start_syntax="s",
        initial_blocks={"q": sigma},
        output_dim=2,
        reference_state=sigma,
        name="dephase-or-halt",
    )


def make_dephase_reference_potential_certificates(
    model: FiniteControlModel,
) -> tuple[ReferencePotentialCertificate, ...]:
    """Return the tight and positive-margin H.4 certificates for the model."""

    block = ("s", "q")
    return (
        ReferencePotentialCertificate(
            theta={block: model.reference_state},
            a={block: 1.0},
            transition_coefficients={(block, block): 0.5},
            halt_coefficients={block: 0.5},
            potential={block: 1.0},
            name="tight C=1 reference-potential certificate",
        ),
        ReferencePotentialCertificate(
            theta={block: model.reference_state},
            a={block: 1.0},
            transition_coefficients={(block, block): 0.5},
            halt_coefficients={block: 0.5},
            potential={block: 2.0},
            name="positive-margin reference-potential certificate",
        ),
    )


def make_dephase_bellman_choi_certificate(
    model: FiniteControlModel,
) -> BellmanChoiCertificate:
    """Return the minimum H.3 value-map certificate for the one-block model."""

    scale = np.sqrt(0.5)
    identity = np.eye(2, dtype=complex)
    p0 = np.array([[1, 0], [0, 0]], dtype=complex)
    p1 = np.array([[0, 0], [0, 1]], dtype=complex)
    value_choi = choi_from_kraus((scale * identity, scale * p0, scale * p1))
    return BellmanChoiCertificate(
        choi_envelopes={("s", "q"): value_choi},
        constant=1.0,
        name="minimum Bellman–Choi value-map certificate",
    )


def make_same_space_reference_envelopes(
    model: FiniteControlModel,
) -> dict[tuple[str, str], Array]:
    """Use ``sigma_R`` when every transient block shares the output space."""

    return {key: model.reference_state for key in model.transient_keys()}


def _trace_to_scalar_kraus(dim: int) -> tuple[Array, ...]:
    matrices = []
    for index in range(dim):
        matrix = np.zeros((1, dim), dtype=complex)
        matrix[0, index] = 1.0
        matrices.append(matrix)
    return tuple(matrices)


def _prepare_from_scalar_kraus(dim: int, index: int) -> tuple[Array, ...]:
    if not 0 <= index < dim:
        raise ValueError("preparation index is outside the target dimension")
    matrix = np.zeros((dim, 1), dtype=complex)
    matrix[index, 0] = 1.0
    return (matrix,)


def make_multiblock_rectangular_model() -> FiniteControlModel:
    """A two-syntax, two-control regression with 2->1 and 1->2 branches.

    The declaration order is intentionally non-canonical.  Matrix realization
    must nevertheless use the sorted direct-sum order returned by
    :meth:`FiniteControlModel.transient_keys`.
    """

    sigma = np.eye(2, dtype=complex) / 2.0
    q2_to_q1 = _trace_to_scalar_kraus(2)
    q1_to_q2_zero = _prepare_from_scalar_kraus(2, 0)
    q1_to_zero_out = _prepare_from_scalar_kraus(2, 0)
    q1_to_one_out = _prepare_from_scalar_kraus(2, 1)

    s0_continue = Action(
        name="compress-and-continue",
        codeword="0",
        successor="s1",
        continue_kraus={
            ("q2", "q1"): q2_to_q1,
            ("q1", "q2"): q1_to_q2_zero,
        },
    )
    s0_halt = Action(
        name="halt-from-s0",
        codeword="1",
        successor=None,
        halt_kraus={"q2": identity_kraus(2), "q1": q1_to_zero_out},
    )
    s1_continue = Action(
        name="expand-and-continue",
        codeword="10",
        successor="s0",
        continue_kraus={
            ("q1", "q2"): q1_to_q2_zero,
            ("q2", "q1"): q2_to_q1,
        },
    )
    s1_halt = Action(
        name="halt-from-s1",
        codeword="0",
        successor=None,
        halt_kraus={"q1": q1_to_one_out, "q2": identity_kraus(2)},
    )
    return FiniteControlModel(
        syntax_states=("s1", "s0"),
        control_dims={"q2": 2, "q1": 1},
        actions_by_syntax={
            "s1": (s1_continue, s1_halt),
            "s0": (s0_continue, s0_halt),
        },
        start_syntax="s0",
        initial_blocks={"q2": sigma},
        output_dim=2,
        reference_state=sigma,
        name="multiblock-rectangular",
        scope_note="H.1-H.2 regression with canonical block order and rectangular Kraus maps",
    )


def make_multiblock_reference_potential_certificate() -> ReferencePotentialCertificate:
    """A nontrivial H.4 certificate for ``make_multiblock_rectangular_model``."""
    keys = (
        ("s0", "q1"),
        ("s0", "q2"),
        ("s1", "q1"),
        ("s1", "q2"),
    )
    theta = {
        ("s0", "q1"): np.ones((1, 1), dtype=complex),
        ("s0", "q2"): np.eye(2, dtype=complex) / 2.0,
        ("s1", "q1"): np.ones((1, 1), dtype=complex),
        ("s1", "q2"): np.eye(2, dtype=complex) / 2.0,
    }
    return ReferencePotentialCertificate(
        theta=theta,
        a={key: (1.0 if key == ("s0", "q2") else 0.0) for key in keys},
        transition_coefficients={
            (("s0", "q1"), ("s1", "q2")): 1.0,
            (("s0", "q2"), ("s1", "q1")): 0.5,
            (("s1", "q1"), ("s0", "q2")): 0.5,
            (("s1", "q2"), ("s0", "q1")): 0.25,
        },
        halt_coefficients={
            ("s0", "q1"): 1.0,
            ("s0", "q2"): 0.5,
            ("s1", "q1"): 1.0,
            ("s1", "q2"): 0.5,
        },
        potential={
            ("s0", "q1"): 2.0,
            ("s0", "q2"): 4.0 / 3.0,
            ("s1", "q1"): 5.0 / 3.0,
            ("s1", "q2"): 1.0,
        },
        name="multiblock rectangular reference-potential certificate",
    )


def make_multiblock_reference_potential_certificates(
    _model: FiniteControlModel,
) -> tuple[ReferencePotentialCertificate, ...]:
    """Return the supplied H.4 certificate for the multiblock model."""

    return (make_multiblock_reference_potential_certificate(),)


def make_multiblock_bellman_choi_certificate(
    model: FiniteControlModel,
) -> BellmanChoiCertificate:
    """Construct the minimum value-map candidate used by the H.3 verifier."""

    return BellmanChoiCertificate(
        choi_envelopes=linear_value_choi_envelopes(model),
        constant=15.0 / 14.0,
        name="multiblock minimum value-map certificate",
    )


def make_multiblock_gain_cost_envelopes(
    _model: FiniteControlModel,
) -> dict[tuple[str, str], Array]:
    """Return the H.4 reference envelopes used for the H.6 calculation."""

    return make_multiblock_reference_potential_certificate().theta


def _two_qubit_local_reset_kraus(qubit: int, bit: int) -> tuple[Array, ...]:
    if qubit not in (0, 1) or bit not in (0, 1):
        raise ValueError("qubit and bit must both lie in {0,1}")
    identity = np.eye(2, dtype=complex)
    single = reset_kraus_qubit(bit)
    if qubit == 0:
        return tuple(np.kron(matrix, identity) for matrix in single)
    return tuple(np.kron(identity, matrix) for matrix in single)


def make_f5_two_qubit_witness() -> F5QubitWitness:
    """Execute sigma_2 -> |00><00| -> |Phi+><Phi+| from Appendix F.5.

    Paired reset-to-zero/reset-to-one channels are checked on the maximally
    mixed reference, while the selected reset-to-zero path carries the actual
    direction and preparation cost.
    """

    sigma = np.eye(4, dtype=complex) / 4.0
    balance_errors: list[float] = []
    for qubit in (0, 1):
        reset_zero = apply_kraus(_two_qubit_local_reset_kraus(qubit, 0), sigma)
        reset_one = apply_kraus(_two_qubit_local_reset_kraus(qubit, 1), sigma)
        balance_errors.append(
            float(np.linalg.norm(0.5 * (reset_zero + reset_one) - sigma, ord=2))
        )

    after_resets = apply_kraus(_two_qubit_local_reset_kraus(0, 0), sigma)
    after_resets = apply_kraus(_two_qubit_local_reset_kraus(1, 0), after_resets)

    hadamard = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2.0)
    h_first = np.kron(hadamard, np.eye(2, dtype=complex))
    cnot = np.array(
        [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]],
        dtype=complex,
    )
    generated = apply_kraus((h_first,), after_resets)
    generated = apply_kraus((cnot,), generated)

    bell = np.array([1, 0, 0, 1], dtype=complex) / math.sqrt(2.0)
    target = np.outer(bell, bell.conj())
    return F5QubitWitness(
        reference_state=sigma,
        after_resets=after_resets,
        generated_state=generated,
        target_state=target,
        reset_pair_balance_errors=(balance_errors[0], balance_errors[1]),
    )


def make_dark_nonhalting_loop_model() -> FiniteControlModel:
    sigma = np.eye(2, dtype=complex) / 2.0
    left = Action(
        name="dark-left",
        codeword="0",
        successor="s",
        continue_kraus={("q", "q"): identity_kraus(2)},
    )
    right = Action(
        name="dark-right",
        codeword="1",
        successor="s",
        continue_kraus={("q", "q"): identity_kraus(2)},
    )
    return FiniteControlModel(
        syntax_states=("s",),
        control_dims={"q": 2},
        actions_by_syntax={"s": (left, right)},
        start_syntax="s",
        initial_blocks={"q": sigma},
        output_dim=2,
        reference_state=sigma,
        name="dark-nonhalting-loop",
        scope_note="valid H.2 boundary with no finite accepting program",
    )


def make_global_reset_loop_model(n: int) -> FiniteControlModel:
    """Fixed-size member of the global-reset family from F.1 and H.6."""
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise ValueError("n must be a positive integer")
    dim = 2**n
    sigma = np.eye(dim, dtype=complex) / dim
    reset = []
    for index in range(dim):
        matrix = np.zeros((dim, dim), dtype=complex)
        matrix[0, index] = 1.0
        reset.append(matrix)
    continue_action = Action(
        name="continue",
        codeword="1",
        successor="s",
        continue_kraus={("q", "q"): identity_kraus(dim)},
    )
    halt_action = Action(
        name="global-reset-and-halt",
        codeword="0",
        successor=None,
        halt_kraus={"q": tuple(reset)},
    )
    return FiniteControlModel(
        syntax_states=("s",),
        control_dims={"q": dim},
        actions_by_syntax={"s": (continue_action, halt_action)},
        start_syntax="s",
        initial_blocks={"q": sigma},
        output_dim=dim,
        reference_state=sigma,
        name=f"global-reset-loop-n={n}",
        scope_note=(
            "fixed-size global-reset counterexample; family uniformity fails as n grows"
        ),
    )


def make_rank_deficient_reference_model() -> FiniteControlModel:
    model = make_dephase_or_halt_model()
    model.reference_state = np.array([[1.0, 0.0], [0.0, 0.0]], dtype=complex)
    model.name = "rank-deficient-reference-on-unreduced-output"
    return model


def make_invalid_prefix_model() -> FiniteControlModel:
    model = make_dephase_or_halt_model()
    model.actions_by_syntax["s"][0].codeword = "0"
    model.actions_by_syntax["s"][1].codeword = "01"
    return model


def make_incomplete_instrument_model() -> FiniteControlModel:
    model = make_dephase_or_halt_model()
    p0 = np.array([[1, 0], [0, 0]], dtype=complex)
    model.actions_by_syntax["s"][0].continue_kraus = {("q", "q"): (p0,)}
    return model


def gamma5_qubit_alphabet() -> dict[str, tuple[Array, ...]]:
    hadamard = np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2.0)
    phase_t = np.diag([1.0, np.exp(1j * math.pi / 4.0)]).astype(complex)
    return {
        "H": (hadamard,),
        "T": (phase_t,),
        "Delta": dephasing_kraus_qubit(),
        "R0": reset_kraus_qubit(0),
        "R1": reset_kraus_qubit(1),
    }


def gamma5_reference_balance_error() -> float:
    sigma = np.eye(2, dtype=complex) / 2.0
    outputs = [apply_kraus(kraus, sigma) for kraus in gamma5_qubit_alphabet().values()]
    average = sum(outputs, np.zeros_like(sigma)) / 5.0
    return float(np.linalg.norm(average - sigma, ord=2))


def gamma5_explicit_word_average_error(length: int) -> float:
    if length < 0:
        raise ValueError("length must be nonnegative")
    sigma = np.eye(2, dtype=complex) / 2.0
    alphabet = list(gamma5_qubit_alphabet().values())
    if length == 0:
        return 0.0
    total = np.zeros_like(sigma)
    count = 0
    for word in itertools.product(alphabet, repeat=length):
        state = sigma
        for channel in word:
            state = apply_kraus(channel, state)
        total += state
        count += 1
    return float(np.linalg.norm(total / count - sigma, ord=2))


def gamma5_summary(max_length: int = 5) -> Gamma5Summary:
    if max_length < 0:
        raise ValueError("max_length must be nonnegative")
    return Gamma5Summary(
        reference_balance_error=gamma5_reference_balance_error(),
        word_average_errors=tuple(
            gamma5_explicit_word_average_error(length)
            for length in range(1, max_length + 1)
        ),
        partial_kraft_mass=partial_program_kraft_mass(5, max_length),
        occupancy_factors=tuple(
            occupancy_factor(5, length) for length in range(max_length + 1)
        ),
    )


def natural_c_gt_one_interval(max_length: int = 100) -> tuple[Decimal, Decimal]:
    """Certified decimal interval for 2 - sum_L q_L 2^{-L}.

    The omitted sum is bounded by 2^{-(max_length+1)} because the
    remaining Elias length weights have total mass at most one.
    """
    if max_length < 0:
        raise ValueError("max_length must be nonnegative")
    with localcontext() as context:
        context.prec = max(80, max_length + 30)
        two = Decimal(2)
        partial = Decimal(0)
        for length in range(max_length + 1):
            q_length = two ** (-elias_header_length(length))
            partial += q_length * (two ** (-length))
        omitted_upper = two ** (-(max_length + 1))
        upper = two - partial
        lower = upper - omitted_upper
        return +lower, +upper


def global_reset_family_constants(max_n: int = 8) -> list[tuple[int, int]]:
    if max_n < 1:
        return []
    from .domination import minimum_domination_constant

    constants: list[tuple[int, int]] = []
    for n in range(1, max_n + 1):
        dim = 2**n
        semidensity = np.zeros((dim, dim), dtype=complex)
        semidensity[0, 0] = 1.0
        reference = np.eye(dim, dtype=complex) / dim
        result = minimum_domination_constant(semidensity, reference)
        if not np.isfinite(result.constant):  # pragma: no cover - mathematical guard
            raise RuntimeError(
                "global-reset fixed-size model unexpectedly lacks finite domination"
            )
        constants.append((n, round(result.constant)))
    return constants
