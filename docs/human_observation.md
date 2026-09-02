# Human Research Notes

Each chart-quarter or quarter-level record separates:

- **Human Observation** — directly observed facts, blank by default.
- **Optional tags** — exploratory indexing aids, never labels.
- **Human Hypothesis** — a possible mechanism.
- **Counter-Hypothesis / Alternative Explanation** — competing mechanisms.
- **Evidence Needed** — evidence capable of distinguishing alternatives.
- **Confidence** — optional human judgment, not a statistical probability.

The loopback-only local application persists an append-only JSONL revision log
outside generated report and machine artifacts. Multiple observations may share
a target. Editing appends a revision with the same observation ID and original
`created_at`; `updated_at` and revision number advance.

The server, not the browser, binds provenance: pair, quarter, target scope,
chart path/hash, machine-measurement path/hash/version, report path/hash/version,
manifest/config identity, raw-cache paths/hashes, provider, and Observatory
version/Git commit. Static HTML remains readable without the server, but cannot
claim that a draft was persisted.

Notes cannot mutate or feed machine metrics, scoring, selection, signals,
labels, or confirmatory evidence. Reuse requires a separate recorded research
decision.

Schema: `schemas/human_observation.schema.json`.
