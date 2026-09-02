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

MACHINE_OBSERVATION_CONTRACTS = {
    "return_overlay": {
        "question": "How large and how often are the two stocks' daily adjusted moves in the quarter?",
        "definition": "Daily log returns, sample volatility, volatility ratio B/A, and same-sign return share.",
        "inputs": "Quarter-dated paired daily log returns computed once on the full aligned qfq-close series.",
        "calculation": "Drop rows missing either return; compute ddof=1 standard deviations, B/A ratio, and equal-sign count divided by paired count.",
        "rule": "Direct numerical display only; no categorical threshold is applied.",
        "interpretation": "The values describe relative movement magnitude and how often return directions coincide.",
        "assumptions": "Aligned dates are comparable; qfq returns are suitable for retrospective description; valid rows represent the quarter sample.",
        "failure_modes": "Small samples, outliers, volatility clustering, suspensions, stale prices, and later qfq revisions can distort comparison.",
        "does_not_imply": "Common causation, stable dependence, predictability, pair quality, or a trading opportunity.",
        "related_chart": "Daily log-return overlay.",
        "research_relevance": "Magnitude mismatch or changing co-movement can motivate questions about common versus stock-specific price discovery.",
    },
    "normalized_price": {
        "question": "How did the two quarter-local price paths evolve relative to their own starting values?",
        "definition": "Quarter-local normalized price N_i(t)=P_i(t)/P_i(first common quarter date).",
        "inputs": "Quarter-dated qfq closes on common trading dates.",
        "calculation": "Divide each stock's qfq close by its first common close in the quarter; display final normalized levels.",
        "rule": "Direct numerical display only; no convergence category is assigned.",
        "interpretation": "The path shows relative cumulative movement from a common visual baseline of 1.",
        "assumptions": "The first common close is an appropriate descriptive baseline and qfq revisions are acceptable for retrospective exploration.",
        "failure_modes": "Endpoint choice, quarter rebasing, corporate-action revisions, and a single extreme start date can change the apparent gap.",
        "does_not_imply": "Mean reversion, catch-up, equilibrium, cointegration, or tradability.",
        "related_chart": "Quarterly normalized-price path.",
        "research_relevance": "Persistent or changing relative paths can motivate explicit hypotheses and evidence requests without validating them.",
    },
    "return_scatter": {
        "question": "What is the contemporaneous descriptive relation between paired daily returns?",
        "definition": "Pearson/Spearman correlation, same-sign share, and OLS r_B=alpha+beta*r_A+epsilon with R².",
        "inputs": "Quarter-dated paired daily log returns with both values present.",
        "calculation": "Compute correlations and average-rank correlation; fit intercept and slope by least squares; compute R² from SSE/SST.",
        "rule": "Direct numerical display only; beta is not labeled a hedge ratio.",
        "interpretation": "The measurements summarize linear/rank co-movement, directional agreement, and cross-sectional dispersion around a fitted line.",
        "assumptions": "Paired rows are comparable and descriptive OLS is numerically defined; no distributional inference is made.",
        "failure_modes": "Outliers, nonlinear structure, heteroskedasticity, serial dependence, small samples, and regime mixtures can mislead.",
        "does_not_imply": "Causality, stable beta, hedge effectiveness, predictability, or statistical significance.",
        "related_chart": "Contemporaneous return scatter.",
        "research_relevance": "Changes in descriptive co-movement can identify periods requiring company, sector, liquidity, or event context.",
    },
    "lag_correlation": {
        "question": "How does descriptive return correlation vary across the fixed lag profile?",
        "definition": "corr(r_A(t),r_B(t+lag)) for every integer lag -5 through +5.",
        "inputs": "Quarter-dated paired log returns; each lag uses its reported valid shifted-pair count.",
        "calculation": "Shift B within the quarter, drop incomplete pairs, compute Pearson correlation, then locate signed maxima in negative and positive lag subsets.",
        "rule": "Evaluate exact rules: lag-0 equals the full-profile maximum; positive-lag peak exceeds negative-lag peak.",
        "interpretation": "The profile describes where sample correlations are numerically largest under the fixed sign convention.",
        "assumptions": "The lag convention is understood; shifted samples are comparable; descriptive correlations are sufficiently defined.",
        "failure_modes": "Serial correlation, common multi-session shocks, unequal liquidity, sample loss at lags, multiple testing intuition, and small samples can create off-zero peaks.",
        "does_not_imply": "That A leads B, B will catch up, predictive power, causal timing, or a trade.",
        "related_chart": "Lagged cross-correlation.",
        "research_relevance": "Profile changes can motivate falsifiable timing questions for a separate formal research design.",
    },
    "event_response": {
        "question": "What response-return paths are observed around fixed large-return event dates?",
        "definition": "For source dates with |log return|>=3%, cumulative response log return at offsets -5 through +5 common sessions.",
        "inputs": "Full aligned return series, event dates assigned to the quarter, and only complete fixed windows.",
        "calculation": "Select qualifying source dates, extract full-series windows, and compute per-offset event counts, means, and medians.",
        "rule": "Direct summaries only; no response threshold or predictive category is applied.",
        "interpretation": "The values describe the center and sample size of observed response paths around qualifying dates.",
        "assumptions": "The fixed event definition is useful descriptively and complete-window selection does not represent all possible events.",
        "failure_modes": "Few events, overlapping windows, common shocks, asymmetric event signs, outliers, and selection on large moves can mislead.",
        "does_not_imply": "Causal response, repeatability, predictability, mean reversion, or trading profitability.",
        "related_chart": "Event-centered response.",
        "research_relevance": "Event-path dispersion can identify dated cases needing sourced company or market context and competing explanations.",
    },
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
        "observation_contracts": MACHINE_OBSERVATION_CONTRACTS,
        "fixed_definitions": {"event_threshold": 0.03, "event_window": [-5, 5], "lag_range": [-5, 5], "return": "daily log return"},
        "prohibited_uses": ["causal lead-lag claims", "predictability claims", "mean-reversion claims", "pair quality", "trading opportunity", "training labels", "formal classifications"],
        "records": records,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
