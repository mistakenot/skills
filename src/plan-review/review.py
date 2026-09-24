#!/usr/bin/env python3
"""plan-review CLI — generate plans in Harbor, ingest them, review them by hand.

    make plan-review ARGS='generate [fixture.json ...] [--skills-ref REF ...] [--batch ID] [--trials N] [--dry-run]'
    make plan-review ARGS='ingest <harbor-run-dir> ... | --all'
    make plan-review ARGS='serve [--port 8765] [--host 127.0.0.1] [--reviewer NAME]'
    make plan-review ARGS='status'
    make plan-review ARGS='label <plan_id> <mode> present|absent [--evidence ID ...] [--reason TEXT]'
    make plan-review ARGS='report [--by version|fixture] [--batch ID]'

`generate` replays each fixture through planning-eval-harbor (`run.py run
--skills-ref`) and ingests what it produced. `serve` starts the open-coding
app. `label` records axial-coding judgements against data/taxonomy.json and
`report` counts verdicts and failure modes per skills version. Nothing here
scores a plan by itself: judgement is the reviewer's.
"""

from __future__ import annotations

import argparse
import getpass
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import coding  # noqa: E402
import corpus  # noqa: E402
import notes  # noqa: E402
import server  # noqa: E402

HARBOR_DIR = corpus.REPO_ROOT / "src" / "planning-eval-harbor"
FIXTURES_DIR = HERE / "fixtures"


def _reviewer_default() -> str:
    out = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True)
    return (out.stdout.strip() or getpass.getuser()).lower()


def _ingest(run_dirs: list[Path], runs_dir: Path, data_dir: Path, batch: str | None) -> int:
    added = 0
    for rd in run_dirs:
        try:
            entries = corpus.ingest_run(rd, batch)
        except ValueError as exc:
            print(f"plan-review: skip {rd.name}: {exc}", file=sys.stderr)
            continue
        fresh = corpus.add(entries, runs_dir, data_dir)
        added += len(fresh)
        if not entries:
            print(f"plan-review: {rd.name}: no plan.html produced")
        for e in entries:
            c = e["checks"]
            lint = c["lint"]
            flags = []
            if c["codex_ran"]:
                flags.append("CODEX RAN (stop line ignored)")
            if lint and lint["blocking"]:
                flags.append("lint: " + ",".join(lint["blocking"]))
            print(f"plan-review: {e['plan_id']} {e['fixture_id']:<34} {e['completion'] or '?':<8} "
                  f"questions {c['questions']} (open {c['open_questions']})"
                  + (f"  [{'; '.join(flags)}]" if flags else "")
                  + ("" if e in fresh else "  (already in corpus)"))
    return added


def cmd_generate(args: argparse.Namespace) -> int:
    fixtures = [Path(f) for f in args.fixtures] or sorted(FIXTURES_DIR.glob("*.json"))
    if not fixtures:
        print("plan-review: no fixtures", file=sys.stderr)
        return 2
    # One batch per invocation: every arm and fixture generated here is
    # comparable with the others, and `report --batch` keeps it apart from
    # earlier batches (see the iterate reference).
    batch = args.batch or time.strftime("b%Y%m%d-%H%M%S")
    refs = args.skills_ref or ["HEAD"]
    print(f"plan-review: batch {batch}: {len(refs)} arm(s) x {len(fixtures)} fixture(s) x {args.trials} trial(s)")
    rc = 0
    run_dirs: list[Path] = []
    for ref, fx in ((r, f) for r in refs for f in fixtures):
        cmd = [
            "uv", "run", "--project", str(HARBOR_DIR), "--no-dev", "python", str(HARBOR_DIR / "run.py"),
            "run", str(fx), "--skills-ref", ref, "--trials", str(args.trials),
            "--concurrent", str(args.concurrent),
        ]
        if args.model:
            cmd += ["--model", args.model]
        if args.dry_run:
            cmd.append("--dry-run")
        print("plan-review: " + " ".join(cmd), flush=True)
        # Stream Harbor's progress through; pick the run directory off the last line.
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        run_dir = None
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            if m := re.match(r"peval-harbor: -> (.+)$", line.strip()):
                run_dir = Path(m.group(1))
        code = proc.wait()
        rc = rc or code
        if run_dir and not args.dry_run:
            run_dirs.append(run_dir)
    if run_dirs:
        added = _ingest(run_dirs, args.runs_dir, args.data_dir, batch)
        print(f"plan-review: {added} new plan(s) in the corpus (batch {batch})")
    return rc


def cmd_ingest(args: argparse.Namespace) -> int:
    dirs = [Path(d) for d in args.run_dirs]
    if args.all:
        dirs += sorted(p for p in corpus.HARBOR_RUNS.iterdir() if (p / "peval.json").is_file()) \
            if corpus.HARBOR_RUNS.is_dir() else []
    if not dirs:
        print("plan-review: give run directories or --all", file=sys.stderr)
        return 2
    added = _ingest(dirs, args.runs_dir, args.data_dir, args.batch)
    print(f"plan-review: {added} new plan(s) in the corpus")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    review = server.Review(args.runs_dir, args.data_dir, _reviewer_default())
    plans = review.plan_list()
    if not plans:
        print("corpus is empty — run `generate` or `ingest` first")
        return 0
    print(f"{'#':>3}  {'plan':<12}  {'fixture':<36} {'verdict':<8} {'notes':>5}  kept")
    for p in plans:
        print(f"{p['n']:>3}  {p['plan_id']:<12}  {p['fixture_id'] or '?':<36} {p['verdict'] or '-':<8} "
              f"{p['notes']:>5}  {'yes' if p['snapshotted'] else ''}")
    reviewed = sum(1 for p in plans if p["verdict"])
    total_notes = sum(p["notes"] for p in plans)
    print(f"\n{reviewed}/{len(plans)} plans have a verdict; {total_notes} span note(s); "
          f"{len(notes.load(review.notes_path))} event(s) in {review.notes_path}")
    return 0


