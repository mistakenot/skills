"""Tests for `REPORT.md` as a *reading aid*.

The harness has no grader: judgement is a human reading two outputs side by
side, and this file is the entry point to that reading. So its usability is the
behaviour under test — one table with the arms as columns, an excerpt of what
each arm produced, and never a path that is not on disk.
"""

import json

import pytest

from evals import invocation, manifest, paths, report, runners

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
