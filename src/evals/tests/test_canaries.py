"""Tests for the isolation canaries.

Each canary guards a silent failure: a leaked repo tree still produces a
plausible-looking run, so an untested canary is worse than none. Every check
therefore gets both a passing case and the failure it exists to catch.
"""

import pytest

from evals import canaries
from evals.canaries import CanaryFailure


def _make_git_repo(root):
    """A directory git would recognise as a working tree root."""
    (root / ".git").mkdir(parents=True)
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    return root


def test_bare_dot_git_directory_is_not_a_repo_ancestor(tmp_path):
    """An empty `.git` (this machine has one at /tmp) must not fail the canary."""
    (tmp_path / "notrepo" / ".git").mkdir(parents=True)
    ws = tmp_path / "notrepo" / "ws"
    ws.mkdir()
    canaries.check_workspace_has_no_repo_ancestor(ws, tmp_path / "elsewhere")


@pytest.fixture
def repo(tmp_path):
    """A fake repo root with a `.git` dir, and a clean-room base beside it."""
    root = tmp_path / "repo"
    _make_git_repo(root)
    clean = tmp_path / "clean"
    clean.mkdir()
    return root, clean


# --- canary 1: config dir outside the repo tree ----------------------------


def test_config_dir_outside_repo_passes(repo):
    root, clean = repo
    cfg = clean / "config"
    cfg.mkdir()
    canaries.check_config_dir_outside_repo(cfg, root)


def test_config_dir_inside_repo_fails(repo):
    root, _ = repo
    cfg = root / ".tmp" / "config"
    cfg.mkdir(parents=True)
    with pytest.raises(CanaryFailure, match="inside the repo tree"):
        canaries.check_config_dir_outside_repo(cfg, root)


def test_config_dir_equal_to_repo_root_fails(repo):
    root, _ = repo
    with pytest.raises(CanaryFailure):
        canaries.check_config_dir_outside_repo(root, root)


# --- canary 2: no repo ancestor above the workspace ------------------------


def test_workspace_without_repo_ancestor_passes(repo):
    root, clean = repo
    ws = clean / "ws"
    ws.mkdir()
    canaries.check_workspace_has_no_repo_ancestor(ws, root)


def test_workspace_under_repo_fails(repo):
    """The intuitive `.tmp/` workspace — the exact trap the canary exists for."""
    root, _ = repo
    ws = root / ".tmp" / "ws"
    ws.mkdir(parents=True)
    with pytest.raises(CanaryFailure, match="ancestor"):
        canaries.check_workspace_has_no_repo_ancestor(ws, root)


def test_workspace_under_some_other_git_repo_fails(tmp_path):
    """Not just *this* repo: any `.git` above cwd re-enters project context."""
    other = tmp_path / "other"
    _make_git_repo(other)
    ws = other / "ws"
    ws.mkdir()
    unrelated_repo_root = tmp_path / "repo"
    unrelated_repo_root.mkdir()
    with pytest.raises(CanaryFailure, match="git repo ancestor"):
        canaries.check_workspace_has_no_repo_ancestor(ws, unrelated_repo_root)


# --- canary 3: installed skill set is exactly what we placed ---------------


def _install(config_dir, name):
    skill = config_dir / "skills" / name
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: %s\n---\n" % name)
    return skill


def test_installed_skills_exact_passes(tmp_path):
    cfg = tmp_path / "config"
    _install(cfg, "rich-doc")
    canaries.check_installed_skills_exact(cfg, {"rich-doc"})


def test_extra_skill_fails(tmp_path):
    cfg = tmp_path / "config"
    _install(cfg, "rich-doc")
    _install(cfg, "stowaway")
    with pytest.raises(CanaryFailure, match="expected exactly"):
        canaries.check_installed_skills_exact(cfg, {"rich-doc"})


def test_missing_skill_fails(tmp_path):
    cfg = tmp_path / "config"
    (cfg / "skills").mkdir(parents=True)
    with pytest.raises(CanaryFailure):
        canaries.check_installed_skills_exact(cfg, {"rich-doc"})


