"""Tests for `REPORT.md` as a *reading aid*.

The harness has no grader: judgement is a human reading two outputs side by
side, and this file is the entry point to that reading. So its usability is the
behaviour under test — one table with the arms as columns, an excerpt of what
each arm produced, and never a path that is not on disk.
"""

import json

import pytest

from evals import arms, invocation, manifest, paths, report, runners

MARKDOWN = """# Design: a thing

## Background

Prose about the thing.

```python
print("hello")
```

| a | b |
| --- | --- |
| 1 | 2 |
"""

HTML = """<!doctype html>
<html lang="en">
<head><title>Design: a thing</title>
<script src="https://cdn.example/pd.min.js" defer></script>
</head>
<body>
  <pd-doc title="Design: a thing">
    <pd-tab name="Overview">
      <pd-section id="summary" title="Summary">prose</pd-section>
      <pd-section id="detail" title="Detail">more prose</pd-section>
    </pd-tab>
  </pd-doc>
</body>
</html>
"""


def _cell(run_dir, arm, trial=1, *, output=None, name=None, skill=True, out_md="done\n"):
    """A cell directory shaped like one a real run leaves behind."""
    cell_dir = paths.cell_dir(run_dir.parent, run_dir.name, arm, trial)
    (cell_dir / "ws").mkdir(parents=True)
    (cell_dir / "out.md").write_text(out_md)
    (cell_dir / "err.txt").write_text("")
    (cell_dir / "stream.jsonl").write_text(
        json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": out_md})
        + "\n"
    )
    if skill:
        (cell_dir / "skill").mkdir()
        (cell_dir / "skill" / "SKILL.md").write_text("---\nname: demo\n---\n")
    if output is not None:
        (cell_dir / "ws" / name).write_text(output)
    return cell_dir


def _record(arm, *, invoked=True, registered=True, trials=1):
    return invocation.ArmInvocation(
        arm=arm,
        skill="demo",
        invoke_mode=invocation.INSTRUCTED,
        invoked=invoked,
        cells=[
            invocation.CellInvocation(
                trial=t,
                invoked=invoked,
                registered=registered,
                skill_calls=["demo"] if invoked else [],
            )
            for t in range(1, trials + 1)
        ],
    )


@pytest.fixture
def two_arm_run(tmp_path):
    """A `none`-vs-`WORKTREE` run: markdown out of one arm, HTML out of the other."""
    run_dir = tmp_path / "runs" / "run-a"
    none_cell = _cell(
        run_dir, "none", output=MARKDOWN, name="design.md", skill=False
    )
    worktree_cell = _cell(
        run_dir, "WORKTREE", output=HTML, name="design.html", skill=True
    )
    path = report.write_report(
        run_dir=run_dir,
        run_id="run-a",
        skill="demo",
        arm="none, WORKTREE",
        model="m",
        prompt="write a design doc",
        cells=[("none", 0, none_cell), ("WORKTREE", 0, worktree_cell)],
        invocations=[
            _record("none", invoked=True, registered=False),
            _record("WORKTREE", invoked=True, registered=True),
        ],
    )
    return path.read_text(), none_cell, worktree_cell


# --- the phantom path, which is the bug that started this ------------------


def test_none_arm_never_names_a_skill_directory_it_does_not_have(two_arm_run):
    """`none` installs nothing by design; naming a `skill/` path invents evidence."""
    text, none_cell, worktree_cell = two_arm_run
    assert not (none_cell / "skill").exists(), "fixture: the none arm must install nothing"

    assert str(none_cell / "skill") not in text
    assert "none/1/skill" not in text
    # And it says so, rather than leaving the reader to notice an absence.
    assert report.NO_SKILL_INSTALLED in text
    # The arm that *does* have one is still named.
    assert str(worktree_cell / "skill") in text


def test_no_printed_path_is_missing_from_disk(two_arm_run):
    """Every backticked absolute path in the report must resolve."""
    import re
    from pathlib import Path

    text, none_cell, _ = two_arm_run
    root = str(none_cell.parents[2])
    # Only the Files section: excerpted output carries its own backticks, and a
    # naive scan of the whole report pairs them with the report's own.
    files_section = text.split("## Files", 1)[1]
    printed = {m for m in re.findall(r"`([^`]+)`", files_section) if m.startswith(root)}
    assert printed, "the report printed no paths at all"
    missing = [p for p in printed if not Path(p).exists()]
    assert not missing, f"report names paths that do not exist: {missing}"


