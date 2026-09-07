"""The invocation check — the only automated check, so it is itself checked.

A detector nobody tested is worse than no detector, because it will be trusted.
The negative control is therefore the first test in the file and is run three
ways: against the real recorded transcript (which contains no `Skill` call at
all), against a stub run with nothing installed, and against a run that invoked
some *other* skill.

Nothing here needs a network or a billed token.
"""

import dataclasses
import io
import json

import pytest

from evals import __main__ as cli
from evals import arms, cell, invocation, paths, report, runners

from . import helpers


@pytest.fixture
def skill_src(tmp_path):
    src = tmp_path / "skills" / "demo"
    (src / "references").mkdir(parents=True)
    (src / "SKILL.md").write_text("---\nname: demo\n---\nbody\n")
    (src / "references" / "extra.md").write_text("detail\n")
    return src


def _stream(tmp_path, events, name="stream.jsonl"):
    path = tmp_path / name
    path.write_text("".join(json.dumps(e) + "\n" for e in events))
    return path


def _assistant(blocks):
    return {"type": "assistant", "message": {"role": "assistant", "content": blocks}}


def _tool_use(name, args, tid="toolu_1"):
    return {"type": "tool_use", "id": tid, "name": name, "input": args}


def _init(skills):
    return {"type": "system", "subtype": "init", "skills": list(skills)}


# --- the negative control ---------------------------------------------------


def test_the_recorded_live_stream_reports_not_invoked():
    """The real transcript from the walking skeleton never called a skill.

    This is the strongest negative control available offline: not a hand-written
    stream shaped to fail, but a stream a real agent actually produced.
    """
    record = invocation.parse_stream(helpers.LIVE_STREAM, "rich-doc")
    assert record.invoked is False
    assert record.skill_calls == []


def test_a_stub_run_with_nothing_installed_reports_not_invoked(tmp_path):
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
    stream = tmp_path / "stream.jsonl"
    stream.write_bytes(buf.getvalue())

    record = invocation.parse_stream(stream, "demo")
    assert record.invoked is False
    assert record.registered is False
    assert record.reads == []


def test_another_skill_firing_is_not_this_skill_firing(tmp_path):
    """Half the value of the check is that it cannot be satisfied by accident."""
    stream = _stream(tmp_path, [
        _init(["demo", "other"]),
        _assistant([_tool_use("Skill", {"skill": "other"})]),
    ])
    record = invocation.parse_stream(stream, "demo")
    assert record.invoked is False
    assert record.skill_calls == ["other"]
    assert record.registered is True


# --- the positive case ------------------------------------------------------


def test_a_stub_run_reports_invoked_with_a_nonempty_read_list(tmp_path, skill_src):
    out = tmp_path / "cell"
    cell.run_cell(out, "demo", skill_src, "p", model="m", runner=runners.STUB)

    record = invocation.parse_stream(out / "stream.jsonl", "demo")
    assert record.invoked is True
    assert record.registered is True
    assert record.skill_calls == ["demo"]
    assert record.reads == ["SKILL.md"]
    assert record.bash == ["ls -la"]


def test_plugin_qualified_and_slashed_names_name_the_same_skill(tmp_path):
    for named in ("plugin:demo", "/demo", "demo"):
        stream = _stream(tmp_path, [
            _init(["demo"]),
            _assistant([_tool_use("Skill", {"skill": named})]),
        ])
        assert invocation.parse_stream(stream, "demo").invoked is True, named


def test_the_skill_name_is_read_from_whichever_key_carries_it(tmp_path):
    for key in ("skill", "command", "name"):
        stream = _stream(tmp_path, [
            _init(["demo"]),
            _assistant([_tool_use("Skill", {key: "demo"})]),
        ])
        assert invocation.parse_stream(stream, "demo").invoked is True, key


# --- what it read -----------------------------------------------------------


def test_reads_are_normalised_to_skill_relative_paths(tmp_path):
    stream = _stream(tmp_path, [
        _init(["demo"]),
        _assistant([_tool_use("Skill", {"skill": "demo"}, "t0")]),
        _assistant([_tool_use("Read", {"file_path": "/tmp/evals-x/config/skills/demo/SKILL.md"}, "t1")]),
        _assistant([_tool_use("Read", {"file_path": "/tmp/evals-y/config/skills/demo/references/deep.md"}, "t2")]),
    ])
    record = invocation.parse_stream(stream, "demo")
    # Two different clean rooms, comparable paths: the temp prefix is exactly
    # what makes raw paths useless for comparing arms.
    assert record.reads == ["SKILL.md", "references/deep.md"]


