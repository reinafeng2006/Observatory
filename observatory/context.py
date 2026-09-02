from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

COMPANY_REQUIRED = {"quarter", "ticker", "group", "attribute", "value", "unit", "effective_date", "available_at", "retrieved_at", "provider", "source", "source_url", "provenance_id"}
EVENT_REQUIRED = {"date", "quarter", "event_type", "scope", "description", "published_at", "retrieved_at", "provider", "source", "source_url", "provenance_id"}


def _validate(path: Path, required: set[str], kind: str) -> None:
    frame = pd.read_csv(path)
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{kind} context lacks required columns: {sorted(missing)}")
    provenance_columns = ["provider", "source", "source_url", "provenance_id"]
    provenance = frame[provenance_columns].fillna("").astype(str).apply(lambda column: column.str.strip())
    if (provenance == "").any(axis=None):
        raise ValueError(f"Every {kind} context row must carry provider, source, source_url, and provenance_id")
    availability_column = "available_at" if kind == "company" else "published_at"
    availability = pd.to_datetime(frame[availability_column], utc=True, errors="raise")
    retrieved = pd.to_datetime(frame["retrieved_at"], utc=True, errors="raise")
    quarter_ends = pd.PeriodIndex(frame["quarter"].astype(str), freq="Q").end_time.tz_localize("UTC")
    if (availability > quarter_ends).any():
        raise ValueError(f"{kind} context is not publicly available by the end of its observation quarter")
    if (retrieved < availability).any():
        raise ValueError(f"{kind} context retrieval cannot precede public availability")
    if kind == "event":
        event_quarters = pd.to_datetime(frame["date"], errors="raise").dt.to_period("Q").astype(str)
        if not event_quarters.equals(frame["quarter"].astype(str)):
            raise ValueError("event date must belong to the declared quarter")


def prepare_context(output: Path, company_path: Path | None, event_path: Path | None) -> list[Path]:
    artifacts: list[Path] = []
    if company_path is None and event_path is None:
        return artifacts
    context_dir = output / "context"
    context_dir.mkdir(parents=True)
    if company_path is not None:
        _validate(company_path, COMPANY_REQUIRED, "company")
        destination = context_dir / "company_context.csv"
        shutil.copyfile(company_path, destination); artifacts.append(destination)
    if event_path is not None:
        _validate(event_path, EVENT_REQUIRED, "event")
        destination = context_dir / "event_context.csv"
        shutil.copyfile(event_path, destination); artifacts.append(destination)
    return artifacts
