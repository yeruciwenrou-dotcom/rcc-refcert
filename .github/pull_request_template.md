## Purpose

What scientific question, audit risk, interface need, or reader problem does
this change address?

## RCC layer

- [ ] Finite numerical input or realization
- [ ] Fixed-model semidensity or certificate
- [ ] Model-family or uniform-scaling argument
- [ ] Theorem-facing interpretation
- [ ] Documentation or public interface only

Explain the highest claim layer affected and identify its accompanying analytic
or physical obligations.

## Evidence

Describe the positive, negative, or boundary case that protects the change. For
convention changes, include the regression that catches the most plausible
incorrect implementation.

## Verification

- [ ] Ruff check and format pass
- [ ] Tests pass with warnings treated as errors
- [ ] `rcc-refcert reproduce --check` passes
- [ ] Distribution build passes
- [ ] Frozen reference files are unchanged, or their intentional change is explained

## RCC paper and documentation map

List the affected RCC sections or equations and the user-facing documents that
were updated.
