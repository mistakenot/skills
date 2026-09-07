"""A `Skill` call that failed is not an invocation — checked against reality.

This file exists because the check it guards was already wrong once, and passed
its own negative control while being wrong (`skills-7k7.11`). The `none` arm of
an `--invoke instructed` run reported `invoked: true`, because the CLI emits a
`Skill` tool_use even when the skill is not installed and the detector read the
call without its reply.

**The stub was too kind.** It modelled "skill absent" as *no `Skill` call at
all*, and never emitted a failed tool call of any kind — so the negative control
passed against the world the implementer imagined instead of against the CLI.
Every assertion here is therefore anchored to a recorded live transcript
(`fixtures/live-none-instructed-stream.jsonl` and its `WORKTREE` twin), and the
stub is checked *against* those recordings rather than trusted on its own.

The order is deliberate: reality first, then the stub, then the CLI end to end.
"""

import io
import json

import pytest

from evals import __main__ as cli
from evals import arms, invocation, paths, report, runners

from . import helpers


def _stream(tmp_path, events, name="stream.jsonl"):
    path = tmp_path / name
    path.write_text("".join(json.dumps(e) + "\n" for e in events))
    return path


def _assistant(blocks):
    return {"type": "assistant", "message": {"role": "assistant", "content": blocks}}


def _tool_use(name, args, tid="toolu_1"):
    return {"type": "tool_use", "id": tid, "name": name, "input": args}


def _tool_result(tid, content, is_error=None):
    block = {"type": "tool_result", "tool_use_id": tid, "content": content}
    if is_error is not None:
        block["is_error"] = is_error
    return {"type": "user", "message": {"role": "user", "content": [block]}}


def _init(skills):
    return {"type": "system", "subtype": "init", "skills": list(skills)}


def _skill_calls(events):
    return [
        b
        for e in events
        if e.get("type") == "assistant"
        for b in e["message"]["content"]
        if b.get("type") == "tool_use" and b["name"] == "Skill"
    ]


# --- ground truth: the recorded run ----------------------------------------


def test_the_recorded_none_arm_asked_for_the_skill_and_was_refused():
    """The fixture has to contain the thing it is a fixture for.

    If the recording is ever re-cut without the failed call, every assertion
    below becomes vacuous while still passing — so the evidence is asserted
    before it is relied on.
    """
    events = helpers.read_stream(helpers.LIVE_NONE_STREAM)
    calls = _skill_calls(events)
    assert [c["input"]["skill"] for c in calls] == [helpers.LIVE_SKILL]

    results = {
        b["tool_use_id"]: b
        for e in events
        if e.get("type") == "user"
        for b in e["message"]["content"]
        if b.get("type") == "tool_result"
    }
    refusal = results[calls[0]["id"]]
    assert refusal["is_error"] is True
    assert "Unknown skill" in refusal["content"]


def test_the_recorded_none_arm_reports_not_invoked():
    """The bug, as a test: a real transcript in which the skill did not load.

    `invoked` was `true` here. Nothing else about the run changed — the same
    bytes, read correctly.
    """
    record = invocation.parse_stream(helpers.LIVE_NONE_STREAM, helpers.LIVE_SKILL)
    assert record.invoked is False
    assert record.registered is False, "init.skills corroborates: it was never installed"
    assert record.skill_calls == [helpers.LIVE_SKILL], "it *was* asked for"
    assert record.failed_skill_calls == [helpers.LIVE_SKILL], "and refused"


def test_the_recorded_worktree_arm_reports_invoked():
    """The other half of the same run, or the fix is just a detector that says no.

    A check that reports NOT INVOKED for everything is exactly as useless as one
    that reports INVOKED for everything; both halves come from one real A/B.
    """
    record = invocation.parse_stream(helpers.LIVE_WORKTREE_STREAM, helpers.LIVE_SKILL)
    assert record.invoked is True
    assert record.registered is True
    assert record.failed_skill_calls == []


def test_the_recorded_worktree_arm_never_read_the_skill_with_a_read_tool():
    """The read-list undercount: the `Skill` tool opens `SKILL.md` itself.

    A genuinely-invoked arm made *zero* `Read` calls into the skill directory, so
    counting only `Read` blocks reported "0 files read from it" for the arm that
    ran the skill — evidence pointing the wrong way. The load itself is counted,
    and the corroborating evidence the run really left is the `Bash` line that
    runs a script out of the skill directory.
    """
    events = helpers.read_stream(helpers.LIVE_WORKTREE_STREAM)
    reads = [
        b["input"]["file_path"]
        for e in events
        if e.get("type") == "assistant"
        for b in e["message"]["content"]
        if b.get("type") == "tool_use" and b["name"] == "Read"
    ]
    assert not [p for p in reads if f"skills/{helpers.LIVE_SKILL}/" in p]

    record = invocation.parse_stream(helpers.LIVE_WORKTREE_STREAM, helpers.LIVE_SKILL)
    assert record.reads == ["SKILL.md"]
    assert record.skill_bash and "pd-lint.mjs" in record.skill_bash[0]


