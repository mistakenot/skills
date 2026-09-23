"""Reading Harbor's evidence back into planning-eval's result shape.

The fixtures under `fixtures/scripted-trial/` and `fixtures/simulated-trial/`
are real Harbor 0.23.0 trial directories from the smoke runs that verified this
harness (a three-turn scripted replay with native resume; a three-message
simulated-user replay over the ACP bridge), trimmed to the files the reader
consumes. They are the ground truth the parser is held to, not a shape someone
imagined.
"""

from __future__ import annotations

import io
import json
import shutil
import tarfile
from pathlib import Path

import pytest

import results

FIXTURES = Path(__file__).resolve().parent / "fixtures"

SCRIPTED_STEPS = ["turn-1", "turn-2", "turn-3"]
SCRIPTED_MESSAGES = [
    "List every skill available to you by name. If a skill named `peval-marker` is present, "
    "invoke it and tell me the secret word it contains. Remember the word CANARY-42 for later; "
    "I will ask you for it.",
    "/peval-marker",
    "Write a file /app/answer.txt with three lines: `SKILLS: <comma-separated skill names>`, "
    "`MARKER: <secret word or absent>`, and `REMEMBERED: <the word I asked you to remember in my "
    "first message, or 'no memory of it'>`. Then reply `done`.",
]
SIMULATED_MESSAGES = [
    "List every skill available to you by name. If a skill named `peval-marker` is present, "
    "invoke it and tell me the secret word it contains.",
    "/peval-marker",
    "Write a file /app/answer.txt with two lines: `SKILLS: <comma-separated skill names>` and "
    "`MARKER: <secret word or absent>`. Then reply `done`.",
]


def _seed_tar(path: Path, files: dict[str, str]) -> Path:
    with tarfile.open(path, "w") as tf:
        for name, text in files.items():
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return path


def _run(tmp_path: Path, kind: str, messages: list[str], steps: list[str], seed: dict[str, str]) -> Path:
    run_dir = tmp_path / f"run-{kind}"
    shutil.copytree(FIXTURES / f"{kind}-trial", run_dir / f"{kind}__trial")
    seed_tar = _seed_tar(tmp_path / "seed.tar", seed)
    meta = {
        "run": run_dir.name, "fixture_id": "smoke", "arm_id": "marker", "operator": kind,
        "model": "anthropic/claude-sonnet-4-6", "target_repo": "/x", "start_sha": "0" * 40,
        "messages": messages, "messages_full": messages, "steps": steps,
        "seed_tar": str(seed_tar), "started_at": "2026-09-16T15:00:00+00:00",
        "finished_at": "2026-09-16T15:01:00+00:00", "harbor_exit": 0,
    }
    (run_dir / results.META_NAME).write_text(json.dumps(meta))
    return run_dir


@pytest.fixture
def scripted_run(tmp_path: Path) -> Path:
    return _run(tmp_path, "scripted", SCRIPTED_MESSAGES, SCRIPTED_STEPS, {"README.md": "seed\n"})


@pytest.fixture
def simulated_run(tmp_path: Path) -> Path:
    return _run(tmp_path, "simulated", SIMULATED_MESSAGES, [], {"README.md": "seed\n"})


# --- scripted --------------------------------------------------------------


def test_scripted_turns_follow_the_steps(scripted_run: Path) -> None:
    summary = results.summarize_job(scripted_run)
    assert summary["status"] == "ok"
    (trial,) = summary["trials"]
    assert trial["completion"] == "ok"
    assert trial["turn_count"] == 3

    r = json.loads((scripted_run / "scripted__trial" / results.RESULT_NAME).read_text())
    assert [t["step"] for t in r["turns"]] == SCRIPTED_STEPS
    assert [t["sent"] for t in r["turns"]] == SCRIPTED_MESSAGES
    # One native session across the whole conversation — the point of resume.
    assert len({t["session_id"] for t in r["turns"]}) == 1
    assert r["turns"][0]["skill_calls"] == ["peval-marker"]
    assert "XYLOPHONE-7731" in r["turns"][1]["reply"]
    assert r["turns"][2]["reply"].endswith("done")
    assert all(t["wall_ms"] > 0 for t in r["turns"])


