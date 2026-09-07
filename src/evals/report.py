"""The run report: what each arm produced, side by side, and what to open.

Judgement in this harness is a human reading two outputs, and this file is the
entry point to that reading. So it is built as a *reading aid*, not a grader:
there is no score, no verdict, and no claim about which arm did better. What it
owes the reader is the facts placed next to each other — one table with the arms
as columns, and enough of each output inline that the difference is visible
before anyone opens a file.

Two rules it must keep:

  * **Never print a path that does not exist.** The `none` arm installs nothing,
    by design; naming a `skill/` directory for it invents evidence, and a reader
    who goes looking finds nothing and distrusts the rest.
  * **Never judge.** Counts and excerpts are observations. "Better" is the
    reader's call, and stating one here would anchor it.
"""

from __future__ import annotations

import dataclasses
import json
import re
from pathlib import Path

from . import arms as arms_mod
from . import invocation as invocation_mod
from . import manifest as manifest_mod
from . import runners

REPORT_NAME = "REPORT.md"

# How much of each output to inline. Long enough to show the shape of the thing
# (a markdown heading tree vs. an HTML component tree is obvious within a dozen
# lines), short enough that the table above it stays on screen.
EXCERPT_LINES = 24
EXCERPT_WIDTH = 160

# Counting is cheap up to a point. Past this the file is not something a human is
# going to read side by side anyway, so record size and stop.
MAX_SCAN_BYTES = 2_000_000

# Enough to see that a document is component-built, not a full inventory.
MAX_CUSTOM_ELEMENTS = 6

NO_SKILL_INSTALLED = "*(nothing installed — this arm is the baseline)*"

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
    "The prompt explicitly asked for this skill and did not get it. Check "
    "`invocation.json` and the arm's installed `skill/` snapshot before reading "
    "anything else."
)

# Organic mode is asking whether the description routes. A miss is data.
NOT_INVOKED_ORGANIC = (
    "The prompt did not name the skill (`--invoke organic`), so this is the "
    "measurement rather than a fault: the description did not route. The output "
    "below is a no-skill run and must be read as one."
)

# Only ever printed when *no* arm ran the skill. Split out of the instructed
# sentence, which used to assert it unconditionally and so said "every arm ran
# without the skill" on runs where one arm plainly had not (`skills-7k7.15`).
NOT_A_COMPARISON = (
    "**This run is not a comparison** — no arm below ran the skill, so any "
    "difference between them is sampling noise."
)

# The baseline is *supposed* to be silent. Said once, in the banner, only when
# the banner was already going to fire for some other arm; on a healthy run the
# fact lives in the comparison table instead, where it is not an alarm.
BASELINE_MISS_NOTE = (
    "(Arms that install nothing are expected not to run the skill; they are not "
    "counted above.)"
)

# How the table and the invocation detail say "did not invoke, and that is the
# design". Kept apart from `**NO**`, which means something is wrong.
BASELINE_NOT_INVOKED = "no — expected (nothing installed)"

REBUILT_NOTE = (
    "regenerated from the run directory; agent exit read back from each "
    "transcript's `result` event"
)


# --- looking at what an arm produced ---------------------------------------

TYPE_NAMES = {
    ".md": "Markdown",
    ".markdown": "Markdown",
    ".html": "HTML",
    ".htm": "HTML",
    ".txt": "plain text",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".py": "Python",
    ".csv": "CSV",
}


def _type_name(path: Path) -> str:
    suffix = path.suffix.lower()
    return TYPE_NAMES.get(suffix) or (suffix.lstrip(".").upper() if suffix else "no extension")


