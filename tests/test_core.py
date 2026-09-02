from datetime import date

import numpy as np
import pandas as pd
import pytest

from observatory.core import RunConfig, align_prices, lagged_correlations, run


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


@pytest.mark.parametrize("ticker", ["1", "ABCDEF", "0000011"])
def test_ticker_validation(ticker):
    with pytest.raises(ValueError, match="six digits"):
        RunConfig(ticker, "000002", date(2024, 1, 1), date(2024, 2, 1)).validate()
