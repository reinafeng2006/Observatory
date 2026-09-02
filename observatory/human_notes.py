from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .reports import PLOT_ROWS, REPORT_VERSION

CHART_TYPES = {kind for _, _, kind in PLOT_ROWS}
TAGS = {"synchronous", "possible catch-up", "possible reversal", "persistent divergence", "stock-specific outlier", "stock-specific event", "sector-wide move", "possible regime change", "unclear"}
PROHIBITED_USES = ["training labels", "formal classifications", "pair-selection inputs", "prediction targets", "trading signals", "confirmatory evidence"]
REQUIRED_FIELDS = {
    "observation_id", "revision", "record_type", "pair_id", "company_a", "company_b", "year", "quarter",
    "target_scope", "chart_type", "observation_text", "tags", "hypothesis", "counter_hypothesis",
    "alternative_explanation", "evidence_needed", "confidence", "created_at", "updated_at", "author",
    "provenance", "prohibited_uses",
}
NEW_NOTE_FIELDS = {"raw_note", "derived_analysis"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_timestamp(value: object, field: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO date-time string")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO date-time string") from exc


def validate_record(record: dict) -> None:
    if not REQUIRED_FIELDS.issubset(record) or not set(record).issubset(REQUIRED_FIELDS | NEW_NOTE_FIELDS):
        missing, extra = REQUIRED_FIELDS - set(record), set(record) - (REQUIRED_FIELDS | NEW_NOTE_FIELDS)
        raise ValueError(f"Human observation schema fields mismatch; missing={sorted(missing)}, extra={sorted(extra)}")
    if bool("raw_note" in record) != bool("derived_analysis" in record):
        raise ValueError("raw_note and derived_analysis must be present together")
    if not isinstance(record["observation_id"], str) or not record["observation_id"]:
        raise ValueError("observation_id is required")
    if not isinstance(record["revision"], int) or record["revision"] < 1:
        raise ValueError("revision must be a positive integer")
    if record["record_type"] != "exploratory_human_note":
        raise ValueError("record_type must be exploratory_human_note")
    pair = record["pair_id"].split("/") if isinstance(record["pair_id"], str) else []
    if len(pair) != 2 or any(len(ticker) != 6 or not ticker.isdigit() for ticker in pair):
        raise ValueError("pair_id must contain two six-digit tickers")
    if [record["company_a"], record["company_b"]] != pair:
        raise ValueError("company fields must match pair_id")
    quarter = record["quarter"]
    if not isinstance(quarter, str) or len(quarter) != 6 or quarter[4] != "Q" or quarter[:4].isdigit() is False or quarter[5] not in "1234":
        raise ValueError("quarter must use YYYYQn")
    if record["year"] != int(quarter[:4]):
        raise ValueError("year must match quarter")
    if record["target_scope"] not in {"chart", "quarter"}:
        raise ValueError("target_scope must be chart or quarter")
    if record["target_scope"] == "chart" and record["chart_type"] not in CHART_TYPES:
        raise ValueError("chart observations require a supported chart_type")
    if record["target_scope"] == "quarter" and record["chart_type"] is not None:
        raise ValueError("quarter observations must have chart_type null")
    for field in ("observation_text", "hypothesis", "counter_hypothesis", "alternative_explanation", "evidence_needed", "author"):
        if not isinstance(record[field], str):
            raise ValueError(f"{field} must be a string")
    if record["alternative_explanation"] != record["counter_hypothesis"]:
        raise ValueError("alternative_explanation must mirror counter_hypothesis")
    if not isinstance(record["tags"], list) or len(record["tags"]) != len(set(record["tags"])) or not set(record["tags"]).issubset(TAGS):
        raise ValueError("tags contain unsupported or duplicate values")
    confidence = record["confidence"]
    if confidence is not None and (isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1):
        raise ValueError("confidence must be null or between 0 and 1")
    _parse_timestamp(record["created_at"], "created_at"); _parse_timestamp(record["updated_at"], "updated_at")
    if not isinstance(record["provenance"], dict):
        raise ValueError("provenance must be an object")
    provenance_required = {"chart_artifacts", "machine_measurement", "report_artifact", "report_version", "run_identity", "cache_identity", "provider", "observatory_version", "observatory_git_commit"}
    if not provenance_required.issubset(record["provenance"]):
        raise ValueError("provenance is incomplete")
    if record["prohibited_uses"] != PROHIBITED_USES:
        raise ValueError("prohibited_uses must use the frozen exploratory restrictions")
    if "raw_note" in record:
        if not isinstance(record["raw_note"], str): raise ValueError("raw_note must be a string")
        analysis = record["derived_analysis"]
        if not isinstance(analysis, dict) or not {"analysis_version", "analyzed_at", "extracted_claims", "machine_derived_retrieval_metadata", "analysis_method", "limitations"}.issubset(analysis):
            raise ValueError("derived_analysis is incomplete")
        if not isinstance(analysis["analysis_version"], int) or analysis["analysis_version"] < 1: raise ValueError("analysis_version must be positive")
        _parse_timestamp(analysis["analyzed_at"], "analyzed_at")
        if not isinstance(analysis["extracted_claims"], list): raise ValueError("extracted_claims must be an array")


class HumanObservationStore:
    """Append-only JSONL revisions; latest revision is the editable view."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()

    def _all(self) -> list[dict]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open(encoding="utf-8") as stream:
            for number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                record = json.loads(line); validate_record(record); records.append(record)
        return records

    def latest(self, pair_id: str | None = None, quarter: str | None = None, target_scope: str | None = None, chart_type: str | None = None) -> list[dict]:
        latest: dict[str, dict] = {}
        with self._lock:
            for record in self._all():
                current = latest.get(record["observation_id"])
                if current is None or record["revision"] > current["revision"]:
                    latest[record["observation_id"]] = record
        records = list(latest.values())
        if pair_id is not None: records = [r for r in records if r["pair_id"] == pair_id]
        if quarter is not None: records = [r for r in records if r["quarter"] == quarter]
        if target_scope is not None: records = [r for r in records if r["target_scope"] == target_scope]
        if chart_type is not None: records = [r for r in records if r["chart_type"] == chart_type]
        return sorted(records, key=lambda r: (r["created_at"], r["observation_id"]))

    def save(self, draft: dict, provenance: dict, derived_analysis: dict | None = None) -> dict:
        with self._lock:
            records = self._all()
            existing = None
            requested_id = draft.get("observation_id")
            if requested_id:
                matches = [r for r in records if r["observation_id"] == requested_id]
                if not matches:
                    raise ValueError("Cannot edit an unknown observation_id")
                existing = max(matches, key=lambda r: r["revision"])
            now = _utcnow(); pair = draft["pair_id"].split("/")
            raw_note = draft.get("raw_note", draft.get("observation_text", ""))
            if not isinstance(raw_note, str): raise ValueError("raw_note must be a string")
            def legacy(field: str, default: object) -> object:
                return draft[field] if field in draft else existing[field] if existing else default
            counter = legacy("counter_hypothesis", "")
            alternative = draft.get("alternative_explanation", counter) if "counter_hypothesis" in draft else legacy("alternative_explanation", "")
            analysis = deepcopy(derived_analysis or {"extracted_claims": [], "machine_derived_retrieval_metadata": [], "analysis_method": "not analyzed", "limitations": "No derived analysis was supplied."})
            previous_analysis = existing.get("derived_analysis", {}).get("analysis_version", 0) if existing else 0
            analysis["analysis_version"] = previous_analysis + 1; analysis["analyzed_at"] = now
            record = {
                "observation_id": requested_id or str(uuid.uuid4()),
                "revision": existing["revision"] + 1 if existing else 1,
                "record_type": "exploratory_human_note",
                "pair_id": draft["pair_id"], "company_a": pair[0], "company_b": pair[1],
                "year": int(draft["quarter"][:4]), "quarter": draft["quarter"],
                "target_scope": draft["target_scope"], "chart_type": draft.get("chart_type"),
                "observation_text": legacy("observation_text", ""), "tags": legacy("tags", []),
                "hypothesis": legacy("hypothesis", ""), "counter_hypothesis": counter,
                "alternative_explanation": alternative, "evidence_needed": legacy("evidence_needed", ""),
                "confidence": legacy("confidence", None), "created_at": existing["created_at"] if existing else now,
                "updated_at": now, "author": legacy("author", ""), "provenance": deepcopy(provenance),
                "prohibited_uses": PROHIBITED_USES.copy(),
                "raw_note": raw_note, "derived_analysis": analysis,
            }
            if existing and any(record[field] != existing[field] for field in ("pair_id", "quarter", "target_scope", "chart_type")):
                raise ValueError("An edit cannot change its original target")
            validate_record(record)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
                stream.flush(); os.fsync(stream.fileno())
            return record


def _git_commit() -> str:
    try:
        root = Path(__file__).resolve().parents[1]
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=root, check=True, capture_output=True, text=True).stdout.strip()
        return commit + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def build_provenance(output: Path, manifest: dict, quarter: str, target_scope: str, chart_type: str | None) -> dict:
    plot_by_kind = {kind: filename for _, filename, kind in PLOT_ROWS}
    kinds = [chart_type] if target_scope == "chart" else [kind for _, _, kind in PLOT_ROWS]
    chart_artifacts = []
    for kind in kinds:
        relative = f"quarters/{quarter}/{plot_by_kind[kind]}"
        path = output / relative
        if not path.exists(): raise ValueError(f"Chart artifact is unavailable: {relative}")
        chart_artifacts.append({"chart_type": kind, "path": relative, "sha256": sha256(path)})
    machine_path = output / "machine_measurements.json"
    report_candidates = [f"reports/{quarter[:4]}_pair_observation.html", f"reports/{quarter[:4]}_YTD_pair_observation.html"]
    report_relative = next((value for value in report_candidates if (output / value).exists()), None)
    if report_relative is None: raise ValueError("Annual report artifact is unavailable")
    manifest_path = output / "manifest.json"
    return {
        "chart_artifacts": chart_artifacts,
        "machine_measurement": {"path": "machine_measurements.json", "sha256": sha256(machine_path), "period": quarter, "format_version": "1"},
        "report_artifact": {"path": report_relative, "sha256": sha256(output / report_relative)},
        "report_version": REPORT_VERSION,
        "run_identity": {"manifest_path": "manifest.json", "manifest_sha256": sha256(manifest_path), "generated_at_utc": manifest.get("generated_at_utc"), "config": manifest.get("config")},
        "cache_identity": manifest.get("raw_inputs", {}), "provider": manifest.get("provider", {}),
        "observatory_version": __version__, "observatory_git_commit": _git_commit(),
    }
