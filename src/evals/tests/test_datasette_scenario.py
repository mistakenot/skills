"""The bundled datasette scenario, fetched for real.

Everything else about scenarios is tested offline. This one performs the actual
fetch, because the failure modes worth catching here are the ones a stand-in
cannot have: the sha no longer resolving, the tarball layout changing, or the
fixture quietly growing a `CLAUDE.md` that the clean room would load as project
instructions.

Skipped when the network is unavailable, and only when: a silently-passing
network test is worse than no network test.
"""

import shutil
import socket

import pytest

from evals import canaries, scenarios

SCENARIO = "datasette-parquet-renderer"
SHA = "bdc973174096cae350ddaa733a10ed8b3ffd970b"


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


def test_the_pinned_fetch_lands_a_usable_checkout(prepared):
    _, _, seed = prepared
    repo = seed / "datasette"

    assert (repo / "datasette" / "hookspecs.py").is_file()
    # The two files the prompt points the agent at.
    assert "register_output_renderer" in (repo / "datasette" / "hookspecs.py").read_text()
    assert (repo / "datasette" / "blob_renderer.py").is_file()


def test_the_task_is_genuinely_absent_at_this_sha(prepared):
    """If upstream had already done it, the scenario would measure nothing.

    This is the reason the sha is pinned rather than a branch, asserted rather
    than assumed — a floating fetch would eventually make this fail, which is
    exactly the contamination the pin exists to prevent.
    """
    _, _, seed = prepared
    hits = [
        path
        for path in (seed / "datasette").rglob("*")
        if path.is_file() and b"parquet" in path.read_bytes().lower()
    ]
    assert not hits, f"the checkout already mentions parquet: {hits[:5]}"


def test_the_fixture_carries_no_project_context_of_its_own(prepared):
    """A `CLAUDE.md` in the fetched tree would be loaded as instructions.

    Canary 4 tolerates project context *inside* the workspace by design, so
    nothing downstream would catch this; it has to be caught here.
    """
    _, _, seed = prepared
    for name in canaries.PROJECT_CONTEXT_NAMES:
        found = [p for p in seed.rglob(name)]
        assert not found, f"the fixture ships {name}: {found}"


def test_the_workspace_root_is_not_a_git_repo(prepared):
    """Canary 2 rejects a cell whose workspace is a repo — so the tarball goes
    into a subdirectory, and the tree has no `.git` at all."""
    _, _, seed = prepared
    assert not (seed / ".git").exists()
    assert not list(seed.rglob(".git"))


def test_a_second_preparation_does_not_fetch_again(prepared, monkeypatch):
    """The acceptance criterion, against the real fetch.

    Two independent proofs, neither of them a stopwatch: `setup.sh` is not
    executed at all (a spy that fails if it is), and the marker the first fetch
    wrote is byte-for-byte and mtime-for-mtime unchanged.
    """
    scenario, cache, seed = prepared
    marker = scenarios.entry_dir(scenario, cache) / scenarios.MARKER_NAME
    before = marker.read_text(), marker.stat().st_mtime_ns

    def refetched(*_args, **_kwargs):
        raise AssertionError("setup.sh ran a second time — the cache missed")

    monkeypatch.setattr(scenarios, "_run_setup", refetched)
    again = scenarios.prepare(scenario, cache_dir=cache)

    assert again == seed
    assert (marker.read_text(), marker.stat().st_mtime_ns) == before
    assert (again / "datasette" / "datasette" / "hookspecs.py").is_file()


def test_the_scenario_pins_this_exact_sha():
    """Offline. The pin is the scenario's contract with everything downstream."""
    scenario = scenarios.resolve(SCENARIO)
    assert SHA in scenario.setup.read_text()
    scenarios.check_pins(scenario.setup.read_text(), where=scenario.setup)