def test_empty_expectation_passes_with_no_skills_dir(tmp_path):
    """The `none` arm: no skills dir at all is an exact match for an empty set."""
    cfg = tmp_path / "config"
    cfg.mkdir()
    canaries.check_installed_skills_exact(cfg, set())


def test_skill_dir_without_manifest_fails(tmp_path):
    cfg = tmp_path / "config"
    (cfg / "skills" / "rich-doc").mkdir(parents=True)
    with pytest.raises(CanaryFailure, match="no SKILL.md"):
        canaries.check_installed_skills_exact(cfg, {"rich-doc"})


# --- canary 4: no project context above the workspace ---------------------


def test_ancestor_claude_md_fails(tmp_path):
    """The leak canary 2 cannot see: `/tmp/CLAUDE.md` reached a real clean room."""
    base = tmp_path / "base"
    ws = base / "cell" / "ws"
    ws.mkdir(parents=True)
    (base / "CLAUDE.md").write_text("# Project instructions\n")
    with pytest.raises(CanaryFailure, match="project context"):
        canaries.check_no_ancestor_project_context(ws)


def test_ancestor_dot_claude_dir_fails(tmp_path):
    base = tmp_path / "base"
    ws = base / "cell" / "ws"
    ws.mkdir(parents=True)
    (base / ".claude").mkdir()
    with pytest.raises(CanaryFailure, match="project context"):
        canaries.check_no_ancestor_project_context(ws)


def test_ancestor_context_beside_a_bare_dot_git_fails(tmp_path):
    """The exact live configuration: an empty `.git` canary 2 tolerates, plus a
    `CLAUDE.md` the CLI loads anyway because its walk-up is name-based."""
    base = tmp_path / "base"
    (base / ".git").mkdir(parents=True)
    (base / "CLAUDE.md").write_text("# Project instructions\n")
    ws = base / "cell" / "ws"
    ws.mkdir(parents=True)
    canaries.check_workspace_has_no_repo_ancestor(ws, tmp_path / "elsewhere")
    with pytest.raises(CanaryFailure, match="project context"):
        canaries.check_no_ancestor_project_context(ws)


def test_workspace_own_claude_md_passes(tmp_path):
    """Strict ancestors: a fixture's own project context is meant to load."""
    ws = tmp_path / "base" / "ws"
    ws.mkdir(parents=True)
    (ws / "CLAUDE.md").write_text("# fixture instructions\n")
    (ws / ".claude").mkdir()
    canaries.check_no_ancestor_project_context(ws)


def test_clean_ancestors_pass(tmp_path):
    ws = tmp_path / "base" / "ws"
    ws.mkdir(parents=True)
    canaries.check_no_ancestor_project_context(ws)


# --- the composite ---------------------------------------------------------


def test_check_all_reports_the_first_failure(repo):
    root, clean = repo
    cfg = clean / "config"
    _install(cfg, "rich-doc")
    ws = root / ".tmp" / "ws"
    ws.mkdir(parents=True)
    with pytest.raises(CanaryFailure, match="ancestor"):
        canaries.check_all(cfg, ws, root, {"rich-doc"})


def test_check_all_catches_ancestor_project_context(repo):
    """`check_all` must run canary 4, not just define it."""
    root, clean = repo
    cfg = clean / "config"
    _install(cfg, "rich-doc")
    ws = clean / "cell" / "ws"
    ws.mkdir(parents=True)
    (clean / "CLAUDE.md").write_text("# Project instructions\n")
    with pytest.raises(CanaryFailure, match="project context"):
        canaries.check_all(cfg, ws, root, {"rich-doc"})


def test_check_all_passes_on_a_well_formed_cell(repo):
    root, clean = repo
    cfg = clean / "config"
    _install(cfg, "rich-doc")
    ws = clean / "ws"
    ws.mkdir()
    canaries.check_all(cfg, ws, root, {"rich-doc"})
