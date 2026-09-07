"""Isolation canaries, asserted on every cell.

All four are filesystem checks: no agent is invoked, so they cost nothing and
run before we spend a token. Isolation failing is silent — a leaked repo tree
gives a plausible-looking result that is measuring the wrong thing — so these
raise rather than warn.

Deliberately absent: any assertion about the agent's *visible* skill list. The
built-in skill floor drifts across CLI versions (14 on 2.1.175, 13 on 2.1.260,
with membership changes), so a hard-coded floor is a time bomb. We assert on the
config dir's contents instead, which we control.
"""

from __future__ import annotations

from pathlib import Path


class CanaryFailure(AssertionError):
    """An isolation guarantee did not hold. Never proceed to the agent call."""


def _is_git_repo(path: Path) -> bool:
    """True if `path` is a git working tree root.

    Tested properly rather than by the presence of a `.git` name: this machine
    has an empty `/tmp/.git` directory that git itself does not recognise, and
    treating it as a repo would fail the canary on every clean-room run.
    """
    dot_git = path / ".git"
    if dot_git.is_file():  # a worktree/submodule gitlink
        return True
    return (dot_git / "HEAD").is_file()


def _is_within(child: Path, ancestor: Path) -> bool:
    child = child.resolve()
    ancestor = ancestor.resolve()
    return child == ancestor or ancestor in child.parents


def check_config_dir_outside_repo(config_dir: Path, repo_root: Path) -> None:
    """Canary 1: `CLAUDE_CONFIG_DIR` resolves outside the repo tree.

    A config dir inside the repo would be swept up by the repo's own tooling and
    could inherit repo state.
    """
    if _is_within(config_dir, repo_root):
        raise CanaryFailure(
            f"config dir {config_dir.resolve()} is inside the repo tree "
            f"{repo_root.resolve()}; it must live outside it"
        )


def check_workspace_has_no_repo_ancestor(workspace: Path, repo_root: Path) -> None:
    """Canary 2: no repo above the workspace.

    Claude Code walks *up* from cwd and re-discovers a parent repo's project
    skills and CLAUDE.md regardless of `CLAUDE_CONFIG_DIR`. A workspace under
    this repo (the intuitive `.tmp/` choice) leaks all ~38 repo skills and this
    repo's CLAUDE.md straight back into a supposedly clean room.

    Two assertions: this repo's root is never reached walking up, and no `.git`
    is found on the way to the filesystem root (the general form of the trap).
    """
    ws = workspace.resolve()
    root = repo_root.resolve()

    for candidate in (ws, *ws.parents):
        if candidate == root:
            raise CanaryFailure(
                f"workspace {ws} has this repo ({root}) as an ancestor; "
                f"claude walks up from cwd and would re-discover its skills and CLAUDE.md"
            )
        if _is_git_repo(candidate):
            raise CanaryFailure(
                f"workspace {ws} has a git repo ancestor at {candidate}; "
                f"claude walks up from cwd and would re-discover its project context"
            )


# Claude Code loads these from every directory between cwd and the project root.
PROJECT_CONTEXT_NAMES = ("CLAUDE.md", ".claude")


def check_no_ancestor_project_context(workspace: Path) -> None:
    """Canary 4: no `CLAUDE.md` or `.claude/` in any directory above the workspace.

    Canary 2 is not sufficient, because the CLI's project-root walk-up is
    *name-based* while ours is content-based. Measured on 2.1.260: a workspace
    seven levels below `/tmp` resolved its project root to `/tmp` — on the
    strength of an empty `/tmp/.git` that git itself rejects — and a
    `CLAUDE.md` planted anywhere on that path was loaded into the clean room and
    presented to the agent as project instructions. Canary 2 deliberately
    tolerates that empty `.git`, so it stays green through exactly that leak.

    `/tmp` is world-writable, so this is not hypothetical: any process can drop a
    `CLAUDE.md` there. This turns a silent contamination into a hard failure.

    Strict ancestors only. A fixture that ships its own `CLAUDE.md`/`.claude/`
    *in the workspace* is legitimate and loads on purpose.
    """
    ws = workspace.resolve()
    for ancestor in ws.parents:
        for name in PROJECT_CONTEXT_NAMES:
            if (ancestor / name).exists():
                raise CanaryFailure(
                    f"workspace {ws} has project context at {ancestor / name}; "
                    f"claude walks up from cwd and loads it regardless of git status"
                )


def check_installed_skills_exact(config_dir: Path, expected: set[str]) -> None:
    """Canary 3: the config dir's skill set is exactly what we installed.

    Asserted against the directory we populated, not against what the agent says
    it can see — the latter includes a built-in floor we do not control.
    """
    skills_dir = config_dir / "skills"
    found = (
        {p.name for p in skills_dir.iterdir() if p.is_dir()}
        if skills_dir.is_dir()
        else set()
    )
    if found != expected:
        raise CanaryFailure(
            f"config dir {config_dir.resolve()} has skills {sorted(found)}, "
            f"expected exactly {sorted(expected)}"
        )
    for name in expected:
        manifest = skills_dir / name / "SKILL.md"
        if not manifest.is_file():
            raise CanaryFailure(f"installed skill {name!r} has no SKILL.md at {manifest}")


def check_all(config_dir: Path, workspace: Path, repo_root: Path, expected_skills: set[str]) -> None:
    """Run every canary. Raises `CanaryFailure` on the first one that fails."""
    check_config_dir_outside_repo(config_dir, repo_root)
    check_workspace_has_no_repo_ancestor(workspace, repo_root)
    check_no_ancestor_project_context(workspace)
    check_installed_skills_exact(config_dir, expected_skills)
