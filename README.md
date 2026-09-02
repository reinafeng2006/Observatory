# Observatory

Observatory is a reusable, human-in-the-loop **discovery environment** for
statistical-arbitrage hypothesis discovery. It organizes market behavior, pair
relationships, company/market context, dated events, deterministic descriptive
facts, visual comparisons, and human research notes into a reproducible
workspace. Its governing principle is: **maximize observability, not
conclusions**.

> Observatory should maximize observability, not conclusions.

Observatory stops at hypothesis discovery. It does **not** backtest, optimize,
rank pair profitability, generate signals, validate alpha, infer causality or
predictability, label pairs good/bad, select strategies, or silently promote
exploratory notes into labels or confirmatory evidence. Hypothesis packages may
only be exported as inputs to a separate formal research pipeline. Every chart
is labelled `EXPLORATORY — NOT A TRADING SIGNAL`.

The boundaries are intentionally distinct:

> Machine Measurement != Human Observation
>
> Human Observation != Hypothesis
>
> Hypothesis != Validated Relationship
>
> Validated Relationship != Trading Opportunity

See [Product Charter](docs/product_charter.md) and
[Architecture](docs/architecture.md) for the frozen v1 contract.

## Install and run

```bash
python -m pip install -e .
observatory-pair 600519 000858 --start 2023-01-01 --end 2024-12-31 --output runs/demo
```

Ticker inputs are six digits. Raw provider responses are cached immutably under
`cache/raw/`; rerunning the same request uses the cached CSV. A run directory
contains the aligned observations, five fixed PNG plots, and `manifest.json`
with inputs, fixed method settings, dependency versions, timestamps, provider
identity, cache provenance, and SHA-256 hashes for every artifact.

The full-period outputs are always retained. The same five plots are also
generated for every calendar quarter in the request under `quarters/YYYYQn/`.
Log returns are computed once on the full aligned common-date series, so a
quarter's first trading observation retains its return from the preceding
common observation when one is available. Normalized prices rebase within each
quarter. Lagged correlations use only observations dated in that quarter.
Events belong to the quarter of their event date, while their fixed ±5-session
response windows come from the full aligned series and may cross quarter
boundaries. Parameters are never re-estimated. Plot labels state the quarter,
common-observation count, relevant descriptive sample size, and qualifying
complete-window event counts. `quarterly_summary.csv` provides the corresponding
descriptive inventory.

## Annual visual-observation reports

After the quarterly artifacts are written, Observatory creates `reports/` with
an index and one wide HTML comparison matrix for each complete calendar year.
An incomplete final year is explicitly named and labelled `YTD — INCOMPLETE
CALENDAR YEAR`, and includes only quarters present in the requested sample.
Columns are quarters and the five fixed plot types are rows. The HTML links
directly to the existing full-resolution quarterly PNGs; it does not regenerate
images or recompute statistics. Empty researcher-note prompts are provided for
manual observation only.

## Human and machine observation layers

Annual reports visibly separate four layers: deterministic Machine
Measurement, Human Observation, Human Hypothesis, and Alternative Explanation /
Counter-Hypothesis. Chart explanations and traditional visual prompts guide
attention without pre-filling any field or forcing a category. Optional tags
are selected only by the researcher.

Human notes are stored as structured browser-local records and can be exported
or imported as JSON. Each record contains pair, period, chart type, observation,
tags, hypothesis, alternative explanation, optional confidence, and timestamp.
They are exploratory notes only and never become training labels, formal
classifications, pair-selection inputs, or trading signals automatically. The
record contract is documented in `schemas/human_observation.schema.json`.

`machine_measurements.json` contains fixed formula definitions, input artifact
paths, sample sizes, per-quarter values, full lag profiles, event-aligned
summaries, and deterministic rule results. These are descriptive measurements,
not LLM visual interpretations or claims about causality, predictability,
mean-reversion, pair quality, or trading opportunity.

Optional sourced context can be supplied with `--company-context` and
`--event-context`. Company rows require quarter/ticker/group/attribute/value,
effective and availability dates, retrieval time, provider, source URL, and a
provenance ID. Event rows require date/quarter/type/scope/description,
publication and retrieval times, provider, source URL, and a provenance ID.
Records unavailable by the observation quarter are rejected. If no context is
supplied, reports say so explicitly and invent nothing. See the schemas and
[Data Provenance](docs/data_provenance.md) for exact contracts.

Use `--offline` to require an existing cache entry. The event view uses the
fixed default definition `abs(log return) >= 0.03` and a fixed ±5 common-session
window; these can be changed explicitly for visual exploration and are recorded
in the manifest.

## Development

```bash
python -m pip install -e .[test]
pytest
```

The package is isolated from any future production research pipeline. Its
provider protocol permits deterministic test fixtures without network access.
