"""Tests for strip-closed-threads.sh — the request-*-review cleanup step.

After resolution, regular docs (README, guides, plain HTML) lose their RESOLVED
and REJECTED threads; plan files (under docs/tasks/, or pd-* HTML) keep them as
the decision log. UNRESOLVED threads and .review.md sidecars are never touched.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SKILLS = ["request-codex-review", "request-claude-review", "request-grok-review", "request-council-review"]

RESOLVED = """<!-- RESOLVED(P1): Wrong class name
REVIEW: RateLimiter does not exist.
AUTHOR: Now TokenBucket.
-->"""
REJECTED = """<!-- REJECTED(P3): Style nit
REVIEW: Prefer shorter heading.
AUTHOR: Heading is fine.
-->"""
UNRESOLVED = """<!-- UNRESOLVED(P2): Needs a decision
REVIEW: Package or PYTHONPATH?
AUTHOR: Asking the user.
-->"""


def strip(skill: str, tmp_path: Path, files: list[Path]) -> str:
    scope = tmp_path / "scope.txt"
    scope.write_text("".join(f"{f}\n" for f in files))
    script = REPO / "skills" / skill / "scripts" / "strip-closed-threads.sh"
    out = subprocess.run(["bash", str(script), str(scope)], capture_output=True, text=True, cwd=tmp_path)
    assert out.returncode == 0, out.stderr
    return out.stdout


@pytest.mark.parametrize("skill", SKILLS)
def test_regular_doc_loses_closed_threads_and_keeps_unresolved(skill: str, tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(
        f"{RESOLVED}\n\n# Title\n\nIntro.\n\n{RESOLVED}\n\n{REJECTED}\n\nBody.\n\n"
        f"{UNRESOLVED}\n\nMore.\n\n{RESOLVED}\n"
    )
    out = strip(skill, tmp_path, [readme])
    assert "removed 4 closed thread(s)" in out
    assert readme.read_text() == f"# Title\n\nIntro.\n\nBody.\n\n{UNRESOLVED}\n\nMore.\n"


@pytest.mark.parametrize("skill", SKILLS)
def test_plain_html_is_a_regular_doc(skill: str, tmp_path: Path) -> None:
    page = tmp_path / "index.html"
    page.write_text(f"<body>\n<p>a</p>\n\n{RESOLVED}\n\n<p>b</p>\n</body>\n")
    strip(skill, tmp_path, [page])
    assert page.read_text() == "<body>\n<p>a</p>\n\n<p>b</p>\n</body>\n"


@pytest.mark.parametrize("skill", SKILLS)
def test_plan_files_and_sidecars_are_kept(skill: str, tmp_path: Path) -> None:
    task = tmp_path / "docs" / "tasks" / "042-x"
    task.mkdir(parents=True)
    plan_md = task / "plan.md"
    pd_doc = tmp_path / "design.html"
    sidecar = tmp_path / "client.py.review.md"
    plan_md.write_text(f"# Plan\n\n{RESOLVED}\n")
    pd_doc.write_text(f"<pd-doc>\n{RESOLVED}\n</pd-doc>\n")
    sidecar.write_text(f"# Review: client.py\n\n{RESOLVED}\n")
    # Relative and absolute paths into docs/tasks/ are both recognised.
    files = [Path("docs/tasks/042-x/plan.md"), plan_md, pd_doc, sidecar, tmp_path / "missing.md"]
    before = {f: f.read_text() for f in (plan_md, pd_doc, sidecar)}
    assert strip(skill, tmp_path, files) == ""
    assert {f: f.read_text() for f in before} == before


@pytest.mark.parametrize("skill", SKILLS)
def test_doc_without_closed_threads_is_untouched(skill: str, tmp_path: Path) -> None:
    doc = tmp_path / "guide.md"
    text = f"# Guide\n\n\n\nKeep   spacing.\n\n{UNRESOLVED}"  # odd spacing, no final newline
    doc.write_text(text)
    assert strip(skill, tmp_path, [doc]) == ""
    assert doc.read_text() == text
