#!/usr/bin/env python3
"""run.py — orchestrate one planning-eval arm end to end (hacked v1, thin spine).

    uv run --no-project python src/planning-eval/run.py src/planning-eval/fixtures/example.json

Pipeline: build a worktree at the fixture's start SHA with the arm's skills overlaid
(build.sh) -> spawn an NTM-hosted agent there -> send the opening prompt -> replay the
hand-scripted human turns -> capture the produced task docs + per-turn metrics -> tear the
agent down. The worktree is left in place for inspection (auto-eval ethos).

Deliberately NOT done in the thin spine: auto-extracted intent corpus / simulator agent,
the second arm, automated scoring, full CLAUDE_CONFIG_DIR isolation (the agent needs the
operator's auth to run; skill-overlay is the arm boundary for now).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent  # .../skills

# All arm work happens OUTSIDE this repo and out of its git tree: agent worktrees and run
# outputs live under a tmp workspace. `ws/` is NTM's projects_base (so spawned agents land
# there), `runs/` holds captured artifacts + metrics.
WORKSPACE = Path(os.environ.get("PLANNING_EVAL_WORKSPACE", "/tmp/planning-eval"))
WS_PROJECTS = WORKSPACE / "ws"
RUNS_DIR = WORKSPACE / "runs"
# Make NTM derive every spawned agent's cwd from our workspace, not /home/vscode/src.
os.environ["NTM_PROJECTS_BASE"] = str(WS_PROJECTS)

sys.path.insert(0, str(HERE))
from driver import Session  # noqa: E402

# Prepended to the opening prompt. The agent is driven by an automated harness, so it must
# not pop interactive selectors (AskUserQuestion) — those can't be answered through the
# text channel and stall the run in UNKNOWN. Applied equally to every arm, so the v2-vs-v3
# comparison stays fair; it just forces the "autonomous" path both workflows already define.
HARNESS_PREAMBLE = (
    "[EVAL HARNESS] You are driven programmatically by an evaluation harness, not a live "
    "human at a terminal. Do NOT use interactive question tools or menus (AskUserQuestion) — "
    "they cannot be answered and will stall you. When a decision is needed, proceed on your "
    "best judgment and record genuinely load-bearing open decisions as pd-questions with a "
    "recommendedAnswer (the workflow's autonomous mode). If you must ask, ask in plain text "
    "and keep going; operator replies arrive as ordinary chat messages. Task follows:\n\n"
)


def _run_id(fixture_id: str, arm_id: str) -> str:
    return f"peval-{fixture_id}-{arm_id}-{int(time.time())}"


def build_worktree(cfg: dict, session: str) -> Path:
    arm_skills = (REPO_ROOT / cfg["arm"]["skills_dir"]).resolve()
    out = subprocess.run(
        [
            "bash",
            str(HERE / "build.sh"),
            cfg["fixture"]["target_repo"],
            cfg["fixture"]["start_sha"],
            str(arm_skills),
            session,
        ],
        capture_output=True,
        text=True,
    )
    sys.stderr.write(out.stderr)
    if out.returncode != 0:
        raise SystemExit(f"build.sh failed ({out.returncode})")
    return Path(out.stdout.strip().splitlines()[-1])


def capture_artifacts(worktree: Path, run_dir: Path) -> list[str]:
    """Copy only what THIS run produced — the worktree's git diff vs the start commit.

    The start commit (with arm skills amended in) is the baseline, so `git status` surfaces
    exactly the agent's new/modified files — not the pre-existing task docs in the checkout.
    """
    dest = run_dir / "artifacts"
    out = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-C", str(worktree),
         "status", "--porcelain", "--untracked-files=all"],
        capture_output=True, text=True,
    )
    captured: list[str] = []
    for line in out.stdout.splitlines():
        rel = line[3:].strip()
        if not rel:
            continue
        src = worktree / rel
        if src.is_file():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / rel)
            captured.append(rel)
    return captured


def main(fixture_path: str) -> None:
    sys.stdout.reconfigure(line_buffering=True)  # stream progress even when redirected
    cfg = json.loads(Path(fixture_path).read_text())
    fixture_id = cfg["id"]
    arm_id = cfg["arm"]["id"]
    limits = cfg.get("limits", {})
    session = _run_id(fixture_id, arm_id)
    WS_PROJECTS.mkdir(parents=True, exist_ok=True)
    run_dir = RUNS_DIR / session
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"[run] {session}")
    worktree = build_worktree(cfg, session)
    print(f"[run] worktree {worktree}")

    started = time.monotonic()
    deadline = started + limits.get("wall_clock_s", 1800)
    per_turn = limits.get("per_turn_timeout_s", 600)
    max_turns = limits.get("max_turns", 12)
    turns_log: list[dict] = []

    agent = Session.spawn(session)
    print("[run] agent ready")
    try:
        queue = [HARNESS_PREAMBLE + cfg["fixture"]["prompt"], *cfg.get("human_turns", [])]
        for i, msg in enumerate(queue):
            if i >= max_turns or time.monotonic() > deadline:
                print(f"[run] limit reached at turn {i}")
                break
            label = "PROMPT" if i == 0 else f"HUMAN[{i}]"
            print(f"[run] -> {label}: {msg[:70]}")
            turn = agent.send(msg, turn_timeout_s=per_turn)
            print(f"[run] <- {turn.wall_ms}ms ({turn.state_at_end}): {turn.reply[:90]!r}")
            turns_log.append(
                {
                    "i": i,
                    "label": label,
                    "sent": msg,
                    "reply": turn.reply,
                    "wall_ms": turn.wall_ms,
                    "state_at_end": turn.state_at_end,
                }
            )
    finally:
        artifacts = capture_artifacts(worktree, run_dir)
        result = {
            "session": session,
            "fixture_id": fixture_id,
            "arm_id": arm_id,
            "worktree": str(worktree),
            "total_wall_ms": int((time.monotonic() - started) * 1000),
            "turns": turns_log,
            "artifacts": artifacts,
        }
        (run_dir / "result.json").write_text(json.dumps(result, indent=2))
        print(f"[run] captured {len(artifacts)} artifact files -> {run_dir/'result.json'}")
        agent.kill()
        print("[run] agent killed (worktree left for inspection)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: run.py <fixture.json>")
    main(sys.argv[1])
