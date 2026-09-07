"""Did the skill actually fire, and what did it open?

This is the only automated check in the harness, and it guards the one failure
that is silent and self-deceiving: **if the skill never loaded, both arms are the
same run.** Every other failure here announces itself — a missing credential, a
failing canary, a non-zero exit. This one produces two plausible outputs and lets
a human invent explanations for what is actually sampling noise.

**Ground truth is the tool calls, never a self-report.** The transcript is
`--output-format stream-json`, so the `Skill`, `Read` and `Bash` `tool_use` blocks
are right there. Asking the agent to emit a `FILES_READ:` trailer instead — the
route a multi-host harness has to take — buys a declaration where we can have a
record, at a cost in prompt tokens. Two views of the same run genuinely disagree:
`system/init`'s `skills` array and the agent's own account of its skills differ by
4-5 entries on the same binary ("The irreducible floor" in
`docs/headless-claude-cli-evals.md`). The machine-emitted one is the target.

Two things this module deliberately does not do:

  * It never compares `init.skills` to a hard-coded list. The built-in floor
    drifts by CLI version *and* environment; the only membership question asked
    is "was *our* skill registered", which is about the arm, not about the floor.
  * It never treats "not invoked" as an error to be raised. In `--invoke organic`
    a skill that does not fire *is the finding*. The job here is to make the fact
    impossible to miss, not to decide what it means.

`analyse_arm` writes `invocation.json` next to the arm's cells;
`report.py` renders `NOT_INVOKED_BANNER` from the same record.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

INVOCATION_NAME = "invocation.json"

# --- how the prompt asks for the skill -------------------------------------

INSTRUCTED = "instructed"
ORGANIC = "organic"
INVOKE_CHOICES = (INSTRUCTED, ORGANIC)
INVOKE_DEFAULT = INSTRUCTED


def instruction_for(skill: str) -> str:
    """The sentence `instructed` mode appends. Kept short and unambiguous."""
    return f"Invoke the {skill} skill before you begin."


def apply_invoke_mode(prompt: str, skill: str, mode: str = INVOKE_DEFAULT) -> str:
    """Return the prompt as it will actually be sent.

    `instructed` (the default) appends an explicit "invoke <skill>" instruction:
    it removes routing from the experiment so the run measures the skill's
    *content*, which is what a version-vs-version A/B is asking about.

    `organic` appends nothing, so the description has to earn the invocation.
    That measures *routing* — and there "did it fire" is the result, not a
    precondition, which is why nothing in this module escalates a miss.
    """
    if mode not in INVOKE_CHOICES:
        raise ValueError(f"unknown invoke mode {mode!r}; expected one of {', '.join(INVOKE_CHOICES)}")
    if mode == ORGANIC:
        return prompt
    return f"{prompt}\n\n{instruction_for(skill)}"


# --- reading the transcript -------------------------------------------------


def _events(stream_path: Path) -> list[dict]:
    """Parse a stream-json transcript, skipping blank and unparseable lines.

    A truncated final line is normal when a run is killed, and a stream carrying
    event types this module does not model is normal always. Neither may stop the
    check: a parser that throws on a damaged transcript reports nothing about the
    run it was meant to describe.
    """
    events: list[dict] = []
    try:
        text = stream_path.read_text(errors="replace")
    except OSError:
        return events
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _tool_uses(events: list[dict]) -> list[dict]:
    blocks = []
    for event in events:
        if event.get("type") != "assistant":
            continue
        content = (event.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                blocks.append(block)
    return blocks


def _skill_named(block: dict) -> str | None:
    """The skill a `Skill` tool_use names, whichever key the CLI used for it."""
    args = block.get("input")
    if not isinstance(args, dict):
        return None
    for key in ("skill", "command", "name"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _matches(named: str, skill: str) -> bool:
    """`rich-doc`, `plugin:rich-doc` and `/rich-doc` all name the same skill."""
    tail = named.lstrip("/").rsplit(":", 1)[-1]
    return tail == skill


def relative_to_skill(path: str, skill: str) -> str | None:
    """`.../skills/<skill>/references/x.md` -> `references/x.md`, else `None`.

    Matching on the `skills/<skill>/` segment rather than on the clean room's
    config dir keeps this honest for a skill read from anywhere it was installed,
    and keeps the recorded path comparable between arms whose temp dirs differ.
    """
    parts = Path(path.strip()).as_posix().split("/")
    for i in range(len(parts) - 2):
        if parts[i] == "skills" and parts[i + 1] == skill:
            rest = "/".join(parts[i + 2:])
            return rest or None
    return None


@dataclass(frozen=True)
class CellInvocation:
    """What one cell's transcript says about the skill under test."""

    trial: int
    invoked: bool
    registered: bool
    skill_calls: list[str] = field(default_factory=list)
    reads: list[str] = field(default_factory=list)
    reads_outside_skill: int = 0
    bash: list[str] = field(default_factory=list)


