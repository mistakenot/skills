"""Tests for the run-directory layout and the cell's bookkeeping.

The agent call itself is faked: everything around it — canaries, the installed-
skill snapshot, transcript capture, result extraction, workspace copy-out — is
plumbing that must be regression-tested without billing a multi-minute run.
"""

import json
import pathlib
import subprocess
import tempfile

import pytest

from evals import cell, paths, report, runners
from evals.canaries import CanaryFailure

RESULT_TEXT = "# Answer\n\nfour\n"


def _stream_lines(result_text=RESULT_TEXT):
    return "\n".join(
        [
            json.dumps({"type": "system", "subtype": "init"}),
            json.dumps({"type": "assistant", "message": {"content": []}}),
            json.dumps({"type": "result", "subtype": "success", "result": result_text}),
        ]
    ) + "\n"


@pytest.fixture
def fake_agent(monkeypatch, tmp_path):
    """Replace the `claude` invocation with a stand-in that writes a transcript."""
    calls = {}

    def fake_run(argv, cwd, env, stdin, stdout, stderr):
        calls["argv"] = argv
        calls["cwd"] = cwd
        calls["config_dir"] = env["CLAUDE_CONFIG_DIR"]
        stdout.write(_stream_lines().encode())
        stderr.write(b"")
        # The agent leaves something behind in the workspace.
        (cwd / "notes.txt").write_text("worked here\n")
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(runners.subprocess, "run", fake_run)

    creds = tmp_path / "credentials.json"
    creds.write_text("{}")
    monkeypatch.setattr(cell, "CREDENTIALS", creds)
    return calls


@pytest.fixture
def skill_src(tmp_path):
    src = tmp_path / "skills" / "demo"
    (src / "references").mkdir(parents=True)
    (src / "SKILL.md").write_text("---\nname: demo\n---\nbody\n")
    (src / "references" / "extra.md").write_text("detail\n")
    return src


def test_cell_leaves_the_full_evidence_set(tmp_path, fake_agent, skill_src):
    out = tmp_path / "runs" / "r1" / "WORKTREE" / "1"
    result = cell.run_cell(out, "demo", skill_src, "what is 2+2?", model="test-model")

    assert result.exit_code == 0
    assert (out / "skill").is_dir()
    assert (out / "ws").is_dir()
    assert (out / "stream.jsonl").is_file()
    assert (out / "out.md").is_file()
    assert (out / "err.txt").is_file()
    assert (out / "out.md").read_text() == RESULT_TEXT
    assert (out / "out.md").read_text().strip() != ""


def test_installed_skill_is_snapshotted_in_full(tmp_path, fake_agent, skill_src):
    """`skill/` answers "what exactly was in that arm?" — references included."""
    out = tmp_path / "cell"
    cell.run_cell(out, "demo", skill_src, "p", model="m")
    assert (out / "skill" / "SKILL.md").read_text() == "---\nname: demo\n---\nbody\n"
    assert (out / "skill" / "references" / "extra.md").read_text() == "detail\n"


def test_workspace_is_copied_out_after_the_run(tmp_path, fake_agent, skill_src):
    out = tmp_path / "cell"
    cell.run_cell(out, "demo", skill_src, "p", model="m")
    assert (out / "ws" / "notes.txt").read_text() == "worked here\n"


def test_agent_runs_in_the_workspace_with_the_relocated_config(tmp_path, fake_agent, skill_src):
    out = tmp_path / "cell"
    result = cell.run_cell(out, "demo", skill_src, "p", model="m")
    assert fake_agent["cwd"] == result.workspace
    assert fake_agent["config_dir"] == str(result.config_dir)
    assert (result.config_dir / "skills" / "demo" / "SKILL.md").is_file()
    assert (result.config_dir / ".credentials.json").is_file()