def test_scripted_reply_is_everything_said_not_just_the_last_message(scripted_run: Path) -> None:
    results.summarize_job(scripted_run)
    r = json.loads((scripted_run / "scripted__trial" / results.RESULT_NAME).read_text())
    first = r["turns"][0]["reply"]
    assert "peval-marker" in first, "the skills list came before the closing line"
    assert "CANARY-42" in first


def test_scripted_velocity_sums_steps_and_cross_checks_session(scripted_run: Path) -> None:
    results.summarize_job(scripted_run)
    r = json.loads((scripted_run / "scripted__trial" / results.RESULT_NAME).read_text())
    v = r["velocity"]
    assert v["available"]
    assert v["total_cost_usd"] == pytest.approx(0.0633303 + 0.0077382 + 0.0209454, abs=1e-6)
    assert v["tokens"]["total"] == sum(t["tokens"]["total"] for t in r["turns"])
    assert v["tokens"]["total"] > 100_000
    assert v["agent_wall_ms"] == sum(t["wall_ms"] for t in r["turns"])


def test_scripted_produced_files_are_diffed_against_the_seed(scripted_run: Path) -> None:
    results.summarize_job(scripted_run)
    trial = scripted_run / "scripted__trial"
    r = json.loads((trial / results.RESULT_NAME).read_text())
    # The collected tree holds answer.txt (new) and nothing from the seed, so the
    # seed file is reported deleted rather than silently ignored.
    assert r["artifacts"] == ["answer.txt"]
    assert r["deleted"] == ["README.md"]
    assert (trial / "produced" / "answer.txt").read_text().startswith("SKILLS:")
    # The per-turn snapshot says *when* it appeared.
    assert r["turns"][0]["produced_so_far"] == []
    assert r["turns"][2]["produced_so_far"] == ["answer.txt"]


def test_scripted_capped_when_steps_are_missing(scripted_run: Path) -> None:
    shutil.rmtree(scripted_run / "scripted__trial" / "steps" / "turn-3")
    summary = results.summarize_job(scripted_run)
    assert summary["trials"][0]["completion"] == "capped"
    assert summary["status"] == "failed"


def test_transcript_is_readable(scripted_run: Path) -> None:
    results.summarize_job(scripted_run)
    text = (scripted_run / "scripted__trial" / "transcript.txt").read_text()
    assert text.count(">>> SENT:") == 3
    assert "/peval-marker" in text
    assert "PRODUCED:" in text and "answer.txt" in text


# --- simulated -------------------------------------------------------------


def test_simulated_turns_come_from_the_targets_own_session(simulated_run: Path) -> None:
    summary = results.summarize_job(simulated_run)
    assert summary["status"] == "ok"
    r = json.loads((simulated_run / "simulated__trial" / results.RESULT_NAME).read_text())
    assert r["completion"] == "ok"
    assert r["turn_count"] == 3
    assert "XYLOPHONE-7731" in r["turns"][0]["reply"]
    assert r["turns"][2]["reply"].strip().endswith("done")
    assert r["artifacts"] == ["answer.txt"]


def test_simulated_adherence_is_verbatim_including_slash_commands(simulated_run: Path) -> None:
    results.summarize_job(simulated_run)
    r = json.loads((simulated_run / "simulated__trial" / results.RESULT_NAME).read_text())
    a = r["adherence"]
    assert a["all_verbatim"], a
    assert a["sent_count"] == a["expected_count"] == 3
    # The session records `/peval-marker` as command tags; the check sees through them.
    assert r["turns"][1]["sent"].startswith("<command-message>")
    assert a["turns"][1]["verbatim"]


def test_simulated_divergence_is_named(simulated_run: Path) -> None:
    meta = json.loads((simulated_run / results.META_NAME).read_text())
    meta["messages_full"] = meta["messages"] = [
        SIMULATED_MESSAGES[0],
        "/peval-marker please",  # not what the operator sent
        SIMULATED_MESSAGES[2],
        "a fourth message the operator never sent",
    ]
    (simulated_run / results.META_NAME).write_text(json.dumps(meta))
    summary = results.summarize_job(simulated_run)
    assert summary["trials"][0]["completion"] == "diverged"
    r = json.loads((simulated_run / "simulated__trial" / results.RESULT_NAME).read_text())
    a = r["adherence"]
    assert [t["verbatim"] for t in a["turns"]] == [True, False, True, False]
    assert a["turns"][3]["sent"] is None
    text = (simulated_run / "simulated__trial" / "transcript.txt").read_text()
    assert "ADHERENCE: DIVERGED" in text