def test_reads_outside_the_skill_are_counted_not_listed(tmp_path):
    stream = _stream(tmp_path, [
        _init(["demo"]),
        _assistant([_tool_use("Read", {"file_path": "/tmp/ws/notes.txt"}, "t1")]),
        _assistant([_tool_use("Read", {"file_path": "/tmp/c/skills/other/SKILL.md"}, "t2")]),
    ])
    record = invocation.parse_stream(stream, "demo")
    assert record.reads == []
    assert record.reads_outside_skill == 2


def test_repeated_reads_are_deduped(tmp_path):
    path = "/tmp/c/skills/demo/SKILL.md"
    stream = _stream(tmp_path, [
        _init(["demo"]),
        _assistant([_tool_use("Read", {"file_path": path}, "t1")]),
        _assistant([_tool_use("Read", {"file_path": path}, "t2")]),
    ])
    assert invocation.parse_stream(stream, "demo").reads == ["SKILL.md"]


def test_bash_commands_are_collected_in_order(tmp_path):
    """rich-doc shells out to `pd-lint.mjs`; whether it did is a real signal."""
    stream = _stream(tmp_path, [
        _init(["demo"]),
        _assistant([_tool_use("Bash", {"command": "node pd-lint.mjs doc.html"}, "t1")]),
        _assistant([_tool_use("Bash", {"command": "ls"}, "t2")]),
    ])
    assert invocation.parse_stream(stream, "demo").bash == ["node pd-lint.mjs doc.html", "ls"]


def test_a_skill_directory_named_like_the_skill_is_matched_anywhere(tmp_path):
    assert invocation.relative_to_skill("x/skills/demo/a/b.md", "demo") == "a/b.md"
    assert invocation.relative_to_skill("/skills/demo/SKILL.md", "demo") == "SKILL.md"
    assert invocation.relative_to_skill("/skills/demo/", "demo") is None
    assert invocation.relative_to_skill("/skills/demoish/SKILL.md", "demo") is None
    assert invocation.relative_to_skill("/other/SKILL.md", "demo") is None


# --- registration, without asserting the built-in floor ---------------------


def test_registration_asks_only_about_our_own_skill(tmp_path, monkeypatch, skill_src):
    """The built-in floor drifts by CLI version *and* environment.

    So `registered` is membership of the skill under test and nothing else.
    Rewriting the floor entirely must not move the verdict — the moment a count
    or a membership of the floor becomes a contract, this check has a time bomb
    in it (`test_stub_floor_is_not_load_bearing` pins the same principle).
    """
    monkeypatch.setattr(runners, "STUB_BUILTIN_SKILLS", ("something", "else"))
    out = tmp_path / "cell"
    cell.run_cell(out, "demo", skill_src, "p", model="m", runner=runners.STUB)
    record = invocation.parse_stream(out / "stream.jsonl", "demo")
    assert record.invoked is True
    assert record.registered is True


def test_a_stream_with_no_init_event_is_simply_unregistered(tmp_path):
    stream = _stream(tmp_path, [_assistant([_tool_use("Skill", {"skill": "demo"})])])
    record = invocation.parse_stream(stream, "demo")
    assert record.registered is False
    assert record.invoked is True


# --- damaged input ----------------------------------------------------------


def test_a_truncated_transcript_still_yields_a_verdict(tmp_path):
    """A killed run leaves a half-written line. That must not crash the check."""
    path = tmp_path / "stream.jsonl"
    path.write_text(
        json.dumps(_init(["demo"])) + "\n"
        + json.dumps(_assistant([_tool_use("Skill", {"skill": "demo"})])) + "\n"
        + '{"type": "result", "resu'
    )
    assert invocation.parse_stream(path, "demo").invoked is True


