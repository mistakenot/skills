"""Remote target repos (`fixture.repo_url`) and commit-pinned arms (`arm.skills_ref`)."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import fixture as fixture_mod
import sources


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
    )
    return out.stdout.strip()


@pytest.fixture
def cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    c = tmp_path / "cache"
    monkeypatch.setattr(sources, "CACHE", c)
    # ensure_commit/export_skills take the cache as a default argument, bound at
    # import time; point those defaults at the temp cache too.
    monkeypatch.setattr(sources.ensure_commit, "__defaults__", (c,))
    monkeypatch.setattr(sources.export_skills, "__defaults__", (c,))
    return c


@pytest.fixture
def skills_repo(tmp_path: Path) -> tuple[Path, str, str]:
    """A repo shaped like this one: compiled skills under `skills/`, two commits."""
    repo = tmp_path / "skills-repo"
    (repo / "skills" / "new-task-quick").mkdir(parents=True)
    (repo / "skills" / "new-task-quick" / "SKILL.md").write_text("---\nname: new-task-quick\n---\nv1\n")
    (repo / "src").mkdir()
    (repo / "src" / "compile.py").write_text("# not part of an arm\n")
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "v1")
    v1 = _git(repo, "rev-parse", "HEAD")
    (repo / "skills" / "new-task-quick" / "SKILL.md").write_text("---\nname: new-task-quick\n---\nv2\n")
    _git(repo, "commit", "-q", "-am", "v2")
    return repo, v1, _git(repo, "rev-parse", "HEAD")


def test_ensure_commit_fetches_one_commit_into_the_cache(cache: Path, target_repo) -> None:
    repo, sha = target_repo
    local = sources.ensure_commit(f"file://{repo}", sha)
    assert local.is_relative_to(cache)
    assert sources.has_commit(local, sha)
    # Second call is a cache hit: no fetch, same directory.
    assert sources.ensure_commit(f"file://{repo}", sha) == local


def test_ensure_commit_unknown_sha_fails(cache: Path, target_repo) -> None:
    repo, _ = target_repo
    with pytest.raises(sources.SourceError, match="cannot fetch"):
        sources.ensure_commit(f"file://{repo}", "0" * 40)


def test_export_skills_pins_the_tree_at_the_ref(cache: Path, skills_repo) -> None:
    repo, v1, v2 = skills_repo
    sha, d = sources.export_skills(repo, "HEAD~1")
    assert sha == v1
    assert (d / "new-task-quick" / "SKILL.md").read_text().endswith("v1\n")
    assert not (d.parent / "src").exists()  # only skills/ is exported
    sha2, d2 = sources.export_skills(repo, v2)
    assert (d2 / "new-task-quick" / "SKILL.md").read_text().endswith("v2\n")
    assert d != d2


def test_export_skills_bad_ref(cache: Path, skills_repo) -> None:
    repo, _, _ = skills_repo
    with pytest.raises(sources.SourceError, match="not a commit"):
        sources.export_skills(repo, "no-such-branch")


def _write(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "fx.json"
    p.write_text(json.dumps(data))
    return p


def test_fixture_with_repo_url_and_skills_ref(cache: Path, tmp_path: Path, target_repo, skills_repo) -> None:
    repo, sha = target_repo
    srepo, v1, _ = skills_repo
    fx = fixture_mod.load(_write(tmp_path, {
        "id": "oss-1",
        "fixture": {"repo_url": f"file://{repo}", "start_sha": sha, "prompt": "/new-task-quick x"},
        "arm": {"id": "old", "skills_ref": v1},
    }), repo_root=srepo)
    assert fx.repo_url == f"file://{repo}"
    assert fx.target_repo.is_relative_to(cache)
    assert fx.skills_sha == v1
    assert (fx.skills_dir / "new-task-quick" / "SKILL.md").is_file()


def test_fixture_rejects_both_repo_forms(cache: Path, tmp_path: Path, target_repo, arm_skills) -> None:
    repo, sha = target_repo
    with pytest.raises(fixture_mod.FixtureError, match="not both"):
        fixture_mod.load(_write(tmp_path, {
            "id": "x",
            "fixture": {"repo_url": f"file://{repo}", "target_repo": str(repo),
                        "start_sha": sha, "prompt": "p"},
            "arm": {"id": "a", "skills_dir": str(arm_skills)},
        }))


def test_fixture_rejects_both_arm_forms(tmp_path: Path, target_repo, arm_skills) -> None:
    repo, sha = target_repo
    with pytest.raises(fixture_mod.FixtureError, match="exactly one"):
        fixture_mod.load(_write(tmp_path, {
            "id": "x",
            "fixture": {"target_repo": str(repo), "start_sha": sha, "prompt": "p"},
            "arm": {"id": "a", "skills_dir": str(arm_skills), "skills_ref": "HEAD"},
        }))


def test_with_skills_ref_replaces_the_arm(cache: Path, fixture_file: Path, skills_repo) -> None:
    srepo, _, v2 = skills_repo
    fx = fixture_mod.load(fixture_file)
    swapped = fixture_mod.with_skills_ref(fx, "HEAD", repo_root=srepo)
    assert swapped.skills_sha == v2
    assert swapped.arm_id == f"skills-{v2[:12]}"
    assert swapped.prompt == fx.prompt and swapped.start_sha == fx.start_sha
    named = fixture_mod.with_skills_ref(fx, "HEAD", arm_id="head", repo_root=srepo)
    assert named.arm_id == "head"