# --- one table, arms as columns --------------------------------------------


def test_comparison_table_puts_the_arms_side_by_side(two_arm_run):
    text, _, _ = two_arm_run
    header = next(line for line in text.splitlines() if line.startswith("|  |"))
    assert "**none**" in header and "**WORKTREE**" in header
    assert header.index("**none**") < header.index("**WORKTREE**")


def test_comparison_table_states_type_size_and_output_file(two_arm_run):
    text, _, _ = two_arm_run
    rows = {
        line.split("|")[1].strip(): [c.strip() for c in line.split("|")[2:-1]]
        for line in text.splitlines()
        if line.startswith("| ") and line.count("|") >= 3
    }
    assert rows["type"] == ["Markdown", "HTML"]
    assert rows["output file"] == ["`none/1/ws/design.md`", "`WORKTREE/1/ws/design.html`"]
    assert all(cell.endswith("B") or cell.endswith("KB") for cell in rows["size"])
    assert rows["lines"] == [str(MARKDOWN.count("\n")), str(HTML.count("\n"))]
    assert rows["skill invoked"] == ["yes", "yes"]
    assert rows["registered in `init.skills`"] == ["no", "yes"]


def test_html_arm_reports_its_custom_elements(two_arm_run):
    """The cheapest available signal that a page is component-built."""
    text, _, _ = two_arm_run
    row = next(line for line in text.splitlines() if line.startswith("| custom elements"))
    assert "`pd-section` ×2" in row
    assert "`pd-doc` ×1" in row
    # The markdown arm has no such column value to give.
    assert row.split("|")[2].strip() == "—"


def test_cross_format_counts_are_flagged_as_not_comparable(two_arm_run):
    """`31 | 0` would otherwise read as an absence of structure that is not there."""
    text, _, _ = two_arm_run
    assert "not comparable across columns" in text


def test_the_report_does_not_grade(two_arm_run):
    """No score, no verdict: the human decides which arm is better."""
    text, _, _ = two_arm_run
    lowered = text.lower()
    for word in ("winner", "verdict", "score:", "passed", "failed"):
        assert word not in lowered, f"the report is a reading aid, not a grader: {word!r}"


# --- excerpts ---------------------------------------------------------------


def test_each_arm_is_excerpted_inline(two_arm_run):
    """The difference has to be visible without leaving the report."""
    text, _, _ = two_arm_run
    assert "## Output excerpts" in text
    assert "# Design: a thing" in text
    assert "<pd-doc" in text
    assert text.index("## Output excerpts") < text.index("## Prompt")


def test_excerpt_is_capped_and_says_what_it_left_out(tmp_path):
    run_dir = tmp_path / "runs" / "run-a"
    body = "".join(f"line {i}\n" for i in range(200))
    cell_dir = _cell(run_dir, "WORKTREE", output=body, name="notes.md")
    text = report.write_report(
        run_dir=run_dir, run_id="run-a", skill="demo", arm="WORKTREE", model="m",
        prompt="p", cells=[("WORKTREE", 0, cell_dir)],
    ).read_text()
    assert f"line {report.EXCERPT_LINES - 1}" in text
    assert f"line {report.EXCERPT_LINES}\n" not in text
    assert f"{200 - report.EXCERPT_LINES} more lines" in text


def test_excerpt_fence_outlives_the_fences_inside_it(two_arm_run):
    """A markdown output full of ``` must not break out of its own block."""
    text, _, _ = two_arm_run
    assert "````" in text, "a nested ``` needs a longer outer fence"


def test_binary_output_is_named_but_not_excerpted(tmp_path):
    run_dir = tmp_path / "runs" / "run-a"
    cell_dir = _cell(run_dir, "WORKTREE")
    (cell_dir / "ws" / "out.parquet").write_bytes(b"PAR1\x00\x01\x02binary")
    text = report.write_report(
        run_dir=run_dir, run_id="run-a", skill="demo", arm="WORKTREE", model="m",
        prompt="p", cells=[("WORKTREE", 0, cell_dir)],
    ).read_text()
    assert "`WORKTREE/1/ws/out.parquet`" in text
    assert "not excerpted" in text


