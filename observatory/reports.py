from __future__ import annotations

import csv
import html
import json
from datetime import date
from pathlib import Path

import pandas as pd

from .core import LABEL, RunConfig
from .measurements import MACHINE_OBSERVATION_CONTRACTS

PLOT_ROWS = (
    ("Daily log-return overlay", "01_return_overlay.png", "return_overlay"),
    ("Quarterly normalized-price path", "02_normalized_price.png", "normalized_price"),
    ("Contemporaneous return scatter", "03_return_scatter.png", "return_scatter"),
    ("Lagged cross-correlation", "04_lagged_cross_correlation.png", "lag_correlation"),
    ("Event-centered response", "05_event_centered_response.png", "event_response"),
)
TAGS = ("synchronous", "possible catch-up", "possible reversal", "persistent divergence", "stock-specific outlier", "stock-specific event", "sector-wide move", "possible regime change", "unclear")
GUIDANCE = {
    "return_overlay": {"shows": "Daily log returns of both stocks on common trading dates.", "math": "r(t)=ln(P(t)/P(t-1)).", "axes": "x: common trading date; y: daily log return.", "features": "Synchronous signs, magnitude mismatch, isolated shocks, volatility clustering, and visual regime changes.", "trap": "A visually delayed move is not evidence of predictive lead-lag.", "questions": "Was a move company-specific, sector-wide, liquidity-related, or associated with a sourced dated event?"},
    "normalized_price": {"shows": "Quarter-local normalized qfq price paths, each rebased to 1.", "math": "N_i(t)=P_i(t)/P_i(first common date in quarter).", "axes": "x: common trading date; y: normalized price level.", "features": "Persistent gaps, convergence/divergence, path crossings, and changes in relative direction.", "trap": "Visual convergence does not establish mean reversion or tradability.", "questions": "Do company state, sector movement, or sourced events coincide with changes in the relative path?"},
    "return_scatter": {"shows": "Paired contemporaneous daily log returns.", "math": "Points are (r_A(t), r_B(t)); displayed OLS is descriptive B-on-A with intercept.", "axes": "x: A daily log return; y: B daily log return.", "features": "Orientation, dispersion, asymmetry, clusters, nonlinear appearance, and outliers.", "trap": "Correlation, slope, and R² do not identify causality or a hedge ratio.", "questions": "Are outliers associated with sourced company or sector events, or different volatility/liquidity states?"},
    "lag_correlation": {"shows": "The complete fixed lag-correlation profile.", "math": "corr(r_A(t), r_B(t+lag)) for lag -5…+5, using quarter-dated rows after within-quarter shifting.", "axes": "x: fixed common-session lag; y: Pearson correlation.", "features": "Lag-0 position, positive/negative profile shape, peaks, symmetry, and instability across quarters.", "trap": "An off-zero maximum does not establish that one stock leads, predicts, or causes the other.", "questions": "Could persistence, common shocks, sector movement, liquidity, or sampling variation produce the profile?"},
    "event_response": {"shows": "Response paths around qualifying source-stock large-return dates.", "math": "Source event: |log return|>=3%; response: cumulative log return at offsets -5…+5 common sessions.", "axes": "x: common-session offset from event; y: cumulative response log return.", "features": "Across-event dispersion, same/next-session movement, path asymmetry, and sensitivity to individual events.", "trap": "Event coincidence and average response do not imply causality or predictability.", "questions": "Which company, industry, market, filing, or data explanations are supported by point-in-time sources?"},
}


def _fmt(value: object, digits: int = 6) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.{digits}f}"


