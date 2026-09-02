from __future__ import annotations

import csv
import html
from datetime import date
from pathlib import Path

import pandas as pd

from .core import LABEL, RunConfig

PLOT_ROWS = (
    ("Daily log-return overlay", "01_return_overlay.png"),
    ("Quarterly normalized-price path", "02_normalized_price.png"),
    ("Contemporaneous return scatter", "03_return_scatter.png"),
    ("Lagged cross-correlation", "04_lagged_cross_correlation.png"),
    ("Event-centered response", "05_event_centered_response.png"),
)
NOTE_PROMPTS = (
    "Co-movement:",
    "Possible lead-lag:",
    "Catch-up vs reversal:",
    "Regime change:",
    "Stock-specific outliers:",
    "Questions / hypotheses:",
)


def _quarter_metadata(output: Path) -> dict[str, dict[str, str]]:
    with (output / "quarterly_summary.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    metadata = {row["quarter"]: row for row in rows if row["status"] == "generated"}
    for quarter, row in metadata.items():
        lags = pd.read_csv(output / "quarters" / quarter / "lagged_correlations.csv")
        contemporaneous = lags.loc[lags["lag"] == 0, "correlation"]
        row["contemporaneous_correlation"] = "n/a" if contemporaneous.empty or pd.isna(contemporaneous.iloc[0]) else f"{contemporaneous.iloc[0]:.4f}"
    return metadata


def _header(config: RunConfig, year_label: str, provider_id: str, provider_version: str) -> str:
    fields = (
        ("Ticker pair", f"{config.ticker_a} / {config.ticker_b}"),
        ("Year", year_label),
        ("Data provider", f"{provider_id} v{provider_version}"),
        ("Adjustment", "qfq"),
        ("Return definition", "daily log return"),
        ("Event threshold", "|log return| >= 3%"),
        ("Event window", "+/-5 common trading sessions"),
        ("Lag range", "-5 ... +5"),
    )
    return "".join(f"<dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd>" for label, value in fields)


def _annual_html(
    output: Path,
    config: RunConfig,
    year_label: str,
    quarters: list[str],
    metadata: dict[str, dict[str, str]],
    provider_id: str,
    provider_version: str,
) -> str:
    quarter_headers = []
    for quarter in quarters:
        row = metadata[quarter]
        quarter_headers.append(
            f"<th><strong>{html.escape(quarter)}</strong>"
            f"<span>common observations n={row['common_observations']}</span>"
            f"<span>contemporaneous correlation={row['contemporaneous_correlation']}</span></th>"
        )
    body_rows = []
    for row_label, filename in PLOT_ROWS:
        cells = []
        for quarter in quarters:
            source = f"../quarters/{quarter}/{filename}"
            detail = ""
            if filename == "05_event_centered_response.png":
                row = metadata[quarter]
                detail = (
                    f"<span class=\"cell-meta\">qualifying events: {config.ticker_a} n={row[f'qualifying_events_{config.ticker_a}']}; "
                    f"{config.ticker_b} n={row[f'qualifying_events_{config.ticker_b}']}</span>"
                )
            cells.append(
                f"<td><a href=\"{source}\" target=\"_blank\" rel=\"noopener\">"
                f"<img src=\"{source}\" alt=\"{html.escape(quarter + ' ' + row_label)}\"></a>{detail}</td>"
            )
        body_rows.append(f"<tr><th class=\"row-label\">{html.escape(row_label)}</th>{''.join(cells)}</tr>")
    notes = "".join(f"<div class=\"note\"><label>{html.escape(prompt)}</label><div class=\"blank\"></div></div>" for prompt in NOTE_PROMPTS)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(year_label)} pair observation — {config.ticker_a}/{config.ticker_b}</title>
