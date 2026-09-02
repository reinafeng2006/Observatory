from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from .core import RunConfig, run
from .provider import AkShareQfqProvider


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="EXPLORATORY manual A-share pair observation; not a trading signal")
    p.add_argument("ticker_a"); p.add_argument("ticker_b")
    p.add_argument("--start", required=True, type=date.fromisoformat)
    p.add_argument("--end", required=True, type=date.fromisoformat)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--cache", type=Path, default=Path("cache/raw"))
    p.add_argument("--event-threshold", type=float, default=0.03)
    p.add_argument("--event-window", type=int, default=5)
    p.add_argument("--offline", action="store_true")
    p.add_argument("--company-context", type=Path, help="Optional sourced quarter-level company context CSV")
    p.add_argument("--event-context", type=Path, help="Optional sourced dated event context CSV")
    return p


def main() -> None:
    args = parser().parse_args()
    config = RunConfig(args.ticker_a, args.ticker_b, args.start, args.end, args.event_threshold, args.event_window)
    manifest = run(config, AkShareQfqProvider(), args.cache, args.output, args.offline, args.company_context, args.event_context)
    print(f"EXPLORATORY output written: {manifest}")


if __name__ == "__main__":
    main()
