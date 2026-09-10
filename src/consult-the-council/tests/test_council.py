"""Tests for the consult-the-council fan-out script.

Two concerns:

* **Flags** — every member's argv is read-only and every flag it uses is
  pinned in the agent CLI contract (src/planning-workflow/tests/
  agent-cli-contract.toml), so a CLI release that renames a flag fails the
  contract suite rather than a live council.
* **Usage** — the CLI surface behaves: member selection keeps preference
  order, blind labels are a permutation with a key, failures of one member
  do not lose the others, and bad input exits 2 with a message.

No CLI is executed here; `ask` runs with `--runner stub`.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
SCRIPT = HERE.parent / "scripts" / "council.py"
CONTRACT = REPO_ROOT / "src" / "planning-workflow" / "tests" / "agent-cli-contract.toml"


def _load_script():
    spec = importlib.util.spec_from_file_location("council", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["council"] = mod
    spec.loader.exec_module(mod)
    return mod


council = _load_script()


def _contract_flags(member: str, path: tuple[str, ...]) -> tuple[set[str], dict[str, list[str]]]:
    raw = tomllib.loads(CONTRACT.read_text())
    for entry in raw["agent"][member].get("command", []):
        if tuple(entry.get("path", "").split()) == path:
            return set(entry.get("flags", [])), entry.get("values", {})
    raise AssertionError(f"contract has no `{member} {' '.join(path)}` command")


# Words that must never appear in a council member's argv. Each is the
# write-capable or prompt-bypassing mode of one CLI.
FORBIDDEN = {
    "--dangerously-skip-permissions", "bypassPermissions", "acceptEdits", "auto",
    "--dangerously-bypass-approvals-and-sandbox", "workspace-write", "danger-full-access",
    "--yolo", "auto_edit", "build", "--always-approve",
}

CASES = [(m, a) for m in council.MEMBERS for a in council.ACCESS_MODES]


# --- flags -------------------------------------------------------------------


@pytest.mark.parametrize("member,access", CASES, ids=[f"{m}-{a}" for m, a in CASES])
def test_argv_is_read_only(member, access, tmp_path):
    argv = council.build_argv(member, access, "Q", tmp_path, tmp_path / "ans")
    assert argv[0] == member
    assert "Q" in argv, "the prompt must be passed verbatim as an argument"
    forbidden = FORBIDDEN & set(argv)
    assert not forbidden, f"{member} argv carries a write-capable flag: {forbidden}"


@pytest.mark.parametrize("member,access", CASES, ids=[f"{m}-{a}" for m, a in CASES])
def test_argv_flags_are_in_contract(member, access, tmp_path):
    argv = council.build_argv(member, access, "Q", tmp_path, tmp_path / "ans")
    path = tuple(a for a in argv[1:3] if not a.startswith("-") and a in ("exec", "run"))
    flags, values = _contract_flags(member, path)
    used = {a for a in argv if a.startswith("-") and a != "-"}
    missing = used - flags
    assert not missing, f"{member} uses {missing}, not in the agent CLI contract; add them there and verify against --help"
    # The read-only enum values must be the contracted ones.
    for flag, allowed in values.items():
        if flag in argv:
            value = argv[argv.index(flag) + 1]
            assert value in allowed, f"{member} {flag} {value!r} is not a contracted value {allowed}"


def test_every_member_has_a_read_only_mode_marker(tmp_path):
    """Belt and braces: each argv contains the specific token that makes it read-only."""
    expected = {
        "claude": "Read,Grep,Glob", "codex": "read-only", "gemini": "plan", "opencode": "plan", "grok": "plan",
    }
    for member, token in expected.items():
        argv = council.build_argv(member, "repo", "Q", tmp_path, tmp_path / "ans")
        assert token in argv, f"{member} argv lacks its read-only marker {token!r}: {argv}"


# --- answer extraction ---------------------------------------------------------


def test_clean_answer_extracts_opencode_text_events():
    raw = (
        '{"type":"step_start","timestamp":1,"part":{"type":"step-start"}}\n'
        '{"type":"text","timestamp":2,"part":{"type":"text","text":"PONG"}}\n'
        '{"type":"text","timestamp":3,"part":{"type":"text","text":"second"}}\n'
        'not json\n'
    )
    assert council.clean_answer("opencode", raw) == "PONG\nsecond"


@pytest.mark.parametrize("access", council.ACCESS_MODES)
def test_claude_prompt_is_not_swallowed_by_variadic_flags(access, tmp_path):
    """`--add-dir <dirs...>` and `--tools <tools...>` eat every following non-flag
    token, so the prompt must be last and preceded by the boolean `-p`."""
    argv = council.build_argv("claude", access, "Q", tmp_path, tmp_path / "ans")
    assert argv[-1] == "Q" and argv[-2] == "-p"
    for variadic in ("--add-dir", "--tools"):
        if variadic in argv:
            following = argv[argv.index(variadic) + 2]
            assert following.startswith("-"), f"prompt would be parsed as a {variadic} value: {argv}"


def test_claude_none_mode_has_no_tools(tmp_path):
    argv = council.build_argv("claude", "none", "Q", tmp_path, tmp_path / "ans")
    assert argv[argv.index("--tools") + 1] == "" and "--add-dir" not in argv


def test_opencode_sets_project_dir_and_json_format(tmp_path):
    argv = council.build_argv("opencode", "repo", "Q", tmp_path, tmp_path / "ans")
    assert argv[argv.index("--dir") + 1] == str(tmp_path)
    assert argv[argv.index("--format") + 1] == "json"


def test_clean_answer_prefers_codex_output_file(tmp_path):
    f = tmp_path / "ans"
    f.write_text("final message\n")
    assert council.clean_answer("codex", "session noise\nmore noise", f) == "final message"


def test_clean_answer_codex_falls_back_to_stdout_without_file(tmp_path):
    assert council.clean_answer("codex", "PONG\n", tmp_path / "absent") == "PONG"


# --- usage ---------------------------------------------------------------------


def test_auth_markers_do_not_misclassify_a_successful_answer(tmp_path, monkeypatch):
    """A codex answer that mentions `codex login` is still an answer (rc 0)."""
    class Proc:
        returncode = 0
        stdout = "Run codex login if you are not logged in.\n"
        stderr = ""
    monkeypatch.setattr(council.subprocess, "run", lambda *a, **k: Proc())
    monkeypatch.setattr(council, "installed", lambda m: True)
    r = council.run_member("codex", "Q", "none", tmp_path, tmp_path, 5, "live")
    assert r.status == "ok" and "codex login" in r.answer


def test_auth_markers_apply_on_failed_run(tmp_path, monkeypatch):
    class Proc:
        returncode = 41
        stdout = ""
        stderr = "you must specify the GEMINI_API_KEY environment variable"
    monkeypatch.setattr(council.subprocess, "run", lambda *a, **k: Proc())
    monkeypatch.setattr(council, "installed", lambda m: True)
    r = council.run_member("gemini", "Q", "none", tmp_path, tmp_path, 5, "live")
    assert r.status == "auth"


def test_select_members_defaults_to_all_in_preference_order():
    assert council.select_members(None) == list(council.MEMBERS)


def test_select_members_keeps_preference_order_regardless_of_input_order():
    assert council.select_members("grok,claude,gemini") == ["claude", "gemini", "grok"]


def test_select_members_rejects_unknown():
    with pytest.raises(ValueError, match="unknown member"):
        council.select_members("claude,chatgpt")


def _run(*args, env=None, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, cwd=cwd,
        env={**os.environ, **(env or {})},
    )


def test_help_exits_zero():
    for sub in ([], ["ask"], ["argv"], ["members"], ["reveal"]):
        proc = _run(*sub, "--help")
        assert proc.returncode == 0, proc.stderr
        assert "usage" in proc.stdout.lower()


def test_argv_subcommand_prints_json_argv():
    proc = _run("argv", "--member", "codex", "--access", "none", "--cwd", "/tmp")
    assert proc.returncode == 0, proc.stderr
    argv = json.loads(proc.stdout)
    assert argv[:2] == ["codex", "exec"] and "--skip-git-repo-check" in argv


def test_ask_requires_existing_nonempty_prompt(tmp_path):
    proc = _run("ask", "--prompt-file", str(tmp_path / "nope.md"), "--runner", "stub")
    assert proc.returncode == 2 and "not found" in proc.stderr
    empty = tmp_path / "empty.md"
    empty.write_text("  \n")
    proc = _run("ask", "--prompt-file", str(empty), "--runner", "stub")
    assert proc.returncode == 2 and "empty" in proc.stderr


def test_ask_rejects_unknown_member(tmp_path):
    q = tmp_path / "q.md"
    q.write_text("What could go wrong?")
    proc = _run("ask", "--prompt-file", str(q), "--members", "claude,bard", "--runner", "stub")
    assert proc.returncode == 2 and "bard" in proc.stderr


def test_ask_stub_writes_blind_layout(tmp_path):
    q = tmp_path / "q.md"
    q.write_text("What could go wrong?")
    out = tmp_path / "out"
    proc = _run("ask", "--prompt-file", str(q), "--runner", "stub", "--out", str(out), "--seed", "7")
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert (out / "question.md").read_text() == "What could go wrong?"
    key = json.loads((out / "key.json").read_text())
    assert sorted(key) == ["A", "B", "C", "D", "E"]
    assert sorted(key.values()) == sorted(council.MEMBERS)
    for label, member in key.items():
        assert (out / f"{label}.md").read_text().startswith(f"STUB ANSWER from {member}")
        assert (out / f"{label}.log").exists()
    summary = json.loads((out / "summary.json").read_text())
    assert all(v["status"] == "ok" for v in summary["members"].values())
    assert summary["quorum"] == 3 and len(summary["preflight"]) == 5
    assert "5/5 answered" in proc.stdout and "blind" in proc.stdout


def test_ask_blind_labels_are_shuffled_not_positional(tmp_path):
    """Across seeds the letter for `claude` must not always be A."""
    q = tmp_path / "q.md"
    q.write_text("Q")
    seen = set()
    for seed in range(6):
        out = tmp_path / f"out{seed}"
        assert _run("ask", "--prompt-file", str(q), "--runner", "stub", "--out", str(out), "--seed", str(seed)).returncode == 0
        key = json.loads((out / "key.json").read_text())
        seen.add(next(l for l, m in key.items() if m == "claude"))
    assert len(seen) > 1, "blind labels never varied; the shuffle is not applied"


def test_ask_attributed_names_files_by_member(tmp_path):
    q = tmp_path / "q.md"
    q.write_text("Q")
    out = tmp_path / "out"
    proc = _run("ask", "--prompt-file", str(q), "--runner", "stub", "--out", str(out), "--members", "claude,codex", "--attributed")
    assert proc.returncode == 0, proc.stderr
    assert (out / "claude.md").exists() and (out / "codex.md").exists()
    assert not (out / "A.md").exists()


def test_preflight_drops_broken_members_and_proceeds_with_quorum(tmp_path):
    """Two members unusable, three left: the council runs with the three."""
    q = tmp_path / "q.md"
    q.write_text("Q")
    out = tmp_path / "out"
    proc = _run("ask", "--prompt-file", str(q), "--runner", "stub", "--out", str(out), "--attributed",
                env={"COUNCIL_STUB_AUTH": "grok", "COUNCIL_STUB_FAIL": "gemini"})
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "proceeding without gemini, grok" in proc.stdout
    assert "grok login" in proc.stdout, "auth failures must say how to fix them"
    summary = json.loads((out / "summary.json").read_text())
    assert sorted(summary["members"]) == ["claude", "codex", "opencode"]
    assert summary["preflight"]["grok"]["status"] == "auth"
    assert summary["preflight"]["gemini"]["status"] == "error"
    assert (out / "preflight-grok.log").exists() and not (out / "grok.md").exists()
    assert "3/3 answered" in proc.stdout


def test_preflight_below_quorum_exits_three_with_fixes(tmp_path):
    q = tmp_path / "q.md"
    q.write_text("Q")
    out = tmp_path / "out"
    proc = _run("ask", "--prompt-file", str(q), "--runner", "stub", "--out", str(out),
                env={"COUNCIL_STUB_AUTH": "grok,gemini", "COUNCIL_STUB_FAIL": "codex"})
    assert proc.returncode == 3
    assert "cannot meet quorum: 2 usable member(s), 3 required" in proc.stderr
    assert "grok: auth — run `grok login`" in proc.stderr
    assert "codex: error" in proc.stderr
    assert not list(out.glob("[A-E].md")), "no council should run under quorum"


def test_quorum_override_lets_a_smaller_council_run(tmp_path):
    q = tmp_path / "q.md"
    q.write_text("Q")
    out = tmp_path / "out"
    proc = _run("ask", "--prompt-file", str(q), "--runner", "stub", "--out", str(out), "--quorum", "2",
                env={"COUNCIL_STUB_AUTH": "grok,gemini", "COUNCIL_STUB_FAIL": "codex"})
    assert proc.returncode == 0, proc.stderr
    assert "2/2 answered" in proc.stdout


def test_quorum_defaults_to_requested_count_when_fewer_than_three():
    assert council.effective_quorum(2, None) == 2
    assert council.effective_quorum(5, None) == 3
    assert council.effective_quorum(5, 4) == 4
    assert council.effective_quorum(2, 4) == 2


def test_skip_preflight_runs_without_probing(tmp_path):
    q = tmp_path / "q.md"
    q.write_text("Q")
    out = tmp_path / "out"
    proc = _run("ask", "--prompt-file", str(q), "--runner", "stub", "--out", str(out), "--skip-preflight", "--attributed",
                env={"COUNCIL_STUB_FAIL": "grok"})
    assert proc.returncode == 1, "without preflight a failing member surfaces at answer time"
    summary = json.loads((out / "summary.json").read_text())
    assert summary["preflight"] == {} and summary["members"]["grok"]["status"] == "error"
    assert "4/5 answered" in proc.stdout


def test_preflight_subcommand_reports_and_exits_by_quorum(tmp_path):
    ok = _run("preflight", "--runner", "stub")
    assert ok.returncode == 0 and "5/5 usable, quorum 3" in ok.stdout
    bad = _run("preflight", "--runner", "stub", env={"COUNCIL_STUB_AUTH": "claude,codex,gemini"})
    assert bad.returncode == 3 and "2/5 usable" in bad.stdout and "claude login" in bad.stderr


def test_preflight_rejects_probe_answer_without_pong(monkeypatch, tmp_path):
    monkeypatch.setattr(council, "run_member",
                        lambda m, *a, **k: council.Result(m, "ok", 0, 0.1, "I cannot help with that.", ""))
    results = council.preflight(["claude"], "live")
    assert results[0].status == "error"


def test_reveal_prints_key(tmp_path):
    q = tmp_path / "q.md"
    q.write_text("Q")
    out = tmp_path / "out"
    assert _run("ask", "--prompt-file", str(q), "--runner", "stub", "--out", str(out), "--members", "claude").returncode == 0
    proc = _run("reveal", "--out", str(out))
    assert proc.returncode == 0 and proc.stdout.strip() == "A  claude"


def test_reveal_without_key_exits_two(tmp_path):
    proc = _run("reveal", "--out", str(tmp_path))
    assert proc.returncode == 2
