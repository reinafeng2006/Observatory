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


def _machine_learning_card(kind: str) -> str:
    contract = MACHINE_OBSERVATION_CONTRACTS[kind]
    fields = (
        ("Question", contract["question"]), ("Definition", contract["definition"]),
        ("Inputs", contract["inputs"]), ("Calculation", contract["calculation"]),
        ("Rule", contract["rule"]),
        ("Interpretation", contract["interpretation"]),
        ("Assumptions", contract["assumptions"]), ("Failure modes", contract["failure_modes"]),
        ("Does NOT imply", contract["does_not_imply"]), ("Related chart", contract["related_chart"]),
        ("Research relevance", contract["research_relevance"]),
    )
    body = "".join(f"<h5>{label}</h5><p>{html.escape(value)}</p>" for label, value in fields)
    return f'<details class="learning-card" id="learn-machine-{kind}"><summary>Learn machine methodology and interpretation boundaries</summary>{body}</details>'


def _peak(value: dict | None) -> str:
    return "n/a" if not value else f"{_fmt(value['correlation'])} @ {value['lag']:+d}"


def _event_summary(machine: dict, source: str, response: str) -> dict | None:
    return next((row for row in machine["event_aligned"] if row["source"] == source and row["response"] == response), None)


def _event_offset(summary: dict | None, offset: int) -> str:
    if not summary:
        return "n/a"
    row = next((item for item in summary["offsets"] if item["offset"] == offset), None)
    return "n/a" if not row else f"mean {_fmt(row['mean'])}; median {_fmt(row['median'])}; n={row['observation_count']}"


def _machine_rows(kind: str, quarters: list[str], metadata: dict[str, dict], a: str, b: str) -> list[tuple[str, list[str]]]:
    machines = [metadata[q]["machine"] for q in quarters]
    common = ("Common observations N", [str(m["sample_sizes"]["common_observations"]) for m in machines])
    paired = ("Paired returns n", [str(m["sample_sizes"]["paired_returns"]) for m in machines])
    missing = ("Return rows missing a pair", [str(m["sample_sizes"]["common_observations"] - m["sample_sizes"]["paired_returns"]) for m in machines])
    if kind == "return_overlay":
        return [common, paired, missing,
            (f"Volatility {a}", [_fmt(m["return_measures"]["volatility"][a]) for m in machines]),
            (f"Volatility {b}", [_fmt(m["return_measures"]["volatility"][b]) for m in machines]),
            (f"Volatility ratio {b}/{a}", [_fmt(m["return_measures"]["volatility_ratio_b_over_a"]) for m in machines]),
            ("Same-sign return share", [_fmt(m["return_measures"]["same_sign_share"]) for m in machines])]
    if kind == "normalized_price":
        return [common,
            (f"Quarter-end normalized {a}", [_fmt(m["normalized_end"][a]) for m in machines]),
            (f"Quarter-end normalized {b}", [_fmt(m["normalized_end"][b]) for m in machines])]
    if kind == "return_scatter":
        return [common, paired, missing,
            ("Pearson correlation", [_fmt(m["return_measures"]["pearson"]) for m in machines]),
            ("Spearman correlation", [_fmt(m["return_measures"]["spearman"]) for m in machines]),
            ("Same-sign return share", [_fmt(m["return_measures"]["same_sign_share"]) for m in machines]),
            (f"OLS intercept ({b} on {a})", [_fmt(m["linear_response_b_on_a"]["intercept"]) for m in machines]),
            (f"OLS slope ({b} on {a})", [_fmt(m["linear_response_b_on_a"]["slope"]) for m in machines]),
            ("OLS R²", [_fmt(m["linear_response_b_on_a"]["r_squared"]) for m in machines])]
    if kind == "lag_correlation":
        return [common, paired,
            ("Lag 0 correlation", [_fmt(m["lag0"]) for m in machines]),
            ("Positive-lag peak (corr @ lag)", [_peak(m["positive_lag_peak"]) for m in machines]),
            ("Negative-lag peak (corr @ lag)", [_peak(m["negative_lag_peak"]) for m in machines]),
            ("Deterministic rule results", ["<br>".join(html.escape(s["statement"]) for s in m["deterministic_statements"]) or "n/a" for m in machines])]
    ab = [_event_summary(m, a, b) for m in machines]
    ba = [_event_summary(m, b, a) for m in machines]
    return [common, paired,
        (f"Qualifying complete-window events {a}→{b}", [str(s["event_count"]) if s else "0" for s in ab]),
        (f"Qualifying complete-window events {b}→{a}", [str(s["event_count"]) if s else "0" for s in ba]),
        (f"{a}→{b} response @ 0", [_event_offset(s, 0) for s in ab]),
        (f"{a}→{b} response @ +1", [_event_offset(s, 1) for s in ab]),
        (f"{a}→{b} response @ +5", [_event_offset(s, 5) for s in ab]),
        (f"{b}→{a} response @ 0", [_event_offset(s, 0) for s in ba]),
        (f"{b}→{a} response @ +1", [_event_offset(s, 1) for s in ba]),
        (f"{b}→{a} response @ +5", [_event_offset(s, 5) for s in ba])]