def _human_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def _markdown_counts(text: str) -> dict[str, str]:
    """Structure a reader would otherwise have to scroll for."""
    return {
        "headings": str(len(re.findall(r"(?m)^#{1,6}\s", text))),
        "code blocks": str(len(re.findall(r"(?m)^\s*```", text)) // 2),
        "tables": str(len(re.findall(r"(?m)^\s*\|[\s:|-]*-[\s:|-]*\|\s*$", text))),
    }


def _html_counts(text: str) -> dict[str, str]:
    """The same, plus the tags that say *how* the page was built.

    Custom elements — any tag with a hyphen in it — are the cheapest available
    signal that a document is component-built rather than hand-rolled, and they
    are what a with/without-a-doc-skill comparison turns on.
    """
    counts = {
        "headings": str(len(re.findall(r"(?i)<h[1-6][\s>]", text))),
        "code blocks": str(len(re.findall(r"(?i)<pre[\s>]", text))),
        "tables": str(len(re.findall(r"(?i)<table[\s>]", text))),
    }
    tags: dict[str, int] = {}
    for tag in re.findall(r"(?i)<([a-z][a-z0-9]*-[a-z0-9-]+)[\s>/]", text):
        tag = tag.lower()
        tags[tag] = tags.get(tag, 0) + 1
    if tags:
        ranked = sorted(tags.items(), key=lambda kv: (-kv[1], kv[0]))
        shown = ", ".join(f"`{tag}` ×{n}" for tag, n in ranked[:MAX_CUSTOM_ELEMENTS])
        if len(ranked) > MAX_CUSTOM_ELEMENTS:
            shown += f", +{len(ranked) - MAX_CUSTOM_ELEMENTS} more"
        counts["custom elements"] = shown
    else:
        counts["custom elements"] = "none"
    return counts


@dataclasses.dataclass(frozen=True)
class OutputFile:
    """One file the agent left at the workspace root, described."""

    path: Path
    rel: str
    type_name: str
    size: int
    lines: int
    binary: bool
    counts: dict[str, str]
    excerpt: list[str]

    @property
    def size_text(self) -> str:
        return _human_size(self.size)


def _rel(path: Path, run_dir: Path) -> str:
    """A path as it reads from inside the run directory, or unchanged."""
    try:
        return str(path.relative_to(run_dir))
    except ValueError:
        return str(path)


def _describe(path: Path, run_dir: Path) -> OutputFile:
    size = path.stat().st_size
    try:
        raw = path.read_bytes()[:MAX_SCAN_BYTES]
    except OSError:
        raw = b""
    binary = b"\0" in raw
    text = "" if binary else raw.decode("utf-8", errors="replace")
    lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)

    if binary:
        counts: dict[str, str] = {}
        excerpt: list[str] = []
    else:
        type_name = _type_name(path)
        if type_name == "HTML":
            counts = _html_counts(text)
        elif type_name == "Markdown":
            counts = _markdown_counts(text)
        else:
            counts = {}
        excerpt = [
            line if len(line) <= EXCERPT_WIDTH else line[:EXCERPT_WIDTH] + " …"
            for line in text.splitlines()[:EXCERPT_LINES]
        ]

    return OutputFile(
        path=path,
        rel=_rel(path, run_dir),
        type_name=_type_name(path),
        size=size,
        lines=lines,
        binary=binary,
        counts=counts,
        excerpt=excerpt,
    )


def workspace_outputs(cell_dir: Path, run_dir: Path) -> list[OutputFile]:
    """Files sitting at the root of a cell's `ws/`, newest first.

    Only the root, and only files: a scenario fixture arrives as a directory
    tree (`ws/datasette/…`), while the deliverable a prompt asks for lands
    beside it. This is a heuristic and the report labels it as one — it says
    "newest file at `ws/` root", not "the thing the agent wrote".
    """
    ws = cell_dir / "ws"
    if not ws.is_dir():
        return []
    files = [p for p in ws.iterdir() if p.is_file() and not p.name.startswith(".")]
    files.sort(key=lambda p: (-p.stat().st_mtime, p.name))
    return [_describe(p, run_dir) for p in files]


# --- the side-by-side table -------------------------------------------------


@dataclasses.dataclass
class Column:
    """One cell of the run, as a column of the comparison table."""

    arm: str
    trial: int
    label: str
    exit_code: int | None
    run_dir: Path
    cell_dir: Path
    invocation: invocation_mod.CellInvocation | None
    outputs: list[OutputFile]
    final_message: Path | None
    skill_dir: Path | None
    # `none` / `worktree` / `ref` off the arm's own manifest, or None when it
    # could not be read. See `_arm_kinds`.
    kind: str | None = None


def _cell_invocations(
    records: list[invocation_mod.ArmInvocation],
) -> dict[tuple[str, int], invocation_mod.CellInvocation]:
    return {
        (record.arm, cell.trial): cell for record in records for cell in record.cells
    }


