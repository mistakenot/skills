"""Regression test for the comment/author-reply counting in the request-*-review skills.

The skills gate on "did the reviewer leave any comments?" and "did resolve-comments
run?" by counting markers in the task folder. The original pipeline was
``rg -c ... | awk -F: '{s+=$2}'``, which silently returns 0 whenever the glob
matches a single file — ``rg -c`` prints a bare count (no ``path:`` prefix) for one
file — and every HTML-era task folder has exactly one ``plan.html``. So a
successful review was reported as "no comments found" and resolution never ran.

This test lifts the exact counting lines out of each compiled skill and runs them
against fixture folders with one and with two doc files.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SKILLS = [
    "request-codex-review",
    "request-claude-review",
    "request-grok-review",
    "request-council-review",
]
VARS = ("MD_COUNT", "HTML_COUNT", "MD_REPLIES", "HTML_REPLIES")
LINE_RE = re.compile(r"^(?:%s)=\$\(.*\)$" % "|".join(VARS), re.M)

HTML_DOC = """<html><body>
<pd-tabs><pd-tab title="Requirements"><p>x</p></pd-tab></pd-tabs>
<pd-thread id="t1" priority="P1"><pd-comment by="reviewer">a</pd-comment>
<pd-comment by="author">reply</pd-comment></pd-thread>
<pd-thread id="t2" priority="P2"><pd-comment by="reviewer">b</pd-comment></pd-thread>
</body></html>
"""
MD_DOC = """# Requirements
<!-- UNRESOLVED(P1): thing -->
<!-- AUTHOR: done -->
<!-- RESOLVED(P2): other -->
"""


def counting_lines(skill: str) -> list[str]:
    src = (REPO / "skills" / skill / "SKILL.md").read_text()
    lines = LINE_RE.findall(src)
    assert len(lines) == 4, f"{skill}: expected 4 counting lines, found {len(lines)}"
    return lines


def run_counts(skill: str, task_dir: Path) -> dict[str, int]:
    script = f'TASK_DIR="{task_dir}"\n' + "\n".join(counting_lines(skill)) + "\n"
    script += "\n".join(f'echo {v}=${v}' for v in VARS) + "\n"
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True)
    return {k: int(v) for k, v in (l.split("=") for l in out.stdout.split())}


@pytest.mark.parametrize("skill", SKILLS)
def test_single_html_doc_is_counted(skill: str, tmp_path: Path) -> None:
    (tmp_path / "plan.html").write_text(HTML_DOC)
    (tmp_path / "context.md").write_text("# context\n")
    assert run_counts(skill, tmp_path) == {
        "MD_COUNT": 0, "HTML_COUNT": 2, "MD_REPLIES": 0, "HTML_REPLIES": 1,
    }


@pytest.mark.parametrize("skill", SKILLS)
def test_single_md_doc_is_counted(skill: str, tmp_path: Path) -> None:
    (tmp_path / "requirements.md").write_text(MD_DOC)
    assert run_counts(skill, tmp_path) == {
        "MD_COUNT": 2, "HTML_COUNT": 0, "MD_REPLIES": 1, "HTML_REPLIES": 0,
    }


@pytest.mark.parametrize("skill", SKILLS)
def test_multiple_docs_are_summed(skill: str, tmp_path: Path) -> None:
    (tmp_path / "requirements.md").write_text(MD_DOC)
    (tmp_path / "solution.md").write_text(MD_DOC)
    (tmp_path / "plan.html").write_text(HTML_DOC)
    (tmp_path / "epic.html").write_text(HTML_DOC)
    assert run_counts(skill, tmp_path) == {
        "MD_COUNT": 4, "HTML_COUNT": 4, "MD_REPLIES": 2, "HTML_REPLIES": 2,
    }


@pytest.mark.parametrize("skill", SKILLS)
def test_empty_folder_counts_zero(skill: str, tmp_path: Path) -> None:
    assert run_counts(skill, tmp_path) == {v: 0 for v in VARS}
