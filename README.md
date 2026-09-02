# Observatory

Observatory is a deliberately small, standalone tool for **exploratory manual
inspection** of two A-share price series. It fetches daily forward-adjusted
(`qfq`) prices from a pinned AkShare adapter, aligns common trading dates,
computes log returns, and writes a reproducible bundle of fixed plots and data.

It does **not** select pairs, classify lead/lag relationships, generate trading
signals, optimize parameters, backtest strategies, or perform formal inference.
Every chart is labelled `EXPLORATORY — NOT A TRADING SIGNAL`.

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
Quarterly transforms use only that quarter's aligned common closes; parameters
are never re-estimated. Plot labels state the quarter, common-observation count,
relevant descriptive sample size, and qualifying complete-window event counts.
`quarterly_summary.csv` provides the corresponding descriptive inventory.

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
