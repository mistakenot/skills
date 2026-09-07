"""The minimal run report: which arm ran, whether the skill fired, what to open."""

from __future__ import annotations

from pathlib import Path

from . import invocation as invocation_mod
from . import runners

REPORT_NAME = "REPORT.md"

STUB_BANNER = (
    "> **Stub run — no agent was invoked.** The transcript below is canned. "
    "It exercises the harness, not the skill; nothing here is evidence about "
    "the skill's behaviour."
)

NOT_INVOKED_HEADING = "# ⚠️ SKILL NOT INVOKED"

# Instructed mode asked for the skill by name and did not get it, so whatever
# the outputs differ by, it is not the skill. Said plainly and first, because the
# alternative is a reader comparing two baselines and theorising about the gap.
NOT_INVOKED_INSTRUCTED = (
    "The prompt explicitly asked for this skill and the transcript shows no "
    "`Skill` call for it. **This run is not a comparison** — every arm below ran "
    "without the skill, so any difference between them is sampling noise. Check "
    "`invocation.json` and the arm's installed `skill/` snapshot before reading "
    "anything else."
)

# Organic mode is asking whether the description routes. A miss is data.
NOT_INVOKED_ORGANIC = (
    "The prompt did not name the skill (`--invoke organic`), so this is the "
    "measurement rather than a fault: the description did not route. The output "
    "below is a no-skill run and must be read as one."
)


def _invocation_lines(records: list[invocation_mod.ArmInvocation]) -> list[str]:
    """The per-arm invocation summary: fired, what it opened, what it shelled out to."""
    lines = ["## Invocation", ""]
    for record in records:
        verdict = "invoked" if record.invoked else "**NOT INVOKED**"
        lines.append(f"### {record.arm} — {verdict} (`--invoke {record.invoke_mode}`)")
        lines.append("")
        for cell in record.cells:
            registered = "yes" if cell.registered else "no"
            lines.append(
                f"- trial {cell.trial}: "
                f"skill calls {cell.skill_calls or '[]'}; "
                f"registered in `init.skills`: {registered}"
            )
            if cell.reads:
                lines.append(f"  - read: {', '.join(f'`{p}`' for p in cell.reads)}")
            else:
                lines.append("  - read: *(no file inside the skill was opened)*")
            if cell.reads_outside_skill:
                lines.append(f"  - plus {cell.reads_outside_skill} read(s) outside the skill")
            for command in cell.bash:
                lines.append(f"  - bash: `{command}`")
        lines.append("")
        lines.append(f"- record: `{record.arm}/{invocation_mod.INVOCATION_NAME}`")
        lines.append("")
    return lines


def write_report(
    run_dir: Path,
    run_id: str,
    skill: str,
    arm: str,
    model: str,
    prompt: str,
    cells: list[tuple[str, int, Path]],
    runner: str = runners.DEFAULT,
    invocations: list[invocation_mod.ArmInvocation] | None = None,
    invoke_mode: str = invocation_mod.INVOKE_DEFAULT,
    trials: int = 1,
) -> Path:
    """Write `REPORT.md` into `run_dir`. `cells` is (arm, exit_code, cell_dir).

    The runner is named at the top, and a stub run is banner-flagged: the whole
    point of the fast lane is that its output looks exactly like a real run, so
    the report has to say which one a reader is holding.

    `trials` is stated on its own line rather than left to be counted off the
    cells: `--n` exists so a single sample does not fool a human eyeballing the
    outputs, and that only works if the report says which it is. Nothing here
    aggregates across trials — no medians, no bests — because the trials are for
    looking at, not for reducing to a number.

    `invocations` (one record per arm, from `invocation.analyse_arm`) drives the
    loudest thing in the file. An arm whose skill never fired puts
    `SKILL NOT INVOKED` above everything — above the title's own content, above
    the prompt, above the outputs — because a reader who scrolls past it will
    spend the next hour explaining a difference that is not there.
    """
    records = invocations or []
    missed = [r for r in records if not r.invoked]

    lines: list[str] = []
    if missed:
        lines += [
            NOT_INVOKED_HEADING,
            "",
            f"Arms with no `Skill` call for `{skill}`: "
            + ", ".join(f"`{r.arm}`" for r in missed),
            "",
            NOT_INVOKED_ORGANIC
            if invoke_mode == invocation_mod.ORGANIC
            else NOT_INVOKED_INSTRUCTED,
            "",
            "---",
            "",
        ]

    lines += [f"# eval run `{run_id}`", ""]
    if runner == runners.STUB:
        lines += [STUB_BANNER, ""]
    lines += [
        f"- skill: `{skill}`",
        f"- arm: `{arm}`",
        f"- model: `{model}`",
        f"- runner: `{runner}`",
        f"- invoke: `{invoke_mode}`",
        # Always stated, never inferred from the cell count below: one sample
        # and three read identically at a glance, and which one a reader is
        # holding changes what the outputs are worth.
        f"- trials per arm: `{trials}`",
        "",
        "## Prompt",
        "",
        "```",
        prompt,
        "```",
        "",
    ]
    if records:
        lines += _invocation_lines(records)
    lines += ["## Cells", ""]
    for cell_arm, exit_code, cell_dir in cells:
        rel = cell_dir.relative_to(run_dir)
        lines += [
            f"### {cell_arm} — `{rel}` (agent exit {exit_code})",
            "",
            f"- output: `{cell_dir / 'out.md'}`",
            f"- transcript: `{cell_dir / 'stream.jsonl'}`",
            f"- stderr: `{cell_dir / 'err.txt'}`",
            f"- installed skill: `{cell_dir / 'skill'}`",
            f"- workspace: `{cell_dir / 'ws'}`",
            "",
        ]
    path = run_dir / REPORT_NAME
    path.write_text("\n".join(lines))
    return path
