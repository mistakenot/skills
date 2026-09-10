"""Replay recorded CLI transcripts through the council script's real classification path.

The stub runner is kind by construction. These fixtures are not: each is the
verbatim output a real CLI produced (see fixtures/recorded/README.md), including
the shapes that broke the first live council. Every case pins the status and
answer the script must derive from it, so a regression in answer extraction or
failure classification fails here without spending a token.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "council.py"
RECORDED = HERE / "fixtures" / "recorded"


def _load_script():
    spec = importlib.util.spec_from_file_location("council_replay", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["council_replay"] = mod
    spec.loader.exec_module(mod)
    return mod


council = _load_script()

# case directory -> (member, expected status, text the answer must start with or None)
CASES = {
    "claude-variadic-prompt-swallowed": ("claude", "error", None),
    "claude-ok": ("claude", "ok", "Neither AskUserQuestion nor ExitPlanMode"),
    "codex-echoes-auth-marker": ("codex", "ok", "Treat each CLI invocation as a versioned integration contract"),
    "opencode-json-stream": ("opencode", "ok", "I've read the contract TOML"),
    "opencode-default-format-drops-answer": ("opencode", "error", None),
    "opencode-external-dir-rejected": ("opencode", "error", None),
    "gemini-api-key-missing": ("gemini", "auth", None),
    "grok-device-code-hang": ("grok", "auth", None),
}


def _replay(case: str, tmp_path: Path):
    member = CASES[case][0]
    os.environ["COUNCIL_REPLAY_DIR"] = str(RECORDED / case)
    try:
        return council._run_replay(member, "Q", tmp_path)
    finally:
        os.environ.pop("COUNCIL_REPLAY_DIR", None)


def test_every_recorded_case_is_covered():
    on_disk = sorted(p.name for p in RECORDED.iterdir() if p.is_dir())
    assert on_disk == sorted(CASES), "add each recorded transcript to CASES with its expected outcome"


@pytest.mark.parametrize("case", sorted(CASES))
def test_recorded_transcript_classifies_as_expected(case, tmp_path):
    member, status, prefix = CASES[case]
    r = _replay(case, tmp_path)
    assert r.status == status, f"{case}: got {r.status}, log tail:\n{r.log[-600:]}"
    if prefix is not None:
        assert r.answer.startswith(prefix), f"{case}: answer starts {r.answer[:120]!r}"
    else:
        assert r.answer == "", f"{case}: a failed member must not carry an answer"


# --- the specific shapes that broke the first live council ---------------------


def test_codex_auth_marker_in_echoed_repo_content_is_not_auth(tmp_path):
    """The session log contains 'not logged in' because codex read it from a repo
    file; with rc 0 that must not turn a complete answer into an auth failure."""
    r = _replay("codex-echoes-auth-marker", tmp_path)
    assert "not logged in" in r.log
    assert r.status == "ok"


def test_opencode_answer_comes_from_text_events_only(tmp_path):
    r = _replay("opencode-json-stream", tmp_path)
    assert not r.answer.startswith("{"), "raw JSON leaked into the answer"
    assert "tool_use" not in r.answer and '"type":' not in r.answer


def test_grok_hang_is_auth_not_timeout(tmp_path):
    r = _replay("grok-device-code-hang", tmp_path)
    assert r.rc is None and r.status == "auth"
    assert "timed out" in r.log


def test_gemini_exit_41_names_the_fix(tmp_path):
    r = _replay("gemini-api-key-missing", tmp_path)
    assert r.status == "auth" and "GEMINI_API_KEY" in council.auth_hint("gemini")


# --- end to end: a council assembled from recorded transcripts -----------------


def _assemble(tmp_path: Path, cases: list[str]) -> Path:
    root = tmp_path / "replay"
    for case in cases:
        member = CASES[case][0]
        shutil.copytree(RECORDED / case / member, root / member)
    return root


def test_replayed_council_drops_broken_members_and_answers_with_the_rest(tmp_path):
    replay_dir = _assemble(tmp_path, [
        "claude-ok", "codex-echoes-auth-marker", "opencode-json-stream",
        "gemini-api-key-missing", "grok-device-code-hang",
    ])
    q = tmp_path / "q.md"
    q.write_text("Q")
    out = tmp_path / "out"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "ask", "--prompt-file", str(q), "--runner", "replay", "--out", str(out), "--seed", "1"],
        capture_output=True, text=True, env={**os.environ, "COUNCIL_REPLAY_DIR": str(replay_dir)},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "proceeding without gemini, grok" in proc.stdout
    summary = json.loads((out / "summary.json").read_text())
    assert sorted(summary["members"]) == ["claude", "codex", "opencode"]
    assert summary["preflight"]["grok"]["status"] == "auth"
    key = json.loads((out / "key.json").read_text())
    for label, member in key.items():
        text = (out / f"{label}.md").read_text()
        assert text.startswith(CASES[{"claude": "claude-ok", "codex": "codex-echoes-auth-marker", "opencode": "opencode-json-stream"}[member]][2])


def test_replayed_council_under_quorum_exits_three(tmp_path):
    replay_dir = _assemble(tmp_path, ["claude-ok", "gemini-api-key-missing", "grok-device-code-hang", "opencode-default-format-drops-answer"])
    q = tmp_path / "q.md"
    q.write_text("Q")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "ask", "--prompt-file", str(q), "--runner", "replay", "--out", str(tmp_path / "out")],
        capture_output=True, text=True, env={**os.environ, "COUNCIL_REPLAY_DIR": str(replay_dir)},
    )
    assert proc.returncode == 3
    assert "1 usable member(s), 3 required" in proc.stderr
    assert "grok: auth" in proc.stderr and "opencode: error" in proc.stderr
