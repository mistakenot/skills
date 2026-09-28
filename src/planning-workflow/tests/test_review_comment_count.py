"""Regression tests for target resolution and comment counting in the request-*-review skills.

The skills gate on "did the reviewer leave any comments?" and "did resolve-comments
run?" by counting markers in every comment sink. The original pipeline was
``rg -c ... | awk -F: '{s+=$2}'``, which silently returns 0 whenever the glob
matches a single file — ``rg -c`` prints a bare count (no ``path:`` prefix) for one
file — and every HTML-era task folder has exactly one ``plan.html``. So a
successful review was reported as "no comments found" and resolution never ran.

Since the skills also accept arbitrary files, a Step 1 block resolves the target
(task mode vs file mode) into a list of sinks: inline docs, plus a
``<file>.review.md`` sidecar for every non-markdown/HTML file. These tests lift
that block and the exact counting lines out of each compiled skill and run them
against fixture repos.
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
SCOPE_RE = re.compile(r"### Step 1: Resolve the Targets\n\n```bash\n(.*?)\n```", re.S)

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


def skill_source(skill: str) -> str:
    return (REPO / "skills" / skill / "SKILL.md").read_text()


def counting_lines(skill: str) -> list[str]:
    lines = LINE_RE.findall(skill_source(skill))
    assert len(lines) == 4, f"{skill}: expected 4 counting lines, found {len(lines)}"
    return lines


def run_counts(skill: str, sinks: list[Path], tmp_path: Path) -> dict[str, int]:
    scope = tmp_path / "scope.txt"
    scope.write_text("".join(f"{s}\n" for s in sinks))
    script = f'mapfile -t SINKS < "{scope}"\n' + "\n".join(counting_lines(skill)) + "\n"
    script += "\n".join(f'echo {v}=${v}' for v in VARS) + "\n"
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True)
    return {k: int(v) for k, v in (l.split("=") for l in out.stdout.split())}


def run_scope(skill: str, repo: Path, args: str) -> dict[str, str | list[str]]:
    """Run the skill's Step 1 block in `repo` with ARGS=(<args>); return its variables."""
    match = SCOPE_RE.search(skill_source(skill))
    assert match, f"{skill}: Step 1 target-resolution block not found"
    block = (match.group(1)
             .replace("<ABSOLUTE_REPO_ROOT>", str(repo))
             .replace("ARGS=(<TARGET> ...)", f"ARGS=({args})"))
    block += '\necho "SINKS=$(IFS=,; echo "${SINKS[*]}")"\necho "REVIEW_ARGS=$REVIEW_ARGS"\n'
    out = subprocess.run(["bash", "-c", block], capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    got: dict[str, str | list[str]] = {}
    for line in out.stdout.splitlines():
        if line.startswith("mode="):
            got.update(kv.split("=", 1) for kv in line.split()[:2])
        elif line.startswith(("SINKS=", "REVIEW_ARGS=")):
            key, _, value = line.partition("=")
            got[key] = value.split(",") if key == "SINKS" and value else value
    return got


# --- counting ---------------------------------------------------------------


@pytest.mark.parametrize("skill", SKILLS)
def test_single_html_doc_is_counted(skill: str, tmp_path: Path) -> None:
    (tmp_path / "plan.html").write_text(HTML_DOC)
    (tmp_path / "context.md").write_text("# context\n")
    assert run_counts(skill, [tmp_path / "plan.html", tmp_path / "context.md"], tmp_path) == {
        "MD_COUNT": 0, "HTML_COUNT": 2, "MD_REPLIES": 0, "HTML_REPLIES": 1,
    }


@pytest.mark.parametrize("skill", SKILLS)
def test_single_md_doc_is_counted(skill: str, tmp_path: Path) -> None:
    (tmp_path / "requirements.md").write_text(MD_DOC)
    assert run_counts(skill, [tmp_path / "requirements.md"], tmp_path) == {
        "MD_COUNT": 2, "HTML_COUNT": 0, "MD_REPLIES": 1, "HTML_REPLIES": 0,
    }


@pytest.mark.parametrize("skill", SKILLS)
def test_multiple_docs_are_summed(skill: str, tmp_path: Path) -> None:
    names = ["requirements.md", "solution.md", "plan.html", "epic.html"]
    for n in names:
        (tmp_path / n).write_text(MD_DOC if n.endswith(".md") else HTML_DOC)
    assert run_counts(skill, [tmp_path / n for n in names], tmp_path) == {
        "MD_COUNT": 4, "HTML_COUNT": 4, "MD_REPLIES": 2, "HTML_REPLIES": 2,
    }


@pytest.mark.parametrize("skill", SKILLS)
def test_sidecars_counted_and_missing_sidecars_ignored(skill: str, tmp_path: Path) -> None:
    (tmp_path / "client.py.review.md").write_text(MD_DOC)
    sinks = [tmp_path / "client.py.review.md", tmp_path / "untouched.py.review.md"]
    assert run_counts(skill, sinks, tmp_path) == {
        "MD_COUNT": 2, "HTML_COUNT": 0, "MD_REPLIES": 1, "HTML_REPLIES": 0,
    }


@pytest.mark.parametrize("skill", SKILLS)
def test_no_threads_counts_zero(skill: str, tmp_path: Path) -> None:
    (tmp_path / "plan.html").write_text("<html></html>")
    assert run_counts(skill, [tmp_path / "plan.html"], tmp_path) == {v: 0 for v in VARS}


# --- target resolution ------------------------------------------------------


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    task = tmp_path / "docs" / "tasks" / "042-add-team-settings"
    task.mkdir(parents=True)
    (task / "plan.html").write_text(HTML_DOC)
    (task / "context.md").write_text("# context\n")
    src = tmp_path / "src"
    src.mkdir()
    (src / "client.py").write_text("x = 1\n")
    (src / "README.md").write_text("# readme\n")
    (src / "old.py.review.md").write_text(MD_DOC)
    return tmp_path


@pytest.mark.parametrize("skill", SKILLS)
@pytest.mark.parametrize("arg", ["042", "042-add-team-settings", "docs/tasks/042-add-team-settings/"])
def test_task_id_or_folder_selects_task_mode(skill: str, repo: Path, arg: str) -> None:
    got = run_scope(skill, repo, arg)
    task = repo / "docs" / "tasks" / "042-add-team-settings"
    assert got["mode"] == "task"
    assert got["REVIEW_ARGS"] == "042-add-team-settings"
    assert sorted(got["SINKS"]) == sorted([str(task / "context.md"), str(task / "plan.html")])


@pytest.mark.parametrize("skill", SKILLS)
def test_files_get_inline_or_sidecar_sinks(skill: str, repo: Path) -> None:
    got = run_scope(skill, repo, "src/client.py src/README.md")
    assert got["mode"] == "files"
    assert got["SINKS"] == ["src/client.py.review.md", "src/README.md"]
    assert got["REVIEW_ARGS"] == "src/client.py src/README.md"


@pytest.mark.parametrize("skill", SKILLS)
def test_directory_expands_and_skips_existing_sidecars(skill: str, repo: Path) -> None:
    got = run_scope(skill, repo, "src")
    assert got["mode"] == "files"
    assert sorted(got["SINKS"]) == ["src/README.md", "src/client.py.review.md"]


@pytest.mark.parametrize("skill", SKILLS)
def test_unknown_task_id_fails(skill: str, repo: Path) -> None:
    match = SCOPE_RE.search(skill_source(skill))
    block = match.group(1).replace("<ABSOLUTE_REPO_ROOT>", str(repo)).replace("ARGS=(<TARGET> ...)", "ARGS=(999)")
    out = subprocess.run(["bash", "-c", block], capture_output=True, text=True)
    assert out.returncode != 0 and "no task folder found for ID 999" in out.stdout
