# Deterministic Machine Observation

Machine observations are reproducible descriptive measurements, not LLM visual
interpretation. `machine_measurements.json` records formula definitions, input
artifact paths, observation counts, exact values, and deterministic rule
results.

Every report chart uses the same traceability card, in this fixed order:

1. Question
2. Definition
3. Inputs
4. Calculation
5. Intermediate values
6. Rule
7. Machine statement
8. Interpretation
9. Assumptions
10. Failure modes
11. Does NOT imply
12. Related chart
13. Research relevance

The first six fields establish what was measured and how. The machine statement
contains only a direct numeric result or an evaluation of an explicitly stated
deterministic rule. Interpretation is fixed educational context, not a generated
reading of the chart. Prohibited conclusions remain explicit in every card.
The reusable text contracts are also serialized under `observation_contracts`
in `machine_measurements.json`, alongside the exact pair-quarter measurements.

The v1 surface includes co-movement, movement magnitude, descriptive OLS,
fixed-lag structure, fixed event responses, and relative normalized paths.
Lag convention is `corr(r_A(t), r_B(t+lag))`; positive lag is descriptive only.
OLS beta is never named a hedge ratio.

Direct numbers are preferred. No High/Medium/Low categories exist. Statements
such as “lag 0 is the maximum” are allowed only as direct rule evaluations with
the values shown. Lead/lag causality, predictability, mean reversion, pair
quality, and trading opportunity are prohibited interpretations.

Schema: `schemas/machine_observation.schema.json`.
