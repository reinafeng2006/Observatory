# Deterministic Machine Observation

Machine observations are reproducible descriptive measurements, not LLM visual
interpretation. `machine_measurements.json` records formula definitions, input
artifact paths, observation counts, exact values, and deterministic rule
results.

Each chart type has one shared, collapsible traceability card, in this fixed
order:

1. Question
2. Definition
3. Inputs
4. Calculation
5. Rule
6. Interpretation
7. Assumptions
8. Failure modes
9. Does NOT imply
10. Related chart
11. Research relevance

The report's default view presents realized metrics in a metric-by-quarter
comparison table. Sample sizes, missingness, peaks, estimates, event counts, and
deterministic rule results remain quarter-specific. Complete lag and event
intermediate values and provenance paths are available in per-quarter disclosure
controls. Interpretation is fixed educational context, not a generated reading
of the chart. Prohibited conclusions remain explicit in every shared card.
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