def test_the_none_arm_ran_bash_but_none_of_it_touched_the_skill():
    """`skill_bash` must discriminate, or it is just `bash` under another name."""
    record = invocation.parse_stream(helpers.LIVE_NONE_STREAM, helpers.LIVE_SKILL)
    assert record.bash, "the baseline agent did work"
    assert record.skill_bash == []


# --- the rule, in isolation -------------------------------------------------


def test_a_refused_skill_call_is_not_an_invocation(tmp_path):
    stream = _stream(tmp_path, [
        _init(["other"]),
        _assistant([_tool_use("Skill", {"skill": "demo"}, "t0")]),
        _tool_result("t0", "<tool_use_error>Unknown skill: demo</tool_use_error>", True),
    ])
    record = invocation.parse_stream(stream, "demo")
    assert record.invoked is False
    assert record.failed_skill_calls == ["demo"]


def test_the_error_marker_alone_is_enough(tmp_path):
    """Belt and braces: `<tool_use_error>` without the `is_error` flag still fails.

    The flag and the marker are two encodings of one fact and the CLI has emitted
    both; relying on exactly one of them is how this check broke the first time.
    """
    stream = _stream(tmp_path, [
        _init(["demo"]),
        _assistant([_tool_use("Skill", {"skill": "demo"}, "t0")]),
        _tool_result("t0", "<tool_use_error>Unknown skill: demo</tool_use_error>"),
    ])
    assert invocation.parse_stream(stream, "demo").invoked is False


def test_a_successful_call_is_still_an_invocation(tmp_path):
    stream = _stream(tmp_path, [
        _init(["demo"]),
        _assistant([_tool_use("Skill", {"skill": "demo"}, "t0")]),
        _tool_result("t0", "Launching skill: demo"),
    ])
    record = invocation.parse_stream(stream, "demo")
    assert record.invoked is True
    assert record.failed_skill_calls == []


def test_a_result_that_never_arrived_is_unknown_not_failed(tmp_path):
    """A run killed mid-call still called. Absence of a reply is not a refusal."""
    stream = _stream(tmp_path, [
        _init(["demo"]),
        _assistant([_tool_use("Skill", {"skill": "demo"}, "t0")]),
    ])
    assert invocation.parse_stream(stream, "demo").invoked is True


def test_an_init_event_that_omits_the_skill_vetoes_the_claim(tmp_path):
    """Corroboration, not substitution.

    `registered` is not swapped in for the tool-call evidence — it constrains it
    in one direction. If the CLI said the skill was not there, no later event in
    the same transcript can mean it loaded, whatever the result block says.
    """
    stream = _stream(tmp_path, [
        _init(["something", "else"]),
        _assistant([_tool_use("Skill", {"skill": "demo"}, "t0")]),
        _tool_result("t0", "Launching skill: demo"),
    ])
    record = invocation.parse_stream(stream, "demo")
    assert record.invoked is False
    assert record.registered is False


def test_no_init_event_vetoes_nothing(tmp_path):
    """Unknown registration is not absent registration.

    A transcript without an init event says nothing about what was installed, so
    it may not be read as saying the skill was missing.
    """
    stream = _stream(tmp_path, [
        _assistant([_tool_use("Skill", {"skill": "demo"}, "t0")]),
        _tool_result("t0", "Launching skill: demo"),
    ])
    record = invocation.parse_stream(stream, "demo")
    assert record.init_seen is False
    assert record.invoked is True


# --- the stub, checked against the recording --------------------------------


def _stub_events(tmp_path, prompt, skill_name):
    ws = tmp_path / "ws"
    ws.mkdir(exist_ok=True)
    inv = runners.Invocation(
        argv=runners.build_argv(prompt, "m"),
        cwd=ws,
        env={"CLAUDE_CONFIG_DIR": str(tmp_path / "config")},
        prompt=prompt,
        model="m",
        skill_name=skill_name,
    )
    buf = io.BytesIO()
    runners.run_stub(inv, buf, io.BytesIO())
    return [json.loads(line) for line in buf.getvalue().decode().splitlines()]


