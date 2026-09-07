"""What the stub's canned transcript has to contain.

The invocation parser (skills-7k7.4) will be built and regression-tested against
this output. If the stub emits a simplified stream, the parser passes here and
fails on the only stream that matters — so the `tool_use` blocks it will parse
are asserted individually, and `test_stream_parity.py` checks their shape against
a recorded live run.
"""

import io
import json

import pytest

from evals import cell, runners

from . import helpers


@pytest.fixture
def skill_src(tmp_path):
    src = tmp_path / "skills" / "demo"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("---\nname: demo\n---\nbody\n")
    return src


@pytest.fixture
def stub_events(tmp_path, skill_src):
    out = tmp_path / "cell"
    cell.run_cell(out, "demo", skill_src, "p", model="m", runner=runners.STUB)
    return helpers.read_stream(out / "stream.jsonl")


def _tool_uses(events):
    return [
        block
        for event in events
        if event.get("type") == "assistant"
        for block in event["message"]["content"]
        if block.get("type") == "tool_use"
    ]


def test_stub_emits_a_skill_tool_use_naming_the_installed_skill(stub_events):
    skills = [b for b in _tool_uses(stub_events) if b["name"] == "Skill"]
    assert len(skills) == 1
    assert skills[0]["input"]["skill"] == "demo"
    assert skills[0]["id"].startswith("toolu_")


def test_stub_emits_read_and_bash_tool_uses(stub_events):
    names = [b["name"] for b in _tool_uses(stub_events)]
    assert {"Read", "Bash", "Write"} <= set(names)
    read = next(b for b in _tool_uses(stub_events) if b["name"] == "Read")
    assert read["input"]["file_path"].endswith("/skills/demo/SKILL.md")
    bash = next(b for b in _tool_uses(stub_events) if b["name"] == "Bash")
    assert bash["input"]["command"]


def test_every_tool_use_gets_a_matching_tool_result(stub_events):
    """A parser that pairs calls with results must have pairs to find."""
    used = {b["id"] for b in _tool_uses(stub_events)}
    returned = {
        block["tool_use_id"]
        for event in stub_events
        if event.get("type") == "user"
        for block in event["message"]["content"]
        if block.get("type") == "tool_result"
    }
    assert used and used == returned


def test_stub_init_event_lists_the_installed_skill(stub_events):
    init = next(e for e in stub_events if e.get("subtype") == "init")
    assert "demo" in init["skills"]
    assert init["permissionMode"] == "bypassPermissions"
    assert init["model"] == "m"


def test_stub_floor_is_not_load_bearing(tmp_path, monkeypatch, skill_src):
    """Nothing may depend on the built-in skill floor — it drifts by environment.

    Rewriting the floor entirely must change only the init event's contents, and
    break nothing: the moment a count or a membership becomes a contract, the
    harness has a time bomb in it.
    """
    monkeypatch.setattr(runners, "STUB_BUILTIN_SKILLS", ("something", "else"))
    out = tmp_path / "cell"
    result = cell.run_cell(out, "demo", skill_src, "p", model="m", runner=runners.STUB)
    assert result.exit_code == 0
    helpers.assert_cell_shape(out)
    helpers.assert_stream_is_wellformed(out / "stream.jsonl")
    init = next(e for e in helpers.read_stream(out / "stream.jsonl") if e.get("subtype") == "init")
    assert set(init["skills"]) == {"something", "else", "demo"}


def test_stub_narrates_only_what_it_actually_did(tmp_path, skill_src):
    """The Write it reports must really be on disk, or `ws/` and the transcript lie."""
    out = tmp_path / "cell"
    cell.run_cell(out, "demo", skill_src, "p", model="m", runner=runners.STUB)
    events = helpers.read_stream(out / "stream.jsonl")
    write = next(b for b in _tool_uses(events) if b["name"] == "Write")
    written = out / "ws" / write["input"]["file_path"].rsplit("/", 1)[-1]
    assert written.read_text() == write["input"]["content"]


def test_stub_transcript_is_deterministic(tmp_path, skill_src):
    """Same invocation and same starting workspace — byte-identical transcript.

    The workspace is reset between the two runs because the stub's `Bash` result
    reports the workspace as it really is: after the first run `answer.md` exists.
    Reflecting the true directory is worth more than determinism across differing
    states, and the fast lane is still diffable where it matters.
    """
    ws = tmp_path / "ws"
    ws.mkdir()
    inv = runners.Invocation(
        argv=runners.build_argv("p", "m"),
        cwd=ws,
        env={"CLAUDE_CONFIG_DIR": str(tmp_path / "config")},
        prompt="p",
        model="m",
        skill_name="demo",
    )
    written = []
    for _ in range(2):
        for stale in ws.iterdir():
            stale.unlink()
        buf = io.BytesIO()
        runners.run_stub(inv, buf, io.BytesIO())
        written.append(buf.getvalue())
    assert written[0] == written[1]


def test_stub_omits_the_skill_block_when_no_skill_is_installed(tmp_path):
    """The `none` arm: nothing to invoke, so nothing may claim it was invoked."""
    ws = tmp_path / "ws"
    ws.mkdir()
    inv = runners.Invocation(
        argv=runners.build_argv("p", "m"),
        cwd=ws,
        env={"CLAUDE_CONFIG_DIR": str(tmp_path / "config")},
        prompt="p",
        model="m",
        skill_name=None,
    )
    buf = io.BytesIO()
    runners.run_stub(inv, buf, io.BytesIO())
    events = [json.loads(line) for line in buf.getvalue().decode().splitlines()]
    names = [
        b["name"]
        for e in events
        if e.get("type") == "assistant"
        for b in e["message"]["content"]
        if b.get("type") == "tool_use"
    ]
    assert "Skill" not in names
    init = next(e for e in events if e.get("subtype") == "init")
    assert "demo" not in init["skills"]
