"""Companion skills (`--with`): scaffolding held constant across arms.

A skill that loads another by name — `new-epic` loads `rich-doc` — cannot run
in a clean room without it, and an arm that improvises around the missing
dependency measures the wrong thing. A companion is installed beside the skill
under test on every arm that installs it, from one source, so the arms still
differ in exactly one thing. The `none` arm stays empty: a baseline carrying
the companion is a different experiment, and canary 3 would be the only thing
to notice if that ever changed silently.
"""

import json
import subprocess

import pytest

from evals import __main__ as cli
from evals import arms, cell, manifest, paths, runners
from evals.canaries import CanaryFailure

from .test_arms import COMPILER_SRC, COMMITTED, _git  # noqa: F401  (fixture plumbing)

COMPANION_SRC = COMPILER_SRC + """\
helper = root / "skills" / "helper"
helper.mkdir(parents=True, exist_ok=True)
(helper / "SKILL.md").write_text((root / "src" / "helper.md").read_text())
"""
HELPER = "---\nname: helper\n---\nhelper body\n"


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A repo whose compiler renders two skills: `demo` under test, `helper` beside it."""
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src" / "compile.py").write_text(COMPANION_SRC)
    (root / "src" / "demo.md").write_text(COMMITTED)
    (root / "src" / "helper.md").write_text(HELPER)
    _git(root, "init", "-q", "-b", "main")
    subprocess.run([__import__("sys").executable, "src/compile.py"], cwd=root, check=True)
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "two skills")
    monkeypatch.setattr(arms, "REPO_ROOT", root)
    monkeypatch.setattr(arms, "COMPILER", root / "src" / "compile.py")
    monkeypatch.setattr(arms, "COMPILED_SKILLS_DIR", root / "skills")
    return root


# --- resolution --------------------------------------------------------------


def test_companions_resolve_off_the_compiled_working_tree(repo):
    (repo / "src" / "helper.md").write_text("---\nname: helper\n---\nedited helper\n")
    [companion] = arms.resolve_companions(["helper"], "demo")
    assert companion.name == "helper"
    assert (companion.skill_src / "SKILL.md").read_text().endswith("edited helper\n")
    assert companion.dirty is True


def test_no_companions_is_the_empty_list(repo):
    assert arms.resolve_companions([], "demo") == []


def test_the_skill_under_test_cannot_be_its_own_companion(repo):
    with pytest.raises(arms.ArmResolutionError, match="names the skill under test"):
        arms.resolve_companions(["demo"], "demo")


def test_a_companion_named_twice_is_refused(repo):
    with pytest.raises(arms.ArmResolutionError, match="given twice"):
        arms.resolve_companions(["helper", "helper"], "demo")


def test_a_missing_companion_fails_before_any_arm_runs(repo):
    with pytest.raises(arms.ArmResolutionError, match="no skill 'ghost'"):
        arms.resolve_companions(["ghost"], "demo")


# --- the cell ----------------------------------------------------------------


@pytest.fixture
def fake_agent(monkeypatch, tmp_path):
    seen = {}

    def fake_run(argv, cwd, env, stdin, stdout, stderr):
        seen["config_dir"] = env["CLAUDE_CONFIG_DIR"]
        stdout.write(
            (
                json.dumps({"type": "system", "subtype": "init"}) + "\n"
                + json.dumps({"type": "result", "subtype": "success", "result": "done"}) + "\n"
            ).encode()
        )
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(runners.subprocess, "run", fake_run)
    creds = tmp_path / "credentials.json"
    creds.write_text("{}")
    monkeypatch.setattr(cell, "CREDENTIALS", creds)
    return seen


def _skill(tmp_path, name, body):
    src = tmp_path / "src-skills" / name
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text(body)
    return src


def test_companions_are_installed_beside_the_skill_and_snapshotted(tmp_path, fake_agent):
    demo = _skill(tmp_path, "demo", COMMITTED)
    helper = _skill(tmp_path, "helper", HELPER)
    out = tmp_path / "cell"
    cell.run_cell(out, "demo", demo, "p", model="m", companions={"helper": helper})

    assert (out / "skill" / "SKILL.md").read_text() == COMMITTED
    assert (out / "with" / "helper" / "SKILL.md").read_text() == HELPER
    assert {p.name for p in out.iterdir()} == {
        "skill", "with", "ws", "stream.jsonl", "out.md", "err.txt"
    }


def test_a_cell_without_companions_keeps_its_five_entry_shape(tmp_path, fake_agent):
    demo = _skill(tmp_path, "demo", COMMITTED)
    out = tmp_path / "cell"
    cell.run_cell(out, "demo", demo, "p", model="m")
    assert not (out / "with").exists()


def test_the_none_arm_installs_no_companions(tmp_path, fake_agent):
    """A baseline with the companion in it is a different experiment."""
    helper = _skill(tmp_path, "helper", HELPER)
    out = tmp_path / "cell"
    cell.run_cell(out, "demo", None, "p", model="m", companions={"helper": helper})
    from pathlib import Path
    assert not (Path(fake_agent["config_dir"]) / "skills").exists()
    assert not (out / "with").exists()


def test_canary_three_counts_companions_as_expected(tmp_path, fake_agent, monkeypatch):
    """The exact-set canary must include companions, or every `--with` run fails
    pre-flight — and must still fail on a skill that was not asked for."""
    demo = _skill(tmp_path, "demo", COMMITTED)
    helper = _skill(tmp_path, "helper", HELPER)
    original = cell._install_skill

    def install_extra(config_dir, skill_name, skill_src, companions=None):
        original(config_dir, skill_name, skill_src, companions)
        (config_dir / "skills" / "stowaway").mkdir()

    monkeypatch.setattr(cell, "_install_skill", install_extra)
    with pytest.raises(CanaryFailure):
        cell.run_cell(tmp_path / "cell", "demo", demo, "p", model="m", companions={"helper": helper})


# --- end to end, stub lane ---------------------------------------------------


def test_with_flows_into_manifests_and_report(repo, tmp_path, monkeypatch, capsys):
    runs = tmp_path / "runs"
    monkeypatch.setattr(paths, "RUNS_DIR", runs)
    rc = cli.main([
        "run", "--skill", "demo", "--arm", "none", "--arm", "WORKTREE",
        "--with", "helper", "--prompt", "p", "--runner", "stub",
    ])
    assert rc == 0
    [run_dir] = [p for p in runs.iterdir() if p.is_dir()]

    record = manifest.read(run_dir)
    assert record.with_skills == ["helper"]

    worktree = json.loads((run_dir / "WORKTREE" / "manifest.json").read_text())
    assert [c["skill"] for c in worktree["with"]] == ["helper"]
    assert worktree["with"][0]["sha"] == arms.WORKTREE
    none = json.loads((run_dir / "none" / "manifest.json").read_text())
    assert none["with"] == []

    assert (run_dir / "WORKTREE" / "1" / "with" / "helper" / "SKILL.md").is_file()
    assert not (run_dir / "none" / "1" / "with").exists()

    report = (run_dir / "REPORT.md").read_text()
    assert "- with: `helper`" in report
    assert "with helper ->" in capsys.readouterr().out


def test_with_naming_the_skill_under_test_is_a_usage_error(repo, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(paths, "RUNS_DIR", tmp_path / "runs")
    rc = cli.main([
        "run", "--skill", "demo", "--arm", "WORKTREE", "--with", "demo",
        "--prompt", "p", "--runner", "stub",
    ])
    assert rc == 2
    assert "names the skill under test" in capsys.readouterr().err
    assert not (tmp_path / "runs").exists() or not list((tmp_path / "runs").iterdir())
