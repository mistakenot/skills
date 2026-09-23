"""Open-coding notes: an append-only event log, folded into current state.

`data/notes.jsonl` is never rewritten. Every change the reviewer makes is one
line, so the file is the full history of how their reading of the corpus
developed — which is exactly the evidence axial coding and, later, judge
validation need. Current state is a fold over the events.

Event kinds:

  note.create  {id, plan_id, tab, quote, prefix, suffix, text}
               A span note. The span is anchored by its quoted text plus a
               little context either side and the pd-tab it sits in — not by
               character offsets, which a re-render or a hidden tab breaks.
  note.update  {id, text}
  note.delete  {id}
  verdict      {plan_id, verdict: pass|fail|defer, text}
               The whole-plan judgement. Latest wins.

Every event also carries `ts` and `reviewer`, stamped by the server.
"""

from __future__ import annotations

import datetime as _dt
import json
import threading
import uuid
from pathlib import Path

VERDICTS = ("pass", "fail", "defer")
_lock = threading.Lock()


class EventError(ValueError):
    """An event the log refuses."""


def _str(ev: dict, key: str, *, allow_empty: bool = False, limit: int = 20000) -> str:
    v = ev.get(key)
    if not isinstance(v, str) or (not allow_empty and not v.strip()):
        raise EventError(f"{ev.get('event')}: {key} must be a non-empty string")
    if len(v) > limit:
        raise EventError(f"{ev.get('event')}: {key} is longer than {limit} characters")
    return v


def validate(ev: dict, plan_ids: set[str], reviewer: str) -> dict:
    """A clean copy of `ev`, stamped; raises EventError if it cannot be logged."""
    if not isinstance(ev, dict):
        raise EventError("event must be an object")
    kind = ev.get("event")
    out: dict = {"event": kind}
    if kind == "note.create":
        out["id"] = ev.get("id") or uuid.uuid4().hex[:12]
        out["plan_id"] = _str(ev, "plan_id")
        out["tab"] = ev.get("tab") if isinstance(ev.get("tab"), str) else ""
        out["quote"] = _str(ev, "quote", limit=4000)
        out["prefix"] = _str(ev, "prefix", allow_empty=True, limit=200)
        out["suffix"] = _str(ev, "suffix", allow_empty=True, limit=200)
        out["text"] = _str(ev, "text")
    elif kind == "note.update":
        out["id"] = _str(ev, "id")
        out["text"] = _str(ev, "text")
    elif kind == "note.delete":
        out["id"] = _str(ev, "id")
    elif kind == "verdict":
        out["plan_id"] = _str(ev, "plan_id")
        if ev.get("verdict") not in VERDICTS:
            raise EventError(f"verdict must be one of {VERDICTS}")
        out["verdict"] = ev["verdict"]
        out["text"] = _str(ev, "text", allow_empty=True)
    else:
        raise EventError(f"unknown event kind {kind!r}")
    if "plan_id" in out and out["plan_id"] not in plan_ids:
        raise EventError(f"unknown plan {out['plan_id']!r}")
    out["ts"] = _dt.datetime.now().astimezone().isoformat(timespec="milliseconds")
    out["reviewer"] = reviewer
    return out


def append(ev: dict, path: Path) -> None:
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as f:
            f.write(json.dumps(ev) + "\n")


def load(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def fold(events: list[dict]) -> dict:
    """`{"notes": [...live notes...], "verdicts": {plan_id: verdict}}`."""
    notes: dict[str, dict] = {}
    verdicts: dict[str, dict] = {}
    for ev in events:
        kind = ev.get("event")
        if kind == "note.create":
            notes[ev["id"]] = {k: ev[k] for k in (
                "id", "plan_id", "tab", "quote", "prefix", "suffix", "text", "reviewer")}
            notes[ev["id"]]["created"] = notes[ev["id"]]["updated"] = ev["ts"]
        elif kind == "note.update" and ev["id"] in notes:
            notes[ev["id"]]["text"] = ev["text"]
            notes[ev["id"]]["updated"] = ev["ts"]
        elif kind == "note.delete":
            notes.pop(ev["id"], None)
        elif kind == "verdict":
            verdicts[ev["plan_id"]] = {"verdict": ev["verdict"], "text": ev["text"],
                                       "ts": ev["ts"], "reviewer": ev["reviewer"]}
    return {"notes": list(notes.values()), "verdicts": verdicts}
