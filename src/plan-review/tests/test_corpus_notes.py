"""Corpus ingest/snapshot and the append-only notes log."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import corpus
import notes


def test_ingest_one_entry_per_produced_plan(harbor_run: Path) -> None:
    [e] = corpus.ingest_run(harbor_run)
    assert len(e["plan_id"]) == 12
    assert e["fixture_id"] == "fx-1"
    assert e["skills_sha"].startswith("abc")
    assert e["target"] == "https://example.com/repo.git"
    assert e["task_dir"] == "docs/tasks/001-thing"
    assert e["cost_usd"] == 1.25
    assert e["checks"]["questions"] == 1
    assert e["checks"]["open_questions"] == 1
    assert e["checks"]["codex_ran"] is False


def test_ingest_flags_a_codex_review(harbor_run: Path) -> None:
    trial = harbor_run / "fx-1__trial1"
    result = json.loads((trial / "peval-result.json").read_text())
    result["turns"][0]["skill_calls"].append("request-codex-review")
    (trial / "peval-result.json").write_text(json.dumps(result))
    [e] = corpus.ingest_run(harbor_run)
    assert e["checks"]["codex_ran"] is True


def test_ingest_rejects_a_non_run(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="peval.json"):
        corpus.ingest_run(tmp_path)


def test_add_is_idempotent(harbor_run: Path, tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    entries = corpus.ingest_run(harbor_run)
    assert len(corpus.add(entries, runs)) == 1
    assert corpus.add(entries, runs) == []
    assert list(corpus.load(runs, None)) == [entries[0]["plan_id"]]


def test_snapshot_makes_a_plan_outlive_its_run(harbor_run: Path, tmp_path: Path) -> None:
    runs, data = tmp_path / "runs", tmp_path / "data"
    [e] = corpus.ingest_run(harbor_run)
    corpus.add([e], runs)
    snap = corpus.snapshot(e, data)
    d = data / "plans" / e["plan_id"]
    assert (d / "plan.html").read_bytes() == Path(e["plan_path"]).read_bytes()
    assert (d / "context.md").is_file()
    assert "snapshot_at" in snap
    # Remove the run and the local corpus: the snapshot alone keeps it listed.
    import shutil
    shutil.rmtree(harbor_run)
    (runs / "corpus.jsonl").unlink()
    loaded = corpus.load(runs, data)
    assert corpus.resolve(loaded[e["plan_id"]]["plan_path"]).read_text().startswith("<!doctype")
    # A second snapshot is a no-op that returns the stored meta.
    assert corpus.snapshot(e, data)["snapshot_at"] == snap["snapshot_at"]


def test_display_prompt_strips_the_stop_line() -> None:
    assert corpus.display_prompt(f"/new-task-quick x\n\n{corpus.STOP_SUFFIX}") == "/new-task-quick x"
    assert corpus.display_prompt("plain") == "plain"


# --- notes ---------------------------------------------------------------------

PIDS = {"aaaaaaaaaaaa"}


def _create(**kw) -> dict:
    ev = {"event": "note.create", "plan_id": "aaaaaaaaaaaa", "tab": "Plan",
          "quote": "retry webhooks", "prefix": "Phase 1: ", "suffix": " with", "text": "vague"}
    ev.update(kw)
    return notes.validate(ev, PIDS, "charlie")


def test_validate_stamps_and_cleans() -> None:
    ev = _create(extra="dropped")
    assert ev["reviewer"] == "charlie" and ev["ts"] and ev["id"]
    assert "extra" not in ev


@pytest.mark.parametrize("bad", [
    {"event": "nope"},
    {"event": "note.create", "plan_id": "aaaaaaaaaaaa", "quote": "q", "prefix": "", "suffix": "", "text": " "},
    {"event": "note.create", "plan_id": "bbbbbbbbbbbb", "quote": "q", "prefix": "", "suffix": "", "text": "t"},
    {"event": "verdict", "plan_id": "aaaaaaaaaaaa", "verdict": "meh", "text": ""},
    {"event": "note.update", "text": "t"},
    "not an object",
])
def test_validate_refuses(bad) -> None:
    with pytest.raises(notes.EventError):
        notes.validate(bad, PIDS, "charlie")


def test_fold_create_update_delete_verdict(tmp_path: Path) -> None:
    log = tmp_path / "notes.jsonl"
    a = _create(text="first")
    b = _create(text="second")
    for ev in (
        a, b,
        notes.validate({"event": "note.update", "id": a["id"], "text": "first, edited"}, PIDS, "charlie"),
        notes.validate({"event": "note.delete", "id": b["id"]}, PIDS, "charlie"),
        notes.validate({"event": "verdict", "plan_id": "aaaaaaaaaaaa", "verdict": "fail", "text": "x"}, PIDS, "charlie"),
        notes.validate({"event": "verdict", "plan_id": "aaaaaaaaaaaa", "verdict": "defer", "text": "y"}, PIDS, "charlie"),
    ):
        notes.append(ev, log)
    assert len(log.read_text().splitlines()) == 6  # nothing is ever rewritten
    state = notes.fold(notes.load(log))
    assert [n["text"] for n in state["notes"]] == ["first, edited"]
    assert state["verdicts"]["aaaaaaaaaaaa"]["verdict"] == "defer"
