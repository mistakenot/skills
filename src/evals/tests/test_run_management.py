"""Runs accumulate, so they have to be listable, readable and droppable.

Everything here is a stub-mode round trip through the real CLI: `run` three
times, then `list`, `show` and `clean` over what it left. Arm resolution is the
one part stood in for — `arms.resolve` shells out to the compiler and rewrites
the repo's `skills/` tree, which a test must not do.

`clean` deletes, so it is tested the way a delete has to be: with a second run
present that must survive, and with a non-run directory parked alongside that a
sweep must not touch.
"""

import json
from pathlib import Path

import pytest

from evals import __main__ as cli
from evals import arms, manage, manifest, paths, report, runners

REF = "abc1234"
REF_SHA = "a" * 40
HEAD_SHA = "b" * 40


@pytest.fixture
def runs_dir(tmp_path, monkeypatch):
    """A relocated `runs/` and a compiler-free `arms.resolve`."""
    src = tmp_path / "compiled" / "demo"
    (src / "references").mkdir(parents=True)
    (src / "SKILL.md").write_text("---\nname: demo\n---\nbody\n")
    (src / "references" / "extra.md").write_text("detail\n")

    def fake_resolve(arm, skill):
        if arm == arms.NONE:
            return arms.Arm(name=arm, kind=arms.KIND_NONE, skill_src=None)
        if arm == arms.WORKTREE:
            return arms.Arm(
                name=arm,
                kind=arms.KIND_WORKTREE,
                skill_src=src,
                sha=arms.WORKTREE,
                head=HEAD_SHA,
                dirty=True,
            )
        return arms.Arm(name=arm, kind=arms.KIND_REF, skill_src=src, sha=REF_SHA)

    monkeypatch.setattr(arms, "resolve", fake_resolve)
    monkeypatch.setattr(paths, "RUNS_DIR", tmp_path / "runs")
    return tmp_path / "runs"


def _run(capsys, *extra, arm_names=(arms.WORKTREE,)):
    """One stub run through the CLI. Returns its run id."""
    argv = ["run", "--skill", "demo"]
    for name in arm_names:
        argv += ["--arm", name]
    argv += ["--prompt", "write me an answer", "--runner", runners.STUB, *extra]
    assert cli.main(argv) == 0
    for line in capsys.readouterr().out.splitlines():
        if line.startswith("evals: run "):
            return line.split()[2]
    raise AssertionError("the run never announced its id")


# --- list -------------------------------------------------------------------


def test_list_returns_every_run_newest_first(runs_dir, capsys):
    made = [_run(capsys) for _ in range(3)]
    assert len(set(made)) == 3, "three runs must not collide on an id"

    lines = manage.list_lines(runs_dir)
    assert [line.split()[0] for line in lines] == list(reversed(made))
    assert all("demo" in line and arms.WORKTREE in line for line in lines)


def test_list_says_so_when_there_is_nothing(runs_dir):
    assert manage.list_lines(runs_dir) == [f"no runs under {runs_dir}"]


def test_list_shows_the_trial_count_only_when_it_is_not_one(runs_dir, capsys):
    _run(capsys)
    _run(capsys, "--n", "3")
    lines = manage.list_lines(runs_dir)
    assert "n=3" in lines[0]
    assert "n=" not in lines[1]


def test_list_still_shows_a_run_that_has_no_manifest(runs_dir, capsys):
    """A run made before manifests existed is still evidence."""
    run_id = _run(capsys)
    (runs_dir / run_id / manifest.RUN_MANIFEST_NAME).unlink()
    line = manage.list_lines(runs_dir)[0]
    assert run_id in line and arms.WORKTREE in line and "no manifest" in line


# --- show -------------------------------------------------------------------


def _printed_paths(lines, root):
    """Every absolute path `show` printed, quotes from the diff line stripped."""
    found = []
    for line in lines:
        for token in line.split():
            token = token.strip("'\"")
            if token.startswith(str(root)):
                found.append(token)
    return found


def test_show_prints_paths_that_exist_on_disk(runs_dir, capsys, tmp_path):
    run_id = _run(capsys, "--n", "2", arm_names=(arms.NONE, arms.WORKTREE))
    lines = manage.show_lines(runs_dir / run_id)

    printed = _printed_paths(lines, tmp_path)
    assert printed, "show printed no paths at all"
    missing = [p for p in printed if not Path(p).exists()]
    assert not missing, f"show named paths that are not there: {missing}"

    text = "\n".join(lines)
    assert str(runs_dir / run_id / report.REPORT_NAME) in text
    assert str(runs_dir / run_id / manifest.RUN_MANIFEST_NAME) in text


def test_show_groups_outputs_by_trial_so_the_arms_sit_together(runs_dir, capsys):
    run_id = _run(capsys, "--n", "2", arm_names=(arms.NONE, arms.WORKTREE))
    lines = manage.show_lines(runs_dir / run_id)

    trials = [i for i, line in enumerate(lines) if line.strip().startswith("trial ")]
    assert len(trials) == 2, "both trials should head their own group"
    # Between one trial heading and the next, both arms' outputs and a diff line.
    block = lines[trials[0]: trials[1]]
    assert any(arms.NONE in line and "out.md" in line for line in block)
    assert any(arms.WORKTREE in line and "out.md" in line for line in block)
    assert any(line.strip().startswith("diff -u ") for line in block)


