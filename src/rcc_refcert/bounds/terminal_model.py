"""One fixed C^4 model with four pure and four mixed terminal outputs.

This example's complete program domain contains the eight three-bit words.
Every program costs one atomic slot. It is a fixed finite model, not a
universal state generator or a family-uniform qualification proof.
"""

from __future__ import annotations

from fractions import Fraction as Q


def declared_spectra() -> dict[str, tuple[Q, ...]]:
    result = {f"pure-{j}": tuple(Q(int(i == j)) for i in range(4)) for j in range(4)}
    base = (Q(11, 20), Q(3, 10), Q(1, 10), Q(1, 20))
    result.update(
        {f"mixed-cycle-{j}": base[-j:] + base[:-j] if j else base for j in range(4)}
    )
    return result


def exact_semidensity_diagonal() -> tuple[Q, ...]:
    states = declared_spectra()
    return tuple(sum((rho[i] / 8 for rho in states.values()), Q(0)) for i in range(4))


def build_terminal_model():
    """Construct the fixed eight-output example using the finite-control kernel."""
    import numpy as np

    from rcc_refcert import Action, FiniteControlModel

    sigma = np.eye(4, dtype=complex) / 4
    actions = []
    for number, (name, spectrum) in enumerate(declared_spectra().items()):
        kraus = []
        for i, p in enumerate(spectrum):
            if p == 0:
                continue
            for j in range(4):
                k = np.zeros((4, 4), dtype=complex)
                k[i, j] = np.sqrt(float(p))
                kraus.append(k)
        actions.append(
            Action(
                name=name,
                codeword=format(number, "03b"),
                successor=None,
                halt_kraus={"q": tuple(kraus)},
            )
        )
    return FiniteControlModel(
        syntax_states=("s",),
        control_dims={"q": 4},
        actions_by_syntax={"s": tuple(actions)},
        start_syntax="s",
        initial_blocks={"q": sigma},
        output_dim=4,
        reference_state=sigma,
        name="terminal-eight-C4",
        scope_note="Fixed eight-program terminal model; no universal or family-uniform claim",
    )
