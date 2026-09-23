"""The Harbor job config: what a run asks Harbor to do."""

from __future__ import annotations

import json
from pathlib import Path

import fixture as fixture_mod
import job as job_mod
import task as task_mod


def _build(fixture_file: Path, tmp_path: Path, operator: str):
    fx = fixture_mod.load(fixture_file)
    built = task_mod.build_task(fx, tmp_path / "tasks", operator)
    return fx, built


def test_scripted_config(fixture_file: Path, tmp_path: Path) -> None:
    fx, built = _build(fixture_file, tmp_path, task_mod.SCRIPTED)
    cfg = job_mod.build_config(built, fx, tmp_path / "runs", "job-1", trials=2, model="anthropic/m", concurrent=1)

    assert cfg["job_name"] == "job-1"
    assert cfg["jobs_dir"] == str(tmp_path / "runs")
    assert cfg["n_attempts"] == 2
    assert cfg["tasks"] == [{"path": str(built.dir)}]
    # No grader, ever: verification off, and the workspace comes back as-is.
    assert cfg["verifier"] == {"disable": True}
    assert cfg["artifacts"] == [{"source": "/app", "destination": "app", "exclude": [".git"]}]
    (agent,) = cfg["agents"]
    assert agent["import_path"] == job_mod.AGENT_IMPORT
    assert agent["model_name"] == "anthropic/m"
    assert agent["skills"] == [str(fx.skills_dir)]
    assert agent["resume_trajectory"] is True, "one native session across every turn"
    assert agent["kwargs"] == {"max_budget_usd": "2.5"}
    assert "user_agent" not in cfg


def test_simulated_config_adds_user_agent(fixture_file: Path, tmp_path: Path) -> None:
    fx, built = _build(fixture_file, tmp_path, task_mod.SIMULATED)
    cfg = job_mod.build_config(built, fx, tmp_path / "runs", "job-2")
    (agent,) = cfg["agents"]
    assert "resume_trajectory" not in agent, "a single-step task has nothing to resume"
    ua = cfg["user_agent"]
    assert ua["import_path"] == job_mod.AGENT_IMPORT
    assert ua["bridge"] == {"kind": "acp"}
    assert ua["user_persona_path"] == str(built.dir / "persona.md")
    assert Path(ua["user_persona_path"]).is_file()


def test_no_budget_means_no_kwarg(fixture_file: Path, tmp_path: Path) -> None:
    data = json.loads(fixture_file.read_text())
    del data["limits"]["max_budget_usd"]
    fixture_file.write_text(json.dumps(data))
    fx, built = _build(fixture_file, tmp_path, task_mod.SCRIPTED)
    cfg = job_mod.build_config(built, fx, tmp_path / "runs", "j")
    assert cfg["agents"][0]["kwargs"] == {}


def test_config_round_trips_through_file(fixture_file: Path, tmp_path: Path) -> None:
    fx, built = _build(fixture_file, tmp_path, task_mod.SCRIPTED)
    cfg = job_mod.build_config(built, fx, tmp_path / "runs", "j")
    path = job_mod.write_config(cfg, built.dir / "job-config.json")
    assert json.loads(path.read_text()) == cfg


def test_harbor_env_exports_agent_module_not_auth(monkeypatch) -> None:
    monkeypatch.setenv("PYTHONPATH", "/elsewhere")
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    env = job_mod.harbor_env()
    assert env["HARBOR_TELEMETRY"] == "off"
    assert env["PYTHONPATH"].split(":")[0] == str(job_mod.HERE)
    assert "/elsewhere" in env["PYTHONPATH"]
    # The agent seeds a credentials file; the harness never mints a token env.
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in env


def test_argv_is_the_reproducible_command(tmp_path: Path) -> None:
    cfg = tmp_path / "c.json"
    assert job_mod.argv("/x/harbor", cfg) == ["/x/harbor", "run", "--config", str(cfg), "--yes"]
    assert job_mod.argv("/x/harbor", cfg, dry_run=True)[-1] == "--dry-run"
