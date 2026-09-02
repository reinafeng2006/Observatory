from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

FORMULAS = {
    "pearson_return_correlation": "Pearson correlation of paired daily log returns in the quarter.",
    "spearman_return_correlation": "Pearson correlation of average ranks of paired daily log returns in the quarter.",
    "same_sign_return_share": "count(sign(r_a) == sign(r_b)) / paired-return count; zero has sign 0.",
    "volatility": "Sample standard deviation (ddof=1) of each stock's daily log returns dated in the quarter.",
    "volatility_ratio_b_over_a": "volatility_b / volatility_a.",
    "linear_response": "OLS with intercept: r_b = intercept + slope * r_a; R² = 1 - SSE/SST.",
    "lag_correlation": "Pearson correlation of r_a(t) with r_b(t+lag), using only quarter-dated return rows after shifting within the quarter.",
    "lag_peak": "Maximum signed correlation within the stated fixed lag subset; ties use the lowest lag.",
    "event_count": "Distinct qualifying event dates with a complete fixed ±5-common-session window.",
    "event_aligned_response": "Across qualifying events, mean and median cumulative response log return at each fixed offset; windows come from the full aligned series.",
    "normalized_end": "Last quarter close divided by first quarter common close.",
}


def _number(value: float | int) -> float | int | None:
    return None if pd.isna(value) or np.isinf(value) else float(value)


def compute_quarter_measurement(frame: pd.DataFrame, quarter_dir: Path, ticker_a: str, ticker_b: str, quarter: str) -> dict:
    columns = [f"log_return_{ticker_a}", f"log_return_{ticker_b}"]
    paired = frame[columns].dropna()
    ra, rb = paired.iloc[:, 0], paired.iloc[:, 1]
    pearson = ra.corr(rb, method="pearson")
    spearman = ra.rank(method="average").corr(rb.rank(method="average"), method="pearson")
    same_sign = (np.sign(ra) == np.sign(rb)).mean() if len(paired) else np.nan
    vol_a, vol_b = ra.std(ddof=1), rb.std(ddof=1)
    ratio = vol_b / vol_a if vol_a and not pd.isna(vol_a) else np.nan
    if len(paired) >= 2 and ra.var(ddof=0) > 0:
        slope, intercept = np.polyfit(ra.to_numpy(), rb.to_numpy(), 1)
        fitted = intercept + slope * ra.to_numpy()
        sst = ((rb.to_numpy() - rb.mean()) ** 2).sum()
        r_squared = 1 - ((rb.to_numpy() - fitted) ** 2).sum() / sst if sst > 0 else np.nan
    else:
        slope = intercept = r_squared = np.nan
    lags = pd.read_csv(quarter_dir / "lagged_correlations.csv")
    lag_records = [{"lag": int(row.lag), "correlation": _number(row.correlation), "sample_size": int(row.sample_size)} for row in lags.itertuples()]
    valid_lags = lags.dropna(subset=["correlation"])
    lag0_rows = valid_lags[valid_lags.lag == 0]
    lag0 = lag0_rows.correlation.iloc[0] if not lag0_rows.empty else np.nan
    positive = valid_lags[valid_lags.lag > 0].sort_values(["correlation", "lag"], ascending=[False, True])
    negative = valid_lags[valid_lags.lag < 0].sort_values(["correlation", "lag"], ascending=[False, True])
    positive_peak = None if positive.empty else {"lag": int(positive.iloc[0].lag), "correlation": _number(positive.iloc[0].correlation)}
    negative_peak = None if negative.empty else {"lag": int(negative.iloc[0].lag), "correlation": _number(negative.iloc[0].correlation)}
    statements = []
    if not valid_lags.empty and not pd.isna(lag0):
        maximum = valid_lags.correlation.max()
        statements.append({"rule": "lag0_equals_global_maximum", "result": bool(np.isclose(lag0, maximum)), "statement": f"Lag 0 correlation ({lag0:.6f}) {'equals' if np.isclose(lag0, maximum) else 'does not equal'} the maximum fixed-profile correlation ({maximum:.6f})."})
    if positive_peak and negative_peak:
        pos, neg = positive_peak["correlation"], negative_peak["correlation"]
        relation = "exceeds" if pos > neg else "does not exceed"
        statements.append({"rule": "positive_peak_gt_negative_peak", "result": bool(pos > neg), "statement": f"Positive-lag peak ({pos:.6f} at +{positive_peak['lag']}) {relation} negative-lag peak ({neg:.6f} at {negative_peak['lag']})."})
    events = pd.read_csv(quarter_dir / "event_responses.csv")
    event_summaries = []
    if not events.empty:
        for (source, response), subset in events.groupby(["source", "response"]):
            offsets = subset.groupby("offset").response_cumulative_log_return.agg(["mean", "median", "count"]).reset_index()
            event_summaries.append({
                "source": str(source).zfill(6), "response": str(response).zfill(6),
                "event_count": int(subset.event_date.nunique()),
                "offsets": [{"offset": int(row.offset), "mean": _number(row.mean), "median": _number(row.median), "observation_count": int(row.count)} for row in offsets.itertuples()],
            })
    return {
        "pair": [ticker_a, ticker_b], "period": quarter,
        "inputs": {"aligned_observations": f"quarters/{quarter}/aligned_observations.csv", "lag_profile": f"quarters/{quarter}/lagged_correlations.csv", "event_responses": f"quarters/{quarter}/event_responses.csv"},
        "sample_sizes": {"common_observations": len(frame), "paired_returns": len(paired)},
        "return_measures": {"pearson": _number(pearson), "spearman": _number(spearman), "same_sign_share": _number(same_sign), "volatility": {ticker_a: _number(vol_a), ticker_b: _number(vol_b)}, "volatility_ratio_b_over_a": _number(ratio)},
        "linear_response_b_on_a": {"response": ticker_b, "explanatory": ticker_a, "intercept": _number(intercept), "slope": _number(slope), "r_squared": _number(r_squared)},
        "normalized_end": {ticker_a: _number(frame[f"normalized_{ticker_a}"].iloc[-1]), ticker_b: _number(frame[f"normalized_{ticker_b}"].iloc[-1])},
        "lag_profile": lag_records, "lag0": _number(lag0), "positive_lag_peak": positive_peak, "negative_lag_peak": negative_peak,
        "deterministic_statements": statements, "event_aligned": event_summaries,
    }


def write_measurements(output: Path, records: list[dict]) -> Path:
    path = output / "machine_measurements.json"
    payload = {
        "label": "DETERMINISTIC DESCRIPTIVE MEASUREMENTS — NOT INTERPRETATION",
        "formulas": FORMULAS,
        "fixed_definitions": {"event_threshold": 0.03, "event_window": [-5, 5], "lag_range": [-5, 5], "return": "daily log return"},
        "prohibited_uses": ["causal lead-lag claims", "predictability claims", "mean-reversion claims", "pair quality", "trading opportunity", "training labels", "formal classifications"],
        "records": records,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
