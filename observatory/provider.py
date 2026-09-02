from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

import pandas as pd


class PriceProvider(Protocol):
    provider_id: str
    provider_version: str

    def fetch_qfq(self, ticker: str, start: date, end: date) -> pd.DataFrame: ...


@dataclass(frozen=True)
class AkShareQfqProvider:
    """Frozen adapter: endpoint, adjustment, and output schema are fixed here."""

    provider_id: str = "akshare.stock_zh_a_hist.qfq"
    provider_version: str = "1.17.87"

    def fetch_qfq(self, ticker: str, start: date, end: date) -> pd.DataFrame:
        import akshare as ak

        frame = ak.stock_zh_a_hist(
            symbol=ticker,
            period="daily",
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
            adjust="qfq",
        )
        required = {"日期", "收盘"}
        if not required.issubset(frame.columns):
            raise ValueError(f"Provider response lacks columns: {sorted(required - set(frame.columns))}")
        result = frame.rename(columns={"日期": "date", "收盘": "close"})[["date", "close"]].copy()
        result["date"] = pd.to_datetime(result["date"], errors="raise")
        result["close"] = pd.to_numeric(result["close"], errors="raise")
        return result