def test_the_stub_emits_a_failed_skill_call_for_an_absent_instructed_skill(tmp_path):
    """The fidelity fix. Without this the detection fix cannot be tested offline."""
    prompt = invocation.apply_invoke_mode("do it", "demo", invocation.INSTRUCTED)
    calls = _skill_calls(_stub_events(tmp_path, prompt, skill_name=None))
    assert [c["input"]["skill"] for c in calls] == ["demo"]


def test_the_stubs_failed_result_has_the_shape_the_cli_really_returns(tmp_path):
    """Field by field against the recording, so the stub cannot drift kind again.

    A stub that fails in a shape the CLI never produces is the same bug wearing
    a different hat: the parser would be tuned to the invention.
    """
    prompt = invocation.apply_invoke_mode("do it", "demo", invocation.INSTRUCTED)
    stub = _stub_events(tmp_path, prompt, skill_name=None)
    call = _skill_calls(stub)[0]
    stub_event = next(
        e for e in stub
        if e.get("type") == "user"
        and e["message"]["content"][0]["tool_use_id"] == call["id"]
    )

    live = helpers.read_stream(helpers.LIVE_NONE_STREAM)
    live_call = _skill_calls(live)[0]
    live_event = next(
        e for e in live
        if e.get("type") == "user"
        and e["message"]["content"][0]["tool_use_id"] == live_call["id"]
    )

    assert set(stub_event) == set(live_event)
    assert set(stub_event["message"]["content"][0]) == set(live_event["message"]["content"][0])
    assert stub_event["message"]["content"][0]["is_error"] is True
    assert "<tool_use_error>" in stub_event["message"]["content"][0]["content"]
    assert isinstance(stub_event["tool_use_result"], str)


def test_the_stubs_failed_call_is_read_as_not_invoked(tmp_path):
    prompt = invocation.apply_invoke_mode("do it", "demo", invocation.INSTRUCTED)
    stream = tmp_path / "stream.jsonl"
    stream.write_text(
        "".join(json.dumps(e) + "\n" for e in _stub_events(tmp_path, prompt, None))
    )
    record = invocation.parse_stream(stream, "demo")
    assert record.invoked is False
    assert record.skill_calls == ["demo"]
    assert record.failed_skill_calls == ["demo"]


def test_the_stub_still_makes_no_skill_call_under_organic(tmp_path):
    """Nothing installed and nothing asked for: the agent has no reason to call."""
    prompt = invocation.apply_invoke_mode("do it", "demo", invocation.ORGANIC)
    assert _skill_calls(_stub_events(tmp_path, prompt, skill_name=None)) == []


def test_the_instruction_sentence_round_trips():
    """`instructed_skill` is the inverse of `instruction_for`, or the stub misreads."""
    sent = invocation.apply_invoke_mode("body text", "rich-doc", invocation.INSTRUCTED)
    assert invocation.instructed_skill(sent) == "rich-doc"
    assert invocation.instructed_skill("body text") is None


# --- end to end -------------------------------------------------------------


@pytest.fixture
def compiled(tmp_path, monkeypatch):
    root = tmp_path / "compiled"
    src = root / "demo"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("---\nname: demo\n---\nbody\n")
    monkeypatch.setattr(arms, "compile_skills", lambda: None)
    monkeypatch.setattr(arms, "COMPILED_SKILLS_DIR", root)
    monkeypatch.setattr(paths, "RUNS_DIR", tmp_path / "runs")
    return root


def test_cli_none_arm_under_instructed_asks_and_is_refused(compiled, tmp_path, capsys):
    """The whole failure, end to end, in the mode it actually shipped in.

    The `Skill` call is asserted to be *present* in the transcript: the old code
    passed this run's banner check only because the stub never made the call, and
    a test that passes for the wrong reason is what put this bug in production.
    """
    code = cli.main(
        ["run", "--skill", "demo", "--arm", arms.NONE, "--prompt", "write me an answer",
         "--invoke", invocation.INSTRUCTED, "--runner", runners.STUB]
    )
    assert code == 0

    run_dir = next((tmp_path / "runs").iterdir())
    events = helpers.read_stream(run_dir / arms.NONE / "1" / "stream.jsonl")
    assert [c["input"]["skill"] for c in _skill_calls(events)] == ["demo"], (
        "the stub must model the call the CLI really makes"
    )

    written = json.loads((run_dir / arms.NONE / invocation.INVOCATION_NAME).read_text())
    assert written["invoked"] is False
    assert written["cells"][0]["skill_calls"] == ["demo"]
    assert written["cells"][0]["failed_skill_calls"] == ["demo"]

    text = (run_dir / report.REPORT_NAME).read_text()
    assert text.startswith(report.NOT_INVOKED_HEADING)
    assert "SKILL NOT INVOKED" in capsys.readouterr().out
