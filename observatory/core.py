from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .provider import PriceProvider

LABEL = "EXPLORATORY — NOT A TRADING SIGNAL"


@dataclass(frozen=True)
class RunConfig:
    ticker_a: str
    ticker_b: str
    start: date
    end: date
    event_threshold: float = 0.03
    event_window: int = 5

    def validate(self) -> None:
        if self.ticker_a == self.ticker_b:
            raise ValueError("Tickers must be different")
        if any(len(x) != 6 or not x.isdigit() for x in (self.ticker_a, self.ticker_b)):
            raise ValueError("Tickers must be six digits")
        if self.start > self.end:
            raise ValueError("start must not be after end")
        if self.event_threshold <= 0 or self.event_window < 1:
            raise ValueError("event threshold and window must be positive")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _cache_path(cache_dir: Path, provider: PriceProvider, ticker: str, start: date, end: date) -> Path:
    key = f"{provider.provider_id}|{provider.provider_version}|{ticker}|{start}|{end}|qfq"
    return cache_dir / f"{ticker}_{hashlib.sha256(key.encode()).hexdigest()[:16]}.csv"


def load_price(provider: PriceProvider, cache_dir: Path, ticker: str, start: date, end: date, offline: bool) -> tuple[pd.DataFrame, dict]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(cache_dir, provider, ticker, start, end)
    hit = path.exists()
    if not hit:
        if offline:
            raise FileNotFoundError(f"No cached raw response for {ticker}: {path}")
        frame = provider.fetch_qfq(ticker, start, end).sort_values("date")
        frame.to_csv(path, index=False, date_format="%Y-%m-%d")
    frame = pd.read_csv(path, parse_dates=["date"])
    if frame.empty or frame["date"].duplicated().any() or (frame["close"] <= 0).any():
        raise ValueError(f"Invalid cached series for {ticker}")
    return frame, {"path": str(path), "sha256": _sha256(path), "cache_hit": hit}


def align_prices(a: pd.DataFrame, b: pd.DataFrame, ticker_a: str, ticker_b: str) -> pd.DataFrame:
    joined = a.merge(b, on="date", how="inner", suffixes=(f"_{ticker_a}", f"_{ticker_b}"))
    joined = joined.sort_values("date").reset_index(drop=True)
    if len(joined) < 3:
        raise ValueError("At least three common trading dates are required")
    for ticker in (ticker_a, ticker_b):
        joined[f"log_return_{ticker}"] = np.log(joined[f"close_{ticker}"]).diff()
        joined[f"normalized_{ticker}"] = joined[f"close_{ticker}"] / joined[f"close_{ticker}"].iloc[0]
    return joined


def lagged_correlations(frame: pd.DataFrame, a: str, b: str) -> pd.DataFrame:
    ra, rb = frame[f"log_return_{a}"], frame[f"log_return_{b}"]
    # At lag k, correlate A(t) with B(t+k); signs are descriptive only.
    values = []
    for lag in range(-5, 6):
        pairs = pd.concat([ra, rb.shift(-lag)], axis=1).dropna()
        correlation = pairs.iloc[:, 0].corr(pairs.iloc[:, 1]) if len(pairs) >= 2 else np.nan
        values.append(correlation)
    return pd.DataFrame({"lag": range(-5, 6), "correlation": values})


def event_responses(frame: pd.DataFrame, source: str, response: str, threshold: float, window: int) -> pd.DataFrame:
    source_returns = frame[f"log_return_{source}"]
    response_returns = frame[f"log_return_{response}"]
    rows: list[dict] = []
    for idx in frame.index[source_returns.abs() >= threshold]:
        if idx - window < 0 or idx + window >= len(frame):
            continue
        for offset in range(-window, window + 1):
            segment = response_returns.iloc[idx : idx + offset + 1] if offset >= 0 else response_returns.iloc[idx + offset : idx + 1]
            value = segment.sum() if offset >= 0 else -segment.iloc[1:].sum()
            rows.append({"source": source, "response": response, "event_date": frame.at[idx, "date"], "offset": offset, "response_cumulative_log_return": value})
    return pd.DataFrame(
        rows,
        columns=["source", "response", "event_date", "offset", "response_cumulative_log_return"],
    )


def _finish(fig: plt.Figure, path: Path) -> None:
    fig.suptitle(LABEL, fontsize=9, color="firebrick")
    fig.tight_layout()
    fig.savefig(path, dpi=150, metadata={"Description": LABEL})
    plt.close(fig)