def _quarter_metadata(output: Path) -> dict[str, dict]:
    with (output / "quarterly_summary.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    metadata = {row["quarter"]: row for row in rows if row["status"] == "generated"}
    machine = json.loads((output / "machine_measurements.json").read_text(encoding="utf-8"))
    by_period = {record["period"]: record for record in machine["records"]}
    for quarter, row in metadata.items():
        row["machine"] = by_period[quarter]
        row["contemporaneous_correlation"] = _fmt(by_period[quarter]["lag0"], 4)
    return metadata


def _load_context(output: Path) -> tuple[list[dict], list[dict]]:
    company_path, event_path = output / "context" / "company_context.csv", output / "context" / "event_context.csv"
    company = pd.read_csv(company_path).fillna("").to_dict("records") if company_path.exists() else []
    events = pd.read_csv(event_path).fillna("").to_dict("records") if event_path.exists() else []
    return company, events


def _context_sections(quarter: str, company: list[dict], events: list[dict]) -> str:
    company_rows = [row for row in company if str(row["quarter"]) == quarter]
    event_rows = [row for row in events if str(row["quarter"]) == quarter]
    if company_rows:
        rows = "".join(f"<tr><td>{html.escape(str(r['ticker']))}</td><td>{html.escape(str(r['group']))}</td><td>{html.escape(str(r['attribute']))}</td><td>{html.escape(str(r['value']))} {html.escape(str(r.get('unit','')))}</td><td>{html.escape(str(r['effective_date']))}</td><td>{html.escape(str(r['available_at']))}</td><td><a href=\"{html.escape(str(r['source_url']))}\">{html.escape(str(r['source']))}</a><br><code>{html.escape(str(r['provenance_id']))}</code></td></tr>" for r in company_rows)
        company_html = f"<table class=\"context-table\"><tr><th>Ticker</th><th>Group</th><th>Attribute</th><th>Value</th><th>Effective</th><th>Available</th><th>Source / provenance</th></tr>{rows}</table>"
    else:
        company_html = "<p>No sourced quarter-level company attributes were supplied. Nothing is inferred from price data.</p>"
    if event_rows:
        rows = "".join(f"<tr><td>{html.escape(str(r['date']))}</td><td>{html.escape(str(r['event_type']))}</td><td>{html.escape(str(r['scope']))}</td><td>{html.escape(str(r['description']))}</td><td>{html.escape(str(r['published_at']))}</td><td><a href=\"{html.escape(str(r['source_url']))}\">{html.escape(str(r['source']))}</a><br><code>{html.escape(str(r['provenance_id']))}</code></td></tr>" for r in event_rows)
        event_html = f"<table class=\"context-table\"><tr><th>Date</th><th>Type</th><th>Scope</th><th>Description (no causal claim)</th><th>Published</th><th>Source / provenance</th></tr>{rows}</table>"
    else:
        event_html = "<p>No sourced dated events were supplied. The system does not invent event context or causal explanations.</p>"
    return f"<section class=\"quarter-context\"><h2>{quarter} Context</h2><h3>Company Context</h3>{company_html}<h3>Event Context</h3>{event_html}</section>"


def _machine_html(kind: str, machine: dict, a: str, b: str) -> str:
    returns, linear = machine["return_measures"], machine["linear_response_b_on_a"]
    if kind == "return_overlay":
        items = ((f"Volatility {a}", returns["volatility"][a]), (f"Volatility {b}", returns["volatility"][b]), (f"Volatility ratio {b}/{a}", returns["volatility_ratio_b_over_a"]), ("Same-sign share", returns["same_sign_share"]))
        statement = f"{a} volatility={_fmt(returns['volatility'][a])}; {b} volatility={_fmt(returns['volatility'][b])}; B/A ratio={_fmt(returns['volatility_ratio_b_over_a'])}; same-sign share={_fmt(returns['same_sign_share'])}."
    elif kind == "normalized_price":
        items = ((f"Quarter-end normalized {a}", machine["normalized_end"][a]), (f"Quarter-end normalized {b}", machine["normalized_end"][b]))
        statement = f"Quarter-end normalized levels: {a}={_fmt(machine['normalized_end'][a])}; {b}={_fmt(machine['normalized_end'][b])}."
    elif kind == "return_scatter":
        items = (("Pearson correlation", returns["pearson"]), ("Spearman correlation", returns["spearman"]), ("Same-sign share", returns["same_sign_share"]), (f"OLS slope ({b} on {a})", linear["slope"]), ("OLS R²", linear["r_squared"]))
        statement = f"Pearson={_fmt(returns['pearson'])}; Spearman={_fmt(returns['spearman'])}; same-sign share={_fmt(returns['same_sign_share'])}; OLS slope={_fmt(linear['slope'])}; R²={_fmt(linear['r_squared'])}."
    elif kind == "lag_correlation":
        lag_rows = "".join(f"<tr><td>{r['lag']:+d}</td><td>{_fmt(r['correlation'])}</td><td>{r['sample_size']}</td></tr>" for r in machine["lag_profile"])
        peaks = f"<p>Lag 0: {_fmt(machine['lag0'])}; positive peak: {html.escape(str(machine['positive_lag_peak']))}; negative peak: {html.escape(str(machine['negative_lag_peak']))}</p>"
        rules = "".join(f"<li><code>{html.escape(s['rule'])}</code>: {html.escape(s['statement'])}</li>" for s in machine["deterministic_statements"])
        intermediate = f"{peaks}<table class=\"mini\"><tr><th>Lag</th><th>Correlation</th><th>n</th></tr>{lag_rows}</table>"
        statement = f"<ul>{rules}</ul>"
        return _machine_contract_html(kind, intermediate, statement)
    else:
        summaries = []
        for summary in machine["event_aligned"]:
            offset_rows = "".join(f"<tr><td>{r['offset']:+d}</td><td>{_fmt(r['mean'])}</td><td>{_fmt(r['median'])}</td><td>{r['observation_count']}</td></tr>" for r in summary["offsets"])
            summaries.append(f"<p>{summary['source']} events → {summary['response']} response; events n={summary['event_count']}</p><table class=\"mini\"><tr><th>Offset</th><th>Mean</th><th>Median</th><th>n</th></tr>{offset_rows}</table>")
        intermediate = "".join(summaries) or "<p>No qualifying complete-window events.</p>"
        statement = "Exact event counts and per-offset mean/median response values are displayed above; no further state is assigned."
        return _machine_contract_html(kind, intermediate, statement)
    rows = "".join(f"<tr><th>{html.escape(label)}</th><td>{_fmt(value)}</td></tr>" for label, value in items)
    return _machine_contract_html(kind, f"<table class=\"mini\">{rows}</table>", html.escape(statement))


def _machine_contract_html(kind: str, intermediate_html: str, statement_html: str) -> str:
    contract = MACHINE_OBSERVATION_CONTRACTS[kind]
    fields = (
        ("Question", contract["question"]), ("Definition", contract["definition"]),
        ("Inputs", contract["inputs"]), ("Calculation", contract["calculation"]),
    )
    opening = "".join(f"<h5>{label}</h5><p>{html.escape(value)}</p>" for label, value in fields)
    closing_fields = (
        ("Interpretation", contract["interpretation"]),
        ("Assumptions", contract["assumptions"]), ("Failure modes", contract["failure_modes"]),
        ("Does NOT imply", contract["does_not_imply"]), ("Related chart", contract["related_chart"]),
        ("Research relevance", contract["research_relevance"]),
    )
    closing = "".join(f"<h5>{label}</h5><p>{html.escape(value)}</p>" for label, value in closing_fields)
    rule = html.escape(contract["rule"])
    return f"<div class=\"machine\"><h4>Machine Observation</h4>{opening}<h5>Intermediate values</h5>{intermediate_html}<h5>Rule</h5><p>{rule}</p><h5>Machine statement</h5><div>{statement_html}</div>{closing}</div>"


def _human_form(pair: str, quarter: str, kind: str) -> str:
    form_id = f"{pair}-{quarter}-{kind}".replace("/", "-")
    tags = "".join(f'<label><input type="checkbox" name="tags" value="{html.escape(tag)}"> {html.escape(tag)}</label>' for tag in TAGS)
    return f"""<form class="human-form" data-record-id="{form_id}" data-pair="{pair}" data-period="{quarter}" data-chart="{kind}">
<fieldset class="human"><legend>Human Observation</legend><textarea name="observation" placeholder="Enter a direct observation; blank until reviewed."></textarea><div class="tags"><strong>Optional human-selected tags</strong>{tags}</div></fieldset>
<fieldset class="hypothesis"><legend>Human Hypothesis</legend><textarea name="hypothesis" placeholder="Enter a possible explanation separately."></textarea></fieldset>
<fieldset class="counter"><legend>Alternative Explanation / Counter-Hypothesis</legend><textarea name="alternative" placeholder="Enter competing explanations or confounders separately."></textarea></fieldset>
<fieldset class="evidence"><legend>Evidence Needed / Follow-up Question</legend><textarea name="evidence" placeholder="What evidence could distinguish the hypothesis from alternatives?"></textarea></fieldset>
<label>Optional author: <input name="author" type="text"></label><label class="confidence">Optional confidence (0–1; human judgment only): <input name="confidence" type="number" min="0" max="1" step="0.01"></label><button type="button" class="save-note">Save structured exploratory note</button><span class="save-status" aria-live="polite"></span></form>"""


def _header(config: RunConfig, year_label: str, provider_id: str, provider_version: str) -> str:
    fields = (("Ticker pair", f"{config.ticker_a} / {config.ticker_b}"), ("Year", year_label), ("Data provider", f"{provider_id} v{provider_version}"), ("Adjustment", "qfq"), ("Return definition", "daily log return"), ("Event threshold", "|log return| >= 3%"), ("Event window", "+/-5 common trading sessions"), ("Lag range", "-5 ... +5"))
    return "".join(f"<dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd>" for label, value in fields)


def _annual_html(output: Path, config: RunConfig, year_label: str, quarters: list[str], metadata: dict[str, dict], provider_id: str, provider_version: str, company: list[dict], events: list[dict]) -> str:
    quarter_headers = [f"<th><strong>{q}</strong><span>common observations n={metadata[q]['common_observations']}</span><span>contemporaneous correlation={metadata[q]['contemporaneous_correlation']}</span></th>" for q in quarters]
    body_rows = []; pair = f"{config.ticker_a}/{config.ticker_b}"
    for label, filename, kind in PLOT_ROWS:
        cells = []; guide = GUIDANCE[kind]
        for quarter in quarters:
            source = f"../quarters/{quarter}/{filename}"
            cells.append(f"<td><a href=\"{source}\" target=\"_blank\" rel=\"noopener\"><img src=\"{source}\" alt=\"{quarter} {html.escape(label)}\"></a><section class=\"guide\"><h4>What this chart shows</h4><p>{html.escape(guide['shows'])}</p><h4>Mathematical quantity</h4><p>{html.escape(guide['math'])}</p><h4>How to read the axes</h4><p>{html.escape(guide['axes'])}</p><h4>Traditional features to inspect</h4><p>{html.escape(guide['features'])}</p><h4>Common interpretation trap</h4><p>{html.escape(guide['trap'])}</p><h4>Company / event / context questions</h4><p>{html.escape(guide['questions'])}</p></section>{_machine_html(kind, metadata[quarter]['machine'], config.ticker_a, config.ticker_b)}{_human_form(pair, quarter, kind)}</td>")
        body_rows.append(f"<tr><th class=\"row-label\">{html.escape(label)}</th>{''.join(cells)}</tr>")
    contexts = "".join(_context_sections(q, company, events) for q in quarters)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(year_label)} pair observation — {pair}</title>
