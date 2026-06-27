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
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent  # .../skills
PROJECTS_BASE = Path("/home/vscode/src")

sys.path.insert(0, str(HERE))
from driver import Session  # noqa: E402


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
    """Copy any task docs the agent produced into the run dir."""
    dest = run_dir / "artifacts"
    captured: list[str] = []
    tasks = worktree / "docs" / "tasks"
    if tasks.is_dir():
        shutil.copytree(tasks, dest / "tasks", dirs_exist_ok=True)
        captured = [str(p.relative_to(worktree)) for p in tasks.rglob("*") if p.is_file()]
    return captured


def main(fixture_path: str) -> None:
    cfg = json.loads(Path(fixture_path).read_text())
    fixture_id = cfg["id"]
    arm_id = cfg["arm"]["id"]
    limits = cfg.get("limits", {})
    session = _run_id(fixture_id, arm_id)
    run_dir = HERE / "runs" / session
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
        queue = [cfg["fixture"]["prompt"], *cfg.get("human_turns", [])]
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