def write_plots(frame: pd.DataFrame, config: RunConfig, output: Path) -> list[Path]:
    a, b = config.ticker_a, config.ticker_b
    made: list[Path] = []
    fig, ax = plt.subplots(figsize=(10, 4)); ax.plot(frame.date, frame[f"log_return_{a}"], label=a, alpha=.75); ax.plot(frame.date, frame[f"log_return_{b}"], label=b, alpha=.75); ax.set(title="Daily log-return overlay", ylabel="log return"); ax.legend(); made.append(output / "01_return_overlay.png"); _finish(fig, made[-1])
    fig, ax = plt.subplots(figsize=(10, 4)); ax.plot(frame.date, frame[f"normalized_{a}"], label=a); ax.plot(frame.date, frame[f"normalized_{b}"], label=b); ax.axhline(1, color="grey", lw=.7); ax.set(title="Normalized cumulative price", ylabel="first common close = 1"); ax.legend(); made.append(output / "02_normalized_price.png"); _finish(fig, made[-1])
    fig, ax = plt.subplots(figsize=(5, 5)); ax.scatter(frame[f"log_return_{a}"], frame[f"log_return_{b}"], s=12, alpha=.55); ax.axhline(0, color="grey", lw=.7); ax.axvline(0, color="grey", lw=.7); ax.set(title="Contemporaneous daily returns", xlabel=f"{a} log return", ylabel=f"{b} log return"); made.append(output / "03_return_scatter.png"); _finish(fig, made[-1])
    lags = lagged_correlations(frame, a, b); lags.to_csv(output / "lagged_correlations.csv", index=False)
    fig, ax = plt.subplots(figsize=(7, 4)); ax.bar(lags.lag, lags.correlation); ax.axhline(0, color="black", lw=.7); ax.set(title=f"Lagged cross-correlation: {a}(t) vs {b}(t+lag)", xlabel="lag (common trading sessions)", ylabel="Pearson correlation", xticks=range(-5, 6)); made.append(output / "04_lagged_cross_correlation.png"); _finish(fig, made[-1])
    responses = pd.concat([event_responses(frame, a, b, config.event_threshold, config.event_window), event_responses(frame, b, a, config.event_threshold, config.event_window)], ignore_index=True)
    responses.to_csv(output / "event_responses.csv", index=False, date_format="%Y-%m-%d")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    for ax, (source, response) in zip(axes, ((a, b), (b, a))):
        subset = responses[responses.source == source]
        for _, event in subset.groupby("event_date"):
            ax.plot(event.offset, event.response_cumulative_log_return, alpha=.35)
        if not subset.empty:
            mean = subset.groupby("offset").response_cumulative_log_return.mean()
            ax.plot(mean.index, mean, color="black", lw=2, label="event mean (descriptive)"); ax.legend()
        ax.axvline(0, color="firebrick", lw=.8); ax.axhline(0, color="grey", lw=.7); ax.set(title=f"{source} large move → {response} response", xlabel="common-session offset")
    axes[0].set_ylabel("response cumulative log return")
    made.append(output / "05_event_centered_response.png"); _finish(fig, made[-1])
    return made


def run(config: RunConfig, provider: PriceProvider, cache_dir: Path, output: Path, offline: bool = False) -> Path:
    config.validate(); output.mkdir(parents=True, exist_ok=False)
    a, provenance_a = load_price(provider, cache_dir, config.ticker_a, config.start, config.end, offline)
    b, provenance_b = load_price(provider, cache_dir, config.ticker_b, config.start, config.end, offline)
    aligned = align_prices(a, b, config.ticker_a, config.ticker_b)
    aligned_path = output / "aligned_observations.csv"; aligned.to_csv(aligned_path, index=False, date_format="%Y-%m-%d")
    plots = write_plots(aligned, config, output)
    artifacts = [aligned_path, output / "lagged_correlations.csv", output / "event_responses.csv", *plots]
    manifest = {
        "label": LABEL,
        "scope": "manual exploratory pair observation only",
        "config": {**asdict(config), "start": str(config.start), "end": str(config.end), "lags": [-5, 5], "adjustment": "qfq"},
        "provider": {"id": provider.provider_id, "version": provider.provider_version},
        "raw_inputs": {config.ticker_a: provenance_a, config.ticker_b: provenance_b},
        "common_rows": len(aligned), "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__, "matplotlib": matplotlib.__version__},
        "artifacts": {p.name: _sha256(p) for p in artifacts},
        "prohibited_uses": ["automated pair selection", "lead-lag classification", "trading signals", "parameter optimization", "backtesting", "formal inference"],
    }
    path = output / "manifest.json"; path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
