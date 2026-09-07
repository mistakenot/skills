"""Structural assertions about a run, shared by every runner.

These exist so that "a stub run looks like a live run" is a checked property
rather than a hope. Both arms of `test_runner_seam.py` call the *same* functions
here; if the stub ever grows or loses a file, the shared assertion fails for the
stub arm while the live arm still passes, and the divergence is named.
"""

from __future__ import annotations

import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LIVE_STREAM = FIXTURES / "live-stream.jsonl"

# The two arms of one real `--invoke instructed` run of the rich-doc scenario.
# `none` contains the failed `Skill` call that the detector once read as an
# invocation; `worktree` is the same prompt with the skill installed. They are
# the ground truth for the invocation check — see `fixtures/README.md`.
LIVE_NONE_STREAM = FIXTURES / "live-none-instructed-stream.jsonl"
LIVE_WORKTREE_STREAM = FIXTURES / "live-worktree-instructed-stream.jsonl"
LIVE_SKILL = "rich-doc"

# Every file a cell leaves behind, whichever runner produced it.
CELL_ENTRIES = {"skill", "ws", "stream.jsonl", "out.md", "err.txt"}


def read_stream(path: Path) -> list[dict]:
    """Parse a stream-json transcript, skipping blank and unparseable lines."""
    events = []
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def live_events() -> list[dict]:
    """The recorded real transcript. See `fixtures/README.md`."""
    return read_stream(LIVE_STREAM)


def assert_cell_shape(out_dir: Path) -> None:
    """The evidence directory a cell must leave, regardless of runner."""
    assert out_dir.is_dir(), f"{out_dir} was not created"
    assert {p.name for p in out_dir.iterdir()} == CELL_ENTRIES, (
        f"{out_dir} holds {sorted(p.name for p in out_dir.iterdir())}, "
        f"expected exactly {sorted(CELL_ENTRIES)}"
    )
    assert (out_dir / "skill" / "SKILL.md").is_file(), "the installed skill was not snapshotted"
    assert (out_dir / "ws").is_dir(), "the workspace was not copied out"
    assert (out_dir / "stream.jsonl").is_file()
    assert (out_dir / "err.txt").is_file()
    assert (out_dir / "out.md").read_text().strip(), "out.md is empty — no result envelope was found"


def assert_stream_is_wellformed(stream_path: Path) -> None:
    """A transcript a downstream parser can work with, from either runner."""
    events = read_stream(stream_path)
    assert events, f"{stream_path} has no parseable events"
    assert all(isinstance(e, dict) and "type" in e for e in events)

    init = [e for e in events if e.get("type") == "system" and e.get("subtype") == "init"]
    assert len(init) == 1, "expected exactly one system/init event"
    # The init event is ground truth for what the agent could see. Read the list;
    # never compare it to a constant — the built-in floor drifts by CLI version
    # and by environment (docs/headless-claude-cli-evals.md).
    assert isinstance(init[0].get("skills"), list)

    results = [e for e in events if e.get("type") == "result"]
    assert len(results) == 1, "expected exactly one result envelope"
    assert results[0].get("result")
