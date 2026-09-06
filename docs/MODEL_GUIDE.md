# Model guide

## What a model lets you study

Use a `FiniteControlModel` to ask how a prefix-coded quantum process evolves,
what unconditional output its terminating programs produce, and whether the
description length of each action accounts for its reference gain. This makes
it possible to study state preparation, reset, feedback, and looping control
under one explicit cost convention.

A model contribution is scientifically useful when it asks a new structural
question: Which resource is doing the target-shortening work? Does the declared
reference absorb the background already supplied? Can the program prior remain
uniformly dominated across a scale family? Which local action needs more code
or fuel? The package answers the finite-instance certificate part of these
questions. The corresponding RCC analysis supplies the physical interpretation,
faithful transcription, and family-uniform arguments.

Formally, the model is a finite prefix-coded syntax graph whose actions carry
total quantum channels between transient control blocks or into a common
halting output space.

The syntax code supplies the program weight. Kraus operators supply the physical
Born weight. The package keeps those two sources of weight separate.

## Research workflow

1. Choose the reference state and transient control spaces.
2. Declare the available actions, physical channels, and prefix codewords.
3. Run the model audit to obtain the terminating output and fixed-model checks.
4. Inspect which actions produce large reference gains.
5. Compare the current code lengths with the gain–cost condition.
6. Test a supplied certificate or the suggested sufficient re-encoding.

## A complete two-action model

Install the package from the repository root using the
[quick-start instructions](../README.md#quick-start), then run this example as a
script or notebook cell.

This model either continues with the identity channel or halts with the identity
channel. Both codewords have length one, so each syntax action receives weight
`1/2`.

```python
import numpy as np

from rcc_refcert import Action, FiniteControlModel, audit_model, require_valid_model

identity = np.eye(2, dtype=complex)
reference = identity / 2

model = FiniteControlModel(
    syntax_states=("s",),
    control_dims={"q": 2},
    actions_by_syntax={
        "s": (
            Action(
                name="continue",
                codeword="1",
                successor="s",
                continue_kraus={("q", "q"): (identity,)},
            ),
            Action(
                name="halt",
                codeword="0",
                successor=None,
                halt_kraus={"q": (identity,)},
            ),
        )
    },
    start_syntax="s",
    initial_blocks={"q": reference},
    output_dim=2,
    reference_state=reference,
    name="identity-or-halt",
)

require_valid_model(model)
result = audit_model(model)

print(result.realization_outcome.value)
print(result.fixed_model_domination.constant)
```

The model prints `pass` and a domination constant numerically equal to `1`.

## Construction rules

### Syntax and codewords

Every syntax state declares a nonempty set of actions. Its codewords must be
nonempty binary words and prefix-free within that state. `successor=None` marks
a halt action; any other successor must name a declared syntax state.

### Physical channels

Kraus matrices are the unweighted physical channel. For every source control
block, each action must provide a complete trace-preserving map:

- a continuing action maps that source into one or more declared target control
  blocks;
- a halt action maps that source into the common output space.

Rectangular Kraus matrices are allowed. Their shapes follow the declared source
and target dimensions.

### Initial and reference states

`initial_blocks` are placed at `start_syntax` and must have total trace one. The
reference state is a full-rank density matrix on the declared output support.
If the mathematical reference is rank-deficient in a larger ambient space,
reduce the model to its support before construction.

## Audit workflow

`audit_model` performs the model-level chain:

1. validates the structural and channel contract;
2. compares path enumeration with block-map realization through `max_depth`;
3. computes the partial semidensity through `max_transient_steps` continuation
   steps;
4. attempts the full-space linear fixed point;
5. computes H.34 when that linear branch is available.

```python
result = audit_model(
    model,
    max_depth=8,
    max_transient_steps=16,
    tol=1e-10,
)
```

The least fixed-point semantics is primary. At the spectral-radius boundary,
`linear_fixed_point_outcome` and `domination_outcome` are `not_applicable` and
`inconclusive`, respectively. `truncated_output` remains available as a
finite-depth diagnostic, while H.34 awaits the completed semidensity.

## Supplying proof objects

The verifier functions accept explicit mathematical candidates:

- `verify_bellman_choi(model, certificate)` for H.3;
- `verify_reference_potential(model, certificate)` for H.4;
- `analyze_reference_gain_cost(model, theta)` for H.6.

Each function checks an explicit mathematical candidate. Certificate candidates
may be derived analytically or produced by a separate optimizer; the bundled
factories in `rcc_refcert.examples` show proof objects for both the one-block and
multiblock cases.

Inspect each report's `outcome` before using its `constant`. For H.3 and H.4,
the returned constant includes the numerical correction budget, while
`candidate_constant` retains the original proposal. A local residual check can
pass yet leave the final error budget inconclusive, particularly for slowly
halting dynamics. Such a report has `constant=None`; its checks explain the
unresolved correction.

## Turning a model into a reference case

`audit_case(get_case(NAME))` is the stable case-level interface. Bundled cases
pair a model with its proof-object factories, paper references, and expected
outcomes. A new public case earns its place by exposing a distinct mathematical
mechanism or convention risk.

Before adding a case, run the model directly, add one controlled negative test
for every convention it is meant to protect, and decide whether a failed check
is an error, an expected sufficient-route failure, or a genuine boundary.