def test_empty_workspace_says_so_rather_than_inventing_a_file(tmp_path):
    run_dir = tmp_path / "runs" / "run-a"
    cell_dir = _cell(run_dir, "WORKTREE")
    text = report.write_report(
        run_dir=run_dir, run_id="run-a", skill="demo", arm="WORKTREE", model="m",
        prompt="p", cells=[("WORKTREE", 0, cell_dir)],
    ).read_text()
    assert "no file at `ws/` root" in text


# --- the not-invoked alarm --------------------------------------------------
#
# Both directions, always. A banner that fires on every healthy run and a banner
# that never fires are the same failure with opposite signs: each teaches the
# reader that the row carries no information (`skills-7k7.11`, `skills-7k7.15`).


def _arm_manifest(run_dir, arm, kind):
    """The per-arm record the report reads `kind` out of."""
    arm_dir = run_dir / arm
    arm_dir.mkdir(parents=True, exist_ok=True)
    (arm_dir / arms.MANIFEST_NAME).write_text(
        json.dumps({"run_id": run_dir.name, "arm": arm, "kind": kind, "skill": "demo"})
    )


def _missed(arm, *, failed=(), calls=()):
    """An arm record whose single trial did not invoke."""
    return invocation.ArmInvocation(
        arm=arm,
        skill="demo",
        invoke_mode=invocation.INSTRUCTED,
        invoked=False,
        cells=[
            invocation.CellInvocation(
                trial=1,
                invoked=False,
                registered=False,
                skill_calls=list(calls) or list(failed),
                failed_skill_calls=list(failed),
            )
        ],
    )


def _three_arm_report(tmp_path, worktree_record):
    """`none` (silent baseline), `WORKTREE` (installed), `main` (installed, ran it)."""
    run_dir = tmp_path / "runs" / "run-a"
    cells = []
    for arm, kind, skill_present in (
        ("none", arms.KIND_NONE, False),
        ("WORKTREE", arms.KIND_WORKTREE, True),
        ("main", arms.KIND_REF, True),
    ):
        cells.append(
            (arm, 0, _cell(run_dir, arm, output=MARKDOWN, name="d.md", skill=skill_present))
        )
        _arm_manifest(run_dir, arm, kind)
    return report.write_report(
        run_dir=run_dir, run_id="run-a", skill="demo", arm="none, WORKTREE, main",
        model="m", prompt="p", cells=cells,
        invocations=[
            _missed("none", failed=["demo"]),
            worktree_record,
            _record("main", invoked=True),
        ],
    ).read_text()


def test_a_silent_baseline_alone_raises_no_alarm(tmp_path):
    """The false alarm this fix is for: a textbook healthy with/without run.

    `none` did not invoke because `none` installs nothing. Every other arm did.
    Nothing here is compromised, so nothing may shout.
    """
    text = _three_arm_report(tmp_path, _record("WORKTREE", invoked=True))
    assert report.NOT_INVOKED_HEADING not in text
    assert "This run is not a comparison" not in text
    # Stated, not shouted: the reader still learns the baseline stayed silent.
    assert report.BASELINE_NOT_INVOKED in text
    assert "**NO**" not in text


def test_an_installed_arm_that_stayed_silent_still_shouts(tmp_path):
    """The direction the fix must not break: a real miss, with a healthy arm beside it.

    `WORKTREE` had the skill installed and did not run it. That invalidates the
    `WORKTREE` column even though `main` ran fine, so the banner fires — and
    names `WORKTREE` only, because `none` did exactly what a baseline does.
    """
    text = _three_arm_report(tmp_path, _missed("WORKTREE"))
    assert text.startswith(report.NOT_INVOKED_HEADING)
    banner = text.split("---")[0]
    assert "`WORKTREE` — no `Skill` call for `demo` at all" in banner
    assert "- `none`" not in banner, "the baseline is not blamed for being a baseline"
    assert report.BASELINE_MISS_NOTE in banner
    # `main` ran the skill, so the run *is* a comparison — the old banner said
    # otherwise unconditionally.
    assert "This run is not a comparison" not in text


