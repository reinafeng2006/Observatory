from __future__ import annotations

import json
import re
from pathlib import Path

CLAIM_TYPES = {
    "verifiable_observational": "VERIFIABLE / OBSERVATIONAL CONTENT",
    "interpretation_hypothesis": "INTERPRETATION / HYPOTHESIS",
    "external_context": "CONTEXTUAL / EXTERNAL CLAIM REQUIRING EVIDENCE",
    "question_evidence_need": "QUESTION / EVIDENCE NEED",
}
EVIDENCE_STATUSES = {
    "supported by bound observations", "partially supported", "not established by current evidence",
    "contradicted by bound observations", "not currently testable from available Observatory context",
}
STRONG_TERMS = ("always", "never", "causes", "caused", "predicts", "predict", "leads", "lead", "follows", "follow")
EXTERNAL_TERMS = ("earnings", "policy", "news", "institutional", "liquidity", "filing", "announcement", "sector", "industry", "management", "fundamental")
HYPOTHESIS_TERMS = ("may", "might", "perhaps", "possibly", "appears", "seems", "faster", "catching up", "catch-up", "reversal", "price discovery", "because", "mechanism", *STRONG_TERMS)
QUESTION_TERMS = ("what evidence", "need to check", "need evidence", "verify", "whether", "question", "why ")


def _sentences(raw_note: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?。！？])\s+|[\r\n]+", raw_note) if part.strip()]


def _measurement(provenance: dict, metric: str, value: object, formula_or_rule: str) -> dict:
    source = provenance["machine_measurement"]
    return {"metric": metric, "value": value, "formula_or_rule": formula_or_rule, "artifact_path": source["path"], "artifact_sha256": source["sha256"], "period": source["period"]}


def _classify(statement: str) -> tuple[str, str]:
    lowered = statement.lower()
    if "?" in statement or "？" in statement or any(term in lowered for term in QUESTION_TERMS):
        return "question_evidence_need", "Question mark or explicit evidence/verification wording."
    if any(term in lowered for term in EXTERNAL_TERMS):
        return "external_context", "Explicit company, industry, news, policy, liquidity, or other external-context wording."
    if any(term in lowered for term in HYPOTHESIS_TERMS):
        return "interpretation_hypothesis", "Explicit mechanism, timing, causal, predictive, or tentative interpretation wording."
    return "verifiable_observational", "No external-context or mechanism marker; treated as a potentially checkable observational statement."


