from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

COMPANY_REQUIRED = {"quarter", "ticker", "attribute", "value", "as_of_date", "source", "source_url"}
EVENT_REQUIRED = {"date", "quarter", "scope", "description", "source", "source_url"}


def _validate(path: Path, required: set[str], kind: str) -> None:
    frame = pd.read_csv(path)
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{kind} context lacks required columns: {sorted(missing)}")
    provenance = frame[["source", "source_url"]].fillna("").astype(str).apply(lambda column: column.str.strip())
    if (provenance == "").any(axis=None):
        raise ValueError(f"Every {kind} context row must carry source and source_url provenance")


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