def test_the_banner_separates_a_refused_call_from_no_call_at_all(tmp_path):
    """"Never asked" and "asked and was refused" are different findings.

    The second says the agent tried and the *install* is what failed; reporting
    it as "the transcript shows no `Skill` call" sends the reader looking for
    the wrong thing.
    """
    text = _three_arm_report(tmp_path, _missed("WORKTREE", failed=["demo"]))
    assert "`WORKTREE` — a `Skill` call for `demo` came back an error" in text
    assert "no `Skill` call for `demo` at all" not in text


def test_the_banner_names_an_unregistered_call_as_its_own_failure(tmp_path):
    """A call that neither errored nor loaded: the skill was not in `init.skills`.

    Reporting that as "no `Skill` call" points the reader at the agent when the
    install is what to look at.
    """
    text = _three_arm_report(tmp_path, _missed("WORKTREE", calls=["demo"]))
    assert "was made, but the skill was not registered in `init.skills`" in text


def test_an_arm_with_no_manifest_is_assumed_installed_and_alarms(tmp_path):
    """Unknown provenance fails loud.

    `kind` is unreadable for a run whose manifest was lost. Treating that as a
    baseline would silence the alarm on exactly the runs we know least about, so
    an unknown arm is assumed to have had the skill.
    """
    run_dir = tmp_path / "runs" / "run-a"
    cell_dir = _cell(run_dir, "WORKTREE", output=MARKDOWN, name="d.md")
    text = report.write_report(
        run_dir=run_dir, run_id="run-a", skill="demo", arm="WORKTREE", model="m",
        prompt="p", cells=[("WORKTREE", 0, cell_dir)],
        invocations=[_missed("WORKTREE")],
    ).read_text()
    assert text.startswith(report.NOT_INVOKED_HEADING)


# --- trials -----------------------------------------------------------------


def test_trials_get_their_own_columns_and_labels(tmp_path):
    run_dir = tmp_path / "runs" / "run-a"
    first = _cell(run_dir, "WORKTREE", trial=1, output=MARKDOWN, name="a.md")
    second = _cell(run_dir, "WORKTREE", trial=2, output=HTML, name="b.html")
    text = report.write_report(
        run_dir=run_dir, run_id="run-a", skill="demo", arm="WORKTREE", model="m",
        prompt="p", cells=[("WORKTREE", 0, first), ("WORKTREE", 0, second)],
        invocations=[_record("WORKTREE", trials=2)], trials=2,
    ).read_text()
    header = next(line for line in text.splitlines() if line.startswith("|  |"))
    assert "WORKTREE · trial 1" in header and "WORKTREE · trial 2" in header


# --- rebuilding over a run that is already on disk --------------------------


def test_rebuild_regenerates_the_report_from_the_run_tree(tmp_path):
    """The report is a view: improving it must not require billing a new run."""
    runs = tmp_path / "runs"
    run_dir = runs / "run-a"
    none_cell = _cell(run_dir, "none", output=MARKDOWN, name="design.md", skill=False)
    worktree_cell = _cell(run_dir, "WORKTREE", output=HTML, name="design.html")
    manifest.write(
        run_dir=run_dir,
        run_id="run-a",
        skill="demo",
        arm_names=[("none", "none"), ("WORKTREE", "WORKTREE")],
        prompt="write a design doc",
        model="m",
        runner=runners.LIVE,
        invoke=invocation.INSTRUCTED,
        trials=1,
        scenario="inline",
        started_at=manifest.now(),
    )
    for arm, cell_dir in (("none", none_cell), ("WORKTREE", worktree_cell)):
        (run_dir / arm / invocation.INVOCATION_NAME).write_text(
            json.dumps(_record(arm).to_dict())
        )

    path = report.rebuild(run_dir)
    text = path.read_text()

    assert path == run_dir / report.REPORT_NAME
    assert report.REBUILT_NOTE in text, "a rebuilt report must say the exits were inferred"
    assert "write a design doc" in text
    assert "`none/1/ws/design.md`" in text and "`WORKTREE/1/ws/design.html`" in text
    # The exit code came back off the transcript's result envelope.
    row = next(line for line in text.splitlines() if line.startswith("| agent exit"))
    assert [c.strip() for c in row.split("|")[2:-1]] == ["0", "0"]
    assert report.NO_SKILL_INSTALLED in text


