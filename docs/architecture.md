# Architecture v1

## Five first-class layers

1. **Data & Provenance** — immutable/reproducible inputs, timing, transforms.
2. **Company / Market Context** — point-in-time market, operating,
   fundamental, valuation, sector, benchmark, and event descriptors.
3. **Deterministic Machine Observation** — formula-based descriptive measures,
   never LLM visual interpretation.
4. **Visual Observation** — five fixed plots, full-period/quarterly/annual views.
5. **Local Human Note Service** — loopback-only static serving and an append-only
   JSONL revision log stored outside generated artifacts.
5. **Human Research Notes** — distinct observation, tags, hypothesis,
   counter-hypothesis, evidence needed, and confidence.

## Information flow

```text
Data & Provenance
  -> Company / Market Context
  -> Deterministic Machine Observation
  -> Visual Observation
  -> Human Observation
  -> Human Hypothesis
  -> Counter-Hypothesis
  -> Evidence Needed / Follow-up Question
  -> optional export to a separate formal research pipeline
```

Layers cannot write backward. Human notes never mutate data, context, machine
measurements, plots, or production configuration. Export is one-way and does
not validate a hypothesis.

## Implementation sequence

1. Company State + provenance.
2. Deterministic Machine Observation panel.
3. Human observation/hypothesis/counter-hypothesis interface.
4. Industry/market context.
5. Event timeline.
6. Hypothesis export contract and, only after approval, an exporter.

Strategy testing is outside this sequence and outside Observatory.