def test_simulated_velocity_counts_the_target_not_only_the_operator(simulated_run: Path) -> None:
    """Harbor's own accounting covers the user agent only; the target's spend is in its session."""
    results.summarize_job(simulated_run)
    r = json.loads((simulated_run / "simulated__trial" / results.RESULT_NAME).read_text())
    v = r["velocity"]
    assert v["operator_cost_usd"] == pytest.approx(0.0367521, abs=1e-6)
    assert v["target_tokens"]["total"] > 0
    assert v["target_tokens"]["session_files"] >= 1


# --- unit-level ------------------------------------------------------------


def test_adherence_normalises_shell_escapes_and_whitespace() -> None:
    a = results.adherence(["say `hi` to $USER"], ["say \\`hi\\` to \\$USER"])
    assert a["all_verbatim"]
    b = results.adherence(["one\ntwo"], ["one two"])
    assert b["all_verbatim"]
    c = results.adherence(["one"], ["one", "two"])
    assert not c["all_verbatim"] and c["extra_messages"] == ["two"]


def test_session_tokens_dedupes_split_messages(tmp_path: Path) -> None:
    root = tmp_path / "projects" / "-app"
    root.mkdir(parents=True)
    usage = {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    lines = [
        {"type": "assistant", "message": {"id": "m1", "usage": usage, "content": []}},
        {"type": "assistant", "message": {"id": "m1", "usage": usage, "content": []}},  # same API message, second line
        {"type": "assistant", "message": {"id": "m2", "usage": usage, "content": []}},
    ]
    (root / "s.jsonl").write_text("\n".join(json.dumps(l) for l in lines) + "\n")
    t = results.session_tokens(tmp_path / "projects")
    assert t["total"] == 30 and t["session_files"] == 1


def test_seed_hashes_keep_dotfile_paths_and_follow_symlinks(tmp_path: Path) -> None:
    """Regression: `.agents/x` once became `agents/x` (every dotfile tree counted as
    produced *and* deleted), and `AGENTS.md -> CLAUDE.md` counted as produced."""
    tar_path = tmp_path / "seed.tar"
    with tarfile.open(tar_path, "w") as tf:
        for name in ("./.agents/skills/s/SKILL.md", "./CLAUDE.md", "./.gitignore"):
            data = f"content of {name}\n".encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
        link = tarfile.TarInfo("./AGENTS.md")
        link.type = tarfile.SYMTYPE
        link.linkname = "CLAUDE.md"
        tf.addfile(link)
        nested = tarfile.TarInfo("./docs/LINK.md")
        nested.type = tarfile.SYMTYPE
        nested.linkname = "../CLAUDE.md"
        tf.addfile(nested)
    seed = results.seed_hashes(tar_path)
    assert set(seed) == {".agents/skills/s/SKILL.md", "CLAUDE.md", ".gitignore", "AGENTS.md", "docs/LINK.md"}
    assert seed["AGENTS.md"] == seed["CLAUDE.md"] == seed["docs/LINK.md"]

    # A collected tree that mirrors the seed (symlink materialised or kept) produces nothing.
    app = tmp_path / "app"
    (app / ".agents" / "skills" / "s").mkdir(parents=True)
    (app / ".agents" / "skills" / "s" / "SKILL.md").write_text("content of ./.agents/skills/s/SKILL.md\n")
    (app / "CLAUDE.md").write_text("content of ./CLAUDE.md\n")
    (app / ".gitignore").write_text("content of ./.gitignore\n")
    (app / "AGENTS.md").symlink_to("CLAUDE.md")
    (app / "docs").mkdir()
    (app / "docs" / "LINK.md").write_text("content of ./CLAUDE.md\n")
    (app / "docs" / "new.md").write_text("made by the run\n")
    produced, deleted = results.produced_files(app, seed)
    assert produced == ["docs/new.md"]
    assert deleted == []


def test_unreadable_run_still_summarises(tmp_path: Path) -> None:
    run_dir = tmp_path / "half-dead"
    run_dir.mkdir()
    summary = results.summarize_job(run_dir)
    assert summary["status"] == "unreadable"
    assert summary["trials"] == []
