"""The bundled auto-stack epic scenario, fetched for real.

Like the datasette test, this performs the actual fetch: the failure modes
worth catching are the ones a stand-in cannot have — the sha no longer
resolving, the tarball layout changing, the checkout's own agent skills
surviving the strip and being discovered inside the workspace, or the epic
answer leaking into the fixture.
"""

import shutil
import socket

import pytest

from evals import scenarios

SCENARIO = "auto-stack-multi-host-epic"
SHA = "3f234f0b132bf9704dc158a83603e715d897aaae"


def _online() -> bool:
    try:
        socket.create_connection(("codeload.github.com", 443), timeout=5).close()
        return True
    except OSError:
        return False


@pytest.fixture(scope="module")
def prepared(tmp_path_factory):
    if shutil.which("curl") is None:
        pytest.skip("curl is not installed")
    if not _online():
        pytest.skip("codeload.github.com is unreachable; the real fetch cannot run")
    scenario = scenarios.resolve(SCENARIO)
    cache = tmp_path_factory.mktemp("cache")
    return scenario, cache, scenarios.prepare(scenario, cache_dir=cache)


def test_the_pinned_fetch_lands_the_planning_inputs(prepared):
    _, _, seed = prepared
    repo = seed / "auto-stack"
    assert (repo / "docs" / "auto-bus-spec.md").is_file()
    assert (repo / "auto-ui").is_dir()
    assert (repo / "auto-watch").is_dir()
    # The prior epics the planner numbers after.
    assert (repo / "docs" / "epics" / "002-planning-docs-dashboard.md").is_file()


def test_the_answer_is_genuinely_absent_at_this_sha(prepared):
    """The epic, and every task that implemented it, post-date the pin."""
    _, _, seed = prepared
    repo = seed / "auto-stack"
    assert not list((repo / "docs" / "epics").glob("*003*"))
    assert not list((repo / "docs" / "epics").glob("*multi-host*"))
    tasks = {p.name[:3] for p in (repo / "docs" / "tasks").iterdir() if p.is_dir()}
    assert max(tasks) <= "026", f"tasks past the pin are present: {sorted(tasks)[-3:]}"


def test_the_checkouts_own_skills_are_stripped(prepared):
    """Skills inside the workspace are discovered as project skills — canary 3
    only checks the config dir, so this has to be caught here."""
    _, _, seed = prepared
    # At every depth: sub-projects ship their own .claude/. Bare `skills/`
    # source folders are fine — Claude Code does not discover those.
    assert not [p for p in seed.rglob(".claude")]
    assert not [p for p in seed.rglob(".agents")]


def test_the_ask_user_question_rule_is_stripped(prepared):
    _, _, seed = prepared
    for name in ("CLAUDE.md", "AGENTS.md"):
        text = (seed / "auto-stack" / name).read_text()
        assert "## Agent Interaction Rules" not in text
        assert "ALWAYS use the `AskUserQuestion` tool" not in text
        assert "## Sub-Projects" in text, "stripping removed more than the one section"


def test_the_workspace_root_is_not_a_git_repo(prepared):
    _, _, seed = prepared
    assert not (seed / ".git").exists()
    assert not list(seed.rglob(".git"))


def test_the_scenario_pins_this_exact_sha():
    scenario = scenarios.resolve(SCENARIO)
    assert SHA in scenario.setup.read_text()
    scenarios.check_pins(scenario.setup.read_text(), where=scenario.setup)
