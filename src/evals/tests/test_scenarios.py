"""Scenario directories, the pin check, and the clone cache.

Three things are being defended here:

  * a scenario directory parses, its `setup.sh` runs with the workspace as cwd,
    and its `fixture/` lands where the agent will see it;
  * a *second* trial does not fetch again — proved by a marker the fetch writes
    and reuse must not rewrite, never by timing;
  * a `setup.sh` that names a branch fails, rather than being caught by review.

The fetch itself is stood in for by a script that writes a file and appends to
a counter, so the cache's behaviour is tested offline and deterministically.
`test_datasette_scenario.py` covers the real bundled scenario.
"""

import json
import pathlib

import pytest

from evals import scenarios


# --- helpers ---------------------------------------------------------------


PINNED_SHA = "bdc973174096cae350ddaa733a10ed8b3ffd970b"


def make_scenario(root, prompt="do the thing", setup=None, fixture=None):
    """Write a scenario directory and return its path."""
    root.mkdir(parents=True, exist_ok=True)
    (root / scenarios.PROMPT_NAME).write_text(prompt + "\n")
    if setup is not None:
        (root / scenarios.SETUP_NAME).write_text(setup)
    if fixture is not None:
        fixture_dir = root / scenarios.FIXTURE_NAME
        fixture_dir.mkdir(exist_ok=True)
        for name, content in fixture.items():
            path = fixture_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    return root


def counting_setup(counter):
    """A stand-in for a fetch: it records every time it actually runs.

    The counter lives outside the workspace on purpose — inside, it would be
    copied along with the payload and a reader could not tell one fetch from
    one copy.
    """
    return (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"# pinned: {PINNED_SHA}\n"
        f"echo run >> {counter}\n"
        "mkdir -p checkout\n"
        "echo fetched > checkout/README.md\n"
    )


def fetch_count(counter):
    return len(counter.read_text().splitlines()) if counter.exists() else 0


# --- loading ---------------------------------------------------------------


def test_load_reads_prompt_setup_and_fixture(tmp_path):
    root = make_scenario(
        tmp_path / "demo",
        prompt="write a design doc",
        setup=counting_setup(tmp_path / "count"),
        fixture={"notes.md": "context\n"},
    )
    scenario = scenarios.load(root)

    assert scenario.name == "demo"
    assert scenario.prompt == "write a design doc"
    assert scenario.setup == root / scenarios.SETUP_NAME
    assert scenario.fixture == root / scenarios.FIXTURE_NAME
    assert scenario.needs_preparation