<style>:root{{font-family:Arial,sans-serif}}body{{margin:0;color:#172033;background:#f4f6f8}}header,.quarter-context,.controls{{margin:20px;padding:20px;background:#fff;border:1px solid #d9dee7}}.warning{{color:#a12622;font-weight:700}}dl{{display:grid;grid-template-columns:max-content 1fr;gap:5px 14px}}dt{{font-weight:700}}dd{{margin:0}}.scroll{{overflow-x:auto;padding:0 20px 20px}}table{{border-collapse:separate;border-spacing:8px;min-width:{220+650*len(quarters)}px;table-layout:fixed}}th,td{{background:#fff;border:1px solid #d9dee7;vertical-align:top;padding:10px}}thead th span{{display:block;font-size:13px;font-weight:400;margin-top:4px}}.row-label{{width:190px;text-align:left;position:sticky;left:0;z-index:2}}td{{width:630px}}img{{display:block;width:100%;height:auto;object-fit:contain}}.guide,.machine,fieldset{{margin-top:10px;padding:10px;border:1px solid #c8d0db}}.guide{{background:#f8fafc}}.machine{{background:#eef6ff;border-color:#8bb7e8}}.machine h4,.guide h4{{margin:0 0 6px}}.formula{{font-size:12px}}.mini,.context-table{{min-width:0;width:100%;border-collapse:collapse;table-layout:auto}}.mini th,.mini td,.context-table th,.context-table td{{padding:4px;border:1px solid #ccd3dc;font-size:12px}}fieldset.human{{border-color:#6b9f78}}fieldset.hypothesis{{border-color:#b49344}}fieldset.counter{{border-color:#a86f6f}}legend{{font-weight:700}}textarea{{width:100%;min-height:72px;box-sizing:border-box}}.tags{{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}}.confidence{{display:block;margin:9px 0}}button{{padding:7px 10px}}.save-status{{margin-left:8px;font-size:12px}}.context-table a{{overflow-wrap:anywhere}}.controls button,.controls label{{margin-right:10px}}</style></head><body>
<header><h1>{html.escape(year_label)} Pair Observation</h1><p class="warning">{html.escape(LABEL)}</p><p><strong>Four separate layers:</strong> Machine Measurement; Human Observation; Human Hypothesis; Alternative Explanation / Counter-Hypothesis.</p><dl>{_header(config,year_label,provider_id,provider_version)}</dl><p><a href="../machine_measurements.json">Machine formulas, inputs, records, and deterministic rules</a></p></header>
<section class="controls"><strong>Human note records:</strong> saved only in this browser's localStorage until exported. They never enter models, labels, classifications, pair selection, or signals. <button id="export-notes">Export notes JSON</button><label>Import notes JSON <input id="import-notes" type="file" accept="application/json"></label></section>
{contexts}<main class="scroll"><table><thead><tr><th class="row-label">Plot type</th>{''.join(quarter_headers)}</tr></thead><tbody>{''.join(body_rows)}</tbody></table></main>
<script>const KEY='observatory-human-notes:{pair}';const read=()=>JSON.parse(localStorage.getItem(KEY)||'[]');const write=x=>localStorage.setItem(KEY,JSON.stringify(x));document.querySelectorAll('.human-form').forEach(f=>{{const old=read().find(x=>(x.observation_id||x.id)===f.dataset.recordId);if(old){{f.observation.value=old.observation_text||'';f.hypothesis.value=old.hypothesis||'';f.alternative.value=old.counter_hypothesis||old.alternative_explanation||'';f.evidence.value=old.evidence_needed||'';f.author.value=old.author||'';f.confidence.value=old.confidence??'';f.querySelectorAll('[name=tags]').forEach(x=>x.checked=(old.tags||[]).includes(x.value));}}f.querySelector('.save-note').onclick=()=>{{const c=f.confidence.value,now=new Date().toISOString(),companies=f.dataset.pair.split('/'),period=f.dataset.period;const record={{observation_id:f.dataset.recordId,record_type:'exploratory_human_note',pair_id:f.dataset.pair,company_a:companies[0],company_b:companies[1],year:Number(period.slice(0,4)),quarter:period,chart_type:f.dataset.chart,observation_text:f.observation.value,tags:[...f.querySelectorAll('[name=tags]:checked')].map(x=>x.value),hypothesis:f.hypothesis.value,counter_hypothesis:f.alternative.value,alternative_explanation:f.alternative.value,evidence_needed:f.evidence.value,confidence:c===''?null:Number(c),created_at:old?.created_at||now,updated_at:now,author:f.author.value,prohibited_uses:['training labels','formal classifications','pair-selection inputs','prediction targets','trading signals','confirmatory evidence']}};const all=read().filter(x=>(x.observation_id||x.id)!==record.observation_id);all.push(record);write(all);f.querySelector('.save-status').textContent='Saved '+record.updated_at;}};}});document.getElementById('export-notes').onclick=()=>{{const blob=new Blob([JSON.stringify({{schema_version:'1.1',records:read()}},null,2)],{{type:'application/json'}});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='human_observations_{pair.replace('/','_')}.json';a.click();URL.revokeObjectURL(a.href);}};document.getElementById('import-notes').onchange=e=>{{const reader=new FileReader();reader.onload=()=>{{const data=JSON.parse(reader.result);write(data.records||[]);location.reload();}};reader.readAsText(e.target.files[0]);}};</script></body></html>"""


def _index_html(config: RunConfig, report_names: list[tuple[str, str]]) -> str:
    reports = "".join(f'<li><a href="{filename}">{html.escape(label)}</a></li>' for label, filename in report_names)
    plots = "".join(f'<li><a href="../{filename}">{html.escape(label)}</a></li>' for label, filename, _ in PLOT_ROWS)
    return f"<!doctype html><html><head><meta charset=\"utf-8\"><title>Pair observation report index</title></head><body><h1>{config.ticker_a} / {config.ticker_b} Pair Observation Reports</h1><p>{html.escape(LABEL)}</p><p><a href=\"../machine_measurements.json\">Deterministic machine measurements and formulas</a></p><h2>Annual reports</h2><ul>{reports}</ul><h2>Full-period plots</h2><ul>{plots}</ul></body></html>"


def generate_reports(output: Path, config: RunConfig, provider_id: str, provider_version: str) -> list[Path]:
    reports_dir = output / "reports"; reports_dir.mkdir()
    metadata = _quarter_metadata(output); company, events = _load_context(output)
    report_names: list[tuple[str, str]] = []; artifacts: list[Path] = []
    for year in sorted({int(q[:4]) for q in metadata}):
        available = [f"{year}Q{n}" for n in range(1, 5) if f"{year}Q{n}" in metadata]
        full = config.start <= date(year, 1, 1) and config.end >= date(year, 12, 31)
        if full and len(available) == 4: label, filename = str(year), f"{year}_pair_observation.html"
        elif year == config.end.year and config.end < date(year, 12, 31): label, filename = f"{year} YTD — INCOMPLETE CALENDAR YEAR", f"{year}_YTD_pair_observation.html"
        else: continue
        path = reports_dir / filename; path.write_text(_annual_html(output, config, label, available, metadata, provider_id, provider_version, company, events), encoding="utf-8")
        report_names.append((label, filename)); artifacts.append(path)
    index = reports_dir / "index.html"; index.write_text(_index_html(config, report_names), encoding="utf-8")
    return [index, *artifacts]