def test_show_reports_the_run_summary(runs_dir, capsys):
    run_id = _run(capsys, "--model", "pinned-model", "--invoke", "organic")
    text = "\n".join(manage.show_lines(runs_dir / run_id))
    assert run_id in text
    assert "demo" in text and "pinned-model" in text and "organic" in text
    assert runners.STUB in text
    assert "write me an answer" in text
    # The provenance a reader is actually after, from the per-arm record.
    assert arms.WORKTREE in text and HEAD_SHA[:8] in text and "dirty" in text
    assert "invoked" in text


def test_show_works_on_a_run_with_no_manifest(runs_dir, capsys):
    run_id = _run(capsys, arm_names=(arms.NONE, arms.WORKTREE))
    (runs_dir / run_id / manifest.RUN_MANIFEST_NAME).unlink()
    text = "\n".join(manage.show_lines(runs_dir / run_id))
    assert "no run manifest" in text
    assert arms.NONE in text and arms.WORKTREE in text


def test_show_rejects_an_unknown_run(runs_dir, capsys):
    assert cli.main(["show", "nope"]) == 2
    assert "no run 'nope'" in capsys.readouterr().err


def test_show_rejects_a_path_rather_than_a_run_id(runs_dir, capsys):
    assert cli.main(["show", "../../etc"]) == 2


# --- manifest ---------------------------------------------------------------


def test_manifest_round_trips(runs_dir, capsys):
    """Reading it back reconstructs what was compared, shas included."""
    run_id = _run(
        capsys,
        "--n",
        "2",
        "--model",
        "pinned-model",
        "--invoke",
        "organic",
        arm_names=(arms.NONE, arms.WORKTREE, REF),
    )
    record = manifest.read(runs_dir / run_id)

    assert record.run_id == run_id
    assert record.skill == "demo"
    assert record.model == "pinned-model"
    assert record.runner == runners.STUB
    assert record.invoke == "organic"
    assert record.trials == 2
    assert record.scenario == "inline"
    assert record.prompt == "write me an answer"
    assert record.status == manifest.STATUS_OK
    assert record.started_at and record.finished_at

    assert record.arm_names == [arms.NONE, arms.WORKTREE, REF]
    by_name = {a.name: a for a in record.arms}
    assert by_name[arms.NONE].kind == arms.KIND_NONE
    assert by_name[arms.NONE].sha is None
    assert by_name[arms.WORKTREE].sha == arms.WORKTREE
    assert by_name[arms.WORKTREE].head == HEAD_SHA
    assert by_name[arms.WORKTREE].dirty is True
    assert by_name[REF].kind == arms.KIND_REF
    assert by_name[REF].sha == REF_SHA


def test_the_run_manifest_points_at_the_per_arm_records_rather_than_copying_them(
    runs_dir, capsys
):
    """One source of truth for a sha. A summary that stores it is one that drifts."""
    run_id = _run(capsys, arm_names=(arms.WORKTREE, REF))
    raw = json.loads((runs_dir / run_id / manifest.RUN_MANIFEST_NAME).read_text())

    for pointer in raw["arms"]:
        assert set(pointer) == {"arm", "dir", "manifest"}
        assert (runs_dir / run_id / pointer["manifest"]).is_file()
    # The per-arm record is untouched and still holds the sha.
    per_arm = json.loads((runs_dir / run_id / REF / arms.MANIFEST_NAME).read_text())
    assert per_arm["sha"] == REF_SHA


def test_a_run_that_never_finished_is_still_listable(runs_dir, tmp_path, monkeypatch, capsys):
    """The manifest is written before the first token is spent, not after."""
    from evals import cell

    monkeypatch.setattr(
        cell, "run_cell", lambda **kw: (_ for _ in ()).throw(cell.CellError("boom"))
    )
    assert cli.main(
        ["run", "--skill", "demo", "--arm", arms.WORKTREE,
         "--prompt", "p", "--runner", runners.STUB]
    ) == 2

    line = manage.list_lines(runs_dir)[0]
    assert manifest.STATUS_INCOMPLETE in line and arms.WORKTREE in line


# --- --n --------------------------------------------------------------------


def test_n_three_gives_three_trial_dirs_per_arm(runs_dir, capsys):
    run_id = _run(capsys, "--n", "3", arm_names=(arms.NONE, arms.WORKTREE))
    for arm in (arms.NONE, arms.WORKTREE):
        arm_dir = runs_dir / run_id / arm
        trials = {p.name for p in arm_dir.iterdir() if p.is_dir()}
        assert trials == {"1", "2", "3"}, f"{arm} has {sorted(trials)}"
        for trial in trials:
            assert (arm_dir / trial / "out.md").is_file()


