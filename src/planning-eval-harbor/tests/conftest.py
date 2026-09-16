"""Make the module importable, and provide a throwaway target repo + arm.

The suite imports `fixture`, `task`, `job` and `results` directly — never
`harbor`, which only the module's own environment has — so it runs in the root
environment alongside the other suites (`make test`).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

MODULE_DIR = Path(__file__).resolve().parent.parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
    )
    return out.stdout.strip()


@pytest.fixture
def target_repo(tmp_path: Path) -> tuple[Path, str]:
    """A tiny git repo with one commit, including its own `.claude/skills/`."""
    repo = tmp_path / "target"
    (repo / "src").mkdir(parents=True)
    (repo / "src" / "main.go").write_text("package main\n")
    (repo / "CLAUDE.md").write_text("# project instructions\n")
    (repo / ".claude" / "skills" / "repo-own-skill").mkdir(parents=True)
    (repo / ".claude" / "skills" / "repo-own-skill" / "SKILL.md").write_text("---\nname: repo-own-skill\n---\n")
    (repo / ".claude" / "settings.json").write_text("{}\n")
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "feat: the start commit's subject")
    return repo, _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def arm_skills(tmp_path: Path) -> Path:
    skills = tmp_path / "arm-skills"
    (skills / "new-task").mkdir(parents=True)
    (skills / "new-task" / "SKILL.md").write_text("---\nname: new-task\ndescription: x\n---\n")
    (skills / "new-task" / "README.md").write_text("not a skill dir, a file — ignored\n")
    return skills


@pytest.fixture
def fixture_file(tmp_path: Path, target_repo: tuple[Path, str], arm_skills: Path) -> Path:
    repo, sha = target_repo
    data = {
        "id": "t-001",
        "fixture": {"target_repo": str(repo), "start_sha": sha, "prompt": "/new-task do the thing"},
        "arm": {"id": "vX", "skills_dir": str(arm_skills)},
        "human_turns": ["first steering turn", "/new-solution", "looks good"],
        "limits": {"max_turns": 3, "wall_clock_s": 600, "per_turn_timeout_s": 120, "max_budget_usd": 2.5},
    }
    path = tmp_path / "fixture.json"
    path.write_text(json.dumps(data))
    return path