def test_invocation_flags_match_the_verified_recipe(tmp_path, fake_agent, skill_src):
    cell.run_cell(tmp_path / "cell", "demo", skill_src, "p", model="pinned-model")
    argv = fake_agent["argv"]
    assert argv[0] == "claude"
    assert "-p" in argv
    assert argv[argv.index("--model") + 1] == "pinned-model"
    for flag in ("--output-format", "--verbose", "--strict-mcp-config", "--permission-mode"):
        assert flag in argv
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    assert argv[argv.index("--permission-mode") + 1] == "bypassPermissions"
    # `--setting-sources ''` isolates but silently suppresses the skill under
    # test, turning the with-skill arm into a second baseline.
    assert "--setting-sources" not in argv


def test_canaries_run_before_the_agent_is_invoked(tmp_path, monkeypatch, fake_agent, skill_src):
    """A failing canary must cost nothing — no agent call at all."""
    # Pretend the repo root is the temp root, so the clean room lands "inside" it.
    monkeypatch.setattr(cell, "REPO_ROOT", pathlib.Path(tempfile.gettempdir()))

    def explode(*a, **kw):
        raise AssertionError("agent was invoked despite a failing canary")

    monkeypatch.setattr(runners.subprocess, "run", explode)
    with pytest.raises(CanaryFailure):
        cell.run_cell(tmp_path / "cell", "demo", skill_src, "p", model="m")


def test_missing_credentials_fail_fast(tmp_path, monkeypatch, skill_src):
    monkeypatch.setattr(cell, "CREDENTIALS", tmp_path / "nope.json")
    with pytest.raises(cell.CellError, match="credentials"):
        cell.run_cell(tmp_path / "cell", "demo", skill_src, "p", model="m")


# --- result extraction -----------------------------------------------------


def test_extract_result_takes_the_last_result_envelope(tmp_path):
    stream = tmp_path / "stream.jsonl"
    stream.write_text(
        json.dumps({"type": "result", "result": "first"})
        + "\n"
        + json.dumps({"type": "result", "result": "last"})
        + "\n"
    )
    assert cell.extract_result_text(stream) == "last"


def test_extract_result_survives_partial_lines(tmp_path):
    stream = tmp_path / "stream.jsonl"
    stream.write_text('{"type": "system"}\nnot json at all\n' + json.dumps({"type": "result", "result": "ok"}))
    assert cell.extract_result_text(stream) == "ok"


def test_extract_result_is_empty_when_the_agent_never_finished(tmp_path):
    stream = tmp_path / "stream.jsonl"
    stream.write_text(json.dumps({"type": "system", "subtype": "init"}) + "\n")
    assert cell.extract_result_text(stream) == ""


# --- run identity and report ----------------------------------------------


def test_cell_dir_is_run_arm_trial(tmp_path):
    assert paths.cell_dir(tmp_path, "rid", "WORKTREE", 1) == tmp_path / "rid" / "WORKTREE" / "1"


def test_run_ids_are_unique_and_sortable():
    ids = {paths.new_run_id() for _ in range(50)}
    assert len(ids) == 50
    assert sorted(ids) == sorted(ids, key=str)


def test_runs_accumulate_rather_than_being_cleared(tmp_path, fake_agent, skill_src):
    """Previous runs must survive: keeping only the last one loses the evidence."""
    first = paths.cell_dir(tmp_path, "run-a", "WORKTREE", 1)
    cell.run_cell(first, "demo", skill_src, "p", model="m")
    second = paths.cell_dir(tmp_path, "run-b", "WORKTREE", 1)
    cell.run_cell(second, "demo", skill_src, "p", model="m")
    assert (first / "out.md").is_file()
    assert (second / "out.md").is_file()


def test_report_names_the_arm_and_the_paths(tmp_path):
    run_dir = tmp_path / "run-a"
    cell_dir = paths.cell_dir(tmp_path, "run-a", "WORKTREE", 1)
    cell_dir.mkdir(parents=True)
    path = report.write_report(
        run_dir=run_dir,
        run_id="run-a",
        skill="demo",
        arm="WORKTREE",
        model="m",
        prompt="what is 2+2?",
        cells=[("WORKTREE", 0, cell_dir)],
    )
    text = path.read_text()
    assert path == run_dir / "REPORT.md"
    assert "run-a" in text and "demo" in text and "WORKTREE" in text
    assert "what is 2+2?" in text
    assert str(cell_dir / "out.md") in text
    assert str(cell_dir / "stream.jsonl") in text
