# Human Research Notes

The default researcher input is one open-ended **Your Note** text box per
chart-quarter or quarter-level target. The saved `raw_note` is authoritative
and preserved verbatim. A researcher may freely mix observations,
interpretations, mechanisms, alternatives, questions, context ideas, and
evidence needs without separating them before saving.

Legacy structured records continue to preserve their original Human
Observation, optional tags, Hypothesis, Counter-Hypothesis / Alternative
Explanation, Evidence Needed, Confidence, timestamps, authorship, revision, and
provenance. These fields are carried forward losslessly when an old record is
edited; they are not merged into or replaced by `raw_note`. The original JSONL
revision line remains unchanged.

The loopback-only local application persists an append-only JSONL revision log
outside generated report and machine artifacts. Multiple notes may share a
target. Editing appends a revision with the same observation ID and original
`created_at`; `updated_at`, revision, and derived-analysis version advance.

The server, not the browser, binds provenance: pair, quarter, target scope,
chart path/hash, machine-measurement path/hash/version, report path/hash/version,
manifest/config identity, raw-cache paths/hashes, provider, and Observatory
version/Git commit. Static HTML remains readable without the server, but cannot
claim that a draft was persisted.

## Machine reading of a note

After save, deterministic sentence and keyword rules create a secondary,
versioned `derived_analysis`. Extracted statements are categorized as
verifiable/observational, interpretation/hypothesis, external context requiring
evidence, or question/evidence need. Where a defined mapping exists, the card
links exact bound descriptive measurements and artifact hashes. Strong human
wording such as `always`, `causes`, `predicts`, `leads`, or `follows` remains
human wording and receives an explicit interpretation-boundary warning.

The machine card is collapsed by default. It exposes extracted wording,
classification, calibrated evidence status, measurement/formula, deterministic
or semantic basis, limitation, prohibited stronger claim, and unresolved
evidence. It does not expose hidden reasoning. Machine-derived retrieval
metadata is not a label, model target, pair classification, strategy input, or
signal.

Notes and derived analysis cannot mutate or feed machine metrics, scoring,
selection, signals, labels, strategy paths, or confirmatory evidence. This is a
pedagogical claim-discipline layer; Observatory still stops at hypothesis
discovery.

Schema: `schemas/human_observation.schema.json`.