def test_event_types_the_parser_does_not_model_are_ignored(tmp_path):
    stream = _stream(tmp_path, [
        {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed"}},
        _init(["demo"]),
        {"type": "system", "subtype": "thinking_tokens"},
        _assistant([{"type": "thinking", "thinking": "hm"}]),
        _assistant([_tool_use("Skill", {"skill": "demo"})]),
    ])
    assert invocation.parse_stream(stream, "demo").invoked is True


def test_a_missing_transcript_reports_not_invoked(tmp_path):
    """No evidence is not evidence of invocation."""
    record = invocation.parse_stream(tmp_path / "absent.jsonl", "demo")
    assert record.invoked is False


# --- the arm record ---------------------------------------------------------


def test_analyse_arm_writes_invocation_json_beside_the_cells(tmp_path, skill_src):
    arm_dir = tmp_path / "run" / "WORKTREE"
    cell_dir = arm_dir / "1"
    cell.run_cell(cell_dir, "demo", skill_src, "p", model="m", runner=runners.STUB)

    record = invocation.analyse_arm(arm_dir, "WORKTREE", "demo", [cell_dir])
    written = json.loads((arm_dir / invocation.INVOCATION_NAME).read_text())
    assert written["invoked"] is True
    assert written["arm"] == "WORKTREE"
    assert written["skill"] == "demo"
    assert written["invoke_mode"] == invocation.INSTRUCTED
    assert written["missed_trials"] == []
    assert written["cells"][0]["reads"] == ["SKILL.md"]
    assert record.reads == ["SKILL.md"]


def test_one_silent_trial_makes_the_whole_arm_not_invoked(tmp_path):
    """A miss in one trial of three corrupts the comparison; it cannot be averaged."""
    arm_dir = tmp_path / "arm"
    good, bad = arm_dir / "1", arm_dir / "2"
    good.mkdir(parents=True)
    bad.mkdir(parents=True)
    _stream(good, [_init(["demo"]), _assistant([_tool_use("Skill", {"skill": "demo"})])])
    _stream(bad, [_init(["demo"])])

    record = invocation.analyse_arm(arm_dir, "A", "demo", [good, bad])
    assert record.invoked is False
    assert record.missed_trials == [2]


def test_an_arm_with_no_cells_is_not_invoked(tmp_path):
    assert invocation.analyse_arm(tmp_path / "arm", "A", "demo", []).invoked is False


# --- the two invoke modes ---------------------------------------------------


def test_instructed_mode_names_the_skill_in_the_prompt():
    out = invocation.apply_invoke_mode("do the thing", "rich-doc", invocation.INSTRUCTED)
    assert out.startswith("do the thing")
    assert "rich-doc" in out.removeprefix("do the thing")


def test_organic_mode_leaves_the_prompt_exactly_alone():
    """Any addition at all would be the harness doing the routing it is measuring."""
    assert invocation.apply_invoke_mode("do the thing", "rich-doc", invocation.ORGANIC) == "do the thing"


def test_instructed_is_the_default():
    assert invocation.INVOKE_DEFAULT == invocation.INSTRUCTED
    assert invocation.apply_invoke_mode("p", "s") != "p"


def test_an_unknown_invoke_mode_is_refused():
    with pytest.raises(ValueError, match="invoke mode"):
        invocation.apply_invoke_mode("p", "s", "sometimes")


def test_cell_invocation_is_serialisable(tmp_path):
    """`invocation.json` has to survive a round trip to be worth writing."""
    record = invocation.parse_stream(helpers.LIVE_STREAM, "rich-doc")
    assert json.loads(json.dumps(dataclasses.asdict(record)))["invoked"] is False


# --- through the CLI, both directions ---------------------------------------


@pytest.fixture
def compiled(tmp_path, monkeypatch):
    """A `skills/` tree the WORKTREE arm can copy, without running the compiler.

    The compiler rewrites the repo's real `skills/` directory, which a test must
    not do. Everything downstream of arm resolution is the production path.
    """
    root = tmp_path / "compiled"
    src = root / "demo"
    (src / "references").mkdir(parents=True)
    (src / "SKILL.md").write_text("---\nname: demo\n---\nbody\n")
    (src / "references" / "extra.md").write_text("detail\n")
    monkeypatch.setattr(arms, "compile_skills", lambda: None)
    monkeypatch.setattr(arms, "COMPILED_SKILLS_DIR", root)
    monkeypatch.setattr(paths, "RUNS_DIR", tmp_path / "runs")
    return root


def _report(tmp_path):
    run_dir = next((tmp_path / "runs").iterdir())
    return (run_dir / report.REPORT_NAME).read_text(), run_dir


def test_cli_shouts_when_the_skill_never_fired(compiled, tmp_path, capsys):
    """The negative control, end to end: `--arm none --invoke instructed`.

    Nothing is installed, so nothing can fire. If this run ever reports
    `invoked`, the check is broken and every result it has ever blessed is
    suspect — which is why it is asserted rather than assumed.
    """
    code = cli.main(
        ["run", "--skill", "demo", "--arm", arms.NONE,
         "--prompt", "write me an answer", "--invoke", invocation.INSTRUCTED,
         "--runner", runners.STUB]
    )
    assert code == 0

    text, run_dir = _report(tmp_path)
    assert text.startswith(report.NOT_INVOKED_HEADING), "the warning must be the first thing read"
    assert "This run is not a comparison" in text
    assert "SKILL NOT INVOKED" in capsys.readouterr().out

    written = json.loads((run_dir / arms.NONE / invocation.INVOCATION_NAME).read_text())
    assert written["invoked"] is False
    assert written["cells"][0]["registered"] is False


def test_cli_reports_invoked_with_a_nonempty_read_list(compiled, tmp_path):
    """The positive case. A detector that only ever says 'no' is also broken."""
    code = cli.main(
        ["run", "--skill", "demo", "--arm", arms.WORKTREE,
         "--prompt", "write me an answer", "--runner", runners.STUB]
    )
    assert code == 0

    text, run_dir = _report(tmp_path)
    assert report.NOT_INVOKED_HEADING not in text
    assert "invoked" in text
    assert "`SKILL.md`" in text

    written = json.loads((run_dir / arms.WORKTREE / invocation.INVOCATION_NAME).read_text())
    assert written["invoked"] is True
    assert written["cells"][0]["reads"] == ["SKILL.md"]


def test_cli_healthy_two_arm_run_raises_no_alarm(compiled, tmp_path):
    """The real shape of an A/B: the baseline is *meant* to be silent.

    `none` installs nothing, so it cannot invoke; alarming on that fired the
    banner on every correct with/without run, and a reader who sees the red
    banner on every healthy run stops reading it (`skills-7k7.15`). The fact
    still has to be *stated* — just as a table row, not as an alarm.
    """
    code = cli.main(
        ["run", "--skill", "demo", "--arm", arms.NONE, "--arm", arms.WORKTREE,
         "--prompt", "p", "--runner", runners.STUB]
    )
    assert code == 0
    text, run_dir = _report(tmp_path)

    assert json.loads(
        (run_dir / arms.NONE / invocation.INVOCATION_NAME).read_text()
    )["invoked"] is False, "fixture: the baseline must genuinely not have invoked"
    assert json.loads(
        (run_dir / arms.WORKTREE / invocation.INVOCATION_NAME).read_text()
    )["invoked"] is True, "fixture: the skill arm must genuinely have invoked"

    assert report.NOT_INVOKED_HEADING not in text
    assert "This run is not a comparison" not in text
    assert report.BASELINE_NOT_INVOKED in text, "the baseline's silence is still on the page"


def test_cli_alarm_still_fires_when_an_installed_arm_stays_silent(compiled, tmp_path):
    """The other direction, or the fix is just a banner that never fires.

    Same healthy run, with the skill arm's verdict flipped to a miss and the
    report regenerated over it: the arm *had* the skill installed and did not
    run it, so nothing anywhere ran the skill. That is the failure the banner
    exists for, and it must still shout.
    """
    assert cli.main(
        ["run", "--skill", "demo", "--arm", arms.NONE, "--arm", arms.WORKTREE,
         "--prompt", "p", "--runner", runners.STUB]
    ) == 0
    run_dir = next((tmp_path / "runs").iterdir())

    record_path = run_dir / arms.WORKTREE / invocation.INVOCATION_NAME
    record = json.loads(record_path.read_text())
    record["invoked"] = False
    record["cells"][0]["invoked"] = False
    record["cells"][0]["skill_calls"] = []
    record_path.write_text(json.dumps(record, indent=2))

    text = report.rebuild(run_dir).read_text()
    assert text.startswith(report.NOT_INVOKED_HEADING), "the alarm must be the first thing read"
    banner = text.split("---")[0]
    assert f"`{arms.WORKTREE}` — no `Skill` call" in banner
    # Nothing ran the skill anywhere, so there is genuinely nothing to compare.
    assert "This run is not a comparison" in banner


def test_cli_instructed_mode_puts_the_skill_in_the_sent_prompt(compiled, tmp_path):
    """The report shows the prompt *as sent*, or it documents a run that never happened."""
    cli.main(["run", "--skill", "demo", "--arm", arms.NONE, "--prompt", "do it",
              "--runner", runners.STUB])
    text, _ = _report(tmp_path)
    assert invocation.instruction_for("demo") in text
    assert f"invoke: `{invocation.INSTRUCTED}`" in text


def test_cli_organic_mode_sends_the_prompt_untouched(compiled, tmp_path):
    cli.main(["run", "--skill", "demo", "--arm", arms.NONE, "--prompt", "do it",
              "--invoke", invocation.ORGANIC, "--runner", runners.STUB])
    text, _ = _report(tmp_path)
    assert invocation.instruction_for("demo") not in text
    # A miss under organic is the measurement, not a broken run — and the report
    # has to say so, or a reader files a bug against the harness.
    assert report.NOT_INVOKED_HEADING in text
    assert "this is the measurement rather than a fault" in text


def test_cli_defaults_to_instructed(compiled):
    args = cli.build_parser().parse_args(
        ["run", "--skill", "demo", "--arm", arms.NONE, "--prompt", "p"]
    )
    assert args.invoke == invocation.INSTRUCTED