def test_prompt_md_is_the_one_required_file(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    with pytest.raises(scenarios.ScenarioError, match=scenarios.PROMPT_NAME):
        scenarios.load(root)


def test_missing_directory_names_the_bundled_scenarios(tmp_path):
    with pytest.raises(scenarios.ScenarioError, match="bundled"):
        scenarios.load(tmp_path / "nope")


def test_setup_and_fixture_are_optional(tmp_path):
    scenario = scenarios.load(make_scenario(tmp_path / "bare"))
    assert scenario.setup is None
    assert scenario.fixture is None
    assert not scenario.needs_preparation


def test_inline_prompt_is_a_scenario_with_no_workspace(tmp_path):
    scenario = scenarios.inline("just answer")
    assert scenario.prompt == "just answer"
    assert scenario.root is None
    assert scenarios.prepare(scenario, cache_dir=tmp_path) is None


def test_a_fixture_only_scenario_seeds_from_the_fixture_directly(tmp_path):
    """No setup.sh, no cache entry: there is nothing to prepare or reuse."""
    root = make_scenario(tmp_path / "static", fixture={"a.txt": "x\n"})
    scenario = scenarios.load(root)
    seed = scenarios.prepare(scenario, cache_dir=tmp_path / "cache")

    assert seed == root / scenarios.FIXTURE_NAME
    assert not (tmp_path / "cache").exists()


def test_resolve_finds_a_bundled_scenario_by_bare_name():
    names = scenarios.available()
    assert names, "the module ships no scenarios"
    scenario = scenarios.resolve(names[0])
    assert scenario.name == names[0]
    assert scenario.root == scenarios.SCENARIOS_DIR / names[0]


# --- setup.sh runs in the workspace ----------------------------------------


def test_setup_runs_with_the_workspace_as_cwd_and_sees_the_fixture(tmp_path):
    """setup.sh must be able to build on the fixture, not race it.

    `cp seed.txt derived.txt` is the assertion: a relative path resolving means
    cwd is the workspace and the fixture was already copied in.
    """
    root = make_scenario(
        tmp_path / "demo",
        setup=(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            f"# pinned: {PINNED_SHA}\n"
            "cp seed.txt derived.txt\n"
            "pwd > where.txt\n"
        ),
        fixture={"seed.txt": "from the fixture\n"},
    )
    seed = scenarios.prepare(scenarios.load(root), cache_dir=tmp_path / "cache")

    assert (seed / "seed.txt").read_text() == "from the fixture\n"
    assert (seed / "derived.txt").read_text() == "from the fixture\n"


def test_setup_runs_under_a_staging_name_not_the_published_one(tmp_path):
    """The published entry is only ever assembled, never fetched into.

    The cwd setup.sh sees is a staging directory that is moved into place in one
    `rename` — which is why an interrupted fetch leaves no cache hit, and why
    setup.sh must produce a relocatable tree.
    """
    root = make_scenario(
        tmp_path / "demo",
        setup=(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            f"# pinned: {PINNED_SHA}\n"
            "pwd > where.txt\n"
        ),
    )
    scenario = scenarios.load(root)
    seed = scenarios.prepare(scenario, cache_dir=tmp_path / "cache")

    ran_in = (seed / "where.txt").read_text().strip()
    assert ran_in.endswith(f"/{scenarios.PAYLOAD_NAME}")
    assert ran_in != str(seed)
    assert not pathlib.Path(ran_in).exists(), "the staging directory outlived the move"


def test_a_failing_setup_raises_and_publishes_nothing(tmp_path):
    cache = tmp_path / "cache"
    root = make_scenario(
        tmp_path / "demo",
        setup=f"#!/usr/bin/env bash\nset -e\n# pinned: {PINNED_SHA}\nexit 3\n",
    )
    scenario = scenarios.load(root)

    with pytest.raises(scenarios.SetupError, match="exited 3"):
        scenarios.prepare(scenario, cache_dir=cache)

    # A half-prepared entry must never look like a cache hit on the next run.
    assert not scenarios.entry_dir(scenario, cache).exists()


# --- the cache -------------------------------------------------------------


def test_second_trial_reuses_the_cache_and_does_not_fetch_again(tmp_path):
    """The acceptance check: reuse proved by a marker, not by a stopwatch."""
    counter = tmp_path / "count"
    cache = tmp_path / "cache"
    scenario = scenarios.load(
        make_scenario(tmp_path / "demo", setup=counting_setup(counter))
    )

    first = scenarios.prepare(scenario, cache_dir=cache)
    marker = scenarios.entry_dir(scenario, cache) / scenarios.MARKER_NAME
    assert fetch_count(counter) == 1
    assert (first / "checkout" / "README.md").read_text() == "fetched\n"

    before = marker.read_text(), marker.stat().st_mtime_ns

    second = scenarios.prepare(scenario, cache_dir=cache)

    assert second == first
    assert fetch_count(counter) == 1, "setup.sh ran a second time — the cache missed"
    assert (marker.read_text(), marker.stat().st_mtime_ns) == before, (
        "the marker was rewritten, so the entry was re-fetched"
    )


def test_the_marker_test_fails_without_a_cache(tmp_path):
    """The counter really does count: two unprepared runs run setup twice.

    Without this, the reuse test above would pass just as happily against a
    setup.sh that never ran at all.
    """
    counter = tmp_path / "count"
    scenario = scenarios.load(
        make_scenario(tmp_path / "demo", setup=counting_setup(counter))
    )

    scenarios.prepare(scenario, cache_dir=tmp_path / "cache-a")
    scenarios.prepare(scenario, cache_dir=tmp_path / "cache-b")

    assert fetch_count(counter) == 2


def test_the_marker_stays_out_of_the_workspace(tmp_path):
    """Harness bookkeeping must not appear in the tree the agent sees."""
    cache = tmp_path / "cache"
    scenario = scenarios.load(
        make_scenario(tmp_path / "demo", setup=counting_setup(tmp_path / "count"))
    )
    seed = scenarios.prepare(scenario, cache_dir=cache)

    assert {p.name for p in seed.iterdir()} == {"checkout"}
    assert (scenarios.entry_dir(scenario, cache) / scenarios.MARKER_NAME).is_file()


def test_the_marker_records_what_was_fetched(tmp_path):
    cache = tmp_path / "cache"
    scenario = scenarios.load(
        make_scenario(tmp_path / "demo", setup=counting_setup(tmp_path / "count"))
    )
    scenarios.prepare(scenario, cache_dir=cache)

    marker = json.loads(
        (scenarios.entry_dir(scenario, cache) / scenarios.MARKER_NAME).read_text()
    )
    assert marker["scenario"] == "demo"
    assert marker["key"] == scenarios.cache_key(scenario)
    assert marker["fetched_at"]


def test_editing_setup_invalidates_the_entry(tmp_path):
    """A changed setup.sh is a different fixture, and must not reuse the old one."""
    counter = tmp_path / "count"
    cache = tmp_path / "cache"
    root = make_scenario(tmp_path / "demo", setup=counting_setup(counter))

    first = scenarios.prepare(scenarios.load(root), cache_dir=cache)
    (root / scenarios.SETUP_NAME).write_text(
        counting_setup(counter) + "echo more > checkout/extra.md\n"
    )
    second = scenarios.prepare(scenarios.load(root), cache_dir=cache)

    assert second != first
    assert fetch_count(counter) == 2
    assert (second / "checkout" / "extra.md").is_file()


def test_editing_the_fixture_invalidates_the_entry(tmp_path):
    counter = tmp_path / "count"
    cache = tmp_path / "cache"
    root = make_scenario(
        tmp_path / "demo",
        setup=counting_setup(counter),
        fixture={"seed.txt": "one\n"},
    )

    first = scenarios.prepare(scenarios.load(root), cache_dir=cache)
    (root / scenarios.FIXTURE_NAME / "seed.txt").write_text("two\n")
    second = scenarios.prepare(scenarios.load(root), cache_dir=cache)

    assert second != first
    assert fetch_count(counter) == 2
    assert (second / "seed.txt").read_text() == "two\n"


def test_cache_dir_defaults_into_the_module(tmp_path, monkeypatch):
    """`prepare` with no cache dir writes under the module's own `cache/`."""
    monkeypatch.setattr(scenarios, "CACHE_DIR", tmp_path / "module-cache")
    scenario = scenarios.load(
        make_scenario(tmp_path / "demo", setup=counting_setup(tmp_path / "count"))
    )
    seed = scenarios.prepare(scenario)
    assert (tmp_path / "module-cache") in seed.parents


# --- the pin check ---------------------------------------------------------


PINNED = (
    f"git checkout {PINNED_SHA}",
    f'git checkout "{PINNED_SHA}"',
    f"git -C repo checkout {PINNED_SHA}",
    f"git switch --detach {PINNED_SHA}",
    f"git reset --hard {PINNED_SHA}",
    f"git clone --branch {PINNED_SHA} https://example.invalid/r.git",
    f"curl -fsSL https://codeload.github.com/o/r/tar.gz/{PINNED_SHA} -o r.tgz",
    f"curl -fsSL https://github.com/o/r/archive/{PINNED_SHA}.tar.gz -o r.tgz",
    f"git fetch --depth 1 origin {PINNED_SHA}",
)

FLOATING = (
    "git checkout main",
    "git checkout HEAD",
    "git switch --detach 1.0-branch",
    "git reset --hard origin/main",
    "git clone --branch main https://example.invalid/r.git",
    "git clone --branch=v1.2.3 https://example.invalid/r.git",
    "curl -fsSL https://codeload.github.com/o/r/tar.gz/main -o r.tgz",
    "curl -fsSL https://github.com/o/r/archive/refs/heads/main.tar.gz -o r.tgz",
    "git fetch --depth 1 origin main",
    f"git checkout {PINNED_SHA[:12]}",  # an abbreviated sha is still not the pin
)


@pytest.mark.parametrize("line", PINNED)
def test_pin_check_accepts_a_literal_sha(line):
    scenarios.check_pins(f"#!/usr/bin/env bash\nset -e\n{line}\n")


@pytest.mark.parametrize("line", FLOATING)
def test_pin_check_rejects_a_floating_ref(line):
    with pytest.raises(scenarios.PinError):
        scenarios.check_pins(f"#!/usr/bin/env bash\nset -e\n{line}\n")


def test_pin_check_expands_the_scripts_own_variables():
    """`SHA=... ; use "$SHA"` is the natural way to write it, and must pass."""
    scenarios.check_pins(
        "#!/usr/bin/env bash\n"
        f"SHA={PINNED_SHA}\n"
        'curl -fsSL "https://codeload.github.com/o/r/tar.gz/$SHA" | tar -xz\n'
    )


def test_pin_check_rejects_a_variable_holding_a_branch():
    with pytest.raises(scenarios.PinError, match="expands to 'main'"):
        scenarios.check_pins(
            "#!/usr/bin/env bash\n"
            "REF=main\n"
            'git clone https://example.invalid/r.git && git -C r checkout "$REF"\n'
        )


def test_pin_check_rejects_an_unresolvable_variable():
    """A ref from the environment is a floating ref the scenario cannot vouch for."""
    with pytest.raises(scenarios.PinError):
        scenarios.check_pins(
            "#!/usr/bin/env bash\n"
            f"# pinned: {PINNED_SHA}\n"
            'git checkout "$REF_FROM_SOMEWHERE_ELSE"\n'
        )


def test_pin_check_rejects_a_fetch_with_no_sha_anywhere():
    """A bare clone names no ref, so ref-site checking alone would miss it."""
    with pytest.raises(scenarios.PinError, match="no 40-character sha"):
        scenarios.check_pins(
            "#!/usr/bin/env bash\ngit clone https://example.invalid/r.git\n"
        )


def test_pin_check_allows_a_setup_that_fetches_nothing():
    """A local-only setup.sh has no ref to pin; demanding one would be noise."""
    scenarios.check_pins(
        "#!/usr/bin/env bash\nmkdir -p app\necho hello > app/main.py\n"
    )


def test_pin_check_ignores_branch_names_in_comments():
    scenarios.check_pins(
        "#!/usr/bin/env bash\n"
        "# this was main at the time of writing; pinned so it stays put\n"
        f"git checkout {PINNED_SHA}\n"
    )


def test_load_fails_a_scenario_whose_setup_floats(tmp_path):
    """The check runs at load, so a floating scenario never reaches an arm."""
    root = make_scenario(
        tmp_path / "floating",
        setup="#!/usr/bin/env bash\ngit clone https://example.invalid/r.git\n"
        "git -C r checkout main\n",
    )
    with pytest.raises(scenarios.PinError, match="git checkout"):
        scenarios.load(root)


def test_every_bundled_scenario_is_pinned():
    """The rule applies to what ships, not only to what a test writes."""
    for name in scenarios.available():
        scenarios.load(scenarios.SCENARIOS_DIR / name)
