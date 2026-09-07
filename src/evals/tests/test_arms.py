"""The three arm forms, resolved against a real git repository.

The repository is built here rather than mocked, and its `src/compile.py` is a
real script that really runs: `WORKTREE` is defined as "compile, then copy from
disk", and a test that stubs the compiler out is not testing that. The fixture
repo is deliberately tiny — one skill, one source file — so the interesting
difference between the arms is the only difference there is.

The load-bearing case is `test_ref_and_worktree_differ_on_an_uncommitted_edit`:
`git archive` cannot see an uncommitted edit, which is exactly why `WORKTREE`
exists and why it must never be reimplemented as a git operation.
"""

import json
import subprocess

import pytest

from evals import __main__ as cli
from evals import arms, cell, manifest, paths, report, runners

COMMITTED = "---\nname: demo\n---\ncommitted body\n"
EDITED = "---\nname: demo\n---\nedited body, never committed\n"

# A stand-in for `src/compile.py`: renders `src/demo.md` into `skills/demo/`,
# the same "compiled output, regenerated from source" relationship the real repo
# has. `references/` is there so the arms are compared as trees, not as a file.
COMPILER_SRC = """\
import pathlib, shutil, sys
root = pathlib.Path(__file__).resolve().parent.parent
out = root / "skills" / "demo"
out.mkdir(parents=True, exist_ok=True)
(out / "SKILL.md").write_text((root / "src" / "demo.md").read_text())
(out / "references").mkdir(exist_ok=True)
(out / "references" / "extra.md").write_text("detail\\n")
"""


def _git(repo, *args):
    result = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=repo, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _tree(root):
    """Every file under `root`, as {relative path: bytes}."""
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A git repo with a committed, compiled `skills/demo`, wired into `arms`."""
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "compile.py").write_text(COMPILER_SRC)
    (root / "src" / "demo.md").write_text(COMMITTED)

    _git(root, "init", "-q", "-b", "main")
    subprocess.run([__import__("sys").executable, "src/compile.py"], cwd=root, check=True)
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "committed skill")

    monkeypatch.setattr(arms, "REPO_ROOT", root)
    monkeypatch.setattr(arms, "COMPILER", root / "src" / "compile.py")
    monkeypatch.setattr(arms, "COMPILED_SKILLS_DIR", root / "skills")
    return root


@pytest.fixture
def head(repo):
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def dirty(repo):
    """The uncommitted edit that only the `WORKTREE` arm can see."""
    (repo / "src" / "demo.md").write_text(EDITED)
    return repo


# --- the three forms -------------------------------------------------------


def test_none_resolves_to_no_skill_at_all(repo):
    arm = arms.resolve(arms.NONE, "demo")
    assert arm.kind == arms.KIND_NONE
    assert arm.skill_src is None
    assert arm.sha is None


def test_worktree_is_the_compiled_working_tree(dirty, repo):
    """Compiled first: the arm is the edit on disk, not the last build."""
    arm = arms.resolve(arms.WORKTREE, "demo")
    assert arm.kind == arms.KIND_WORKTREE
    assert (arm.skill_src / "SKILL.md").read_text() == EDITED
    assert _tree(arm.skill_src) == _tree(repo / "skills" / "demo")


def test_a_git_ref_is_archived_at_its_resolved_sha(repo, head):
    arm = arms.resolve("main", "demo")
    assert arm.kind == arms.KIND_REF
    assert arm.sha == head
    assert (arm.skill_src / "SKILL.md").read_text() == COMMITTED
    assert (arm.skill_src / "references" / "extra.md").is_file()


def test_a_ref_arm_matches_git_archive_at_that_ref(repo, head, tmp_path):
    """The archive is the contract; assert it against git's own output."""
    arm = arms.resolve(head, "demo")
    control = tmp_path / "control"
    control.mkdir()
    tar = subprocess.run(
        ["git", "archive", "--format=tar", head, "--", "skills/demo"],
        cwd=repo, capture_output=True, check=True,
    ).stdout
    subprocess.run(["tar", "-x"], cwd=control, input=tar, check=True)
    assert _tree(arm.skill_src) == _tree(control / "skills" / "demo")


