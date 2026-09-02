from __future__ import annotations

import argparse
import json
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .human_notes import CHART_TYPES, HumanObservationStore, build_provenance
from .note_analysis import analyze_note


class ObservatoryHandler(SimpleHTTPRequestHandler):
    server_version = "ObservatoryLocal/1"

    def __init__(self, *args, output: Path, store: HumanObservationStore, manifest: dict, default_author: str, **kwargs):
        self.output, self.store, self.manifest, self.default_author = output, store, manifest, default_author
        super().__init__(*args, directory=str(output), **kwargs)

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/observations":
            query = parse_qs(parsed.query)
            chart = query.get("chart_type", [None])[0]
            if chart == "": chart = None
            records = self.store.latest(query.get("pair_id", [None])[0], query.get("quarter", [None])[0], query.get("target_scope", [None])[0], chart)
            self._json(HTTPStatus.OK, {"records": records}); return
        if parsed.path == "/api/status":
            self._json(HTTPStatus.OK, {"status": "ready", "storage": str(self.store.path), "editing": True}); return
        if parsed.path == "/":
            self.send_response(HTTPStatus.FOUND); self.send_header("Location", "/reports/index.html"); self.end_headers(); return
        super().do_GET()

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/observations":
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"}); return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1_000_000: raise ValueError("Invalid request size")
            draft = json.loads(self.rfile.read(length))
            expected_pair = f"{self.manifest['config']['ticker_a']}/{self.manifest['config']['ticker_b']}"
            if draft.get("pair_id") != expected_pair: raise ValueError("pair_id does not match the served run")
            if draft.get("target_scope") not in {"chart", "quarter"}: raise ValueError("Unsupported target_scope")
            if draft["target_scope"] == "chart" and draft.get("chart_type") not in CHART_TYPES: raise ValueError("Unsupported chart_type")
            if draft["target_scope"] == "quarter": draft["chart_type"] = None
            draft.setdefault("author", self.default_author)
            available = {record["period"] for record in json.loads((self.output / "machine_measurements.json").read_text(encoding="utf-8"))["records"]}
            if draft.get("quarter") not in available: raise ValueError("Quarter is not part of the served run")
            provenance = build_provenance(self.output, self.manifest, draft["quarter"], draft["target_scope"], draft.get("chart_type"))
            raw_note = draft.get("raw_note", draft.get("observation_text", ""))
            if not isinstance(raw_note, str): raise ValueError("raw_note must be a string")
            draft["raw_note"] = raw_note
            derived = analyze_note(raw_note, self.output, draft["quarter"], provenance)
            record = self.store.save(draft, provenance, derived)
            self._json(HTTPStatus.OK, {"record": record})
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})


def create_server(output: Path, notes_path: Path, host: str = "127.0.0.1", port: int = 8765, author: str = "") -> ThreadingHTTPServer:
    if host not in {"127.0.0.1", "localhost", "::1"}: raise ValueError("Observatory notes server may bind only to localhost")
    output = output.resolve(); notes_path = notes_path.resolve()
    if output == notes_path or output in notes_path.parents: raise ValueError("Human notes must be stored outside generated output artifacts")
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    handler = partial(ObservatoryHandler, output=output, store=HumanObservationStore(notes_path), manifest=manifest, default_author=author)
    return ThreadingHTTPServer((host, port), handler)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Serve an Observatory report locally with durable human-note input")
    value.add_argument("--output", required=True, type=Path); value.add_argument("--notes", required=True, type=Path)
    value.add_argument("--host", default="127.0.0.1"); value.add_argument("--port", default=8765, type=int)
    value.add_argument("--author", default="", help="Optional author bound to newly saved notes")
    return value


def main() -> None:
    args = parser().parse_args(); server = create_server(args.output, args.notes, args.host, args.port, args.author)
    print(f"Observatory local report: http://{args.host}:{server.server_port}/reports/index.html")
    print(f"Human notes JSONL: {args.notes.resolve()}")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()


if __name__ == "__main__": main()
