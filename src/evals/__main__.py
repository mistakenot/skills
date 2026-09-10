"""`evals` CLI.

    PYTHONPATH=src uv run --no-dev python -m evals run \
        --skill rich-doc --arm none --arm WORKTREE --prompt "..."

The task is either `--prompt "..."` (inline, for throwaways) or
`--scenario <name-or-dir>` (a directory that also prepares the workspace; see
`scenarios/README.md`).

`--arm` is repeatable. Each arm gets its own clean room and its own
`runs/<run-id>/<arm>/` subtree; one arm is a legal run (single-arm exploration,
not a degenerate A/B).

Named plural deliberately: `eval` is a shell builtin, so a bare `eval` on PATH
would be shadowed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import (
    arms,
    canaries,
    cell,
    invocation,
    manage,
    manifest,
    paths,
    report,
    runners,
    scenarios,
)


def _cmd_run(args: argparse.Namespace) -> int:
    if args.n < 1:
        print(f"evals: --n must be at least 1 (got {args.n})", file=sys.stderr)
        return 2

    # The scenario first: it is the cheapest thing to reject and the pin check
    # lives in it, so a floating fixture fails before the compiler runs.
    try:
        scenario = (
            scenarios.resolve(args.scenario)
            if args.scenario
            else scenarios.inline(args.prompt)
        )
    except scenarios.ScenarioError as exc:
        print(f"evals: {exc}", file=sys.stderr)
        return 2

    # Every arm up front, before a single token is spent: a typo in the third
    # arm's ref should not surface after the first arm has already been billed.
    try:
        resolved = arms.resolve_all(args.arm, args.skill)
        companions = arms.resolve_companions(args.with_skills, args.skill)
    except arms.ArmResolutionError as exc:
        print(f"evals: {exc}", file=sys.stderr)
        return 2
    companion_srcs = {c.name: c.skill_src for c in companions}

    # Once per run, not once per cell: every arm is seeded by copying the same
    # prepared tree, so a fetch happens at most once and no two arms can see a
    # differently-fetched fixture.
    try:
        workspace_seed = scenarios.prepare(scenario)
    except (scenarios.ScenarioError, OSError) as exc:
        print(f"evals: {exc}", file=sys.stderr)
        return 2

    run_id = paths.new_run_id()
    run_dir = paths.run_dir(paths.RUNS_DIR, run_id)
    prompt = invocation.apply_invoke_mode(scenario.prompt, args.skill, args.invoke)

    run_manifest = dict(
        run_dir=run_dir,
        run_id=run_id,
        skill=args.skill,
        arm_names=[(a.name, a.dir_name) for a in resolved],
        prompt=prompt,
        model=args.model,
        runner=args.runner,
        invoke=args.invoke,
        trials=args.n,
        scenario=scenario.name,
        with_skills=[c.name for c in companions],
        seed=str(workspace_seed) if workspace_seed else None,
        started_at=manifest.now(),
    )
    # Written before the first token is spent, so a run killed halfway is still
    # listable and still says what it was comparing.
    manifest.write(**run_manifest)

    print(f"evals: run {run_id} (runner {args.runner}, {args.n} trial(s) per arm)")
    print(f"evals: scenario {scenario.name}", end="")
    print(f" -> {workspace_seed}" if workspace_seed else " (no workspace fixture)")
    if companions:
        print(
            "evals: with "
            + ", ".join(f"{c.name} -> {c.skill_src}" for c in companions)
            + " (held constant on every installed arm)"
        )

    cells: list[tuple[str, int, Path]] = []
    records = []
    for arm in resolved:
        print(f"evals: arm {arm.name} -> {arm.skill_src or '(nothing installed)'}")

        cell_dirs: list[Path] = []
        for trial in range(1, args.n + 1):
            cell_dir = paths.cell_dir(paths.RUNS_DIR, run_id, arm.dir_name, trial)
            try:
                result = cell.run_cell(
                    out_dir=cell_dir,
                    skill_name=args.skill,
                    skill_src=arm.skill_src,
                    prompt=prompt,
                    model=args.model,
                    runner=args.runner,
                    fixture=workspace_seed,
                    companions=companion_srcs,
                )
            except (cell.CellError, canaries.CanaryFailure, runners.RunnerError) as exc:
                print(f"evals: {exc}", file=sys.stderr)
                return 2

            cell_dirs.append(cell_dir)
            cells.append((arm.name, result.exit_code, cell_dir))
            print(
                f"evals: arm {arm.name} trial {trial}/{args.n} "
                f"agent exit {result.exit_code}"
            )

        # Provenance next to the evidence: "which version was this?" has to be
        # answerable from the run tree alone, a day later.
        arms.write_manifest(
            run_dir / arm.dir_name, arm, args.skill, run_id, companions
        )

        # Ground truth from the transcript's tool calls, never a self-report: if
        # the skill never fired, the arms are the same run and nothing below is a
        # comparison. This is the only automated check in the harness.
        record = invocation.analyse_arm(
            arm_dir=run_dir / arm.dir_name,
            arm=arm.name,
            skill=args.skill,
            cell_dirs=cell_dirs,
            invoke_mode=args.invoke,
        )
        records.append(record)

        if record.invoked:
            print(
                f"evals: arm {arm.name}: skill {args.skill} INVOKED "
                f"({len(record.reads)} file(s) read from it)"
            )
        else:
            print(
                f"evals: arm {arm.name}: SKILL NOT INVOKED — "
                f"{args.skill} never fired"
            )

    ok = all(code == 0 for _, code, _ in cells)
    # Rewritten whole, so the start-of-run copy and this one cannot disagree.
    manifest.write(
        **run_manifest,
        finished_at=manifest.now(),
        status=manifest.STATUS_OK if ok else manifest.STATUS_FAILED,
    )

    report_path = report.write_report(
        run_dir=run_dir,
        run_id=run_id,
        skill=args.skill,
        arm=", ".join(arm.name for arm in resolved),
        model=args.model,
        prompt=prompt,
        cells=cells,
        runner=args.runner,
        invocations=records,
        invoke_mode=args.invoke,
        trials=args.n,
        with_skills=[c.name for c in companions],
        seed=workspace_seed,
    )
    print(f"evals: {report_path}")
    print(f"evals: evals show {run_id}")
    return 0 if ok else 1


def _cmd_list(args: argparse.Namespace) -> int:
    for line in manage.list_lines(paths.RUNS_DIR):
        print(line)
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    run_dir = paths.run_dir(paths.RUNS_DIR, args.run_id)
    if "/" in args.run_id or not run_dir.is_dir():
        print(
            f"evals: no run {args.run_id!r} under {paths.RUNS_DIR}; try `evals list`",
            file=sys.stderr,
        )
        return 2
    for line in manage.show_lines(run_dir):
        print(line)
    return 0


def _cmd_clean(args: argparse.Namespace) -> int:
    """Preview, then delete — and only ever the directories the preview named."""
    try:
        plan = manage.select(
            paths.RUNS_DIR, keep=args.keep, run_ids=args.run, everything=args.all
        )
    except manage.CleanError as exc:
        print(f"evals: {exc}", file=sys.stderr)
        return 2

    if not plan.remove:
        print(f"evals: nothing to remove ({plan.reason}); {len(plan.keep)} run(s) kept")
        return 0

    print(
        f"evals: {'removing' if args.yes else 'would remove'} {len(plan.remove)} "
        f"run(s) — {plan.reason}; {len(plan.keep)} kept"
    )
    for path in plan.remove:
        print(f"  {path.name}")

    if not args.yes:
        print("evals: dry run — nothing was deleted; pass --yes to delete")
        return 0

    try:
        removed = manage.remove(paths.RUNS_DIR, plan.remove)
    except manage.CleanError as exc:
        print(f"evals: {exc}", file=sys.stderr)
        return 2
    print(f"evals: removed {len(removed)} run(s)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evals", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run one prompt against one or more arms")
    run.add_argument("--skill", required=True, help="skill name under skills/")
    run.add_argument(
        "--arm",
        required=True,
        action="append",
        metavar="ARM",
        help=(
            f"repeatable: which version of the skill to install. "
            f"{arms.NONE!r} installs nothing (the baseline arm), "
            f"{arms.WORKTREE!r} compiles and copies the working tree, "
            f"anything else is a git ref"
        ),
    )
    # A run needs exactly one task. `--scenario` is the reproducible form (a
    # directory that can also prepare the workspace); `--prompt` is the inline
    # shorthand for a throwaway.
    task = run.add_mutually_exclusive_group(required=True)
    task.add_argument("--prompt", help="the prompt to run, inline")
    task.add_argument(
        "--scenario",
        metavar="NAME_OR_DIR",
        help=(
            "a scenario directory (prompt.md, optional setup.sh and fixture/); "
            "a bare name is looked up under the module's scenarios/. "
            f"bundled: {', '.join(scenarios.available()) or '(none)'}"
        ),
    )
    run.add_argument(
        "--with",
        dest="with_skills",
        action="append",
        default=[],
        metavar="SKILL",
        help=(
            "repeatable: a companion skill the skill under test loads by name "
            "(e.g. new-epic loads rich-doc). Taken from the compiled working "
            "tree and installed identically on every arm that installs the "
            f"skill; the {arms.NONE!r} arm stays empty"
        ),
    )
    run.add_argument("--model", default=cell.DEFAULT_MODEL, help="pinned model id")
    run.add_argument(
        "--n",
        type=int,
        default=1,
        metavar="TRIALS",
        help=(
            "repeat each arm this many times into <arm>/<trial>/. There to stop "
            "one sample fooling you while eyeballing; nothing is aggregated"
        ),
    )
    run.add_argument(
        "--runner",
        default=runners.DEFAULT,
        choices=list(runners.CHOICES),
        help="live spawns claude -p; stub writes a canned transcript offline (no billing)",
    )
    run.add_argument(
        "--invoke",
        default=invocation.INVOKE_DEFAULT,
        choices=list(invocation.INVOKE_CHOICES),
        help=(
            "instructed appends 'invoke <skill>' to the prompt and measures the "
            "skill's content; organic appends nothing and measures whether the "
            "description routes"
        ),
    )
    run.set_defaults(func=_cmd_run)

    listing = sub.add_parser("list", help="every run, newest first")
    listing.set_defaults(func=_cmd_list)

    show = sub.add_parser(
        "show", help="one run: what it compared, and what to open"
    )
    show.add_argument("run_id", help="a run id from `evals list`")
    show.set_defaults(func=_cmd_show)

    clean = sub.add_parser(
        "clean",
        help="drop old runs (prints what it would remove; --yes to do it)",
    )
    # One selector at a time: a clean that had to reconcile "keep 5" with
    # "and also this one" is a clean whose preview is a guess.
    which = clean.add_mutually_exclusive_group()
    which.add_argument(
        "--keep",
        type=int,
        metavar="N",
        help=f"keep the N newest runs, drop the rest (default {manage.DEFAULT_KEEP})",
    )
    which.add_argument(
        "--run",
        action="append",
        metavar="RUN_ID",
        help="repeatable: drop exactly these runs",
    )
    which.add_argument(
        "--all", action="store_true", help="drop every run"
    )
    clean.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="actually delete; without it nothing is removed",
    )
    clean.set_defaults(func=_cmd_clean)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
