"""Axial coding: taxonomy validation, labels, and the per-version report."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import coding

TAX = {"version": 1, "modes": [
    {"id": "vague-verification", "name": "Vague verification", "definition": "ACs without a runnable check"},
    {"id": "ignores-existing-code", "name": "Ignores existing code", "definition": "re-invents what exists"},
]}


def _write_tax(data: Path, tax: dict) -> None:
    data.mkdir(parents=True, exist_ok=True)
    (data / "taxonomy.json").write_text(json.dumps(tax))


def test_no_taxonomy_is_none(tmp_path: Path) -> None:
    assert coding.load_taxonomy(tmp_path) is None


@pytest.mark.parametrize("bad", [
    {"version": 0, "modes": TAX["modes"]},
    {"version": 1, "modes": []},
    {"version": 1, "modes": [{"id": "Bad Id", "name": "n", "definition": "d"}]},
    {"version": 1, "modes": [TAX["modes"][0], TAX["modes"][0]]},
    {"version": 1, "modes": [{"id": "no-def", "name": "n"}]},
])
def test_taxonomy_validation(tmp_path: Path, bad: dict) -> None:
    _write_tax(tmp_path, bad)
    with pytest.raises(coding.CodingError):
        coding.load_taxonomy(tmp_path)


def test_label_refuses_unknown_plan_or_mode() -> None:
    with pytest.raises(coding.CodingError, match="unknown plan"):
        coding.make_label("zzz", "vague-verification", True, TAX, {"aaa"}, "c")
    with pytest.raises(coding.CodingError, match="unknown mode"):
        coding.make_label("aaa", "nope", True, TAX, {"aaa"}, "c")


def test_latest_label_wins_within_a_version() -> None:
    labels = [
        coding.make_label("a", "vague-verification", True, TAX, {"a"}, "c"),
        coding.make_label("a", "vague-verification", False, TAX, {"a"}, "c"),
        {**coding.make_label("a", "ignores-existing-code", True, TAX, {"a"}, "c"), "taxonomy_version": 0},
    ]
    cur = coding.current_labels(labels, 1)
    assert cur == {("a", "vague-verification"): False}  # the v0 label is not counted


def test_report_groups_by_skills_version() -> None:
    rows = [
        {"plan_id": "p1", "skills_sha": "a" * 40, "fixture_id": "f1", "ingested_at": "1"},
        {"plan_id": "p2", "skills_sha": "a" * 40, "fixture_id": "f2", "ingested_at": "2"},
        {"plan_id": "p3", "skills_sha": "b" * 40, "fixture_id": "f1", "ingested_at": "3"},
    ]
    plans = {r["plan_id"] for r in rows}
    verdicts = {"p1": {"verdict": "fail"}, "p3": {"verdict": "pass"}}
    labels = [
        coding.make_label("p1", "vague-verification", True, TAX, plans, "c"),
        coding.make_label("p2", "vague-verification", True, TAX, plans, "c"),
        coding.make_label("p3", "vague-verification", False, TAX, plans, "c"),
    ]
    rep = coding.report(rows, verdicts, TAX, labels)
    a, b = rep["groups"][f"skills@{'a' * 12}"], rep["groups"][f"skills@{'b' * 12}"]
    assert (a["plans"], a["reviewed"], a["fail"]) == (2, 1, 1)
    assert a["modes"]["vague-verification"] == {"present": 2, "labelled": 2}
    assert b["modes"]["vague-verification"] == {"present": 0, "labelled": 1}
    # Unlabelled is not "absent".
    assert a["modes"]["ignores-existing-code"] == {"present": 0, "labelled": 0}
    text = coding.render_report(rep, {m["id"]: m["name"] for m in TAX["modes"]})
    assert "2/2" in text and "0/1" in text and "Vague verification" in text
    by_fx = coding.report(rows, verdicts, TAX, labels, by="fixture")
    assert set(by_fx["groups"]) == {"f1", "f2"}


def test_identical_documents_from_two_arms_count_once_per_arm() -> None:
    # Baseline and candidate wrote byte-identical plans (same plan_id): each arm
    # keeps its sample, and the one label on the document counts for both.
    rows = [
        {"plan_id": "p1", "skills_sha": "a" * 40, "run": "r1", "trial": "t", "task_dir": "d"},
        {"plan_id": "p1", "skills_sha": "b" * 40, "run": "r2", "trial": "t", "task_dir": "d"},
    ]
    labels = [coding.make_label("p1", "vague-verification", True, TAX, {"p1"}, "c")]
    rep = coding.report(rows, {"p1": {"verdict": "fail"}}, TAX, labels)
    for sha in ("a", "b"):
        g = rep["groups"][f"skills@{sha * 12}"]
        assert g["plans"] == 1 and g["fail"] == 1
        assert g["modes"]["vague-verification"] == {"present": 1, "labelled": 1}