def _arm_kinds(cells: list[tuple[str, int | None, Path]]) -> dict[str, str | None]:
    """Arm name -> what that arm installed, read off `<arm>/manifest.json`.

    This is the answer to "was the skill installed for this arm", and it is the
    signal the not-invoked alarm turns on. Two rejected alternatives, because
    picking the wrong one is how this check breaks in each direction:

      * **`registered`** (membership of `init.skills`) is `false` for an arm
        that was installed and failed to load — the single loudest case there
        is, and silencing it would be the same bug over again.
      * **the cell's `skill/` snapshot** is evidence rather than intent: absent
        for `none` by design, but *also* absent when an install silently
        produced nothing, which must alarm and would not.

    `kind` comes from the arm resolver, before anything ran, so it says what the
    run *meant* to install. A manifest that cannot be read leaves the kind
    `None`, which every caller here treats as "assume installed" — an unknown
    arm alarms rather than passing quietly.
    """
    kinds: dict[str, str | None] = {}
    for arm, _exit_code, cell_dir in cells:
        if arm in kinds:
            continue
        data = manifest_mod.read_json(cell_dir.parent / arms_mod.MANIFEST_NAME) or {}
        kind = data.get("kind")
        kinds[arm] = kind if isinstance(kind, str) else None
    return kinds


def _is_baseline(kind: str | None) -> bool:
    """An arm that installed nothing. Its silence is the design, not a fault."""
    return kind == arms_mod.KIND_NONE


def _columns(
    run_dir: Path,
    cells: list[tuple[str, int | None, Path]],
    records: list[invocation_mod.ArmInvocation],
    kinds: dict[str, str | None] | None = None,
) -> list[Column]:
    by_cell = _cell_invocations(records)
    kinds = kinds if kinds is not None else _arm_kinds(cells)
    seen: dict[str, int] = {}
    columns: list[Column] = []
    for arm, exit_code, cell_dir in cells:
        trial = seen.get(arm, 0) + 1
        seen[arm] = trial
        out_md = cell_dir / "out.md"
        skill_dir = cell_dir / "skill"
        columns.append(
            Column(
                arm=arm,
                trial=trial,
                label=arm,
                exit_code=exit_code,
                run_dir=run_dir,
                cell_dir=cell_dir,
                invocation=by_cell.get((arm, trial)),
                outputs=workspace_outputs(cell_dir, run_dir),
                final_message=out_md if out_md.is_file() else None,
                skill_dir=skill_dir if skill_dir.is_dir() else None,
                kind=kinds.get(arm),
            )
        )
    # The trial number only earns column-header space when there is more than
    # one of them; a two-arm N=1 run should read as exactly two columns.
    multi_trial = len(seen) != len(columns)
    for column in columns:
        column.label = f"{column.arm} · trial {column.trial}" if multi_trial else column.arm
    return columns


def _escape(value: str) -> str:
    """A table cell: no pipes, no newlines."""
    return value.replace("|", "\\|").replace("\n", " ")


def _table(rows: list[tuple[str, list[str]]], headers: list[str]) -> list[str]:
    lines = [
        "| " + " | ".join(["", *(f"**{h}**" for h in headers)]) + " |",
        "| " + " | ".join(["---"] * (len(headers) + 1)) + " |",
    ]
    for label, values in rows:
        lines.append("| " + " | ".join([label, *(_escape(v) for v in values)]) + " |")
    return lines


