"""The review server: stdlib only, one process, localhost by default.

    GET  /                          the app (app/index.html)
    GET  /app/<file>                app assets
    GET  /api/plans                 the corpus in review order — blind: no arm, trial, model or cost
    GET  /api/plans/<id>            one plan's request text and which side files exist
    GET  /plan/<id>/plan.html       the plan itself; the first request snapshots it into data/
    GET  /plan/<id>/context.md      its context.md, if the run wrote one
    GET  /plan/<id>/transcript.txt  the run transcript, while the Harbor run still exists
    GET  /api/state                 folded notes + verdicts
    POST /api/events                append one note/verdict event (see notes.py)
    GET  /api/log                   the agent's open-coding log (data/open-coding-log.jsonl)

Review order is by plan_id — a content hash, so effectively shuffled across
fixtures and skill versions, and stable between sessions.
"""

from __future__ import annotations

import json
import mimetypes
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import corpus
import notes

APP_DIR = Path(__file__).resolve().parent / "app"
_PLAN_ROUTE = re.compile(r"^/plan/([0-9a-f]{12})/(plan\.html|context\.md|transcript\.txt)$")
_PLAN_API = re.compile(r"^/api/plans/([0-9a-f]{12})$")


class Review:
    """Server state: where the corpus and notes live, and who is reviewing."""

    def __init__(self, runs_dir: Path, data_dir: Path, reviewer: str):
        self.runs_dir = runs_dir
        self.data_dir = data_dir
        self.reviewer = reviewer

    @property
    def notes_path(self) -> Path:
        return self.data_dir / "notes.jsonl"

    def plans(self) -> dict[str, dict]:
        return corpus.load(self.runs_dir, self.data_dir)

    def state(self) -> dict:
        return notes.fold(notes.load(self.notes_path))

    def plan_list(self) -> list[dict]:
        state = self.state()
        counts: dict[str, int] = {}
        for n in state["notes"]:
            counts[n["plan_id"]] = counts.get(n["plan_id"], 0) + 1
        out = []
        for i, (pid, e) in enumerate(sorted(self.plans().items())):
            v = state["verdicts"].get(pid)
            out.append({
                "plan_id": pid,
                "n": i + 1,
                "fixture_id": e.get("fixture_id"),
                "verdict": v["verdict"] if v else None,
                "notes": counts.get(pid, 0),
                "snapshotted": (self.data_dir / "plans" / pid / "meta.json").is_file(),
            })
        return out

    def plan_detail(self, pid: str) -> dict | None:
        e = self.plans().get(pid)
        if e is None:
            return None
        return {
            "plan_id": pid,
            "fixture_id": e.get("fixture_id"),
            "prompt": corpus.display_prompt(e.get("prompt") or ""),
            "has_context": _exists(e.get("context_path")),
            "has_transcript": _exists(e.get("transcript_path")),
        }

    def plan_file(self, pid: str, name: str) -> Path | None:
        e = self.plans().get(pid)
        if e is None:
            return None
        if name == "plan.html":
            # Opening a plan is what makes it durable (see corpus.snapshot).
            e = corpus.snapshot(e, self.data_dir)
            return corpus.resolve(e["plan_path"])
        key = {"context.md": "context_path", "transcript.txt": "transcript_path"}[name]
        p = corpus.resolve(e.get(key))
        return p if p and p.is_file() else None

    def log(self) -> list[dict]:
        return notes.load(self.data_dir / "open-coding-log.jsonl")


def _exists(stored: str | None) -> bool:
    p = corpus.resolve(stored)
    return bool(p and p.is_file())


def make_handler(review: Review) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "plan-review/1"

        def log_message(self, fmt: str, *args) -> None:  # quiet: the agent tails notes, not HTTP
            pass

        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, status: int = 200) -> None:
            self._send(status, json.dumps(obj).encode(), "application/json")

        def _file(self, path: Path) -> None:
            ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            if path.suffix in (".md", ".txt"):
                ctype = "text/plain"
            if ctype.startswith("text/") or ctype in ("application/javascript",):
                ctype += "; charset=utf-8"
            self._send(200, path.read_bytes(), ctype)

        def _missing(self) -> None:
            self._json({"error": "not found"}, HTTPStatus.NOT_FOUND)

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path == "/":
                return self._file(APP_DIR / "index.html")
            if path.startswith("/app/"):
                p = (APP_DIR / path[len("/app/"):]).resolve()
                return self._file(p) if p.is_relative_to(APP_DIR) and p.is_file() else self._missing()
            if path == "/api/plans":
                return self._json(review.plan_list())
            if m := _PLAN_API.match(path):
                d = review.plan_detail(m.group(1))
                return self._json(d) if d else self._missing()
            if m := _PLAN_ROUTE.match(path):
                p = review.plan_file(m.group(1), m.group(2))
                return self._file(p) if p else self._missing()
            if path == "/api/state":
                return self._json(review.state())
            if path == "/api/log":
                return self._json(review.log())
            return self._missing()

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/api/events":
                return self._missing()
            try:
                length = int(self.headers.get("Content-Length") or 0)
                ev = json.loads(self.rfile.read(length) or b"null")
                clean = notes.validate(ev, set(review.plans()), review.reviewer)
            except (ValueError, notes.EventError) as exc:
                return self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            notes.append(clean, review.notes_path)
            return self._json({"ok": True, "event": clean})

    return Handler


def serve(review: Review, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(review))