<style>
:root {{ color-scheme: light; font-family: Arial, sans-serif; }}
body {{ margin: 0; color: #172033; background: #f4f6f8; }}
header, .notes {{ margin: 20px; padding: 20px; background: white; border: 1px solid #d9dee7; }}
h1 {{ margin: 0 0 8px; }} .warning {{ color: #a12622; font-weight: 700; }}
dl {{ display: grid; grid-template-columns: max-content minmax(240px, 1fr); gap: 5px 14px; }} dt {{ font-weight: 700; }} dd {{ margin: 0; }}
.scroll {{ overflow-x: auto; padding: 0 20px 20px; }}
table {{ border-collapse: separate; border-spacing: 8px; min-width: {220 + 500 * len(quarters)}px; table-layout: fixed; }}
th, td {{ background: white; border: 1px solid #d9dee7; vertical-align: top; padding: 10px; }}
thead th {{ text-align: left; }} thead th span {{ display: block; margin-top: 4px; font-size: 13px; font-weight: 400; }}
.row-label {{ width: 190px; text-align: left; position: sticky; left: 0; z-index: 1; }}
td {{ width: 480px; }} img {{ display: block; width: 100%; height: auto; object-fit: contain; }}
.cell-meta {{ display: block; margin-top: 8px; font-size: 13px; }}
.notes-grid {{ display: grid; grid-template-columns: repeat(2, minmax(360px, 1fr)); gap: 14px; }}
.note label {{ display: block; font-weight: 700; margin-bottom: 5px; }} .blank {{ height: 70px; border: 1px solid #b9c1cd; background: #fff; }}
a {{ color: #174ea6; }}
</style></head><body>
<header><h1>{html.escape(year_label)} Pair Observation</h1><p class="warning">{html.escape(LABEL)}</p><dl>{_header(config, year_label, provider_id, provider_version)}</dl></header>
<main class="scroll"><table><thead><tr><th class="row-label">Plot type</th>{''.join(quarter_headers)}</tr></thead><tbody>{''.join(body_rows)}</tbody></table></main>
<section class="notes"><h2>Manual observation notes</h2><p>Intentionally blank; no automated interpretation is provided.</p><div class="notes-grid">{notes}</div></section>
</body></html>"""


def _index_html(config: RunConfig, report_names: list[tuple[str, str]]) -> str:
    reports = "".join(f'<li><a href="{html.escape(filename)}">{html.escape(label)}</a></li>' for label, filename in report_names)
    plots = "".join(f'<li><a href="../{filename}">{html.escape(label)}</a></li>' for label, filename in PLOT_ROWS)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pair observation report index</title><style>body{{font-family:Arial,sans-serif;max-width:900px;margin:40px auto;line-height:1.5}}.warning{{color:#a12622;font-weight:700}}</style></head>
<body><h1>{config.ticker_a} / {config.ticker_b} Pair Observation Reports</h1><p class="warning">{html.escape(LABEL)}</p><h2>Annual reports</h2><ul>{reports}</ul><h2>Full-period plots</h2><ul>{plots}</ul></body></html>"""


def generate_reports(output: Path, config: RunConfig, provider_id: str, provider_version: str) -> list[Path]:
    """Build HTML only from existing plot and descriptive artifact files."""
    reports_dir = output / "reports"
    reports_dir.mkdir()
    metadata = _quarter_metadata(output)
    report_names: list[tuple[str, str]] = []
    artifacts: list[Path] = []
    years = sorted({int(quarter[:4]) for quarter in metadata})
    for year in years:
        available = [f"{year}Q{number}" for number in range(1, 5) if f"{year}Q{number}" in metadata]
        full_requested_year = config.start <= date(year, 1, 1) and config.end >= date(year, 12, 31)
        if full_requested_year and len(available) == 4:
            label, filename = str(year), f"{year}_pair_observation.html"
        elif year == config.end.year and config.end < date(year, 12, 31):
            label, filename = f"{year} YTD — INCOMPLETE CALENDAR YEAR", f"{year}_YTD_pair_observation.html"
        else:
            continue
        path = reports_dir / filename
        path.write_text(_annual_html(output, config, label, available, metadata, provider_id, provider_version), encoding="utf-8")
        report_names.append((label, filename)); artifacts.append(path)
    index = reports_dir / "index.html"
    index.write_text(_index_html(config, report_names), encoding="utf-8")
    return [index, *artifacts]
