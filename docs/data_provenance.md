# Data and Provenance

Every applicable datum records source, provider, retrieval timestamp, effective
date, publication/availability time, adjustment convention, transformation
rule, and cache/provenance identity. Raw provider responses are immutable;
derived artifacts are hash-tracked in the run manifest.

## Point-in-time rule

A context record may appear in period `P` only when `available_at` is no later
than the end of `P`. Effective/as-of dates do not substitute for public
availability. A later filing cannot contextualize an earlier period. Retrieval
time records collection, not historical availability.

Events require factual description, scope, event date, publication time,
provider/source, source URL, retrieval time, and provenance identifier. Event
coincidence is not causal attribution.

Missing or unreliable fields remain unavailable; they are not inferred.
