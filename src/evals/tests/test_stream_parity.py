"""The stub's transcript must have the *shape* of a real one.

A stub that emits a convenient simplification is worse than no stub: every
downstream check built against it passes locally and fails on the only stream
that ships. So the stub's event shapes are compared, field by field, with a
transcript recorded from a live clean-room run (`fixtures/live-stream.jsonl`,
Claude Code 2.1.260).

When the CLI's stream shape genuinely changes, this test fails: re-record the
fixture and update the stub in the same commit.
"""

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


def _first(events, **match):
    return next(e for e in events if all(e.get(k) == v for k, v in match.items()))


def test_the_recording_is_readable():
    events = helpers.live_events()
    assert len(events) >= 5
    helpers.assert_stream_is_wellformed(helpers.LIVE_STREAM)


def test_stub_emits_the_same_event_types(stub_events):
    assert {e["type"] for e in stub_events} == {e["type"] for e in helpers.live_events()}


def test_init_event_carries_every_field_a_real_one_does(stub_events):
    live = _first(helpers.live_events(), type="system", subtype="init")
    stub = _first(stub_events, type="system", subtype="init")
    assert set(stub) == set(live)


def test_result_envelope_carries_every_field_a_real_one_does(stub_events):
    live = _first(helpers.live_events(), type="result")
    stub = _first(stub_events, type="result")
    assert set(stub) == set(live)


def test_assistant_events_match_the_recorded_shape(stub_events):
    live = _first(helpers.live_events(), type="assistant")
    for stub in (e for e in stub_events if e["type"] == "assistant"):
        assert set(stub) == set(live)
        assert set(stub["message"]) == set(live["message"])


def test_tool_use_blocks_match_the_recorded_shape(stub_events):
    live_block = next(
        b
        for e in helpers.live_events()
        if e["type"] == "assistant"
        for b in e["message"]["content"]
        if b.get("type") == "tool_use"
    )
    stub_blocks = [
        b
        for e in stub_events
        if e["type"] == "assistant"
        for b in e["message"]["content"]
        if b.get("type") == "tool_use"
    ]
    assert stub_blocks
    for block in stub_blocks:
        assert set(block) == set(live_block)


def test_tool_result_events_match_the_recorded_shape(stub_events):
    live = _first(helpers.live_events(), type="user")
    live_block = live["message"]["content"][0]
    for stub in (e for e in stub_events if e["type"] == "user"):
        assert set(stub) == set(live)
        assert set(stub["message"]) == set(live["message"])
        assert set(stub["message"]["content"][0]) == set(live_block)