def test_ref_and_worktree_differ_on_an_uncommitted_edit(dirty, head):
    """The whole reason `WORKTREE` is not a git operation.

    `git archive` sees only committed content. If these two ever agree while the
    tree is dirty, the working-tree arm has quietly become a second ref arm and
    the author loop — evaluate the edit *before* committing it — is gone.
    """
    ref = arms.resolve(head, "demo")
    worktree = arms.resolve(arms.WORKTREE, "demo")
    assert (ref.skill_src / "SKILL.md").read_text() == COMMITTED
    assert (worktree.skill_src / "SKILL.md").read_text() == EDITED
    assert _tree(ref.skill_src) != _tree(worktree.skill_src)


def test_arms_do_not_share_a_source_directory(dirty, head):
    """One arm's materialised source must not be another's."""
    sources = [
        arms.resolve(name, "demo").skill_src
        for name in (arms.WORKTREE, head, "main")
    ]
    assert len({str(p) for p in sources}) == 3


# --- provenance ------------------------------------------------------------


def test_worktree_records_head_and_dirty_state(dirty, head):
    arm = arms.resolve(arms.WORKTREE, "demo")
    manifest = arm.manifest("demo")
    assert manifest["sha"] == arms.WORKTREE
    assert manifest["head"] == head
    assert manifest["dirty"] is True


def test_a_clean_worktree_says_so(repo, head):
    assert arms.resolve(arms.WORKTREE, "demo").manifest("demo")["dirty"] is False


def test_ref_manifest_records_the_resolved_sha(repo, head):
    manifest = arms.resolve("main", "demo").manifest("demo")
    assert manifest["sha"] == head
    assert manifest["kind"] == arms.KIND_REF
    assert manifest["skill"] == "demo"


def test_write_manifest_lands_beside_the_arms_cells(repo, head, tmp_path):
    arm = arms.resolve("main", "demo")
    path = arms.write_manifest(tmp_path / "run" / "main", arm, "demo", "run-id")
    payload = json.loads(path.read_text())
    assert path.name == arms.MANIFEST_NAME
    assert payload["run_id"] == "run-id"
    assert payload["sha"] == head


# --- rejections ------------------------------------------------------------


def test_an_unresolvable_ref_is_rejected_by_name(repo):
    with pytest.raises(arms.ArmResolutionError, match="no-such-ref"):
        arms.resolve("no-such-ref", "demo")


def test_a_ref_without_the_skill_is_rejected(repo, head):
    with pytest.raises(arms.ArmResolutionError, match="ghost"):
        arms.resolve(head, "ghost")


def test_a_missing_skill_in_the_worktree_is_rejected(repo):
    with pytest.raises(arms.ArmResolutionError, match="ghost"):
        arms.resolve(arms.WORKTREE, "ghost")


def test_a_failing_compiler_stops_the_run(repo):
    """A stale `skills/` tree would silently evaluate the wrong bytes."""
    (repo / "src" / "compile.py").write_text("raise SystemExit(3)\n")
    with pytest.raises(arms.ArmResolutionError, match="compile.py failed"):
        arms.resolve(arms.WORKTREE, "demo")


# --- directory safety ------------------------------------------------------


def test_a_ref_name_becomes_one_safe_path_segment():
    """`origin/main` must not nest, and `..` must not climb out of the run."""
    assert arms.dir_name("origin/main") == "origin-main"
    assert "/" not in arms.dir_name("feature/skills/v2")
    with pytest.raises(arms.ArmResolutionError):
        arms.dir_name("..")


def test_arms_that_would_share_a_directory_are_rejected(repo):
    with pytest.raises(arms.ArmResolutionError, match="share a directory"):
        arms.resolve_all(["origin/main", "origin-main"], "demo")


def test_resolve_all_keeps_the_order_it_was_given(repo, head):
    resolved = arms.resolve_all([arms.NONE, arms.WORKTREE, head], "demo")
    assert [a.kind for a in resolved] == [arms.KIND_NONE, arms.KIND_WORKTREE, arms.KIND_REF]


# --- through the CLI, in one command ---------------------------------------


@pytest.fixture
def runs_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "RUNS_DIR", tmp_path / "runs")
    return tmp_path / "runs"