def _comparison_lines(columns: list[Column]) -> list[str]:
    """One table, arms as columns. The point of the whole file."""
    heading = ["## Side by side", ""]
    if not columns:
        return heading + ["*(no cells)*", ""]

    def invoked(column: Column) -> str:
        # `**NO**` is reserved for a miss that invalidates something. An arm
        # that installed nothing was never going to invoke, and dressing that
        # up as a failure is what taught readers to ignore the row.
        if column.invocation is None:
            return "not analysed"
        if column.invocation.invoked:
            return "yes"
        return BASELINE_NOT_INVOKED if _is_baseline(column.kind) else "**NO**"

    def registered(column: Column) -> str:
        if column.invocation is None:
            return "not analysed"
        return "yes" if column.invocation.registered else "no"

    def primary(column: Column) -> OutputFile | None:
        return column.outputs[0] if column.outputs else None

    def output_name(column: Column) -> str:
        out = primary(column)
        return f"`{out.rel}`" if out else "*(no file at `ws/` root)*"

    def other_outputs(column: Column) -> str:
        rest = column.outputs[1:]
        return ", ".join(f"`{o.path.name}`" for o in rest) if rest else "—"

    def final_message(column: Column) -> str:
        if column.final_message is None:
            return "—"
        text = column.final_message.read_text(errors="replace")
        lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
        return f"{_human_size(column.final_message.stat().st_size)}, {lines} lines"

    def installed(column: Column) -> str:
        # Never a phantom path: the `none` arm installs nothing, and saying so
        # is the honest cell. A path here is a promise that it is on disk.
        if column.skill_dir is None:
            return NO_SKILL_INSTALLED
        return f"`{_rel(column.skill_dir, column.run_dir)}`"

    rows: list[tuple[str, list[str]]] = [
        ("skill invoked", [invoked(c) for c in columns]),
        ("registered in `init.skills`", [registered(c) for c in columns]),
        (
            "agent exit",
            [("—" if c.exit_code is None else str(c.exit_code)) for c in columns],
        ),
        ("installed skill", [installed(c) for c in columns]),
        ("output file", [output_name(c) for c in columns]),
        (
            "type",
            [(primary(c).type_name if primary(c) else "—") for c in columns],
        ),
        (
            "size",
            [(primary(c).size_text if primary(c) else "—") for c in columns],
        ),
        (
            "lines",
            [
                (
                    "binary"
                    if primary(c) and primary(c).binary
                    else (str(primary(c).lines) if primary(c) else "—")
                )
                for c in columns
            ],
        ),
    ]

    # Structural counts, only for the labels that any arm actually has: an
    # all-markdown run should not carry an empty "custom elements" row.
    labels: list[str] = []
    for column in columns:
        out = primary(column)
        for label in (out.counts if out else {}):
            if label not in labels:
                labels.append(label)
    for label in labels:
        rows.append(
            (
                label,
                [
                    (primary(c).counts.get(label, "—") if primary(c) else "—")
                    for c in columns
                ],
            )
        )

    rows.append(("other files at `ws/` root", [other_outputs(c) for c in columns]))
    rows.append(("final message (`out.md`)", [final_message(c) for c in columns]))

    footnotes = [
        "Counts are observations, not scores — nothing here says which arm is better.",
    ]
    # Structural counts are literals of the format they were counted in, so a
    # row spanning two formats is not one measure: markdown `#` headings and
    # HTML `<h*>` tags are different things, and a component-built page can
    # score zero on both while being heavily structured. Said out loud, because
    # a bare `31 | 0` reads as an absence that is not there.
    types = {primary(c).type_name for c in columns if primary(c)}
    if labels and len(types) > 1:
        footnotes.append(
            "The arms produced different file types (" + ", ".join(sorted(types)) + "), "
            "so the structural rows count different literals — markdown `#` headings "
            "against HTML `<h*>` tags — and are not comparable across columns. A "
            "component-built page renders its structure from the custom elements row."
        )
    return heading + _table(rows, [c.label for c in columns]) + [""] + [
        line for note in footnotes for line in (note, "")
    ]


# --- inline excerpts --------------------------------------------------------


def _fence(body: list[str]) -> str:
    """A fence longer than any backtick run inside, so nested fences survive."""
    longest = max((len(m) for line in body for m in re.findall(r"`+", line)), default=0)
    return "`" * max(3, longest + 1)


def _excerpt_lines(columns: list[Column]) -> list[str]:
    lines = [
        "## Output excerpts",
        "",
        f"The first {EXCERPT_LINES} lines of each arm's newest `ws/` root file, "
        "so the shape of the difference is visible without opening anything.",
        "",
    ]
    for column in columns:
        out = column.outputs[0] if column.outputs else None
        lines.append(f"### {column.label}")
        lines.append("")
        if out is None:
            lines += ["*(nothing at the workspace root to excerpt)*", ""]
            continue
        lines.append(
            f"`{out.rel}` — {out.type_name}, {out.size_text}, "
            + ("binary" if out.binary else f"{out.lines} lines")
        )
        lines.append("")
        if out.binary:
            lines += ["*(binary file — not excerpted)*", ""]
            continue
        fence = _fence(out.excerpt)
        lines.append(fence)
        lines += out.excerpt
        lines.append(fence)
        if out.lines > len(out.excerpt):
            lines.append("")
            lines.append(f"*… {out.lines - len(out.excerpt)} more lines in `{out.path}`*")
        lines.append("")
    return lines


# --- the per-arm invocation detail ------------------------------------------


