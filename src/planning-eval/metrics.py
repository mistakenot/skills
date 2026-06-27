"""Aggregate real velocity metrics for a run from autoetl / auto-search.

A run's worktree path is unique (`…/ws/<session>`), so every Claude session recorded
against that workspace — the parent planning session AND its spawned subagents (context
gatherers, option explorers) — belongs to this run. We sum across all of them, because the
true cost of a planning workflow includes its fan-out, not just the main thread.
"""

from __future__ import annotations

import json
import subprocess


def _run(args: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def collect(worktree: str, do_ingest: bool = True) -> dict:
    """Return aggregated metrics for the run whose agents ran in `worktree`.

    do_ingest runs `auto etl run` + `auto search index` first so a just-finished run is
    visible. It's the slow part; pass False to query whatever is already indexed.
    """
    if do_ingest:
        try:
            _run(["auto", "etl", "run"], timeout=300)
            _run(["auto", "search", "index"], timeout=120)
        except (subprocess.TimeoutExpired, OSError):
            pass  # best-effort; fall through to whatever's indexed

    try:
        out = _run(
            ["auto", "search", "session", "list", "--cwd", worktree, "--limit", "100"],
            timeout=60,
        )
        sessions = json.loads(out.stdout).get("sessions", [])
    except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError):
        return {"available": False, "reason": "auto-search query failed", "sessions": []}

    if not sessions:
        return {"available": False, "reason": "no sessions indexed for workspace yet", "sessions": []}

    def num(s, k):
        return s.get(k) or 0

    parents = [s for s in sessions if not s.get("is_subagent")]
    subs = [s for s in sessions if s.get("is_subagent")]
    firsts = [num(s, "first_message_at") for s in sessions if num(s, "first_message_at")]
    lasts = [num(s, "last_message_at") for s in sessions if num(s, "last_message_at")]

    return {
        "available": True,
        "session_count": len(sessions),
        "parent_count": len(parents),
        "subagent_count": len(subs),
        "total_tokens": sum(num(s, "total_tokens") for s in sessions),
        "total_messages": sum(num(s, "message_count") for s in sessions),
        "total_tool_duration_ms": sum(num(s, "tool_duration_ms") for s in sessions),
        "wall_span_ms": (max(lasts) - min(firsts)) if firsts and lasts else 0,
        "total_errors": sum(num(s, "error_count") for s in sessions),
        "per_session": [
            {
                "session_id": s.get("session_id"),
                "is_subagent": bool(s.get("is_subagent")),
                "tokens": num(s, "total_tokens"),
                "messages": num(s, "message_count"),
                "tool_duration_ms": num(s, "tool_duration_ms"),
            }
            for s in sorted(sessions, key=lambda s: num(s, "total_tokens"), reverse=True)
        ],
    }