def parse_stream(stream_path: Path, skill: str, trial: int = 1) -> CellInvocation:
    """Read one `stream.jsonl` for evidence that `skill` fired, and what it read.

    `invoked` is true only when a `Skill` tool_use names *this* skill: a run that
    loaded some other skill is not this skill's run. `registered` reads
    `init.skills` — membership of our own skill only, never a comparison against
    the built-in floor. A false `registered` with a false `invoked` says the arm
    was mis-installed; a true `registered` with a false `invoked` says the agent
    chose not to use it, which in `organic` mode is the measurement.
    """
    events = _events(stream_path)

    registered = False
    for event in events:
        if event.get("type") == "system" and event.get("subtype") == "init":
            listed = event.get("skills")
            if isinstance(listed, list):
                registered = skill in listed
            break

    skill_calls: list[str] = []
    reads: list[str] = []
    bash: list[str] = []
    outside = 0
    for block in _tool_uses(events):
        name = block.get("name")
        args = block.get("input") if isinstance(block.get("input"), dict) else {}
        if name == "Skill":
            named = _skill_named(block)
            if named and named not in skill_calls:
                skill_calls.append(named)
        elif name == "Read":
            path = args.get("file_path")
            if not isinstance(path, str) or not path.strip():
                continue
            rel = relative_to_skill(path, skill)
            if rel is None:
                outside += 1
            elif rel not in reads:
                reads.append(rel)
        elif name == "Bash":
            command = args.get("command")
            if isinstance(command, str) and command.strip():
                bash.append(command)

    return CellInvocation(
        trial=trial,
        invoked=any(_matches(named, skill) for named in skill_calls),
        registered=registered,
        skill_calls=skill_calls,
        reads=reads,
        reads_outside_skill=outside,
        bash=bash,
    )


@dataclass(frozen=True)
class ArmInvocation:
    """One arm's verdict, as written to `invocation.json`."""

    arm: str
    skill: str
    invoke_mode: str
    invoked: bool
    cells: list[CellInvocation] = field(default_factory=list)

    @property
    def missed_trials(self) -> list[int]:
        return [c.trial for c in self.cells if not c.invoked]

    @property
    def reads(self) -> list[str]:
        """Every skill-relative file read anywhere in the arm, deduped."""
        seen: list[str] = []
        for c in self.cells:
            for path in c.reads:
                if path not in seen:
                    seen.append(path)
        return seen

    def to_dict(self) -> dict:
        return {
            "arm": self.arm,
            "skill": self.skill,
            "invoke_mode": self.invoke_mode,
            "invoked": self.invoked,
            "missed_trials": self.missed_trials,
            "cells": [asdict(c) for c in self.cells],
        }


def analyse_arm(
    arm_dir: Path,
    arm: str,
    skill: str,
    cell_dirs: list[Path],
    invoke_mode: str = INVOKE_DEFAULT,
) -> ArmInvocation:
    """Parse every cell of one arm and write `invocation.json` into `arm_dir`.

    The record goes beside the cells rather than inside one: the question it
    answers ("did this arm actually exercise the skill?") is about the arm, and
    the cell directory's five entries are the agent's own evidence, not ours.

    An arm counts as invoked only if *every* trial invoked. One silent trial in
    three still corrupts the comparison, so it may not be averaged away.
    """
    cells = [parse_stream(d / "stream.jsonl", skill, trial=i) for i, d in enumerate(cell_dirs, 1)]
    record = ArmInvocation(
        arm=arm,
        skill=skill,
        invoke_mode=invoke_mode,
        invoked=bool(cells) and all(c.invoked for c in cells),
        cells=cells,
    )
    arm_dir.mkdir(parents=True, exist_ok=True)
    (arm_dir / INVOCATION_NAME).write_text(json.dumps(record.to_dict(), indent=2) + "\n")
    return record