def _ground(statement: str, claim_type: str, machine: dict, provenance: dict) -> tuple[str, list[dict], str, list[str], str]:
    lowered = statement.lower(); measures: list[dict] = []; unresolved: list[str] = []
    limitation = "Descriptive evidence is limited to the bound pair-quarter artifacts and does not constitute formal inference."
    boundary = ""
    returns = machine["return_measures"]
    if any(term in lowered for term in ("same direction", "same sign", "synchronous", "together")):
        share = returns["same_sign_share"]
        measures.append(_measurement(provenance, "same_sign_return_share", share, "count(sign(r_A)=sign(r_B)) / paired-return n"))
        if "always" in lowered:
            status = "supported by bound observations" if share == 1 else "contradicted by bound observations"
        elif "most" in lowered:
            status = "supported by bound observations" if share is not None and share > .5 else "contradicted by bound observations"
        elif any(term in lowered for term in ("usually", "often")):
            status = "partially supported" if share is not None and share > .5 else "not established by current evidence"
        else:
            status = "partially supported"
        limitation = "Same-sign share measures direction agreement only; it does not identify timing, mechanism, or stable dependence."
    elif any(term in lowered for term in ("correlat", "co-move", "comove")):
        measures.extend([_measurement(provenance, "pearson_return_correlation", returns["pearson"], "Pearson correlation of paired quarter returns"), _measurement(provenance, "spearman_return_correlation", returns["spearman"], "Pearson correlation of average return ranks")])
        status = "partially supported"
        limitation = "Correlation magnitude is shown without a configured verbal-strength threshold or formal inference."
    elif any(term in lowered for term in ("lead", "follow", "lag", "first", "next day", "next session", "predict")):
        measures.extend([_measurement(provenance, "lag0_correlation", machine["lag0"], "corr(r_A(t),r_B(t))"), _measurement(provenance, "positive_lag_peak", machine["positive_lag_peak"], "maximum signed correlation for lags +1…+5"), _measurement(provenance, "negative_lag_peak", machine["negative_lag_peak"], "maximum signed correlation for lags -5…-1")])
        status = "not established by current evidence"
        boundary = "The fixed lag profile may describe timing asymmetry, but predictive or causal lead-lag is not established."
        limitation = "Off-zero sample correlation can reflect persistence, common shocks, liquidity, sampling variation, or overlapping information arrival."
        unresolved.append("A separate pre-specified predictive design and external timing context would be required.")
    elif any(term in lowered for term in ("diverg", "converg", "normalized", "path")):
        measures.append(_measurement(provenance, "quarter_end_normalized_levels", machine["normalized_end"], "last quarter close / first common quarter close"))
        status = "partially supported"
        limitation = "Endpoint levels do not by themselves establish when divergence occurred, equilibrium, or mean reversion."
    elif any(term in lowered for term in ("large move", "event", "shock")):
        counts = [{"source": row["source"], "response": row["response"], "event_count": row["event_count"]} for row in machine["event_aligned"]]
        measures.append(_measurement(provenance, "complete_window_event_counts", counts, "distinct |log return|>=3% event dates with complete ±5-session windows"))
        status = "partially supported"
        limitation = "Event counts and aligned responses do not supply event causes or repeatability."
    elif claim_type == "external_context":
        status = "not currently testable from available Observatory context"
        unresolved.append("A dated, point-in-time external source is required.")
    elif claim_type == "question_evidence_need":
        status = "not currently testable from available Observatory context"
        unresolved.append(statement)
    elif claim_type == "interpretation_hypothesis":
        status = "not established by current evidence"
        unresolved.append("The proposed meaning or mechanism requires evidence beyond descriptive charts.")
    else:
        status = "not currently testable from available Observatory context"
        unresolved.append("No deterministic measurement mapping is defined for this wording.")
    strong = [term for term in STRONG_TERMS if re.search(rf"\b{re.escape(term)}\b", lowered)]
    if strong and not boundary:
        boundary = f"Strong wording ({', '.join(strong)}) is retained as human wording; the bound exploratory evidence does not establish that stronger claim."
        if status == "supported by bound observations" and any(term in strong for term in ("causes", "caused", "predicts", "predict", "leads", "lead", "follows", "follow")):
            status = "not established by current evidence"
    if not boundary and claim_type == "interpretation_hypothesis":
        boundary = "This is retained as a human interpretation or hypothesis, not converted into an Observatory fact."
    return status, measures, limitation, unresolved, boundary


def analyze_note(raw_note: str, output: Path, quarter: str, provenance: dict) -> dict:
    machine_payload = json.loads((output / "machine_measurements.json").read_text(encoding="utf-8"))
    machine = next(record for record in machine_payload["records"] if record["period"] == quarter)
    claims = []
    for statement in _sentences(raw_note):
        claim_type, basis = _classify(statement)
        status, measurements, limitation, unresolved, boundary = _ground(statement, claim_type, machine, provenance)
        claims.append({"extracted_statement": statement, "claim_type": claim_type, "claim_type_label": CLAIM_TYPES[claim_type], "evidence_status": status, "supporting_measurements": measurements, "semantic_or_deterministic_basis": basis, "limitation": limitation, "interpretation_boundary": boundary, "unresolved_evidence": unresolved})
    descriptors = []
    combined = raw_note.lower()
    if any(term in combined for term in ("same direction", "same sign", "synchronous")): descriptors.append("possible_synchrony")
    if any(term in combined for term in ("lead", "follow", "lag", "first", "next session")): descriptors.append("possible_timing_asymmetry")
    if any(term in combined for term in ("diverg", "converg", "normalized")): descriptors.append("possible_divergence")
    if any(term in combined for term in EXTERNAL_TERMS): descriptors.append("event_context_needed")
    return {"extracted_claims": claims, "machine_derived_retrieval_metadata": descriptors, "analysis_method": "deterministic sentence and keyword rules with bound descriptive measurements; no LLM visual interpretation", "limitations": "Pedagogical claim decomposition only; it does not validate hypotheses, establish causality or predictability, score pairs, or create signals."}
