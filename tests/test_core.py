from datetime import date
import json
import re

import numpy as np
import pandas as pd
import pytest

from observatory.core import RunConfig, align_prices, event_responses, lagged_correlations, quarter_frame, run
from observatory.context import prepare_context
from observatory.measurements import compute_quarter_measurement, write_measurements
from observatory.reports import generate_reports


class FrozenFixtureProvider:
    provider_id = "fixture"
    provider_version = "1"

    def fetch_qfq(self, ticker, start, end):
        dates = pd.date_range(start, end, freq="B")
        offset = 0.1 if ticker == "000002" else 0
        return pd.DataFrame({"date": dates, "close": np.exp(np.arange(len(dates)) * .01 + offset)})


def test_alignment_is_inner_and_returns_are_logarithmic():
    a = pd.DataFrame({"date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]), "close": [10, 11, 12]})
    b = pd.DataFrame({"date": pd.to_datetime(["2024-01-03", "2024-01-04", "2024-01-05"]), "close": [20, 18, 19]})
    with pytest.raises(ValueError, match="three common"):
        align_prices(a, b, "000001", "000002")


def test_lag_definition_detects_shift():
    frame = pd.DataFrame({"log_return_000001": [np.nan, 1, 2, 3, 4, 5], "log_return_000002": [np.nan, np.nan, 1, 2, 3, 4]})
    result = lagged_correlations(frame, "000001", "000002")
    assert result.loc[result.lag == -1, "correlation"].iloc[0] == pytest.approx(1)


def test_reproducible_bundle_and_immutable_cache(tmp_path):
    config = RunConfig("000001", "000002", date(2024, 1, 1), date(2024, 2, 1), .03, 3)
    cache = tmp_path / "cache"
    first = run(config, FrozenFixtureProvider(), cache, tmp_path / "run1")
    second = run(config, FrozenFixtureProvider(), cache, tmp_path / "run2", offline=True)
    assert first.exists() and second.exists()
    assert len(list(cache.glob("*.csv"))) == 2
    assert (tmp_path / "run1" / "05_event_centered_response.png").exists()
    assert (tmp_path / "run1" / "quarters" / "2024Q1" / "05_event_centered_response.png").exists()
    assert (tmp_path / "run1" / "quarterly_summary.csv").exists()
    assert (tmp_path / "run1" / "reports" / "index.html").exists()
    assert (tmp_path / "run1" / "reports" / "2024_YTD_pair_observation.html").exists()
    manifest = json.loads(first.read_text(encoding="utf-8"))
    semantics = manifest["quarter_slicing"]
    assert semantics["returns"] == "computed once on full aligned series before slicing"
    assert "may cross quarter boundaries" in semantics["event_response_windows"]
    assert semantics["parameters_reestimated"] is False
    machine = json.loads((tmp_path / "run1" / "machine_measurements.json").read_text(encoding="utf-8"))
    assert machine["fixed_definitions"] == {"event_threshold": 0.03, "event_window": [-5, 5], "lag_range": [-5, 5], "return": "daily log return"}
    assert set(machine["observation_contracts"]) == {"return_overlay", "normalized_price", "return_scatter", "lag_correlation", "event_response"}
    contract_fields = {"question", "definition", "inputs", "calculation", "rule", "interpretation", "assumptions", "failure_modes", "does_not_imply", "related_chart", "research_relevance"}
    assert all(set(contract) == contract_fields for contract in machine["observation_contracts"].values())
    assert machine["records"][0]["inputs"]["lag_profile"].endswith("lagged_correlations.csv")


def test_quarter_slice_preserves_full_series_returns_and_rebases_normalization():
    dates = pd.to_datetime(["2024-03-29", "2024-04-01", "2024-04-02"])
    a = pd.DataFrame({"date": dates, "close": [10.0, 20.0, 22.0]})
    b = pd.DataFrame({"date": dates, "close": [5.0, 8.0, 8.8]})
    frame = align_prices(a, b, "000001", "000002")
    quarterly = quarter_frame(frame, pd.Period("2024Q2"), "000001", "000002")
    assert len(quarterly) == 2
    assert quarterly.loc[0, "log_return_000001"] == pytest.approx(np.log(20 / 10))
    assert quarterly.loc[0, "normalized_000001"] == 1
    assert quarterly.loc[1, "log_return_000001"] == pytest.approx(np.log(22 / 20))


def test_quarter_event_membership_uses_full_cross_boundary_window():
    dates = pd.bdate_range("2024-03-25", periods=15)
    frame = pd.DataFrame({
        "date": dates,
        "log_return_000001": np.zeros(len(dates)),
        "log_return_000002": np.arange(len(dates), dtype=float) / 1000,
    })
    event_position = dates.get_loc(pd.Timestamp("2024-04-01"))
    frame.loc[event_position, "log_return_000001"] = 0.04
    responses = event_responses(frame, "000001", "000002", 0.03, 5, pd.Period("2024Q2"))
    assert responses.event_date.nunique() == 1
    assert responses.event_date.iloc[0] == pd.Timestamp("2024-04-01")
    assert set(responses.offset) == set(range(-5, 6))
    assert responses.loc[responses.offset == -5, "response_cumulative_log_return"].notna().all()


def test_annual_reports_use_existing_images_and_valid_relative_paths(tmp_path):
    output = tmp_path / "output"
    output.mkdir(parents=True)
    rows = []
    measurements = []
    for year in range(2023, 2027):
        final_quarter = 3 if year == 2026 else 4
        for number in range(1, final_quarter + 1):
            quarter = f"{year}Q{number}"
            quarter_dir = output / "quarters" / quarter
            quarter_dir.mkdir(parents=True)
            pd.DataFrame({"lag": range(-5, 6), "correlation": [0.1] * 11, "sample_size": [50] * 11}).to_csv(quarter_dir / "lagged_correlations.csv", index=False)
            pd.DataFrame(columns=["source", "response", "event_date", "offset", "response_cumulative_log_return"]).to_csv(quarter_dir / "event_responses.csv", index=False)
            frame = pd.DataFrame({"normalized_600031": np.linspace(1, 1.1, 60), "normalized_000425": np.linspace(1, .9, 60), "log_return_600031": np.linspace(-.02, .02, 60), "log_return_000425": np.linspace(-.01, .03, 60)})
            measurements.append(compute_quarter_measurement(frame, quarter_dir, "600031", "000425", quarter))
            for filename in ("01_return_overlay.png", "02_normalized_price.png", "03_return_scatter.png", "04_lagged_cross_correlation.png", "05_event_centered_response.png"):
                (quarter_dir / filename).write_bytes(b"existing-full-resolution-image")
            rows.append({"quarter": quarter, "common_observations": 60, "paired_returns": 60, "qualifying_events_600031": 2, "qualifying_events_000425": 3, "status": "generated"})
    pd.DataFrame(rows).to_csv(output / "quarterly_summary.csv", index=False)
    write_measurements(output, measurements)
    for filename in ("01_return_overlay.png", "02_normalized_price.png", "03_return_scatter.png", "04_lagged_cross_correlation.png", "05_event_centered_response.png"):
        (output / filename).write_bytes(b"existing-full-resolution-image")
    config = RunConfig("600031", "000425", date(2023, 1, 1), date(2026, 8, 31))
    reports = generate_reports(output, config, "fixture", "1")
    assert {path.name for path in reports} == {"index.html", "2023_pair_observation.html", "2024_pair_observation.html", "2025_pair_observation.html", "2026_YTD_pair_observation.html"}
    ytd = (output / "reports" / "2026_YTD_pair_observation.html").read_text(encoding="utf-8")
    assert "2026 YTD — INCOMPLETE CALENDAR YEAR" in ytd
    assert "2026Q4" not in ytd
    assert "Machine Observation" in ytd
    assert "Human Observation" in ytd
    assert "Human Hypothesis" in ytd
    assert "Alternative Explanation / Counter-Hypothesis" in ytd
    assert "observation_text" in ytd and "counter_hypothesis" in ytd and "evidence_needed" in ytd
    assert "No sourced dated events were supplied" in ytd
    invariant_headings = ["Question", "Definition", "Inputs", "Calculation", "Rule", "Interpretation", "Assumptions", "Failure modes", "Does NOT imply", "Related chart", "Research relevance"]
    assert ytd.count('class="chart-context"') == 5
    assert ytd.count("Learn this chart") == 5
    assert ytd.count("Learn machine methodology and interpretation boundaries") == 5
    assert ytd.count('class="machine-comparison"') == 5
    assert ytd.count('class="human-form"') == 15
    assert ytd.count('class="quarter-detail"') == 15
    for heading in invariant_headings:
        assert ytd.count(f"<h5>{heading}</h5>") == 5
    first_block = ytd[ytd.index('id="return_overlay"'):ytd.index('id="normalized_price"')]
    disclosure = first_block.index("Learn this chart")
    assert first_block.index('class="chart-context"') < first_block.index('class="plot-grid"') < first_block.index('class="machine-comparison"') < first_block.index('class="human-section"') < disclosure
    assert "What this chart shows" not in first_block[:disclosure]
    assert ytd.index("Daily log-return overlay") < ytd.index("Quarterly normalized-price path") < ytd.index("Contemporaneous return scatter") < ytd.index("Lagged cross-correlation") < ytd.index("Event-centered response")
    machine_before = (output / "machine_measurements.json").read_bytes()
    for report in reports:
        content = report.read_text(encoding="utf-8")
        for link in re.findall(r'(?:href|src)="([^"]+)"', content):
            if link.startswith("#"):
                assert f'id="{link[1:]}"' in content, f"broken anchor in {report.name}: {link}"
                continue
            assert (report.parent / link).resolve().exists(), f"broken link in {report.name}: {link}"
    assert (output / "machine_measurements.json").read_bytes() == machine_before


def test_context_requires_provenance_and_is_copied(tmp_path):
    output = tmp_path / "output"; output.mkdir()
    valid = tmp_path / "events.csv"
    pd.DataFrame([{"date": "2024-01-10", "quarter": "2024Q1", "event_type": "industry_policy", "scope": "industry", "description": "Sourced event", "published_at": "2024-01-10T08:00:00Z", "retrieved_at": "2024-02-01T00:00:00Z", "provider": "Publisher API", "source": "Publisher", "source_url": "https://example.test/event", "provenance_id": "event-1"}]).to_csv(valid, index=False)
    artifacts = prepare_context(output, None, valid)
    assert artifacts == [output / "context" / "event_context.csv"]
    invalid = tmp_path / "invalid.csv"
    pd.DataFrame([{"date": "2024-01-10", "quarter": "2024Q1", "event_type": "industry_policy", "scope": "industry", "description": "Unsourced", "published_at": "2024-01-10T08:00:00Z", "retrieved_at": "2024-02-01T00:00:00Z", "provider": "", "source": "", "source_url": "", "provenance_id": ""}]).to_csv(invalid, index=False)
    with pytest.raises(ValueError, match="provenance_id"):
        prepare_context(tmp_path / "other", None, invalid)


def test_company_context_rejects_information_available_after_observation_period(tmp_path):
    company = tmp_path / "company.csv"
    pd.DataFrame([{"quarter": "2024Q1", "ticker": "600031", "group": "operating_fundamental_state", "attribute": "revenue", "value": 100, "unit": "CNY", "effective_date": "2023-12-31", "available_at": "2024-04-30T00:00:00Z", "retrieved_at": "2024-05-01T00:00:00Z", "provider": "Filing provider", "source": "Annual report", "source_url": "https://example.test/filing", "provenance_id": "filing-1"}]).to_csv(company, index=False)
    with pytest.raises(ValueError, match="not publicly available"):
        prepare_context(tmp_path / "output", company, None)


@pytest.mark.parametrize("ticker", ["1", "ABCDEF", "0000011"])
def test_ticker_validation(ticker):
    with pytest.raises(ValueError, match="six digits"):
        RunConfig(ticker, "000002", date(2024, 1, 1), date(2024, 2, 1)).validate()
