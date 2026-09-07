"""Managing the runs that accumulate: `list`, `show`, `clean`.

`runs/` deliberately never clears itself, which is what makes "what exactly was
in that arm?" answerable a day later — and what makes a directory that needs
managing. These three commands are that management, and `show` is the everyday
entry point: after a run finishes, the next thing a human does is open two
outputs next to each other.

`show` is therefore laid out for reading *across* arms rather than down them —
outputs are grouped by trial so the arms being compared sit adjacent, and the
`diff` line is printed ready to paste. Every path it prints exists; a path that
was never written is named without one, so the output can be trusted as a list
of things to open.

`clean` deletes, so it is dry by default: it prints what it would remove and
removes nothing until `--yes`. Both the preview and the deletion come from the
same `select`, so what it claims and what it does cannot come apart.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from . import invocation as invocation_mod
from . import manifest as manifest_mod
from . import paths, report

DEFAULT_KEEP = 10

# How much of the prompt `show` prints before pointing at the manifest. A
# scenario prompt runs to dozens of lines, and a view that opens with all of
# them has buried the arms and the outputs — which is what `show` is for.
PROMPT_LINES = 8


class CleanError(RuntimeError):
    """The clean was refused. Raised before anything has been deleted."""


# --- list -------------------------------------------------------------------


def list_lines(runs_dir: Path) -> list[str]:
    """One line per run, newest first: id, skill, arms, trial count, status."""
    runs = paths.list_runs(runs_dir)
    if not runs:
        return [f"no runs under {runs_dir}"]

    rows = []
    for run in runs:
        record = manifest_mod.describe(run)
        arms = ", ".join(record.arm_names) or "-"
        trials = f"n={record.trials}" if record.trials > 1 else ""
        status = "" if record.status == manifest_mod.STATUS_OK else record.status
        if not record.complete_record:
            status = "no manifest"
        rows.append((record.run_id, record.skill or "?", arms, trials, status))

    widths = [max(len(row[i]) for row in rows) for i in range(4)]
    lines = []
    for run_id, skill, arms, trials, status in rows:
        line = (
            f"{run_id:<{widths[0]}}  {skill:<{widths[1]}}  "
            f"{arms:<{widths[2]}}  {trials:<{widths[3]}}"
        ).rstrip()
        lines.append(f"{line}  ({status})" if status else line)
    return lines


# --- show -------------------------------------------------------------------


def _field_lines(record: manifest_mod.RunManifest) -> list[str]:
    fields = [
        ("skill", record.skill),
        ("model", record.model),
        ("runner", record.runner),
        ("invoke", record.invoke),
        ("trials", str(record.trials)),
        ("scenario", record.scenario or "(inline prompt)"),
        ("started", record.started_at),
        ("finished", record.finished_at),
    ]
    width = max(len(name) for name, _ in fields)
    return [f"  {name:<{width}}  {value}" for name, value in fields if value]


def _invocation_note(arm_dir: Path) -> str:
    """One arm's verdict, read back off `invocation.json`.

    Read rather than recomputed. The record written at run time is the evidence;
    re-parsing the transcript here would be a second opinion, free to disagree
    with the one `REPORT.md` was built from.
    """
    data = manifest_mod.read_json(arm_dir / invocation_mod.INVOCATION_NAME)
    if data is None:
        return "no invocation record"
    if not data.get("invoked"):
        missed = data.get("missed_trials") or []
        if missed:
            return f"NOT INVOKED (trials {', '.join(str(t) for t in missed)})"
        return "NOT INVOKED"
    cells = data.get("cells") if isinstance(data.get("cells"), list) else []
    reads = {p for c in cells if isinstance(c, dict) for p in (c.get("reads") or [])}
    return f"invoked, {len(reads)} file(s) read" if reads else "invoked"


def _arm_lines(run_dir: Path, record: manifest_mod.RunManifest) -> list[str]:
    """The comparison itself: what each arm was, and whether the skill fired."""
    if not record.arms:
        return ["arms", "  (none recorded)"]
    rows = []
    for arm in record.arms:
        provenance = arm.sha or "-"
        if arm.head:
            provenance += f" (head {arm.head[:8]}{', dirty' if arm.dirty else ''})"
        rows.append(
            (
                arm.name,
                arm.kind or "?",
                provenance,
                _invocation_note(run_dir / arm.dir_name),
            )
        )
    widths = [max(len(row[i]) for row in rows) for i in range(3)]
    return ["arms"] + [
        f"  {name:<{widths[0]}}  {kind:<{widths[1]}}  {prov:<{widths[2]}}  {note}"
        for name, kind, prov, note in rows
    ]


def _output_lines(run_dir: Path, record: manifest_mod.RunManifest) -> list[str]:
    """Outputs grouped by trial, so the arms being compared sit next to each other.

    Grouped by trial rather than by arm on purpose: the reading is across arms,
    and a per-arm listing puts the two files to compare pages apart.
    """
    if not record.arms:
        return []
    lines = ["outputs"]
    width = max(len(a.name) for a in record.arms)
    for trial in range(1, record.trials + 1):
        present = [
            (arm.name, run_dir / arm.dir_name / str(trial) / "out.md")
            for arm in record.arms
            if (run_dir / arm.dir_name / str(trial) / "out.md").is_file()
        ]
        if not present:
            continue
        lines.append(f"  trial {trial}")
        for name, path in present:
            lines.append(f"    {name:<{width}}  {path}")
        # The next thing a human does with two outputs, pre-typed.
        if len(present) >= 2:
            lines.append(f"    diff -u '{present[0][1]}' '{present[1][1]}'")
    return lines if len(lines) > 1 else []


def _evidence_lines(run_dir: Path, record: manifest_mod.RunManifest) -> list[str]:
    """The rest of the tree. A path that was never written is named without one."""
    labelled: list[tuple[str, Path]] = [
        ("report", run_dir / report.REPORT_NAME),
        ("manifest", run_dir / manifest_mod.RUN_MANIFEST_NAME),
    ]
    labelled += [(arm.name, run_dir / arm.dir_name) for arm in record.arms]
    width = max(len(name) for name, _ in labelled + [("each trial", run_dir)])
    lines = ["evidence"]
    for name, path in labelled:
        lines.append(
            f"  {name:<{width}}  {path}" if path.exists() else f"  {name:<{width}}  (not written)"
        )
    lines.append(
        f"  {'each trial':<{width}}  <arm>/<trial>/ holds out.md, stream.jsonl, "
        f"err.txt, ws/ and (with a skill) skill/"
    )
    return lines


def _prompt_lines(record: manifest_mod.RunManifest) -> list[str]:
    """The head of the prompt, with a pointer to the whole of it."""
    if not record.prompt:
        return []
    body = record.prompt.splitlines()
    head = [f"  {line}" for line in body[:PROMPT_LINES]]
    if len(body) > PROMPT_LINES:
        head.append(
            f"  ... ({len(body) - PROMPT_LINES} more lines; the prompt as sent is "
            f"in {manifest_mod.RUN_MANIFEST_NAME})"
        )
    return ["", "prompt"] + head


def show_lines(run_dir: Path) -> list[str]:
    """The everyday view of one run: what it compared, and what to open."""
    record = manifest_mod.describe(run_dir)
    header = f"run {record.run_id}"
    # A run with no manifest has no status to report — saying `incomplete` would
    # be claiming to know how it ended.
    if record.complete_record and record.status != manifest_mod.STATUS_OK:
        header += f"  [{record.status}]"
    lines = [header]
    if not record.complete_record:
        lines.append("  (no run manifest; the arms below were read off the directory)")
    lines += _field_lines(record)
    lines += _prompt_lines(record)
    lines += [""] + _arm_lines(run_dir, record)
    outputs = _output_lines(run_dir, record)
    if outputs:
        lines += [""] + outputs
    lines += [""] + _evidence_lines(run_dir, record)
    return lines


# --- clean ------------------------------------------------------------------


@dataclass(frozen=True)
class CleanPlan:
    """What a clean would remove, and what it would leave."""

    reason: str
    remove: list[Path]
    keep: list[Path]


def select(
    runs_dir: Path,
    keep: int | None = None,
    run_ids: list[str] | None = None,
    everything: bool = False,
) -> CleanPlan:
    """Decide what to delete. This function never deletes; `remove` does.

    One function so that the dry-run preview and the deletion cannot disagree
    about what "what it claims" means.

    `--run` names an exact directory and will select anything under `runs/` by
    that name. `--keep` and `--all` sweep, so they consider only directories
    whose name has the shape of a run id: a directory someone parked under
    `runs/` is not swept away by a command that was told to drop *runs*.
    """
    all_dirs = paths.list_runs(runs_dir)
    sweepable = [p for p in all_dirs if paths.is_run_id(p.name)]

    if run_ids:
        by_name = {p.name: p for p in all_dirs}
        missing = [r for r in run_ids if r not in by_name]
        if missing:
            raise CleanError(
                f"no such run under {runs_dir}: {', '.join(sorted(missing))}; "
                f"nothing was removed"
            )
        chosen = [by_name[r] for r in dict.fromkeys(run_ids)]
        return CleanPlan(
            reason=f"{len(chosen)} named run(s)",
            remove=chosen,
            keep=[p for p in all_dirs if p not in chosen],
        )

    if everything:
        return CleanPlan(
            reason=f"every run ({len(sweepable)})",
            remove=sweepable,
            keep=[p for p in all_dirs if p not in sweepable],
        )

    n = DEFAULT_KEEP if keep is None else keep
    if n < 0:
        raise CleanError(f"--keep must not be negative (got {n})")
    doomed = sweepable[n:]
    return CleanPlan(
        reason=f"all but the {n} newest",
        remove=doomed,
        keep=[p for p in all_dirs if p not in doomed],
    )


def remove(runs_dir: Path, targets: list[Path]) -> list[Path]:
    """Delete the planned run directories, re-checking each one first.

    The checks are cheap and the failure mode is not: a target that is not a
    plain directory sitting directly under `runs/` is refused outright rather
    than deleted carefully. A refusal stops the whole clean, so a bad plan
    cannot get halfway through.
    """
    root = runs_dir.resolve()
    for target in targets:
        if target.resolve().parent != root:
            raise CleanError(
                f"refusing to remove {target}: not a direct child of {runs_dir}"
            )
        if target.is_symlink() or not target.is_dir():
            raise CleanError(f"refusing to remove {target}: not a plain directory")

    removed = []
    for target in targets:
        shutil.rmtree(target)
        removed.append(target)
    return removed
