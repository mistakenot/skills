"""Fixture loading: the planning-eval schema, validated before any spend."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import fixture as fixture_mod
from fixture import HARNESS_PREAMBLE, FixtureError


def test_loads_planning_eval_shape(fixture_file: Path, arm_skills: Path) -> None:
    fx = fixture_mod.load(fixture_file)
    assert fx.id == "t-001"
    assert fx.arm_id == "vX"
    assert fx.skills_dir == arm_skills.resolve()
    assert fx.human_turns == ("first steering turn", "/new-solution", "looks good")
    assert fx.limits.per_turn_timeout_s == 120
    assert fx.limits.max_budget_usd == 2.5


def test_messages_carry_preamble_once_and_honour_max_turns(fixture_file: Path) -> None:
    fx = fixture_mod.load(fixture_file)
    msgs = fx.messages
    # max_turns=3 counts the opening prompt, exactly as planning-eval's cap does.
    assert len(msgs) == 3
    assert msgs[0] == HARNESS_PREAMBLE + "/new-task do the thing"
    assert not msgs[1].startswith("[EVAL HARNESS]")
    assert fx.shown_messages[0] == "/new-task do the thing"
    assert fx.shown_messages[1:] == ["first steering turn", "/new-solution"]


def test_planning_eval_bundled_fixture_parses_when_repo_present() -> None:
    """The sibling harness's own fixture must load unchanged — same file, either tool."""
    path = Path(__file__).resolve().parents[3] / "src" / "planning-eval" / "fixtures" / "008-commit-session-link.json"
    data = json.loads(path.read_text())
    if not Path(data["fixture"]["target_repo"]).joinpath(".git").exists():
        pytest.skip("target repo for the planning-eval fixture is not on this machine")
    fx = fixture_mod.load(path)
    assert fx.id == "008-commit-session-link"
    assert len(fx.messages) == 6


def _rewrite(path: Path, **changes) -> Path:
    data = json.loads(path.read_text())
    for dotted, value in changes.items():
        cur = data
        keys = dotted.split(".")
        for k in keys[:-1]:
            cur = cur[k]
        if value is None:
            cur.pop(keys[-1], None)
        else:
            cur[keys[-1]] = value
    path.write_text(json.dumps(data))
    return path


@pytest.mark.parametrize(
    "change, needle",
    [
        ({"fixture.start_sha": "HEAD"}, "literal 40-character"),
        ({"fixture.start_sha": "main"}, "literal 40-character"),
        ({"fixture.prompt": ""}, "prompt"),
        ({"fixture.target_repo": "/nonexistent/repo"}, "git checkout"),
        ({"arm.skills_dir": "/nonexistent/skills"}, "does not exist"),
        ({"human_turns": ["ok", 3]}, "human_turns"),
        ({"limits.max_turns": 0}, "max_turns"),
        ({"limits.max_budget_usd": -1}, "max_budget_usd"),
        ({"id": "has space"}, "filename-safe"),
        ({"fixture": None}, "missing required key"),
    ],
)
def test_rejects_bad_fixtures(fixture_file: Path, change: dict, needle: str) -> None:
    with pytest.raises(FixtureError, match=needle):
        fixture_mod.load(_rewrite(fixture_file, **change))


def test_rejects_skills_root_with_non_skill_child(fixture_file: Path, arm_skills: Path) -> None:
    """Harbor's loader wants a root of skills; a stray dir fails after the image build."""
    (arm_skills / "notes").mkdir()
    with pytest.raises(FixtureError, match="without SKILL.md"):
        fixture_mod.load(fixture_file)


def test_relative_skills_dir_resolves_against_repo_root(fixture_file: Path, tmp_path: Path) -> None:
    root = tmp_path / "root"
    (root / "skills" / "s").mkdir(parents=True)
    (root / "skills" / "s" / "SKILL.md").write_text("---\nname: s\n---\n")
    fx = fixture_mod.load(_rewrite(fixture_file, **{"arm.skills_dir": "skills"}), repo_root=root)
    assert fx.skills_dir == (root / "skills").resolve()
