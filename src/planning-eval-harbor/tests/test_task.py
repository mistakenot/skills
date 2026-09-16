"""Fixture → Harbor task directory."""

from __future__ import annotations

import tarfile
import tomllib
from pathlib import Path

import pytest

import fixture as fixture_mod
import task as task_mod


def test_scripted_task_layout(fixture_file: Path, tmp_path: Path) -> None:
    fx = fixture_mod.load(fixture_file)
    built = task_mod.build_task(fx, tmp_path / "tasks", task_mod.SCRIPTED)

    assert built.dir == tmp_path / "tasks" / "t-001-vX-scripted"
    assert built.steps == ["turn-01", "turn-02", "turn-03"]
    for name, msg in zip(built.steps, fx.messages, strict=True):
        assert (built.dir / "steps" / name / "instruction.md").read_text() == msg.rstrip() + "\n"
    # No single-step instruction: a multi-step task takes its instructions from steps/.
    assert not (built.dir / "instruction.md").exists()

    cfg = tomllib.loads((built.dir / "task.toml").read_text())
    assert [s["name"] for s in cfg["steps"]] == built.steps
    assert cfg["agent"]["timeout_sec"] == 120.0  # per_turn_timeout_s, per step
    assert cfg["metadata"]["start_sha"] == fx.start_sha

    test_sh = built.dir / "tests" / "test.sh"
    assert test_sh.stat().st_mode & 0o111, "harbor requires an executable test script"
    assert "exit 1" in test_sh.read_text(), "the no-verifier stub must fail loudly if ever run"


def test_simulated_task_layout(fixture_file: Path, tmp_path: Path) -> None:
    fx = fixture_mod.load(fixture_file)
    built = task_mod.build_task(fx, tmp_path / "tasks", task_mod.SIMULATED)

    assert built.steps == []
    assert not (built.dir / "steps").exists()
    script = (built.dir / "instruction.md").read_text()
    for i, msg in enumerate(fx.messages, 1):
        assert f"=== MESSAGE {i} of 3 ===" in script
        assert msg.rstrip() in script
    assert "verbatim" in script
    persona = (built.dir / "persona.md").read_text()
    assert "replay operator" in persona
    cfg = tomllib.loads((built.dir / "task.toml").read_text())
    assert "steps" not in cfg


def test_fixture_persona_overrides_default(fixture_file: Path, tmp_path: Path) -> None:
    import json
    data = json.loads(fixture_file.read_text())
    data["persona"] = "You are a terse, impatient tech lead."
    fixture_file.write_text(json.dumps(data))
    fx = fixture_mod.load(fixture_file)
    built = task_mod.build_task(fx, tmp_path / "tasks", task_mod.SIMULATED)
    assert (built.dir / "persona.md").read_text() == "You are a terse, impatient tech lead.\n"


def test_seed_tree_drops_repo_skills_but_keeps_project_context(
    fixture_file: Path, tmp_path: Path
) -> None:
    fx = fixture_mod.load(fixture_file)
    built = task_mod.build_task(fx, tmp_path / "tasks", task_mod.SCRIPTED)
    with tarfile.open(built.seed_tar) as tf:
        names = {m.name for m in tf if m.isfile()}
    assert "src/main.go" in names
    assert "CLAUDE.md" in names, "project instructions are shared context, not the variable"
    assert ".claude/settings.json" in names
    assert not any(n.startswith(".claude/skills/") for n in names), (
        "the repo's own skills must not compete with the arm's injected skills"
    )
    assert not any(n.startswith(".git/") for n in names)


def test_dockerfile_commits_seed_with_original_subject(fixture_file: Path, tmp_path: Path) -> None:
    fx = fixture_mod.load(fixture_file)
    built = task_mod.build_task(fx, tmp_path / "tasks", task_mod.SCRIPTED)
    df = (built.dir / "environment" / "Dockerfile").read_text()
    assert "ADD repo.tar /app/" in df
    assert "git init" in df and "commit" in df
    assert "the start commit" in df
    assert "rm -rf" not in df


def test_rebuild_replaces_stale_task_dir(fixture_file: Path, tmp_path: Path) -> None:
    fx = fixture_mod.load(fixture_file)
    built = task_mod.build_task(fx, tmp_path / "tasks", task_mod.SCRIPTED)
    stale = built.dir / "steps" / "turn-09" / "instruction.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("left over from an earlier, longer script\n")
    task_mod.build_task(fx, tmp_path / "tasks", task_mod.SCRIPTED)
    assert not stale.exists()


def test_unknown_operator_rejected(fixture_file: Path, tmp_path: Path) -> None:
    fx = fixture_mod.load(fixture_file)
    with pytest.raises(ValueError, match="operator"):
        task_mod.build_task(fx, tmp_path / "tasks", "interactive")
