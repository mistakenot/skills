"""A whole run, end to end, through the CLI — offline and in milliseconds.

This is the acceptance check for the fast lane: `evals run --runner stub` walks
the real code path (arm resolution, run id, cell, canaries, report) and leaves a
run tree a human could open, without a network call or a billed token.

Arm resolution is the one part stood in for: `arms.resolve` shells out to
`src/compile.py` and rewrites the repo's `skills/` tree, which a test must not
do. Everything downstream of it is the production path.
"""

import pytest

from evals import __main__ as cli
from evals import arms, manifest, paths, report, runners

from . import helpers


@pytest.fixture
def compiled_skill(tmp_path, monkeypatch):
    """Stand in for the compiler: a skill directory, already 'compiled'."""
    src = tmp_path / "compiled" / "demo"
    (src / "references").mkdir(parents=True)
    (src / "SKILL.md").write_text("---\nname: demo\n---\nbody\n")
    (src / "references" / "extra.md").write_text("detail\n")
    resolved = arms.Arm(
        name=arms.WORKTREE,
        kind=arms.KIND_WORKTREE,
        skill_src=src,
        sha=arms.WORKTREE,
        head="0" * 40,
        dirty=False,
    )
    monkeypatch.setattr(arms, "resolve", lambda arm, skill: resolved)
    monkeypatch.setattr(paths, "RUNS_DIR", tmp_path / "runs")
    return src


def test_cli_stub_run_leaves_a_readable_run_tree(compiled_skill, tmp_path, capsys):
    code = cli.main(
        ["run", "--skill", "demo", "--arm", arms.WORKTREE,
         "--prompt", "write me an answer", "--runner", runners.STUB]
    )
    assert code == 0

    runs = tmp_path / "runs"
    run_dir = next(runs.iterdir())
    assert {p.name for p in run_dir.iterdir()} == {
        report.REPORT_NAME, manifest.RUN_MANIFEST_NAME, arms.WORKTREE
    }

    cell_dir = run_dir / arms.WORKTREE / "1"
    helpers.assert_cell_shape(cell_dir)
    helpers.assert_stream_is_wellformed(cell_dir / "stream.jsonl")

    text = (run_dir / report.REPORT_NAME).read_text()
    assert "write me an answer" in text
    assert f"runner: `{runners.STUB}`" in text
    assert report.STUB_BANNER in text
    assert str(cell_dir / "stream.jsonl") in text

    assert "runner stub" in capsys.readouterr().out


def test_cli_defaults_to_the_live_runner(compiled_skill):
    """The fast lane must be asked for: an unflagged run is the real thing."""
    args = cli.build_parser().parse_args(
        ["run", "--skill", "demo", "--arm", arms.WORKTREE, "--prompt", "p"]
    )
    assert args.runner == runners.LIVE