def test_the_report_states_the_trial_count(runs_dir, capsys):
    run_id = _run(capsys, "--n", "3")
    assert "- trials per arm: `3`" in (runs_dir / run_id / report.REPORT_NAME).read_text()


def test_the_report_states_the_trial_count_for_a_single_trial_too(runs_dir, capsys):
    """One and three must not look the same at a glance."""
    run_id = _run(capsys)
    assert "- trials per arm: `1`" in (runs_dir / run_id / report.REPORT_NAME).read_text()


def test_every_trial_is_checked_for_invocation(runs_dir, capsys):
    run_id = _run(capsys, "--n", "3")
    record = json.loads(
        (runs_dir / run_id / arms.WORKTREE / "invocation.json").read_text()
    )
    assert [c["trial"] for c in record["cells"]] == [1, 2, 3]


def test_n_defaults_to_one(runs_dir):
    args = cli.build_parser().parse_args(
        ["run", "--skill", "demo", "--arm", arms.WORKTREE, "--prompt", "p"]
    )
    assert args.n == 1


def test_n_below_one_is_rejected(runs_dir, capsys):
    assert cli.main(
        ["run", "--skill", "demo", "--arm", arms.WORKTREE,
         "--prompt", "p", "--runner", runners.STUB, "--n", "0"]
    ) == 2
    assert "--n must be at least 1" in capsys.readouterr().err


# --- clean ------------------------------------------------------------------


def _intact(run_dir):
    """A run directory that still holds everything it should."""
    return (
        (run_dir / report.REPORT_NAME).is_file()
        and (run_dir / manifest.RUN_MANIFEST_NAME).is_file()
        and (run_dir / arms.WORKTREE / "1" / "out.md").is_file()
    )


def test_clean_removes_the_named_run_and_nothing_else(runs_dir, capsys):
    doomed = _run(capsys)
    survivor = _run(capsys)

    assert cli.main(["clean", "--run", doomed, "--yes"]) == 0
    assert not (runs_dir / doomed).exists()
    assert _intact(runs_dir / survivor)
    assert {p.name for p in runs_dir.iterdir()} == {survivor}


def test_clean_does_nothing_without_yes(runs_dir, capsys):
    first = _run(capsys)
    second = _run(capsys)

    assert cli.main(["clean", "--all"]) == 0
    out = capsys.readouterr().out
    assert "would remove 2 run(s)" in out and "dry run" in out
    assert _intact(runs_dir / first) and _intact(runs_dir / second)


def test_clean_removes_exactly_what_the_dry_run_named(runs_dir, capsys):
    made = [_run(capsys) for _ in range(3)]

    assert cli.main(["clean", "--keep", "1"]) == 0
    named = {line.strip() for line in capsys.readouterr().out.splitlines() if line.startswith("  ")}
    assert named == set(made[:2])

    assert cli.main(["clean", "--keep", "1", "--yes"]) == 0
    assert {p.name for p in runs_dir.iterdir()} == {made[2]}
    assert _intact(runs_dir / made[2])


def test_clean_all_empties_the_directory(runs_dir, capsys):
    for _ in range(2):
        _run(capsys)
    assert cli.main(["clean", "--all", "--yes"]) == 0
    assert list(runs_dir.iterdir()) == []


def test_clean_refuses_an_unknown_run_and_deletes_nothing(runs_dir, capsys):
    kept = _run(capsys)
    assert cli.main(["clean", "--run", "20990101-000000-0000", "--yes"]) == 2
    assert "no such run" in capsys.readouterr().err
    assert _intact(runs_dir / kept)


def test_a_sweep_leaves_a_directory_that_is_not_a_run(runs_dir, capsys):
    """`clean --all` was told to drop runs, not to empty the folder."""
    _run(capsys)
    parked = runs_dir / "keep-my-notes"
    parked.mkdir()
    (parked / "notes.md").write_text("mine\n")

    assert cli.main(["clean", "--all", "--yes"]) == 0
    assert (parked / "notes.md").read_text() == "mine\n"
    assert {p.name for p in runs_dir.iterdir()} == {"keep-my-notes"}


def test_clean_refuses_to_leave_the_runs_directory(runs_dir, tmp_path, capsys):
    _run(capsys)
    with pytest.raises(manage.CleanError, match="not a direct child"):
        manage.remove(runs_dir, [tmp_path / "compiled"])
    assert (tmp_path / "compiled" / "demo" / "SKILL.md").is_file()


def test_clean_keeps_the_newest_by_default(runs_dir, capsys):
    """The default keeps more than a hand-run session is likely to make."""
    made = [_run(capsys) for _ in range(2)]
    plan = manage.select(runs_dir)
    assert plan.remove == []
    assert {p.name for p in plan.keep} == set(made)


def test_clean_reports_when_there_is_nothing_to_drop(runs_dir, capsys):
    _run(capsys)
    assert cli.main(["clean", "--keep", "5"]) == 0
    assert "nothing to remove" in capsys.readouterr().out