def _quarter_machine_detail(kind: str, quarter: str, machine: dict) -> str:
    inputs = "".join(f"<li>{html.escape(name)}: <code>{html.escape(path)}</code></li>" for name, path in machine["inputs"].items())
    body = f"<p><strong>Inputs / provenance paths</strong></p><ul>{inputs}</ul>"
    if kind == "lag_correlation":
        rows = "".join(f"<tr><td>{r['lag']:+d}</td><td>{_fmt(r['correlation'])}</td><td>{r['sample_size']}</td></tr>" for r in machine["lag_profile"])
        body += f'<table class="mini"><tr><th>Lag</th><th>Correlation</th><th>n</th></tr>{rows}</table>'
    elif kind == "event_response":
        summaries = []
        for summary in machine["event_aligned"]:
            rows = "".join(f"<tr><td>{r['offset']:+d}</td><td>{_fmt(r['mean'])}</td><td>{_fmt(r['median'])}</td><td>{r['observation_count']}</td></tr>" for r in summary["offsets"])
            summaries.append(f"<p>{summary['source']} events → {summary['response']} response; events n={summary['event_count']}</p><table class=\"mini\"><tr><th>Offset</th><th>Mean</th><th>Median</th><th>n</th></tr>{rows}</table>")
        body += "".join(summaries) or "<p>No qualifying complete-window events.</p>"
    return f'<details class="quarter-detail"><summary>{quarter} intermediate values and provenance</summary>{body}</details>'


def _machine_comparison(kind: str, quarters: list[str], metadata: dict[str, dict], a: str, b: str) -> str:
    headers = "".join(f"<th>{q}</th>" for q in quarters)
    rows = []
    for label, values in _machine_rows(kind, quarters, metadata, a, b):
        cells = "".join(f"<td>{value}</td>" for value in values)
        rows.append(f'<tr><th>{html.escape(label)} <a class="learn-link" href="#learn-machine-{kind}">Learn</a></th>{cells}</tr>')
    details = "".join(_quarter_machine_detail(kind, q, metadata[q]["machine"]) for q in quarters)
    return f'<section class="machine-comparison"><h3>Quarterly Machine Observation comparison</h3><p>Realized descriptive measurements only; invariant methodology is shared below.</p><div class="table-scroll"><table class="comparison"><thead><tr><th>Metric</th>{headers}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>{details}</section>'


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


def _chart_context(label: str, kind: str) -> str:
    guide = GUIDANCE[kind]
    features = [part.strip().rstrip(".") for part in guide["features"].replace(", and ", ", ").split(",") if part.strip()][:5]
    feature_html = "".join(f"<li>{html.escape(feature)}</li>" for feature in features)
    return f'''<section class="chart-context"><div><p class="eyebrow">Chart Context</p><h2>{html.escape(label)}</h2><p>{html.escape(guide["shows"])}</p><code>{html.escape(guide["math"])}</code></div><div><strong>Inspect</strong><ul>{feature_html}</ul></div><p class="chart-warning"><strong>Interpretation warning:</strong> {html.escape(guide["trap"])}</p></section>'''


def _learn_chart(kind: str) -> str:
    guide = GUIDANCE[kind]
    fields = (("What this chart shows", guide["shows"]), ("Mathematical quantity", guide["math"]),
              ("Axes", guide["axes"]), ("Detailed explanation / traditional features", guide["features"]),
              ("Interpretation boundary", guide["trap"]), ("Company / event / context questions", guide["questions"]))
    body = "".join(f"<h4>{html.escape(label)}</h4><p>{html.escape(value)}</p>" for label, value in fields)
    return f'<details class="learn-chart"><summary>Learn this chart</summary>{body}</details>'


def _annual_html(output: Path, config: RunConfig, year_label: str, quarters: list[str], metadata: dict[str, dict], provider_id: str, provider_version: str, company: list[dict], events: list[dict]) -> str:
    pair = f"{config.ticker_a}/{config.ticker_b}"; chart_blocks = []
    for label, filename, kind in PLOT_ROWS:
        plot_cards = []; forms = []
        for quarter in quarters:
            source = f"../quarters/{quarter}/{filename}"
            event_line = ""
            if kind == "event_response":
                event_line = f"<span>events {config.ticker_a}={metadata[quarter]['qualifying_events_' + config.ticker_a]}; {config.ticker_b}={metadata[quarter]['qualifying_events_' + config.ticker_b]}</span>"
            plot_cards.append(f'<article class="plot-card"><h3>{quarter}</h3><p class="quarter-meta"><span>common N={metadata[quarter]["common_observations"]}</span><span>corr={metadata[quarter]["contemporaneous_correlation"]}</span>{event_line}</p><a href="{source}" target="_blank" rel="noopener"><img src="{source}" alt="{quarter} {html.escape(label)}"></a></article>')
            forms.append(f'<article class="human-card"><h3>{quarter}</h3>{_human_form(pair, quarter, kind)}</article>')
        chart_blocks.append(f'''<section class="chart-block" id="{kind}">{_chart_context(label, kind)}
<div class="plot-grid">{"".join(plot_cards)}</div>
{_machine_comparison(kind, quarters, metadata, config.ticker_a, config.ticker_b)}
<section class="human-section"><h3>Human research notes</h3><div class="human-grid">{"".join(forms)}</div></section>
<div class="learning">{_learn_chart(kind)}{_machine_learning_card(kind)}</div></section>''')
    contexts = "".join(_context_sections(q, company, events) for q in quarters)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{html.escape(year_label)} pair observation — {pair}</title>
