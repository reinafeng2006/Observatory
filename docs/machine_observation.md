# Deterministic Machine Observation

Machine observations are reproducible descriptive measurements, not LLM visual
interpretation. `machine_measurements.json` records formula definitions, input
artifact paths, observation counts, exact values, and deterministic rule
results.

The v1 surface includes co-movement, movement magnitude, descriptive OLS,
fixed-lag structure, fixed event responses, and relative normalized paths.
Lag convention is `corr(r_A(t), r_B(t+lag))`; positive lag is descriptive only.
OLS beta is never named a hedge ratio.

Direct numbers are preferred. No High/Medium/Low categories exist. Statements
such as “lag 0 is the maximum” are allowed only as direct rule evaluations with
the values shown. Lead/lag causality, predictability, mean reversion, pair
quality, and trading opportunity are prohibited interpretations.

Schema: `schemas/machine_observation.schema.json`.