def test_three_arms_from_one_command_install_three_different_things(
    dirty, head, runs_dir, repo
):
    """The acceptance check: `none`, `WORKTREE` and a ref, one invocation."""
    code = cli.main(
        ["run", "--skill", "demo",
         "--arm", arms.NONE, "--arm", arms.WORKTREE, "--arm", head,
         "--prompt", "write me an answer", "--runner", runners.STUB]
    )
    assert code == 0

    run_dir = next(runs_dir.iterdir())
    assert {p.name for p in run_dir.iterdir()} == {
        report.REPORT_NAME, manifest.RUN_MANIFEST_NAME,
        arms.NONE, arms.WORKTREE, head,
    }

    # `none` installed nothing: no `skill/` snapshot to take.
    none_cell = run_dir / arms.NONE / "1"
    assert not (none_cell / "skill").exists()
    assert (none_cell / "out.md").is_file()

    # `WORKTREE` is the uncommitted edit; the ref arm is the commit.
    worktree_skill = run_dir / arms.WORKTREE / "1" / "skill"
    ref_skill = run_dir / head / "1" / "skill"
    assert (worktree_skill / "SKILL.md").read_text() == EDITED
    assert (ref_skill / "SKILL.md").read_text() == COMMITTED
    assert _tree(worktree_skill) == _tree(repo / "skills" / "demo")
    assert _tree(worktree_skill) != _tree(ref_skill)


def test_each_arm_records_its_resolved_sha(dirty, head, runs_dir):
    cli.main(
        ["run", "--skill", "demo",
         "--arm", arms.NONE, "--arm", arms.WORKTREE, "--arm", head,
         "--prompt", "p", "--runner", runners.STUB]
    )
    run_dir = next(runs_dir.iterdir())

    def manifest(arm):
        return json.loads((run_dir / arm / arms.MANIFEST_NAME).read_text())

    assert manifest(arms.NONE)["sha"] is None
    assert manifest(arms.WORKTREE)["sha"] == arms.WORKTREE
    assert manifest(arms.WORKTREE)["head"] == head
    assert manifest(arms.WORKTREE)["dirty"] is True
    assert manifest(head)["sha"] == head


def test_arms_never_share_a_workspace(dirty, head, runs_dir, monkeypatch):
    """Disjoint on disk, in both the run tree and the clean rooms."""
    seen = []
    real = cell.run_cell

    def record(*args, **kwargs):
        result = real(*args, **kwargs)
        seen.append(result)
        return result

    monkeypatch.setattr(cell, "run_cell", record)
    cli.main(
        ["run", "--skill", "demo",
         "--arm", arms.NONE, "--arm", arms.WORKTREE, "--arm", head,
         "--prompt", "p", "--runner", runners.STUB]
    )

    out_dirs = [r.out_dir for r in seen]
    assert len({str(p) for p in out_dirs}) == 3
    assert len({str(r.workspace) for r in seen}) == 3
    assert len({str(r.config_dir) for r in seen}) == 3
    for a in out_dirs:
        for b in out_dirs:
            if a != b:
                assert not a.is_relative_to(b)


def test_one_arm_is_a_legal_run(repo, runs_dir):
    """Single-arm exploration, not a degenerate A/B."""
    code = cli.main(
        ["run", "--skill", "demo", "--arm", arms.WORKTREE,
         "--prompt", "p", "--runner", runners.STUB]
    )
    assert code == 0
    run_dir = next(runs_dir.iterdir())
    assert {p.name for p in run_dir.iterdir()} == {
        report.REPORT_NAME, manifest.RUN_MANIFEST_NAME, arms.WORKTREE
    }


def test_a_bad_arm_is_rejected_before_any_arm_runs(repo, runs_dir, monkeypatch):
    """Resolution is up front: a typo in arm three must not cost arm one."""
    def explode(*a, **kw):
        raise AssertionError("a cell ran despite an unresolvable arm")

    monkeypatch.setattr(cell, "run_cell", explode)
    code = cli.main(
        ["run", "--skill", "demo",
         "--arm", arms.WORKTREE, "--arm", "no-such-ref",
         "--prompt", "p", "--runner", runners.STUB]
    )
    assert code == 2
    assert not runs_dir.exists()