def _miss_note(record: invocation_mod.ArmInvocation) -> str:
    """*How* an arm missed: never asked, or asked and was refused.

    "No `Skill` call" and "a `Skill` call that came back
    `<tool_use_error>Unknown skill: …</tool_use_error>`" are different findings —
    the second says the agent tried and the install is what failed. The banner
    used to assert the first in both cases.
    """
    failed = [
        named
        for cell in record.cells
        for named in cell.failed_skill_calls
        if invocation_mod.names_skill(named, record.skill)
    ]
    if failed:
        return f"a `Skill` call for `{record.skill}` came back an error"
    called = [
        named
        for cell in record.cells
        for named in cell.skill_calls
        if invocation_mod.names_skill(named, record.skill)
    ]
    if called:
        # The call neither errored nor counted, which leaves one explanation:
        # `init.skills` did not list the skill, so nothing it returned can mean
        # the skill loaded (`invocation.parse_stream`'s one-way veto).
        return (
            f"a `Skill` call for `{record.skill}` was made, but the skill was "
            f"not registered in `init.skills`"
        )
    if any(cell.skill_calls for cell in record.cells):
        return "it called other skills, but never this one"
    return f"no `Skill` call for `{record.skill}` at all"


def _invocation_lines(
    records: list[invocation_mod.ArmInvocation],
    kinds: dict[str, str | None] | None = None,
) -> list[str]:
    """The per-arm invocation detail: what it opened, what it shelled out to."""
    kinds = kinds or {}
    lines = ["## Invocation detail", ""]
    for record in records:
        if record.invoked:
            verdict = "invoked"
        elif _is_baseline(kinds.get(record.arm)):
            verdict = "baseline, not invoked (nothing installed)"
        else:
            verdict = "**NOT INVOKED**"
        lines.append(f"### {record.arm} — {verdict} (`--invoke {record.invoke_mode}`)")
        lines.append("")
        for cell in record.cells:
            registered = "yes" if cell.registered else "no"
            # A refused call is named here too: "asked and was told the skill
            # does not exist" is the fact that explains an empty read list.
            refused = (
                f"; refused: {cell.failed_skill_calls}" if cell.failed_skill_calls else ""
            )
            lines.append(
                f"- trial {cell.trial}: "
                f"skill calls {cell.skill_calls or '[]'}{refused}; "
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


def _files_lines(columns: list[Column]) -> list[str]:
    """Absolute paths to open, and only the ones that are actually there."""
    lines = ["## Files", ""]
    for column in columns:
        lines.append(f"### {column.label} — `{_rel(column.cell_dir, column.run_dir)}`")
        lines.append("")
        for name in ("out.md", "stream.jsonl", "err.txt"):
            path = column.cell_dir / name
            label = {"out.md": "output", "stream.jsonl": "transcript", "err.txt": "stderr"}[name]
            suffix = "" if path.exists() else " *(missing)*"
            lines.append(f"- {label}: `{path}`{suffix}")
        if column.skill_dir is not None:
            lines.append(f"- installed skill: `{column.skill_dir}`")
        else:
            lines.append(f"- installed skill: {NO_SKILL_INSTALLED}")
        workspace = column.cell_dir / "ws"
        if workspace.is_dir():
            lines.append(f"- workspace: `{workspace}`")
        for out in column.outputs:
            lines.append(f"- workspace file: `{out.path}`")
        lines.append("")
    return lines


# --- the report -------------------------------------------------------------


def write_report(
    run_dir: Path,
    run_id: str,
    skill: str,
    arm: str,
    model: str,
    prompt: str,
    cells: list[tuple[str, int | None, Path]],
    runner: str = runners.DEFAULT,
    invocations: list[invocation_mod.ArmInvocation] | None = None,
    invoke_mode: str = invocation_mod.INVOKE_DEFAULT,
    trials: int = 1,
    note: str | None = None,
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
    loudest thing in the file. An arm that *had the skill installed* and did not
    run it puts `SKILL NOT INVOKED` above everything — above the title's own
    content, above the prompt, above the outputs — because a reader who scrolls
    past it will spend the next hour explaining a difference that is not there.

    The alarm is scoped to arms that could have invoked. A `none` arm is
    supposed to be silent — that is what a baseline is — so its miss is stated
    in the comparison table as an ordinary fact and never banner-flagged. The
    one exception is a run where *no* arm invoked: there is nothing to compare
    then, whatever each arm installed, and the banner says so. Firing on every
    correct with/without run is not a lesser failure than never firing; it
    teaches the reader to skip the banner, and the next genuine miss goes
    unread (`skills-7k7.15`).

    Below that the file is arranged for the reading it exists to support: the
    comparison table first, the excerpts next, and the paths last. `exit_code`
    may be `None` when the report is rebuilt after the fact and the true code is
    not on disk; the table says "—" rather than guessing a zero.
    """
    records = invocations or []
    kinds = _arm_kinds(cells)
    missed = [r for r in records if not r.invoked]
    # A `none` arm not invoking is what a baseline *is*. Alarming on it fired
    # the banner on every correct with/without run, and a detector that always
    # fires is exactly as useless as one that never does (`skills-7k7.15`).
    installed_missed = [r for r in missed if not _is_baseline(kinds.get(r.arm))]
    nothing_invoked = bool(records) and not any(r.invoked for r in records)
    # Either an arm that had the skill did not run it, or no arm ran it at all —
    # the second covers a run whose every arm is a baseline, where there is
    # still nothing to compare.
    alarming = missed if nothing_invoked else installed_missed
    columns = _columns(run_dir, cells, records, kinds)

    lines: list[str] = []
    if alarming:
        headline = (
            f"No arm ran `{skill}`:"
            if nothing_invoked
            else f"Arms that had `{skill}` installed but did not run it:"
        )
        lines += [NOT_INVOKED_HEADING, "", headline, ""]
        lines += [f"- `{r.arm}` — {_miss_note(r)}" for r in alarming]
        lines += [
            "",
            NOT_INVOKED_ORGANIC
            if invoke_mode == invocation_mod.ORGANIC
            else NOT_INVOKED_INSTRUCTED,
            "",
        ]
        if nothing_invoked:
            lines += [NOT_A_COMPARISON, ""]
        elif len(alarming) < len(missed):
            lines += [BASELINE_MISS_NOTE, ""]
        lines += ["---", ""]

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
    ]
    if note:
        lines.append(f"- note: {note}")
    lines += [""]

    lines += _comparison_lines(columns)
    lines += _excerpt_lines(columns)
    lines += ["## Prompt", "", "```", prompt, "```", ""]
    if records:
        lines += _invocation_lines(records, kinds)
    lines += _files_lines(columns)

    path = run_dir / REPORT_NAME
    path.write_text("\n".join(lines))
    return path


# --- regenerating a report over a finished run ------------------------------


def _exit_from_stream(stream_path: Path) -> int | None:
    """The agent's outcome, read back from the transcript's `result` envelope.

    Only used when rebuilding: the true exit code is not written to the run
    tree, so this is an inference, and the rebuilt report says so in its note.
    """
    if not stream_path.is_file():
        return None
    code: int | None = None
    for line in stream_path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("type") == "result":
            code = 1 if event.get("is_error") else 0
    return code


def _record_from_dict(data: dict) -> invocation_mod.ArmInvocation:
    cell_fields = {f.name for f in dataclasses.fields(invocation_mod.CellInvocation)}
    cells = [
        invocation_mod.CellInvocation(**{k: v for k, v in c.items() if k in cell_fields})
        for c in data.get("cells", [])
    ]
    return invocation_mod.ArmInvocation(
        arm=data["arm"],
        skill=data["skill"],
        invoke_mode=data.get("invoke_mode", invocation_mod.INVOKE_DEFAULT),
        invoked=bool(data.get("invoked")),
        cells=cells,
    )


def rebuild(run_dir: Path) -> Path:
    """Regenerate `REPORT.md` over a run that is already on disk.

    The report is a view over the run tree, so it must be re-renderable without
    re-running anything: improving it is otherwise unverifiable except by
    billing another live run.
    """
    data = json.loads((run_dir / manifest_mod.RUN_MANIFEST_NAME).read_text())

    cells: list[tuple[str, int | None, Path]] = []
    records: list[invocation_mod.ArmInvocation] = []
    for entry in data.get("arms", []):
        arm_dir = run_dir / entry["dir"]
        if not arm_dir.is_dir():
            continue
        trial_dirs = sorted(
            (p for p in arm_dir.iterdir() if p.is_dir() and p.name.isdigit()),
            key=lambda p: int(p.name),
        )
        for cell_dir in trial_dirs:
            cells.append((entry["arm"], _exit_from_stream(cell_dir / "stream.jsonl"), cell_dir))
        record_path = arm_dir / invocation_mod.INVOCATION_NAME
        if record_path.is_file():
            records.append(_record_from_dict(json.loads(record_path.read_text())))

    return write_report(
        run_dir=run_dir,
        run_id=data.get("run_id", run_dir.name),
        skill=data.get("skill", ""),
        arm=", ".join(entry["arm"] for entry in data.get("arms", [])),
        model=data.get("model", ""),
        prompt=data.get("prompt", ""),
        cells=cells,
        runner=data.get("runner", runners.DEFAULT),
        invocations=records,
        invoke_mode=data.get("invoke", invocation_mod.INVOKE_DEFAULT),
        trials=int(data.get("trials", 1) or 1),
        note=REBUILT_NOTE,
    )
