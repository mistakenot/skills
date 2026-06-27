#!/usr/bin/env python3
"""planning-eval harness CLI.

    uv run --no-project python src/planning-eval/run.py run    <fixture.json>
    uv run --no-project python src/planning-eval/run.py list
    uv run --no-project python src/planning-eval/run.py clean  [--keep-runs]

`run` replays one arm end to end: build a worktree at the fixture's start SHA with the
arm's skills installed -> spawn an NTM-hosted agent -> send the opening prompt -> replay
the hand-scripted human turns -> capture the produced docs, the full transcript, and
aggregated velocity metrics -> tear the agent down (always, even on error).

All arm work lives OUTSIDE this repo and out of git, under $PLANNING_EVAL_WORKSPACE
(default /tmp/planning-eval): `ws/<session>/` worktrees, `runs/<session>/` outputs.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent  # .../skills

WORKSPACE = Path(os.environ.get("PLANNING_EVAL_WORKSPACE", "/tmp/planning-eval"))
WS_PROJECTS = WORKSPACE / "ws"
RUNS_DIR = WORKSPACE / "runs"
os.environ["NTM_PROJECTS_BASE"] = str(WS_PROJECTS)  # NTM spawns agents under our workspace

sys.path.insert(0, str(HERE))
from driver import Session  # noqa: E402
import metrics  # noqa: E402

HARNESS_PREAMBLE = (
    "[EVAL HARNESS] You are driven programmatically by an evaluation harness, not a live "
    "human at a terminal. Do NOT use interactive question tools or menus (AskUserQuestion) — "
    "they cannot be answered and will stall you. When a decision is needed, proceed on your "
    "best judgment and record genuinely load-bearing open decisions as pd-questions with a "
    "recommendedAnswer (the workflow's autonomous mode). If you must ask, ask in plain text "
    "and keep going; operator replies arrive as ordinary chat messages. Task follows:\n\n"
)

GIT = ["git", "-c", "core.hooksPath=/dev/null"]


def _run_id(fixture_id: str, arm_id: str) -> str:
    return f"peval-{fixture_id}-{arm_id}-{int(time.time())}"


def build_worktree(cfg: dict, session: str) -> Path:
    arm_skills = (REPO_ROOT / cfg["arm"]["skills_dir"]).resolve()
    out = subprocess.run(
        ["bash", str(HERE / "build.sh"), cfg["fixture"]["target_repo"],
         cfg["fixture"]["start_sha"], str(arm_skills), session],
        capture_output=True, text=True,
    )
    sys.stderr.write(out.stderr)
    if out.returncode != 0:
        raise SystemExit(f"build.sh failed ({out.returncode})")
    return Path(out.stdout.strip().splitlines()[-1])


def capture_artifacts(worktree: Path, run_dir: Path) -> list[str]:
    """Copy only what THIS run produced — the worktree's git diff vs the start commit."""
    dest = run_dir / "artifacts"
    out = subprocess.run(
        [*GIT, "-C", str(worktree), "status", "--porcelain", "--untracked-files=all"],
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


def write_transcript(run_dir: Path, turns: list) -> None:
    lines = []
    for t in turns:
        lines.append(f"{'='*80}\n>>> SENT ({t.wall_ms}ms, end={t.state_at_end}):\n{t.sent}\n")
        lines.append(f"--- AGENT REPLY (scraped):\n{t.reply}\n")
        lines.append(f"--- RAW PANE TAIL:\n{t.raw_tail}\n")
    (run_dir / "transcript.txt").write_text("\n".join(lines))


def cmd_run(args) -> None:
    sys.stdout.reconfigure(line_buffering=True)
    cfg = json.loads(Path(args.fixture).read_text())
    fixture_id, arm_id = cfg["id"], cfg["arm"]["id"]
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

    agent: Session | None = None
    turns: list = []
    completion = "ok"
    try:
        agent = Session.spawn(session)
        print("[run] agent ready")
        queue = [HARNESS_PREAMBLE + cfg["fixture"]["prompt"], *cfg.get("human_turns", [])]
        for i, msg in enumerate(queue):
            if i >= max_turns or time.monotonic() > deadline:
                completion = "capped"
                print(f"[run] limit reached at turn {i}")
                break
            label = "PROMPT" if i == 0 else f"HUMAN[{i}]"
            shown = msg.split("Task follows:\n\n")[-1]
            print(f"[run] -> {label}: {shown[:70]}")
            turn = agent.send(msg, turn_timeout_s=per_turn)
            turn.sent = shown  # store the human-facing message, not the preamble
            print(f"[run] <- {turn.wall_ms}ms ({turn.state_at_end}): {turn.reply[:90]!r}")
            turns.append(turn)
    except Exception as e:  # noqa: BLE001 — record, don't crash teardown
        completion = f"error: {type(e).__name__}: {e}"
        print(f"[run] ERROR: {completion}")
    finally:
        artifacts = capture_artifacts(worktree, run_dir)
        write_transcript(run_dir, turns)
        if agent is not None:
            agent.kill()
        print(f"[run] captured {len(artifacts)} artifact files; agent down")

    print("[run] collecting velocity metrics (auto etl + search)…")
    vel = metrics.collect(str(worktree), do_ingest=not args.no_metrics)

    result = {
        "session": session,
        "fixture_id": fixture_id,
        "arm_id": arm_id,
        "target_repo": cfg["fixture"]["target_repo"],
        "start_sha": cfg["fixture"]["start_sha"],
        "worktree": str(worktree),
        "completion": completion,
        "total_wall_ms": int((time.monotonic() - started) * 1000),
        "turn_count": len(turns),
        "artifacts": artifacts,
        "velocity": vel,
        "turns": [
            {"i": i, "sent": t.sent, "reply": t.reply,
             "wall_ms": t.wall_ms, "state_at_end": t.state_at_end}
            for i, t in enumerate(turns)
        ],
    }
    (run_dir / "result.json").write_text(json.dumps(result, indent=2))

    tok = vel.get("total_tokens") if vel.get("available") else "n/a"
    print(f"[run] DONE {completion} | wall {result['total_wall_ms']//1000}s | "
          f"{len(turns)} turns | {len(artifacts)} artifacts | tokens {tok} | -> {run_dir}")


def cmd_list(args) -> None:
    if not RUNS_DIR.is_dir():
        print("no runs yet")
        return
    rows = sorted(RUNS_DIR.glob("*/result.json"))
    if not rows:
        print("no runs yet")
        return
    print(f"{'run':<48} {'compl':<8} {'wall':>6} {'turns':>5} {'tokens':>12}  artifacts")
    for rj in rows:
        d = json.loads(rj.read_text())
        vel = d.get("velocity", {})
        tok = vel.get("total_tokens", "-") if vel.get("available") else "-"
        print(f"{d['session']:<48} {d.get('completion','?')[:8]:<8} "
              f"{d.get('total_wall_ms',0)//1000:>5}s {d.get('turn_count','?'):>5} "
              f"{str(tok):>12}  {len(d.get('artifacts',[]))}")


def cmd_clean(args) -> None:
    # kill any live eval sessions
    out = subprocess.run(["ntm", "list"], capture_output=True, text=True)
    for line in out.stdout.splitlines():
        name = line.strip().split(":")[0].strip()
        if name.startswith("peval-"):
            subprocess.run(["ntm", "kill", name, "--force"], capture_output=True, text=True)
            print(f"[clean] killed session {name}")
    # remove worktrees
    if WS_PROJECTS.is_dir():
        for wt in WS_PROJECTS.iterdir():
            if not wt.is_dir():
                continue
            common = subprocess.run(
                [*GIT, "-C", str(wt), "rev-parse", "--git-common-dir"],
                capture_output=True, text=True,
            )
            removed = False
            if common.returncode == 0:
                # --git-common-dir may be relative to the worktree; (wt / it) handles both
                # (an absolute path wins, a relative one resolves against wt).
                main_repo = (wt / common.stdout.strip()).resolve().parent
                rm = subprocess.run(
                    [*GIT, "-C", str(main_repo), "worktree", "remove", "--force", str(wt)],
                    capture_output=True, text=True,
                )
                removed = rm.returncode == 0
            if not removed:
                shutil.rmtree(wt, ignore_errors=True)
            print(f"[clean] removed worktree {wt.name}")
    if not args.keep_runs and RUNS_DIR.is_dir():
        shutil.rmtree(RUNS_DIR, ignore_errors=True)
        print("[clean] removed run outputs")
    print("[clean] done")


def main() -> None:
    p = argparse.ArgumentParser(prog="planning-eval")
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("run", help="replay one arm of a fixture")
    pr.add_argument("fixture")
    pr.add_argument("--no-metrics", action="store_true",
                    help="skip the slow auto-etl ingest; query whatever's already indexed")
    pr.set_defaults(func=cmd_run)
    sub.add_parser("list", help="list captured runs").set_defaults(func=cmd_list)
    pc = sub.add_parser("clean", help="kill eval sessions + remove worktrees")
    pc.add_argument("--keep-runs", action="store_true", help="keep runs/ outputs")
    pc.set_defaults(func=cmd_clean)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
