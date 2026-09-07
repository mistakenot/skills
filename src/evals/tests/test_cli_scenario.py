"""`evals run --scenario <dir>`, end to end, offline.

The acceptance shape for a scenario: the directory parses, its `setup.sh` runs,
and its `fixture/` plus whatever setup produced land in the workspace the agent
actually worked in — asserted against `ws/` in the run tree, which is the copy a
human opens afterwards, not against the cache.

Arm resolution is stood in for as in `test_cli_end_to_end.py`: it shells out to
`src/compile.py` and rewrites the repo's `skills/` tree, which a test must not do.
"""

import pytest

from evals import __main__ as cli
from evals import arms, paths, report, runners, scenarios

from .test_scenarios import PINNED_SHA, make_scenario


@pytest.fixture
def compiled_skill(tmp_path, monkeypatch):
    src = tmp_path / "compiled" / "demo"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text("---\nname: demo\n---\nbody\n")
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
    monkeypatch.setattr(scenarios, "CACHE_DIR", tmp_path / "cache")
    return src


@pytest.fixture
def counter(tmp_path):
    """Counts actual `setup.sh` executions, from outside the workspace.

    Inside, it would be copied along with the payload and one fetch would be
    indistinguishable from one copy.
    """
    return tmp_path / "count"


@pytest.fixture
def scenario_dir(tmp_path, counter):
    return make_scenario(
        tmp_path / "scenario" / "demo-task",
        prompt="write a design doc for the thing",
        setup=(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            f"SHA={PINNED_SHA}\n"
            f"echo run >> {counter}\n"
            'echo "$SHA" > checkout/PINNED\n'
        ),
        fixture={"checkout/README.md": "the repo\n"},
    )


def _cell_dir(runs_root):
    run_dir = next(runs_root.iterdir())
    return run_dir / arms.WORKTREE / "1"


def test_scenario_prompt_setup_and_fixture_all_reach_the_workspace(
    compiled_skill, scenario_dir, tmp_path, capsys
):
    code = cli.main(
        ["run", "--skill", "demo", "--arm", arms.WORKTREE,
         "--scenario", str(scenario_dir), "--runner", runners.STUB]
    )
    assert code == 0

    ws = _cell_dir(tmp_path / "runs") / "ws"
    assert (ws / "checkout" / "README.md").read_text() == "the repo\n", "fixture missing"
    assert (ws / "checkout" / "PINNED").read_text().strip() == PINNED_SHA, "setup.sh did not run"

    out = capsys.readouterr().out
    assert "scenario demo-task" in out


def test_the_scenario_prompt_is_the_prompt_the_agent_got(
    compiled_skill, scenario_dir, tmp_path
):
    """prompt.md, not a paraphrase of it, and not the inline flag's job."""
    cli.main(
        ["run", "--skill", "demo", "--arm", arms.WORKTREE,
         "--scenario", str(scenario_dir), "--runner", runners.STUB]
    )
    run_dir = next((tmp_path / "runs").iterdir())
    assert "write a design doc for the thing" in (run_dir / report.REPORT_NAME).read_text()


def test_a_second_run_reuses_the_prepared_workspace(
    compiled_skill, scenario_dir, counter, tmp_path
):
    """Two runs of the same scenario prepare it once.

    Counted, not timed: `setup.sh` appends a line every time it actually runs,
    so a cache that silently missed shows up as two lines rather than as a
    slower test. The marker from the first fetch must also survive untouched,
    and both runs' workspaces must still be fully seeded — a cache that "hits"
    by handing back an empty tree would otherwise pass.
    """
    scenario = scenarios.load(scenario_dir)
    cache = tmp_path / "cache"

    cli.main(["run", "--skill", "demo", "--arm", arms.WORKTREE,
              "--scenario", str(scenario_dir), "--runner", runners.STUB])
    marker = scenarios.entry_dir(scenario, cache) / scenarios.MARKER_NAME
    before = marker.read_text(), marker.stat().st_mtime_ns
    assert counter.read_text().splitlines() == ["run"]

    cli.main(["run", "--skill", "demo", "--arm", arms.WORKTREE,
              "--scenario", str(scenario_dir), "--runner", runners.STUB])

    assert counter.read_text().splitlines() == ["run"], (
        "setup.sh ran again — the second run re-prepared the scenario"
    )
    assert (marker.read_text(), marker.stat().st_mtime_ns) == before

    runs = sorted((tmp_path / "runs").iterdir())
    assert len(runs) == 2
    for run_dir in runs:
        ws = run_dir / arms.WORKTREE / "1" / "ws"
        assert (ws / "checkout" / "PINNED").read_text().strip() == PINNED_SHA


def test_two_arms_of_one_run_share_a_single_preparation(
    compiled_skill, scenario_dir, counter, tmp_path, monkeypatch
):
    """The reason the cache exists: an N-arm run must not fetch N times."""
    monkeypatch.setattr(
        arms, "resolve",
        lambda arm, skill: arms.Arm(name=arm, kind=arms.KIND_NONE, skill_src=None)
        if arm == arms.NONE
        else arms.Arm(name=arm, kind=arms.KIND_WORKTREE, skill_src=compiled_skill,
                      sha=arms.WORKTREE, head="0" * 40, dirty=False),
    )
    cli.main(["run", "--skill", "demo", "--arm", arms.NONE, "--arm", arms.WORKTREE,
              "--scenario", str(scenario_dir), "--runner", runners.STUB])

    assert counter.read_text().splitlines() == ["run"]
    run_dir = next((tmp_path / "runs").iterdir())
    for arm_name in (arms.NONE, arms.WORKTREE):
        ws = run_dir / arm_name / "1" / "ws"
        assert (ws / "checkout" / "PINNED").read_text().strip() == PINNED_SHA


def test_a_floating_scenario_is_rejected_before_any_arm_is_resolved(
    compiled_skill, tmp_path, monkeypatch, capsys
):
    """The pin check is a gate, not a warning — and it fires first.

    `arms.resolve` is replaced with a bomb: reaching it at all would mean the
    harness had started spending on a fixture that drifts.
    """
    def explode(*_args, **_kwargs):
        raise AssertionError("arms were resolved despite a floating scenario")

    monkeypatch.setattr(arms, "resolve", explode)
    floating = make_scenario(
        tmp_path / "scenario" / "floating",
        setup="#!/usr/bin/env bash\ngit clone https://example.invalid/r.git\n"
              "git -C r checkout main\n",
    )

    code = cli.main(
        ["run", "--skill", "demo", "--arm", arms.WORKTREE,
         "--scenario", str(floating), "--runner", runners.STUB]
    )
    assert code == 2
    assert "not a 40-character sha" in capsys.readouterr().err


def test_prompt_and_scenario_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(
            ["run", "--skill", "demo", "--arm", arms.NONE,
             "--prompt", "p", "--scenario", "s"]
        )


def test_a_run_needs_one_or_the_other():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["run", "--skill", "demo", "--arm", arms.NONE])
