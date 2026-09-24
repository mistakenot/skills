#!/usr/bin/env python3
"""planning-eval-harbor CLI — replay a planning-eval fixture as a Harbor job.

    make peval-harbor ARGS='run <fixture.json> [--operator scripted|simulated] [--trials N]
                                [--skills-ref REF [--arm-id ID]]'
    make peval-harbor ARGS='list'
    make peval-harbor ARGS='show <run>'
    make peval-harbor ARGS='clean [--yes]'
    make peval-harbor ARGS='view'

`make peval-harbor` is `uv run --project src/planning-eval-harbor --no-dev python
src/planning-eval-harbor/run.py`; the module's own environment carries `harbor`.

`run` compiles the fixture into a Harbor task (task.py), writes a job config
(job.py), launches `harbor run` — Docker sandbox, the arm's skills injected,
no verifier — and then reads Harbor's evidence back into planning-eval's
result shape (results.py). Everything lands under `runs/<job>/`, which is
Harbor's own job directory with this harness's summaries written beside its
files. Nothing is judged; nothing is scored.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fixture as fixture_mod  # noqa: E402
import job as job_mod  # noqa: E402
import results  # noqa: E402
import task as task_mod  # noqa: E402

RUNS_DIR = HERE / "runs"
TASKS_DIR = HERE / "tasks"


def _now() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _write_meta(run_dir: Path, meta: dict) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / results.META_NAME).write_text(json.dumps(meta, indent=2) + "\n")


def cmd_run(args: argparse.Namespace) -> int:
    try:
        fx = fixture_mod.load(args.fixture)
        if args.skills_ref:
            fx = fixture_mod.with_skills_ref(fx, args.skills_ref, args.arm_id)
    except fixture_mod.FixtureError as exc:
        print(f"peval-harbor: {exc}", file=sys.stderr)
        return 2
    try:
        exe = job_mod.harbor_bin()
        creds = job_mod.check_credentials()
    except job_mod.JobError as exc:
        print(f"peval-harbor: {exc}", file=sys.stderr)
        return 2

    built = task_mod.build_task(fx, TASKS_DIR, args.operator)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    job_name = f"{fx.id}-{fx.arm_id}-{args.operator}-{stamp}"
    cfg = job_mod.build_config(
        built, fx, RUNS_DIR, job_name,
        trials=args.trials, model=args.model, concurrent=args.concurrent,
    )
    cfg_path = job_mod.write_config(cfg, built.dir / "job-config.json")

    print(f"peval-harbor: run {job_name}")
    print(f"peval-harbor: fixture {fx.path}")
    print(f"peval-harbor: arm {fx.arm_id} -> {fx.skills_dir}"
          + (f" (skills @ {fx.skills_sha[:12]})" if fx.skills_sha else ""))
    print(f"peval-harbor: task {built.dir} ({args.operator}, {len(built.messages)} message(s))")
    print(f"peval-harbor: model {args.model}, {args.trials} trial(s); credentials expire "
          f"{'(already expired; refresh will be attempted)' if creds.get('expired') else 'later'}")
    print(f"peval-harbor: {' '.join(job_mod.argv(exe, cfg_path, args.dry_run))}")

    if args.dry_run:
        return job_mod.run_harbor(exe, cfg_path, dry_run=True)

    run_dir = RUNS_DIR / job_name
    meta = {
        "run": job_name,
        "fixture_path": str(fx.path),
        "fixture_id": fx.id,
        "arm_id": fx.arm_id,
        "skills_dir": str(fx.skills_dir),
        "skills_sha": fx.skills_sha,
        "operator": args.operator,
        "model": args.model,
        "trials": args.trials,
        "target_repo": str(fx.target_repo),
        "repo_url": fx.repo_url,
        "start_sha": fx.start_sha,
        "messages": fx.shown_messages,
        "messages_full": built.messages,
        "steps": built.steps,
        "seed_tar": str(built.seed_tar),
        "task_dir": str(built.dir),
        "job_config": str(cfg_path),
        "started_at": _now(),
        "finished_at": None,
        "harbor_exit": None,
    }
    rc: int | None = None
    try:
        rc = job_mod.run_harbor(exe, cfg_path)
    finally:
        # Harbor creates the run directory; if it died before that, make it, so
        # the attempt is still listed and visibly incomplete.
        meta["finished_at"] = _now() if rc is not None else None
        meta["harbor_exit"] = rc
        _write_meta(run_dir, meta)

    summary = results.summarize_job(run_dir)
    _print_summary(summary)
    print(f"peval-harbor: -> {run_dir}")
    return 0 if rc == 0 and summary["status"] == "ok" else 1


def _print_summary(summary: dict) -> None:
    print(f"peval-harbor: {summary['run']} status={summary['status']} "
          f"(harbor exit {summary.get('harbor_exit')})")
    for t in summary["trials"]:
        wall = f"{(t['total_wall_ms'] or 0) // 1000}s"
        cost = f"${t['cost_usd']:.3f}" if isinstance(t.get("cost_usd"), (int, float)) else "n/a"
        print(f"  {t['trial']:<34} {t['completion'][:24]:<24} wall {wall:>6}  turns {t['turn_count']:>2}  "
              f"tokens {t['tokens'] or '-':>10}  cost {cost:>8}  produced {t['artifacts']}")


def _runs() -> list[Path]:
    if not RUNS_DIR.is_dir():
        return []
    return sorted((p for p in RUNS_DIR.iterdir() if p.is_dir()), reverse=True)


def cmd_list(args: argparse.Namespace) -> int:
    runs = _runs()
    if not runs:
        print("no runs yet")
        return 0
    print(f"{'run':<58} {'status':<10} {'trials':>6} {'wall':>7} {'tokens':>11} {'cost':>9}  produced")
    for rd in runs:
        s = results.load_summary(rd) or (results.summarize_job(rd) if (rd / results.META_NAME).is_file() else None)
        if s is None:
            print(f"{rd.name:<58} {'(no meta)':<10}")
            continue
        trials = s["trials"]
        wall = sum((t["total_wall_ms"] or 0) for t in trials) // 1000
        toks = sum((t["tokens"] or 0) for t in trials)
        cost = sum((t["cost_usd"] or 0) for t in trials if isinstance(t.get("cost_usd"), (int, float)))
        produced = sum(t["artifacts"] for t in trials)
        print(f"{rd.name:<58} {s['status']:<10} {len(trials):>6} {wall:>6}s {toks:>11} {cost:>8.3f}  {produced}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    rd = RUNS_DIR / args.run
    if not rd.is_dir():
        print(f"peval-harbor: no run named {args.run!r} under {RUNS_DIR}", file=sys.stderr)
        return 2
    summary = results.summarize_job(rd)
    _print_summary(summary)
    for td in results.trial_dirs(rd):
        r = results.read_json(td / results.RESULT_NAME) or {}
        print(f"\n--- {td.name}: {r.get('completion')}")
        for t in r.get("turns", []):
            sent = (t.get("sent") or "").replace("\n", " ")
            reply = (t.get("reply") or "").replace("\n", " ")
            print(f"  [{t['i']}] > {sent[:90]}")
            print(f"      < {reply[:90]}")
        if r.get("artifacts"):
            print("  produced: " + ", ".join(r["artifacts"][:12]) + (" …" if len(r["artifacts"]) > 12 else ""))
        print(f"  transcript: {td / 'transcript.txt'}")
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    targets = _runs()
    if args.keep:
        targets = targets[args.keep:]
    extra = [TASKS_DIR] if TASKS_DIR.is_dir() else []
    if not targets and not extra:
        print("nothing to clean")
        return 0
    for p in targets + extra:
        print(f"{'removing' if args.yes else 'would remove'} {p}")
    if not args.yes:
        print("dry run — pass --yes to remove. Docker images Harbor built are left "
              "alone; `docker image prune` reclaims them.")
        return 0
    for p in targets + extra:
        shutil.rmtree(p, ignore_errors=True)
    return 0


def cmd_view(args: argparse.Namespace) -> int:
    try:
        exe = job_mod.harbor_bin()
    except job_mod.JobError as exc:
        print(f"peval-harbor: {exc}", file=sys.stderr)
        return 2
    cmd = [exe, "view", str(RUNS_DIR)]
    if args.port:
        cmd += ["--port", str(args.port)]
    print("peval-harbor: " + " ".join(cmd))
    os.execvpe(cmd[0], cmd, job_mod.harbor_env())


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="peval-harbor", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="replay one arm of a fixture as a Harbor job (bills tokens)")
    run.add_argument("fixture", help="a planning-eval fixture JSON")
    run.add_argument("--operator", choices=task_mod.OPERATORS, default=task_mod.SCRIPTED,
                     help="scripted: one Harbor step per message, session resumed (default); "
                          "simulated: a second Claude Code relays the script over ACP")
    run.add_argument("--trials", type=int, default=1, help="attempts of the same arm (default 1)")
    run.add_argument("--concurrent", type=int, default=1, help="trials to run at once (default 1)")
    run.add_argument("--model", default=job_mod.DEFAULT_MODEL, help="pinned model (default %(default)s)")
    run.add_argument("--skills-ref", metavar="REF",
                     help="replace the fixture's arm with this repo's compiled skills/ at REF "
                          "(any commit-ish, e.g. HEAD, main~5, a sha)")
    run.add_argument("--arm-id", help="arm label with --skills-ref (default skills-<sha12>)")
    run.add_argument("--dry-run", action="store_true",
                     help="compile the task and validate the job with harbor, spend nothing")
    run.set_defaults(func=cmd_run)

    sub.add_parser("list", help="every run, newest first").set_defaults(func=cmd_list)
    show = sub.add_parser("show", help="one run's turns and produced files")
    show.add_argument("run")
    show.set_defaults(func=cmd_show)

    clean = sub.add_parser("clean", help="remove runs and compiled tasks (dry by default)")
    clean.add_argument("--keep", type=int, default=0, help="keep the N newest runs")
    clean.add_argument("--yes", action="store_true")
    clean.set_defaults(func=cmd_clean)

    view = sub.add_parser("view", help="open Harbor's results viewer on runs/")
    view.add_argument("--port", type=int)
    view.set_defaults(func=cmd_view)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
