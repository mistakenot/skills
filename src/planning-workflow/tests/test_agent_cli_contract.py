"""Validate the agent CLI flags our skills depend on against the installed CLIs.

Three layers, all driven by ``agent-cli-contract.toml``:

1. **Help contract** — ``<cmd> --help`` of the installed ``claude``, ``codex``,
   ``grok`` and ``herdr`` must advertise every flag and enum value the
   contract lists. Fast, no auth, no tokens. This is the drift detector: a
   CLI release that renames ``--dangerously-skip-permissions`` fails here.
2. **Source contract** — every agent invocation in the skill sources uses only
   contracted flags, and every contracted flag is used somewhere. This keeps
   the contract and the skills from drifting apart in either direction.
3. **Live smoke** (opt-in, ``AGENT_CLI_LIVE=1``) — runs the canonical headless
   unattended invocation for each agent and expects a PONG. Bills tokens.

Run:  uv run pytest src/planning-workflow/tests/
      AGENT_CLI_LIVE=1 uv run pytest src/planning-workflow/tests/ -k live
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

import pytest

from agent_cli_contract import (
    DEFAULT_SCAN_ROOTS,
    REPO_ROOT,
    SRC_ROOT,
    Command,
    installed_version,
    load_contract,
    parse_help,
    run_help,
    scan_sources,
    version_tuple,
)

CONTRACT = load_contract()
COMMANDS = CONTRACT.all_commands()
AGENT_NAMES = list(CONTRACT.agents)


def _cmd_id(c: Command) -> str:
    return c.key.replace(" ", "_")


# --- fixtures ---------------------------------------------------------------


@pytest.fixture(scope="module")
def help_surfaces():
    """``--help`` parsed once per contracted command path."""
    surfaces = {}
    for cmd in COMMANDS:
        if shutil.which(cmd.agent) is None:
            continue
        rc, text = run_help(cmd.argv)
        surfaces[cmd.key] = (rc, parse_help(cmd.argv, text))
    return surfaces


@pytest.fixture(scope="module")
def invocations():
    return [inv for inv in scan_sources(DEFAULT_SCAN_ROOTS) if inv.flags]


# --- layer 0: the CLIs are installed and current ----------------------------


@pytest.mark.parametrize("agent", AGENT_NAMES)
def test_cli_on_path(agent):
    assert shutil.which(agent), (
        f"`{agent}` is not on PATH. The delegate/review skills shell out to it; "
        f"install the latest release before trusting the skills."
    )


@pytest.mark.parametrize("agent", AGENT_NAMES)
def test_installed_version_not_older_than_verified(agent):
    if shutil.which(agent) is None:
        pytest.fail(f"`{agent}` not on PATH")
    want = CONTRACT.agents[agent].verified_version
    got = installed_version(agent)
    assert got, f"could not parse `{agent} --version` output"
    assert version_tuple(got) >= version_tuple(want), (
        f"installed {agent} {got} is older than the contract's verified {want}; "
        f"a green run on an old build proves nothing — update the CLI"
    )


# --- layer 1: --help advertises every contracted flag and value -------------


@pytest.mark.parametrize("cmd", COMMANDS, ids=_cmd_id)
def test_help_runs(cmd, help_surfaces):
    if cmd.key not in help_surfaces:
        pytest.fail(f"`{cmd.agent}` not on PATH")
    rc, surface = help_surfaces[cmd.key]
    assert rc == 0, f"`{cmd.key} --help` exited {rc}:\n{surface.text[-800:]}"
    assert surface.flags, f"`{cmd.key} --help` produced no parseable options:\n{surface.text[:800]}"


@pytest.mark.parametrize("cmd", COMMANDS, ids=_cmd_id)
def test_help_exposes_contract_flags(cmd, help_surfaces):
    if cmd.key not in help_surfaces:
        pytest.fail(f"`{cmd.agent}` not on PATH")
    _, surface = help_surfaces[cmd.key]
    missing = sorted(cmd.flags - surface.flags)
    assert not missing, (
        f"`{cmd.key}` no longer advertises {missing} in --help "
        f"(installed {installed_version(cmd.agent)}). The skills pass these flags; "
        f"update the refs under src/planning-workflow and the contract.\n"
        f"Advertised: {sorted(surface.flags)}"
    )


def _value_cases():
    for cmd in COMMANDS:
        for flag, values in cmd.values.items():
            yield pytest.param(cmd, flag, values, id=f"{_cmd_id(cmd)}[{flag}]")


@pytest.mark.parametrize("cmd,flag,values", list(_value_cases()))
def test_help_exposes_contract_values(cmd, flag, values, help_surfaces):
    if cmd.key not in help_surfaces:
        pytest.fail(f"`{cmd.agent}` not on PATH")
    _, surface = help_surfaces[cmd.key]
    advertised = surface.values.get(flag)
    assert advertised, (
        f"`{cmd.key} --help` lists no enum values for {flag} "
        f"(expected at least {list(values)}); the help format may have changed"
    )
    missing = [v for v in values if v not in advertised]
    assert not missing, (
        f"`{cmd.key} {flag}` no longer accepts {missing}; advertised: {sorted(advertised)}"
    )


# --- layer 2: skill sources and the contract agree --------------------------


def test_sources_use_only_contract_flags(invocations):
    """A skill that starts passing an unverified flag must add it to the contract."""
    problems = []
    for inv in invocations:
        cmd = CONTRACT.command(inv.agent, inv.path)
        known = cmd.flags if cmd else frozenset()
        for fl in inv.flags:
            if fl not in known:
                rel = inv.file.relative_to(REPO_ROOT)
                where = "unknown command path" if cmd is None else "flag not in contract"
                problems.append(f"{rel}:{inv.line}  `{inv.key} {fl}`  ({where})")
    assert not problems, (
        "agent invocations use flags the contract has not verified:\n  "
        + "\n  ".join(sorted(set(problems)))
        + "\nAdd them to src/planning-workflow/tests/agent-cli-contract.toml "
        "(and confirm --help advertises them)."
    )


def test_contract_flags_are_used_somewhere(invocations):
    """The contract should describe the real dependency surface, not accrete."""
    used = {(inv.key, fl) for inv in invocations for fl in inv.flags}
    used |= {("claude", fl) for fl in _evals_build_argv_flags()}
    unused = sorted(f"{cmd.key} {fl}" for cmd in COMMANDS for fl in cmd.flags if (cmd.key, fl) not in used)
    assert not unused, (
        "contract lists flags no skill source uses (remove them, or the scanner "
        "missed an invocation — run `python src/planning-workflow/tests/agent_cli_contract.py`):\n  "
        + "\n  ".join(unused)
    )


def test_scanner_finds_the_known_invocations(invocations):
    """Guard the scanner itself: the core skill invocations must be visible to it."""
    keys = {(inv.key, fl) for inv in invocations for fl in inv.flags}
    for expected in [
        ("claude", "--dangerously-skip-permissions"),
        ("claude", "-p"),
        ("codex", "--dangerously-bypass-approvals-and-sandbox"),
        ("codex exec", "--sandbox"),
        ("grok", "--always-approve"),
        ("herdr agent start", "--kind"),
        ("herdr worktree create", "--branch"),
    ]:
        assert expected in keys, f"scanner no longer sees {expected} in the skill sources"


# --- layer 2b: the evals harness's hardcoded argv ---------------------------


def _evals_build_argv_flags() -> list[str]:
    if str(SRC_ROOT) not in sys.path:
        sys.path.insert(0, str(SRC_ROOT))
    from evals.runners import build_argv  # noqa: WPS433 — repo module

    argv = build_argv("prompt", "model")
    return [a for a in argv if a.startswith("-")]


def test_evals_build_argv_matches_contract():
    claude = CONTRACT.command("claude", ())
    assert claude is not None
    flags = _evals_build_argv_flags()
    unknown = [f for f in flags if f not in claude.flags]
    assert not unknown, f"src/evals/runners.py build_argv uses uncontracted flags: {unknown}"

    if str(SRC_ROOT) not in sys.path:
        sys.path.insert(0, str(SRC_ROOT))
    from evals.runners import build_argv

    argv = build_argv("prompt", "model")
    for flag in ("--permission-mode", "--output-format"):
        value = argv[argv.index(flag) + 1]
        assert value in claude.values[flag], f"build_argv passes {flag} {value!r}, not in contract values"


# --- layer 3: live smoke (opt-in, bills tokens) -----------------------------

LIVE = os.environ.get("AGENT_CLI_LIVE") == "1"


@pytest.mark.parametrize("agent", [a for a in AGENT_NAMES if CONTRACT.agents[a].live_smoke])
def test_live_headless_smoke(agent):
    """The canonical unattended invocation runs to completion under closed stdin."""
    if not LIVE:
        pytest.skip("set AGENT_CLI_LIVE=1 to run live headless smoke tests (bills tokens)")
    spec = CONTRACT.agents[agent]
    try:
        proc = subprocess.run(
            spec.live_smoke,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=REPO_ROOT,
        )
    except subprocess.TimeoutExpired as exc:
        # TimeoutExpired carries raw bytes even in text mode.
        out = "".join(
            part.decode(errors="replace") if isinstance(part, bytes) else (part or "")
            for part in (exc.stdout, exc.stderr)
        )
        if _looks_like_auth_prompt(out):
            pytest.fail(
                f"`{agent}` is not authenticated: headless mode fell into an interactive "
                f"login and hung. Run `{agent} login` and retry.\n{out[-800:]}"
            )
        pytest.fail(f"{' '.join(spec.live_smoke)} hung for 120s with no result:\n{out[-1500:]}")
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, f"{' '.join(spec.live_smoke)} exited {proc.returncode}:\n{out[-1500:]}"
    assert spec.live_expect in out, f"expected {spec.live_expect!r} in output:\n{out[-1500:]}"


_AUTH_MARKERS = ("Waiting for authorization", "Only continue with a code you requested", "Please log in", "not logged in")


def _looks_like_auth_prompt(text: str) -> bool:
    return any(m in text for m in _AUTH_MARKERS)