def cmd_label(args: argparse.Namespace) -> int:
    try:
        tax = coding.load_taxonomy(args.data_dir)
        if tax is None:
            raise coding.CodingError(f"no taxonomy yet: write {args.data_dir / 'taxonomy.json'} first")
        plans = corpus.load(args.runs_dir, args.data_dir)
        lab = coding.make_label(args.plan_id, args.mode, args.value == "present", tax, set(plans),
                                args.by or _reviewer_default(), args.evidence, args.reason)
    except coding.CodingError as exc:
        print(f"plan-review: {exc}", file=sys.stderr)
        return 2
    coding.append_label(lab, args.data_dir)
    print(f"plan-review: {lab['plan_id']} {lab['mode']} = {args.value} (taxonomy v{lab['taxonomy_version']})")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    try:
        tax = coding.load_taxonomy(args.data_dir)
    except coding.CodingError as exc:
        print(f"plan-review: {exc}", file=sys.stderr)
        return 2
    review = server.Review(args.runs_dir, args.data_dir, _reviewer_default())
    rows = corpus.load_rows(args.runs_dir, args.data_dir)
    batches = sorted({r.get("batch") or "-" for r in rows})
    if args.batch:
        rows = [r for r in rows if (r.get("batch") or "-") in args.batch]
    elif len(batches) > 1:
        print(f"plan-review: {len(batches)} batches in the corpus ({', '.join(batches)}); "
              "compare versions within one batch: --batch <id>", file=sys.stderr)
    rep = coding.report(rows, review.state()["verdicts"], tax,
                        coding.load_labels(args.data_dir), by=args.by)
    names = {m["id"]: m["name"] for m in tax["modes"]} if tax else {}
    print(coding.render_report(rep, names))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    review = server.Review(args.runs_dir, args.data_dir, args.reviewer or _reviewer_default())
    httpd = server.serve(review, args.host, args.port)
    host, port = httpd.server_address[:2]
    print(f"plan-review: serving {len(review.plans())} plan(s) at http://{host}:{port}/ "
          f"as reviewer {review.reviewer!r}", flush=True)
    print(f"plan-review: notes -> {review.notes_path}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="plan-review", description=__doc__.split("\n\n")[0])
    p.add_argument("--runs-dir", type=Path, default=corpus.RUNS_DIR, help=argparse.SUPPRESS)
    p.add_argument("--data-dir", type=Path, default=corpus.DATA_DIR, help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="replay fixtures in Harbor and ingest the plans (bills tokens)")
    g.add_argument("fixtures", nargs="*", help=f"fixture JSON files (default: all in {FIXTURES_DIR})")
    g.add_argument("--skills-ref", action="append", metavar="REF",
                   help="skills version to plan with; repeat for several arms in one batch (default HEAD)")
    g.add_argument("--batch", help="batch id stamped on the plans (default: b<timestamp>)")
    g.add_argument("--trials", type=int, default=1)
    g.add_argument("--concurrent", type=int, default=1)
    g.add_argument("--model", help="override planning-eval-harbor's pinned model")
    g.add_argument("--dry-run", action="store_true", help="compile and validate, spend nothing")
    g.set_defaults(func=cmd_generate)

    i = sub.add_parser("ingest", help="add the plans from existing Harbor runs to the corpus")
    i.add_argument("run_dirs", nargs="*")
    i.add_argument("--all", action="store_true", help="every run under planning-eval-harbor/runs/")
    i.add_argument("--batch", help="batch id to stamp on the ingested plans")
    i.set_defaults(func=cmd_ingest)

    s = sub.add_parser("serve", help="start the open-coding app")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--reviewer", help="name stamped on every event (default: git user.name)")
    s.set_defaults(func=cmd_serve)

    sub.add_parser("status", help="corpus and review progress").set_defaults(func=cmd_status)

    lab = sub.add_parser("label", help="record whether a failure mode is present in a plan (axial coding)")
    lab.add_argument("plan_id")
    lab.add_argument("mode", help="a mode id from data/taxonomy.json")
    lab.add_argument("value", choices=("present", "absent"))
    lab.add_argument("--evidence", nargs="*", default=[], metavar="NOTE_ID", help="note ids supporting it")
    lab.add_argument("--reason", default="", help="one line: why")
    lab.add_argument("--by", help="who judged (default: the reviewer name)")
    lab.set_defaults(func=cmd_label)

    rep = sub.add_parser("report", help="verdicts and failure-mode rates per skills version (unblinds)")
    rep.add_argument("--by", choices=("version", "fixture"), default="version")
    rep.add_argument("--batch", action="append", metavar="ID",
                     help="count only plans from this batch (repeatable); '-' = unbatched")
    rep.set_defaults(func=cmd_report)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