def test_rebuild_reports_a_failed_transcript_as_a_nonzero_exit(tmp_path):
    runs = tmp_path / "runs"
    run_dir = runs / "run-a"
    cell_dir = _cell(run_dir, "WORKTREE", output=MARKDOWN, name="design.md")
    (cell_dir / "stream.jsonl").write_text(
        json.dumps({"type": "result", "subtype": "error", "is_error": True}) + "\n"
    )
    manifest.write(
        run_dir=run_dir, run_id="run-a", skill="demo",
        arm_names=[("WORKTREE", "WORKTREE")], prompt="p", model="m",
        runner=runners.LIVE, invoke=invocation.INSTRUCTED, trials=1,
        scenario="inline", started_at=manifest.now(),
    )
    text = report.rebuild(run_dir).read_text()
    row = next(line for line in text.splitlines() if line.startswith("| agent exit"))
    assert [c.strip() for c in row.split("|")[2:-1]] == ["1"]


# --- outputs diffed against a scenario seed ----------------------------------


def test_outputs_are_diffed_against_the_seed_when_one_is_given(tmp_path):
    """An epic planner writes into `ws/<repo>/docs/epics/`; a root-only scan
    says "no output". With the seed known, the answer is exact: new or
    changed files anywhere in the tree, and nothing that was merely copied in."""
    seed = tmp_path / "seed"
    (seed / "repo" / "docs").mkdir(parents=True)
    (seed / "repo" / "README.md").write_text("fixture\n")
    (seed / "repo" / "docs" / "old.md").write_text("old\n")

    run_dir = tmp_path / "runs" / "run-a"
    cell_dir = _cell(run_dir, "WORKTREE")
    ws = cell_dir / "ws"
    (ws / "repo" / "docs").mkdir(parents=True)
    (ws / "repo" / "README.md").write_text("fixture\n")           # untouched copy
    (ws / "repo" / "docs" / "old.md").write_text("old, edited\n")  # changed
    (ws / "repo" / "docs" / "epic-001.html").write_text("<pd-doc></pd-doc>\n")  # new
    (ws / "repo" / ".cache" / "x").parent.mkdir()
    (ws / "repo" / ".cache" / "x").write_text("ignored\n")

    outputs = report.workspace_outputs(cell_dir, run_dir, seed)
    assert {o.path.name for o in outputs} == {"old.md", "epic-001.html"}

    text = report.write_report(
        run_dir=run_dir, run_id="run-a", skill="demo", arm="WORKTREE", model="m",
        prompt="p", cells=[("WORKTREE", 0, cell_dir)], seed=seed,
    ).read_text()
    assert "epic-001.html" in text
    assert "README.md" not in text


def test_a_seeded_run_with_no_changes_says_so_in_seed_terms(tmp_path):
    seed = tmp_path / "seed"
    (seed / "repo").mkdir(parents=True)
    (seed / "repo" / "README.md").write_text("fixture\n")
    run_dir = tmp_path / "runs" / "run-a"
    cell_dir = _cell(run_dir, "WORKTREE")
    (cell_dir / "ws" / "repo").mkdir(parents=True)
    (cell_dir / "ws" / "repo" / "README.md").write_text("fixture\n")
    text = report.write_report(
        run_dir=run_dir, run_id="run-a", skill="demo", arm="WORKTREE", model="m",
        prompt="p", cells=[("WORKTREE", 0, cell_dir)], seed=seed,
    ).read_text()
    assert "no file new or changed against the seed" in text


def test_without_a_seed_the_root_heuristic_is_unchanged(tmp_path):
    run_dir = tmp_path / "runs" / "run-a"
    cell_dir = _cell(run_dir, "WORKTREE")
    (cell_dir / "ws" / "nested").mkdir()
    (cell_dir / "ws" / "nested" / "deep.md").write_text("x\n")
    assert report.workspace_outputs(cell_dir, run_dir) == []
    assert report.workspace_outputs(cell_dir, run_dir, None) == []
