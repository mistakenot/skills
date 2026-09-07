"""The runner seam, checked in both modes against the same assertions.

The whole value of the stub is that it produces a run a live run would be
mistaken for. That is only true if it is *checked* to be true, so every
assertion in this module is parameterised over both runners and comes from
`helpers.py` — one set of expectations, two ways of satisfying them. The live
arm replays a real recorded transcript (`fixtures/live-stream.jsonl`) instead of
spawning `claude`, so it costs nothing but still exercises the live code path
and asserts against output an agent actually emitted.
"""

import socket
import subprocess

import pytest

from evals import cell, report, runners

from . import helpers


@pytest.fixture
def skill_src(tmp_path):
    src = tmp_path / "skills" / "demo"
    (src / "references").mkdir(parents=True)
    (src / "SKILL.md").write_text("---\nname: demo\n---\nbody\n")
    (src / "references" / "extra.md").write_text("detail\n")
    return src


@pytest.fixture(params=[runners.LIVE, runners.STUB])
def runner(request, monkeypatch, tmp_path):
    """Both runners, made cheap: live replays the recorded transcript."""
    if request.param == runners.LIVE:
        recorded = helpers.LIVE_STREAM.read_bytes()

        def replay(argv, cwd, env, stdin, stdout, stderr):
            stdout.write(recorded)
            stderr.write(b"")
            (cwd / "answer.md").write_text("2+2=4\n")
            return subprocess.CompletedProcess(argv, 0)

        monkeypatch.setattr(runners.subprocess, "run", replay)
        creds = tmp_path / "credentials.json"
        creds.write_text("{}")
        monkeypatch.setattr(cell, "CREDENTIALS", creds)
    return request.param


def test_cell_shape_is_the_same_in_both_modes(tmp_path, skill_src, runner):
    out = tmp_path / "cell"
    result = cell.run_cell(out, "demo", skill_src, "p", model="m", runner=runner)

    assert result.exit_code == 0
    assert result.runner == runner
    helpers.assert_cell_shape(out)
    helpers.assert_stream_is_wellformed(out / "stream.jsonl")


def test_isolation_is_identical_in_both_modes(tmp_path, skill_src, runner):
    """Same clean room either way: relocated config, exactly one skill, creds."""
    out = tmp_path / "cell"
    result = cell.run_cell(out, "demo", skill_src, "p", model="m", runner=runner)
    cfg = result.config_dir

    assert [p.name for p in (cfg / "skills").iterdir()] == ["demo"]
    assert (cfg / "skills" / "demo" / "references" / "extra.md").is_file()
    assert (cfg / ".credentials.json").is_file()
    assert not result.workspace.is_relative_to(cell.REPO_ROOT)
    assert (out / "skill" / "references" / "extra.md").read_text() == "detail\n"


def test_workspace_is_copied_out_in_both_modes(tmp_path, skill_src, runner):
    out = tmp_path / "cell"
    cell.run_cell(out, "demo", skill_src, "p", model="m", runner=runner)
    assert (out / "ws" / "answer.md").read_text() == "2+2=4\n"


def test_fixture_seeds_the_workspace_in_both_modes(tmp_path, skill_src, runner):
    """A scenario's starting files reach the agent, and survive into `ws/`."""
    fixture = tmp_path / "fixture"
    (fixture / "src").mkdir(parents=True)
    (fixture / "README.md").write_text("start here\n")
    (fixture / "src" / "app.py").write_text("print('hi')\n")

    out = tmp_path / "cell"
    result = cell.run_cell(
        out, "demo", skill_src, "p", model="m", runner=runner, fixture=fixture
    )
    assert (result.workspace / "src" / "app.py").is_file()
    assert (out / "ws" / "README.md").read_text() == "start here\n"


def test_run_report_names_the_runner_in_both_modes(tmp_path, skill_src, runner):
    run_dir = tmp_path / "run"
    out = run_dir / "WORKTREE" / "1"
    result = cell.run_cell(out, "demo", skill_src, "p", model="m", runner=runner)
    path = report.write_report(
        run_dir=run_dir,
        run_id="run",
        skill="demo",
        arm="WORKTREE",
        model="m",
        prompt="p",
        cells=[("WORKTREE", result.exit_code, out)],
        runner=runner,
    )
    text = path.read_text()
    assert f"runner: `{runner}`" in text
    # A stub report must be unmistakable: it looks exactly like a real one.
    assert (report.STUB_BANNER in text) is (runner == runners.STUB)


# --- what makes the stub a *fast* lane -------------------------------------


def test_stub_runs_with_no_subprocess_and_no_socket(tmp_path, monkeypatch, skill_src):
    """The fast lane must be hermetic: no process spawn, no network, no login."""

    def no_subprocess(*a, **kw):
        raise AssertionError("stub mode spawned a subprocess")

    def no_socket(*a, **kw):
        raise AssertionError("stub mode opened a socket")

    monkeypatch.setattr(runners.subprocess, "run", no_subprocess)
    monkeypatch.setattr(socket, "socket", no_socket)
    monkeypatch.setattr(socket, "create_connection", no_socket)
    # No credentials anywhere: the stub authenticates nothing.
    monkeypatch.setattr(cell, "CREDENTIALS", tmp_path / "absent.json")

    out = tmp_path / "cell"
    result = cell.run_cell(out, "demo", skill_src, "p", model="m", runner=runners.STUB)
    assert result.exit_code == 0
    helpers.assert_cell_shape(out)


def test_stub_still_runs_the_canaries(tmp_path, monkeypatch, skill_src):
    """A fast lane that skips the isolation checks would pass a broken cell."""
    import pathlib
    import tempfile

    from evals.canaries import CanaryFailure

    monkeypatch.setattr(cell, "REPO_ROOT", pathlib.Path(tempfile.gettempdir()))
    with pytest.raises(CanaryFailure):
        cell.run_cell(tmp_path / "cell", "demo", skill_src, "p", model="m", runner=runners.STUB)


def test_unknown_runner_is_rejected_by_name(tmp_path, skill_src):
    with pytest.raises(runners.RunnerError, match="unknown runner"):
        cell.run_cell(tmp_path / "cell", "demo", skill_src, "p", model="m", runner="pretend")
