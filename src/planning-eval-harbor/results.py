"""Turn a finished Harbor job into the record a reader actually wants.

Harbor leaves a trial directory full of evidence — per-step stream-json
transcripts, native session files, ATIF trajectories, collected artifacts, its
own result.json and lock.json. This module reads all of that and writes, next
to it, the same three things `src/planning-eval/` produces for a run:

    <trial>/peval-result.json   turns, velocity, produced files (planning-eval's schema)
    <trial>/transcript.txt      per turn: what was sent, what came back
    <trial>/produced/           only the files the run created or changed

plus `<run>/summary.json` across trials. Nothing here judges anything. The
one automated check is `adherence`, for the simulated operator: did it send
the script verbatim? An operator that paraphrased or skipped a turn makes the
run a different experiment, and nothing else would tell you.

Everything is read tolerantly: a trial that died halfway must still summarise,
visibly incomplete, rather than make the run directory unreadable.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import posixpath
import re
import shutil
import tarfile
from pathlib import Path

STREAM_NAME = "claude-code.txt"
RESULT_NAME = "peval-result.json"
SUMMARY_NAME = "summary.json"
META_NAME = "peval.json"

# --- small readers --------------------------------------------------------


def read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def read_stream(path: Path) -> list[dict]:
    """A stream-json transcript, skipping blank and unparseable lines."""
    events: list[dict] = []
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return events
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(ev, dict):
            events.append(ev)
    return events


def _ts(value: str | None) -> _dt.datetime | None:
    if not value:
        return None
    try:
        return _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _span_ms(timing: dict | None) -> int | None:
    if not timing:
        return None
    a, b = _ts(timing.get("started_at")), _ts(timing.get("finished_at"))
    if a is None or b is None:
        return None
    return int((b - a).total_seconds() * 1000)


# --- one Claude Code invocation (a scripted step) ------------------------


def _usage_tokens(usage: dict | None) -> dict:
    u = usage or {}
    n = lambda k: int(u.get(k) or 0)  # noqa: E731
    out = {
        "input": n("input_tokens"),
        "output": n("output_tokens"),
        "cache_read": n("cache_read_input_tokens"),
        "cache_creation": n("cache_creation_input_tokens"),
    }
    out["total"] = sum(out.values())
    return out


def stream_summary(events: list[dict]) -> dict:
    """What one `claude -p` run said and cost, from its stream-json events."""
    init = next((e for e in events if e.get("type") == "system" and e.get("subtype") == "init"), {})
    result = next((e for e in reversed(events) if e.get("type") == "result"), {})
    skill_calls: list[str] = []
    tool_calls = 0
    said: list[str] = []
    for e in events:
        if e.get("type") != "assistant":
            continue
        for block in (e.get("message") or {}).get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                tool_calls += 1
                if block.get("name") == "Skill":
                    skill_calls.append(str((block.get("input") or {}).get("skill", "")))
            elif block.get("type") == "text" and str(block.get("text", "")).strip():
                said.append(str(block["text"]).strip())
    # Everything the agent said this turn, not only its closing message: a
    # planning turn narrates what it read and decided before it stops, and
    # `result` holds the last message alone.
    reply = "\n\n".join(said) if said else (result.get("result") or "")
    return {
        "session_id": result.get("session_id") or init.get("session_id"),
        "registered_skills": list(init.get("skills") or []),
        "reply": reply,
        "final": result.get("result") or "",
        "is_error": bool(result.get("is_error")),
        "subtype": result.get("subtype"),
        "cost_usd": result.get("total_cost_usd"),
        "num_turns": result.get("num_turns"),
        "duration_ms": result.get("duration_ms"),
        "tokens": _usage_tokens(result.get("usage")),
        "tool_calls": tool_calls,
        "skill_calls": skill_calls,
        "has_result": bool(result),
    }


# --- native session files (the target's own record) ----------------------


def _text_of(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "\n".join(parts)
    return ""


def _is_operator_message(ev: dict) -> bool:
    """A `user` event that is a message from the operator, not a tool result."""
    if ev.get("type") != "user" or ev.get("isSidechain") or ev.get("isMeta"):
        return False
    content = (ev.get("message") or {}).get("content")
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        return bool(content) and all(
            isinstance(b, dict) and b.get("type") == "text" for b in content
        )
    return False


def session_turns(session_file: Path) -> list[dict]:
    """Operator message → assistant text pairs, in order, from a session jsonl."""
    turns: list[dict] = []
    for ev in read_stream(session_file):
        if _is_operator_message(ev):
            turns.append({"sent": _text_of(ev["message"]["content"]), "reply_parts": []})
        elif ev.get("type") == "assistant" and turns and not ev.get("isSidechain"):
            text = _text_of((ev.get("message") or {}).get("content"))
            if text.strip():
                turns[-1]["reply_parts"].append(text)
    for t in turns:
        t["reply"] = "\n".join(t.pop("reply_parts")).strip()
    return turns


def session_tokens(sessions_root: Path) -> dict:
    """Token totals across every session file under a role's config dir —
    parent and subagents alike — deduplicated by API message id."""
    seen: set[str] = set()
    totals = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
    files = sorted(sessions_root.rglob("*.jsonl")) if sessions_root.is_dir() else []
    for f in files:
        for ev in read_stream(f):
            if ev.get("type") != "assistant":
                continue
            msg = ev.get("message") or {}
            mid = msg.get("id")
            if mid:
                if mid in seen:
                    continue
                seen.add(mid)
            u = _usage_tokens(msg.get("usage"))
            for k in totals:
                totals[k] += u[k]
    return {**totals, "total": sum(totals.values()), "session_files": len(files)}


# --- what the run produced ------------------------------------------------


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _tar_name(member: tarfile.TarInfo) -> str:
    return member.name[2:] if member.name.startswith("./") else member.name


def seed_hashes(seed_tar: Path) -> dict[str, str]:
    """`relative path -> sha256` for every file in the seed tree.

    Symlinks are hashed through their target: `git archive` stores
    `AGENTS.md -> CLAUDE.md` as a link, but the tree Harbor collects back from
    the sandbox has it as a regular file with CLAUDE.md's content, and that is
    not something the run produced.
    """
    out: dict[str, str] = {}
    links: list[tuple[str, str]] = []
    with tarfile.open(seed_tar) as tf:
        for member in tf:
            name = _tar_name(member)
            if member.issym():
                target = posixpath.normpath(posixpath.join(posixpath.dirname(name), member.linkname))
                links.append((name, target))
                continue
            if not member.isfile():
                continue
            fh = tf.extractfile(member)
            if fh is None:
                continue
            out[name] = hashlib.sha256(fh.read()).hexdigest()
    for name, target in links:
        if target in out:
            out[name] = out[target]
    return out


def produced_files(app_dir: Path, seed: dict[str, str]) -> tuple[list[str], list[str]]:
    """(added-or-changed, deleted) relative to the seed, ignoring git internals."""
    produced: list[str] = []
    present: set[str] = set()
    if app_dir.is_dir():
        for p in sorted(app_dir.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(app_dir).as_posix()
            if rel == ".git" or rel.startswith(".git/"):
                continue
            present.add(rel)
            if seed.get(rel) != _sha256(p):
                produced.append(rel)
    deleted = sorted(set(seed) - present) if app_dir.is_dir() else []
    return produced, deleted


def copy_produced(app_dir: Path, files: list[str], dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    for rel in files:
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(app_dir / rel, target)


# --- adherence (simulated operator) --------------------------------------


_COMMAND_RE = re.compile(
    r"<command-name>(?P<name>[^<]*)</command-name>(?:\s*<command-args>(?P<args>[^<]*)</command-args>)?",
    re.S,
)


def _norm(text: str) -> str:
    """Compare what the operator meant to send with what the session recorded.

    Claude Code stores a slash command as `<command-message>…</command-message>
    <command-name>/x</command-name>[<command-args>…</command-args>]`, and a
    simulated operator quoting for a shell may escape backticks or dollars.
    Neither is a divergence.
    """
    m = _COMMAND_RE.search(text)
    if m:
        text = f"{m.group('name').strip()} {(m.group('args') or '').strip()}"
    text = re.sub(r"\\([`$\"\\])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def adherence(expected: list[str], sent: list[str]) -> dict:
    """Did the simulated operator send the script, verbatim, in order?"""
    rows = []
    for i, exp in enumerate(expected):
        got = sent[i] if i < len(sent) else None
        rows.append({
            "i": i,
            "expected": exp,
            "sent": got,
            "verbatim": got is not None and _norm(got) == _norm(exp),
        })
    extra = sent[len(expected):]
    return {
        "expected_count": len(expected),
        "sent_count": len(sent),
        "extra_messages": extra,
        "all_verbatim": all(r["verbatim"] for r in rows) and not extra,
        "turns": rows,
    }


# --- trial ----------------------------------------------------------------


def _artifact_app_dir(trial_dir: Path, steps: list[str]) -> Path | None:
    """Where Harbor put the final `/app` tree.

    A single-step trial collects to `<trial>/artifacts/app`; a multi-step one
    collects run-level artifacts *per step* under `steps/<name>/artifacts/`,
    so the final state is the last step that has one.
    """
    top = trial_dir / "artifacts" / "app"
    if top.is_dir():
        return top
    for name in reversed(steps):
        cand = trial_dir / "steps" / name / "artifacts" / "app"
        if cand.is_dir():
            return cand
    return None


def _step_result(harbor: dict, name: str) -> dict:
    for s in harbor.get("step_results") or []:
        if isinstance(s, dict) and (s.get("step_name") == name or s.get("name") == name):
            return s
    return {}


def summarize_trial(run_dir: Path, trial_dir: Path, meta: dict, seed: dict[str, str]) -> dict:
    """Write `peval-result.json`, `transcript.txt` and `produced/` for one trial."""
    harbor = read_json(trial_dir / "result.json") or {}
    operator = meta["operator"]
    shown = list(meta["messages"])
    steps = list(meta.get("steps") or [])
    exc = harbor.get("exception_info")
    turns: list[dict] = []
    adh: dict | None = None
    velocity: dict

    if operator == "scripted":
        for i, name in enumerate(steps):
            stream = trial_dir / "steps" / name / "agent" / STREAM_NAME
            if not stream.is_file():
                break
            s = stream_summary(read_stream(stream))
            step = _step_result(harbor, name)
            step_app = trial_dir / "steps" / name / "artifacts" / "app"
            produced_here, _ = produced_files(step_app, seed) if step_app.is_dir() else ([], [])
            turns.append({
                "i": i,
                "step": name,
                "sent": shown[i] if i < len(shown) else None,
                "reply": s["reply"],
                "wall_ms": _span_ms(step.get("agent_execution")) or s["duration_ms"],
                "cost_usd": s["cost_usd"],
                "tokens": s["tokens"],
                "num_turns": s["num_turns"],
                "tool_calls": s["tool_calls"],
                "skill_calls": s["skill_calls"],
                "is_error": s["is_error"],
                "session_id": s["session_id"],
                "produced_so_far": produced_here,
            })
        sessions = trial_dir / "steps" / steps[-1] / "agent" / "sessions" if steps else trial_dir
        stoks = session_tokens(sessions / "projects") if sessions.is_dir() else {}
        cost = sum(t["cost_usd"] or 0 for t in turns)
        toks = {k: sum((t["tokens"] or {}).get(k, 0) for t in turns)
                for k in ("input", "output", "cache_read", "cache_creation", "total")}
        velocity = {
            "available": bool(turns),
            "source": "stream-json result events, one per step",
            "total_cost_usd": round(cost, 6),
            "tokens": toks,
            "session_tokens": stoks,
            "agent_wall_ms": sum(t["wall_ms"] or 0 for t in turns),
        }
        if exc:
            completion = f"error: {exc.get('exception_type', 'Exception')}: {exc.get('exception_message', '')}".strip()
        elif len(turns) < len(steps):
            completion = "capped"
        elif any(t["is_error"] for t in turns):
            completion = "error: a step ended in an error result"
        else:
            completion = "ok"
    else:
        sessions = trial_dir / "agent" / "sessions" / "projects"
        session_files = sorted(p for p in sessions.rglob("*.jsonl") if "subagents" not in p.parts) if sessions.is_dir() else []
        recorded = session_turns(session_files[0]) if session_files else []
        adh = adherence(list(meta.get("messages_full") or shown), [t["sent"] for t in recorded])
        for i, t in enumerate(recorded):
            turns.append({"i": i, "sent": t["sent"], "reply": t["reply"]})
        target_tokens = session_tokens(sessions)
        user = harbor.get("agent_result") or {}
        velocity = {
            "available": bool(session_files),
            "source": "target: native session usage; operator: harbor agent_result",
            "target_tokens": target_tokens,
            "operator_cost_usd": user.get("cost_usd"),
            "operator_tokens": {
                "input": user.get("n_input_tokens"), "output": user.get("n_output_tokens"),
                "cache": user.get("n_cache_tokens"),
            },
            "agent_wall_ms": _span_ms(harbor.get("agent_execution")),
        }
        if exc:
            completion = f"error: {exc.get('exception_type', 'Exception')}: {exc.get('exception_message', '')}".strip()
        elif not adh["all_verbatim"]:
            completion = "diverged"
        else:
            completion = "ok"

    app_dir = _artifact_app_dir(trial_dir, steps)
    produced, deleted = produced_files(app_dir, seed) if app_dir else ([], [])
    if app_dir and produced:
        copy_produced(app_dir, produced, trial_dir / "produced")

    result = {
        "trial": trial_dir.name,
        "run": run_dir.name,
        "fixture_id": meta.get("fixture_id"),
        "arm_id": meta.get("arm_id"),
        "operator": operator,
        "target_repo": meta.get("target_repo"),
        "start_sha": meta.get("start_sha"),
        "model": meta.get("model"),
        "completion": completion,
        "total_wall_ms": _span_ms({"started_at": harbor.get("started_at"), "finished_at": harbor.get("finished_at")}),
        "environment_setup_ms": _span_ms(harbor.get("environment_setup")),
        "agent_setup_ms": _span_ms(harbor.get("agent_setup")),
        "turn_count": len(turns),
        "artifacts": produced,
        "deleted": deleted,
        "turns": turns,
        "velocity": velocity,
        "adherence": adh,
        "harbor": {
            "trial_dir": str(trial_dir),
            "artifacts_dir": str(app_dir) if app_dir else None,
            "agent_version": (harbor.get("agent_info") or {}).get("version"),
            "exception": exc,
        },
    }
    (trial_dir / RESULT_NAME).write_text(json.dumps(result, indent=2) + "\n")
    (trial_dir / "transcript.txt").write_text(render_transcript(result))
    return result


def render_transcript(result: dict) -> str:
    lines = [f"run {result['run']} / trial {result['trial']} — {result['completion']}", ""]
    for t in result["turns"]:
        head = f"TURN {t['i']}"
        if t.get("wall_ms") is not None:
            head += f" ({t['wall_ms']} ms"
            if t.get("cost_usd") is not None:
                head += f", ${t['cost_usd']:.4f}"
            head += ")"
        lines += ["=" * 80, head, ">>> SENT:", t.get("sent") or "", "", "--- REPLY:", t.get("reply") or "", ""]
    if result.get("adherence"):
        a = result["adherence"]
        lines += ["=" * 80, f"ADHERENCE: {'verbatim' if a['all_verbatim'] else 'DIVERGED'} "
                  f"({a['sent_count']} sent / {a['expected_count']} scripted)"]
        for r in a["turns"]:
            if not r["verbatim"]:
                lines += [f"  turn {r['i']}: expected {r['expected'][:120]!r}", f"           sent     {str(r['sent'])[:120]!r}"]
    if result["artifacts"]:
        lines += ["=" * 80, "PRODUCED:"] + [f"  {p}" for p in result["artifacts"]]
    return "\n".join(lines) + "\n"


# --- run ------------------------------------------------------------------


def trial_dirs(run_dir: Path) -> list[Path]:
    return sorted(p for p in run_dir.iterdir() if p.is_dir() and (p / "result.json").is_file())


def summarize_job(run_dir: Path) -> dict:
    """Summarise every trial of a run and write `summary.json`."""
    meta = read_json(run_dir / META_NAME) or {}
    seed_tar = Path(meta["seed_tar"]) if meta.get("seed_tar") else None
    seed = seed_hashes(seed_tar) if seed_tar and seed_tar.is_file() else {}
    trials = [summarize_trial(run_dir, td, meta, seed) for td in trial_dirs(run_dir)] if meta else []
    harbor_job = read_json(run_dir / "result.json") or {}
    if not meta:
        status = "unreadable"
    elif meta.get("finished_at") is None:
        status = "incomplete"
    elif not trials:
        status = "failed"
    elif all(t["completion"] == "ok" for t in trials):
        status = "ok"
    else:
        status = "failed"
    summary = {
        "run": run_dir.name,
        "status": status,
        "fixture_id": meta.get("fixture_id"),
        "arm_id": meta.get("arm_id"),
        "operator": meta.get("operator"),
        "model": meta.get("model"),
        "started_at": meta.get("started_at"),
        "finished_at": meta.get("finished_at"),
        "harbor_exit": meta.get("harbor_exit"),
        "harbor_job_id": harbor_job.get("id"),
        "trials": [
            {
                "trial": t["trial"],
                "completion": t["completion"],
                "total_wall_ms": t["total_wall_ms"],
                "turn_count": t["turn_count"],
                "cost_usd": (t["velocity"].get("total_cost_usd")
                             if t["operator"] == "scripted" else t["velocity"].get("operator_cost_usd")),
                "tokens": (t["velocity"].get("tokens", {}).get("total")
                           if t["operator"] == "scripted" else t["velocity"].get("target_tokens", {}).get("total")),
                "artifacts": len(t["artifacts"]),
            }
            for t in trials
        ],
    }
    (run_dir / SUMMARY_NAME).write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def load_summary(run_dir: Path) -> dict | None:
    return read_json(run_dir / SUMMARY_NAME)