<style>:root{{font-family:Arial,sans-serif;color:#172033}}*{{box-sizing:border-box}}body{{margin:0;background:#f4f6f8}}header,.quarter-context,.controls,.chart-block{{margin:20px;padding:20px;background:#fff;border:1px solid #d9dee7}}.warning{{color:#a12622;font-weight:700}}dl{{display:grid;grid-template-columns:max-content 1fr;gap:5px 14px}}dt{{font-weight:700}}dd{{margin:0}}.chart-block{{padding:0;overflow:hidden}}.chart-context{{display:grid;grid-template-columns:minmax(420px,1fr) minmax(260px,.7fr);gap:18px;padding:18px 20px;border-bottom:1px solid #d9dee7;background:#f8fafc}}.chart-context h2{{margin:2px 0 8px}}.chart-context ul{{columns:2;margin:6px 0}}.eyebrow{{margin:0;color:#49647f;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.08em}}.chart-warning{{grid-column:1/-1;margin:0;padding:9px 12px;background:#fff3df;border-left:4px solid #d18b22}}.plot-grid,.human-grid{{display:grid;grid-template-columns:repeat({len(quarters)},minmax(500px,1fr));gap:10px;min-width:{len(quarters)*510}px}}.plot-grid{{padding:14px;overflow-x:auto}}.plot-card,.human-card{{border:1px solid #d9dee7;background:#fff;padding:10px}}.plot-card h3,.human-card h3{{margin:0 0 5px}}.quarter-meta{{display:flex;flex-wrap:wrap;gap:4px 12px;margin:0 0 8px;font-size:12px}}img{{display:block;width:100%;height:auto;object-fit:contain}}.machine-comparison,.human-section,.learning{{padding:16px 20px;border-top:1px solid #d9dee7}}.machine-comparison{{background:#eef6ff}}.machine-comparison h3,.human-section>h3{{margin-top:0}}.table-scroll{{overflow-x:auto}}table{{border-collapse:collapse}}.comparison{{width:100%;min-width:{260+210*len(quarters)}px}}th,td{{vertical-align:top;padding:7px;border:1px solid #cbd4df;text-align:left}}.comparison th:first-child{{min-width:250px}}.comparison td{{min-width:200px}}.learn-link{{font-size:11px;font-weight:400;white-space:nowrap}}.quarter-detail{{display:inline-block;vertical-align:top;width:min(100%,420px);margin:10px 8px 0 0}}details{{border:1px solid #b9c7d6;background:#fff;padding:10px}}summary{{cursor:pointer;font-weight:700}}.mini,.context-table{{width:100%;table-layout:auto}}.mini th,.mini td,.context-table th,.context-table td{{padding:4px;font-size:12px}}.human-grid{{overflow-x:auto}}fieldset{{margin-top:10px;padding:10px;border:1px solid #c8d0db}}fieldset.human{{border-color:#6b9f78}}fieldset.hypothesis{{border-color:#b49344}}fieldset.counter{{border-color:#a86f6f}}legend{{font-weight:700}}textarea{{width:100%;min-height:72px}}.tags{{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}}.confidence{{display:block;margin:9px 0}}button{{padding:7px 10px}}.save-status{{margin-left:8px;font-size:12px}}.learning{{display:grid;grid-template-columns:1fr 1fr;gap:12px;background:#f8fafc}}.learning h4,.learning-card h5{{margin-bottom:4px}}.learning p{{margin-top:4px}}.context-table a{{overflow-wrap:anywhere}}.controls button,.controls label{{margin-right:10px}}@media(max-width:900px){{.chart-context{{grid-template-columns:1fr}}.chart-warning{{grid-column:auto}}.learning{{grid-template-columns:1fr}}}}</style></head><body>
<header><h1>{html.escape(year_label)} Pair Observation</h1><p class="warning">{html.escape(LABEL)}</p><p><strong>Four separate layers:</strong> Machine Measurement; Human Observation; Human Hypothesis; Alternative Explanation / Counter-Hypothesis.</p><dl>{_header(config,year_label,provider_id,provider_version)}</dl><p><a href="../machine_measurements.json">Machine formulas, inputs, records, and deterministic rules</a></p></header>
<section class="controls"><strong>Human note records:</strong> saved only in this browser's localStorage until exported. They never enter models, labels, classifications, pair selection, or signals. <button id="export-notes">Export notes JSON</button><label>Import notes JSON <input id="import-notes" type="file" accept="application/json"></label></section>
{contexts}<main>{''.join(chart_blocks)}</main>
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
