"""The corpus: every generated plan the review tool can show.

A plan enters the corpus by being *ingested* from a planning-eval-harbor run
(`ingest_run`): each trial's `produced/docs/tasks/*/plan.html` becomes one
entry, keyed by the content hash of that file. Entries live in
`runs/corpus.jsonl` — local and gitignored, like the Harbor runs they point at.

A plan becomes durable the first time a reviewer opens it (`snapshot`): the
plan, its `context.md` and its corpus entry are copied into
`data/plans/<plan_id>/`, which is committed. Generation is not repeatable, so
a note is only meaningful while the exact document it annotates still exists;
the snapshot is what guarantees that after runs are cleaned.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
DATA_DIR = HERE / "data"
RUNS_DIR = HERE / "runs"
HARBOR_RUNS = REPO_ROOT / "src" / "planning-eval-harbor" / "runs"
PD_LINT = REPO_ROOT / "skills" / "rich-doc" / "scripts" / "pd-lint.mjs"

# Appended to every plan-review fixture prompt: new-task-quick runs straight on
# into a Codex review when it raises no open questions, and the corpus is the
# plan as the first gate presents it. Stripped again for display.
STOP_SUFFIX = "Stop after Stage 4 (self-check); do not run the Codex review."

_OPEN_Q = re.compile(r"<pd-question\b[^>]*\bstatus=\"open\"", re.I)
_QUESTION = re.compile(r"<pd-question\b", re.I)


def plan_id(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:12]


def _now() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def display_prompt(prompt: str) -> str:
    p = prompt.strip()
    if p.endswith(STOP_SUFFIX):
        p = p[: -len(STOP_SUFFIX)].rstrip()
    return p


# --- automated checks on one produced plan ----------------------------------


def lint(plan: Path) -> dict | None:
    """pd-lint's verdict, or None when node/the linter is unavailable."""
    if not PD_LINT.is_file() or not shutil.which("node"):
        return None
    res = subprocess.run(["node", str(PD_LINT), str(plan)], capture_output=True, text=True)
    try:
        out = json.loads(res.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "codes": ["lint-crashed"], "blocking": ["lint-crashed"]}
    codes = sorted({i.get("code", "?") for i in out.get("issues", [])})
    # `open-question` is the gate new-task-quick stops at, not a defect.
    return {"ok": out.get("ok", False), "codes": codes,
            "blocking": [c for c in codes if c != "open-question"]}


def codex_ran(trial_dir: Path, result: dict) -> bool:
    """Did the run go past the stop line into the Codex review?"""
    for turn in result.get("turns", []):
        if any("codex" in (s or "") for s in turn.get("skill_calls", [])):
            return True
    for stream in trial_dir.glob("steps/*/agent/claude-code.txt"):
        text = stream.read_text(errors="replace")
        if "codex exec" in text or "codex review" in text:
            return True
    return False


# --- ingest -------------------------------------------------------------------


def ingest_run(run_dir: Path) -> list[dict]:
    """One corpus entry per plan.html produced by any trial of a Harbor run."""
    meta = _read_json(run_dir / "peval.json")
    if meta is None:
        raise ValueError(f"{run_dir} is not a planning-eval-harbor run (no peval.json)")
    entries: list[dict] = []
    for trial in sorted(p for p in run_dir.iterdir() if (p / "peval-result.json").is_file()):
        result = _read_json(trial / "peval-result.json") or {}
        produced = trial / "produced"
        for plan in sorted(produced.glob("docs/tasks/*/plan.html")):
            content = plan.read_bytes()
            text = content.decode("utf-8", errors="replace")
            ctx = plan.parent / "context.md"
            velocity = result.get("velocity") or {}
            entries.append({
                "plan_id": plan_id(content),
                "fixture_id": meta.get("fixture_id"),
                "prompt": (meta.get("messages") or [""])[0],
                "target": meta.get("repo_url") or meta.get("target_repo"),
                "start_sha": meta.get("start_sha"),
                "arm_id": meta.get("arm_id"),
                "skills_sha": meta.get("skills_sha"),
                "model": meta.get("model"),
                "run": run_dir.name,
                "trial": trial.name,
                "completion": result.get("completion"),
                "cost_usd": velocity.get("total_cost_usd"),
                "wall_ms": result.get("total_wall_ms"),
                "task_dir": str(plan.parent.relative_to(produced)),
                "plan_path": str(plan),
                "context_path": str(ctx) if ctx.is_file() else None,
                "transcript_path": str(trial / "transcript.txt") if (trial / "transcript.txt").is_file() else None,
                "checks": {
                    "questions": len(_QUESTION.findall(text)),
                    "open_questions": len(_OPEN_Q.findall(text)),
                    "codex_ran": codex_ran(trial, result),
                    "lint": lint(plan),
                },
                "ingested_at": _now(),
            })
    return entries


def add(entries: list[dict], runs_dir: Path = RUNS_DIR) -> list[dict]:
    """Append entries not already in the corpus; returns the ones added."""
    known = set(load(runs_dir=runs_dir, data_dir=None))
    fresh = [e for e in entries if e["plan_id"] not in known]
    if fresh:
        runs_dir.mkdir(parents=True, exist_ok=True)
        with (runs_dir / "corpus.jsonl").open("a") as f:
            for e in fresh:
                f.write(json.dumps(e) + "\n")
    return fresh


def load(runs_dir: Path = RUNS_DIR, data_dir: Path | None = DATA_DIR) -> dict[str, dict]:
    """plan_id -> entry: the local corpus, overlaid by committed snapshots.

    A snapshot's meta wins, and its paths point into `data/plans/`, so a plan
    stays reviewable after its Harbor run is gone.
    """
    out: dict[str, dict] = {}
    corpus = runs_dir / "corpus.jsonl"
    if corpus.is_file():
        for line in corpus.read_text().splitlines():
            if line.strip():
                e = json.loads(line)
                out[e["plan_id"]] = e
    if data_dir is not None and (data_dir / "plans").is_dir():
        for meta in sorted((data_dir / "plans").glob("*/meta.json")):
            e = _read_json(meta)
            if e:
                out[e["plan_id"]] = e
    return out


def snapshot(entry: dict, data_dir: Path = DATA_DIR) -> dict:
    """Copy a plan into `data/plans/<plan_id>/` (once) and return the durable entry."""
    dest = data_dir / "plans" / entry["plan_id"]
    meta_path = dest / "meta.json"
    if meta_path.is_file():
        return json.loads(meta_path.read_text())
    dest.mkdir(parents=True, exist_ok=True)
    snap = dict(entry)
    shutil.copyfile(entry["plan_path"], dest / "plan.html")
    snap["plan_path"] = _stored(dest / "plan.html")
    if entry.get("context_path") and Path(entry["context_path"]).is_file():
        shutil.copyfile(entry["context_path"], dest / "context.md")
        snap["context_path"] = _stored(dest / "context.md")
    # The transcript is not copied (it can run to megabytes); it stays a pointer
    # into the Harbor run and is simply unavailable once that run is cleaned.
    snap["snapshot_at"] = _now()
    meta_path.write_text(json.dumps(snap, indent=2) + "\n")
    return snap


def _stored(path: Path) -> str:
    """Repo-relative inside the repo, so committed metas work in any checkout."""
    return str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path)


def resolve(path: str | None) -> Path | None:
    """A stored path — absolute, or repo-relative for committed snapshots."""
    if not path:
        return None
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p
