#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# ///
"""Fan a question out to independent coding-agent CLIs and collect their answers.

Plumbing for the consult-the-council skill. It knows how to run each member
(claude, codex, gemini, opencode, grok) headlessly in a read-only mode, in
parallel, with stdin closed, and how to turn each one's output into a plain
answer file. It adds nothing to the prompt: whatever is in the prompt file is
what every member sees, verbatim, so the parent controls framing entirely.

Usage:
    council.py members                          # who is installed and authed, in preference order
    council.py argv --member codex [--access repo|none] [--cwd DIR]
                                                # print the argv that would run (dry run)
    council.py preflight [--members a,b,c] [--quorum N]
                                                # probe each member with a PONG; exit 3 if under quorum
    council.py ask --prompt-file Q.md [--members a,b,c] [--access repo|none]
                   [--cwd DIR] [--out DIR] [--timeout SECS] [--attributed]
                   [--quorum N] [--skip-preflight]
                                                # preflight, then run the council with whoever passed
    council.py reveal --out DIR                 # print the blind-label -> member key

Preflight and quorum: `ask` first probes every requested member through its
real read-only argv. Members that are missing, not logged in, hung, or
returned nothing are dropped. If at least --quorum members remain (default 3,
or all requested when fewer) the council proceeds with them; otherwise it
stops with exit code 3 and the fix for each broken member.

Output layout (blind by default):
    OUT/question.md      the prompt, as sent
    OUT/A.md, B.md ...   one answer per member, labels shuffled
    OUT/A.log ...        raw stdout+stderr for that member
    OUT/key.json         {"A": "codex", ...}  — read this only after synthesis
    OUT/summary.json     {members: {<m>: status ok|timeout|auth|error|missing, ...}, preflight: {...}, quorum: N}

Exit codes: 0 all members that passed preflight answered; 1 at least one did
not; 2 usage error; 3 preflight left fewer members than the quorum.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

# Preference order: earlier is preferred when only some are available.
MEMBERS = ("claude", "codex", "gemini", "opencode", "grok")
ACCESS_MODES = ("repo", "none")
DEFAULT_TIMEOUT = 600
DEFAULT_QUORUM = 3
PROBE_PROMPT = "Reply with exactly: PONG"
PROBE_TIMEOUT = 120

# Output that means "you are not logged in", per member. Matched against the
# raw log so a hang or a fast failure both get classified as `auth`.
AUTH_MARKERS = {
    "claude": ("not logged in", "Invalid API key", "Please run /login", "OAuth token"),
    "codex": ("codex login", "not logged in", "Unauthorized"),
    "gemini": ("GEMINI_API_KEY", "must specify the GEMINI", "Please authenticate"),
    "opencode": ("no providers", "credentials", "not authenticated"),
    "grok": ("Waiting for authorization", "Only continue with a code you requested", "grok login"),
}

_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


# --- argv per member ----------------------------------------------------------


def build_argv(member: str, access: str, prompt: str, cwd: Path, answer_file: Path) -> list[str]:
    """The read-only headless invocation for one member.

    Every branch here is deliberately incapable of writing: plan modes, read-only
    sandboxes, or the read-only agent. A council member that can edit files is
    a worker, not a council member. The flags are pinned in the repo's agent
    CLI contract (src/planning-workflow/tests/agent-cli-contract.toml) so a CLI
    release that renames one fails a test rather than a council.
    """
    if member not in MEMBERS:
        raise ValueError(f"unknown member {member!r}; choose from {', '.join(MEMBERS)}")
    if access not in ACCESS_MODES:
        raise ValueError(f"unknown access mode {access!r}; choose from {', '.join(ACCESS_MODES)}")

    if member == "claude":
        # Read-only by tool allowlist rather than `--permission-mode plan`:
        # plan mode makes claude behave like a planning session (it wrote a
        # plan file and commented on missing planning tools) and took 20x
        # longer. `--add-dir` and `--tools` are both variadic, so the prompt
        # must come last, after the boolean `-p`.
        if access == "repo":
            return ["claude", "--add-dir", str(cwd), "--tools", "Read,Grep,Glob", "-p", prompt]
        return ["claude", "--tools", "", "-p", prompt]

    if member == "codex":
        argv = ["codex", "exec", "--cd", str(cwd), "--sandbox", "read-only", "-o", str(answer_file)]
        if access == "none":
            argv.append("--skip-git-repo-check")  # an empty temp dir is not a git repo
        return argv + [prompt]

    if member == "gemini":
        return ["gemini", "-p", prompt, "--approval-mode", "plan"]

    if member == "opencode":
        # `--dir` sets the project root (the process cwd is not enough). The
        # default output format drops the answer when stdout is not a TTY;
        # `--format json` emits it reliably as `text` events.
        return ["opencode", "run", "--dir", str(cwd), "--agent", "plan", "--format", "json", prompt]

    if member == "grok":
        return ["grok", "--cwd", str(cwd), "--permission-mode", "plan", "--single", prompt]

    raise AssertionError(member)


# --- answer extraction --------------------------------------------------------


def clean_answer(member: str, raw: str, answer_file: Path | None = None) -> str:
    """Turn a member's raw stdout into the answer text.

    codex writes the final message to `-o FILE`, so its stdout (session and
    tool noise) is ignored when that file exists. opencode emits JSON events
    and the answer is the `text` ones. The others print the answer.
    """
    if member == "codex" and answer_file is not None and answer_file.exists():
        return answer_file.read_text().strip()
    if member == "opencode":
        return _opencode_text(raw)
    return _ANSI.sub("", raw).strip()


def _opencode_text(raw: str) -> str:
    """Concatenate the `text` events of an `opencode run --format json` stream."""
    parts: list[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "text":
            continue
        text = event.get("part", {}).get("text") if isinstance(event.get("part"), dict) else None
        if text is None:
            text = event.get("text")
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


# --- availability -------------------------------------------------------------


def installed(member: str) -> bool:
    return shutil.which(member) is not None


def auth_hint(member: str) -> str:
    return {
        "claude": "claude login",
        "codex": "codex login",
        "gemini": "export GEMINI_API_KEY=... or select OAuth in ~/.gemini/settings.json",
        "opencode": "opencode auth login",
        "grok": "grok login",
    }[member]


# --- running ------------------------------------------------------------------


@dataclass
class Result:
    member: str
    status: str  # ok | timeout | auth | error | missing
    rc: int | None
    seconds: float
    answer: str
    log: str


def run_member(member: str, prompt: str, access: str, cwd: Path, workdir: Path, timeout: int, runner: str) -> Result:
    if runner == "stub":
        return _run_stub(member, prompt)
    if runner == "replay":
        return _run_replay(member, prompt, workdir)
    if not installed(member):
        return Result(member, "missing", None, 0.0, "", f"{member} is not on PATH")
    answer_file = workdir / f"{member}.answer"
    argv = build_argv(member, access, prompt, cwd, answer_file)
    start = time.monotonic()
    try:
        proc = subprocess.run(
            argv,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "NO_COLOR": "1", "TERM": "dumb"},
        )
        rc: int | None = proc.returncode
        stdout, stderr = proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = (p.decode(errors="replace") if isinstance(p, bytes) else (p or "") for p in (exc.stdout, exc.stderr))
        rc = None
    seconds = round(time.monotonic() - start, 1)
    return classify(member, rc, stdout, stderr, answer_file, seconds)


def classify(member: str, rc: int | None, stdout: str, stderr: str, answer_file: Path | None, seconds: float) -> Result:
    """Turn one member's process outcome into a Result. `rc is None` means it timed out.

    This is the whole of the judgement about what a CLI's output means, kept
    separate from process handling so recorded transcripts can be replayed
    through it (tests/fixtures/recorded/).
    """
    log = stdout + ("\n--- stderr ---\n" + stderr if stderr.strip() else "")
    if rc is None:
        log += "\n--- timed out ---"
    # Auth markers are only meaningful on a failed or hung run: a successful
    # answer *about* CLI auth can legitimately contain "codex login", and a
    # member that reads this repo will echo the marker strings it finds here.
    failed = rc is None or rc != 0
    if failed and any(marker in log for marker in AUTH_MARKERS[member]):
        return Result(member, "auth", rc, seconds, "", log)
    if rc is None:
        return Result(member, "timeout", rc, seconds, "", log)
    answer = clean_answer(member, stdout, answer_file)
    if rc != 0 or not answer:
        return Result(member, "error", rc, seconds, answer, log)
    return Result(member, "ok", rc, seconds, answer, log)


def _run_replay(member: str, prompt: str, workdir: Path) -> Result:
    """Replay a recorded transcript through `classify`.

    COUNCIL_REPLAY_DIR/<member>/ holds `stdout`, `stderr`, and either `rc` or a
    `timeout` marker file; `answer` is what codex wrote to its `-o FILE`. A
    probe (preflight) against a transcript that classifies `ok` answers PONG,
    so preflight sees the same pass/fail the real CLI would have produced.
    """
    root = Path(os.environ.get("COUNCIL_REPLAY_DIR", "")) / member
    if not root.is_dir():
        return Result(member, "missing", None, 0.0, "", f"no recorded transcript for {member} under {root.parent}")
    stdout = (root / "stdout").read_text() if (root / "stdout").exists() else ""
    stderr = (root / "stderr").read_text() if (root / "stderr").exists() else ""
    rc = None if (root / "timeout").exists() else int((root / "rc").read_text().strip() or 0)
    answer_file = None
    if (root / "answer").exists():
        answer_file = workdir / f"{member}.answer"
        answer_file.write_text((root / "answer").read_text())
    result = classify(member, rc, stdout, stderr, answer_file, 0.0)
    if prompt == PROBE_PROMPT and result.status == "ok":
        result.answer = "PONG"
    return result


def _run_stub(member: str, prompt: str) -> Result:
    """Offline runner for tests: canned answers, with failures injectable via env.

    COUNCIL_STUB_FAIL=codex,grok        -> those members fail with status `error`
    COUNCIL_STUB_AUTH=gemini            -> those members fail with status `auth`
    """
    failing = set(filter(None, os.environ.get("COUNCIL_STUB_FAIL", "").split(",")))
    unauthed = set(filter(None, os.environ.get("COUNCIL_STUB_AUTH", "").split(",")))
    if member in unauthed:
        return Result(member, "auth", 1, 0.0, "", f"stub auth failure for {member}")
    if member in failing:
        return Result(member, "error", 1, 0.0, "", f"stub failure for {member}")
    if prompt == PROBE_PROMPT:
        return Result(member, "ok", 0, 0.0, "PONG", "stub probe")
    return Result(member, "ok", 0, 0.0, f"STUB ANSWER from {member}: the question has more than one reasonable reading.", "stub")


def preflight(members: list[str], runner: str, timeout: int = PROBE_TIMEOUT) -> list[Result]:
    """Probe each member with a one-line prompt through its real read-only argv.

    A pass means the CLI is installed, logged in, accepts the flags we use,
    finishes, and its output parses to the expected text. Anything else is a
    member that would have failed the council anyway; better to learn it in
    two minutes than after a ten-minute question.
    """
    empty = Path(tempfile.mkdtemp(prefix="council-probe-"))
    workdir = Path(tempfile.mkdtemp(prefix="council-probe-work-"))
    try:
        with ThreadPoolExecutor(max_workers=len(members)) as pool:
            results = list(pool.map(
                lambda m: run_member(m, PROBE_PROMPT, "none", empty, workdir, timeout, runner),
                members,
            ))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
        shutil.rmtree(empty, ignore_errors=True)
    for r in results:
        if r.status == "ok" and "PONG" not in r.answer:
            r.status = "error"
            r.log += "\n--- probe answer did not contain PONG ---"
    return results


def effective_quorum(requested: int, quorum: int | None) -> int:
    """Default quorum is 3, capped at the number of members asked for."""
    return min(requested, DEFAULT_QUORUM if quorum is None else quorum)


def print_preflight(results: list[Result], quorum: int) -> None:
    width = max(len(r.member) for r in results)
    print("preflight:")
    for r in results:
        line = f"  {r.member:<{width}}  {r.status:<8}  {r.seconds:>6.1f}s"
        if r.status == "auth":
            line += f"  (run: {auth_hint(r.member)})"
        elif r.status == "missing":
            line += "  (not on PATH)"
        elif r.status in ("timeout", "error"):
            line += "  (see preflight log)"
        print(line)
    ok = sum(1 for r in results if r.status == "ok")
    print(f"  {ok}/{len(results)} usable, quorum {quorum}")


def preflight_cmd(args: argparse.Namespace) -> int:
    try:
        members = select_members(args.members)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    quorum = effective_quorum(len(members), args.quorum)
    results = preflight(members, args.runner, args.timeout)
    print_preflight(results, quorum)
    usable = [r.member for r in results if r.status == "ok"]
    if len(usable) < quorum:
        print(_quorum_failure(results, quorum), file=sys.stderr)
        return 3
    return 0


def _quorum_failure(results: list[Result], quorum: int) -> str:
    usable = [r.member for r in results if r.status == "ok"]
    lines = [f"council cannot meet quorum: {len(usable)} usable member(s), {quorum} required."]
    for r in results:
        if r.status == "ok":
            continue
        fix = {
            "auth": f"run `{auth_hint(r.member)}`",
            "missing": f"install {r.member} (not on PATH)",
            "timeout": "hung; check auth and network, then rerun preflight",
            "error": "failed; see the preflight log",
        }[r.status]
        lines.append(f"  {r.member}: {r.status} — {fix}")
    lines.append("Fix the members above, or lower --quorum, then rerun.")
    return "\n".join(lines)


def select_members(requested: str | None) -> list[str]:
    """Requested members in preference order; all members when none requested."""
    if not requested:
        return list(MEMBERS)
    wanted = [m.strip() for m in requested.split(",") if m.strip()]
    unknown = [m for m in wanted if m not in MEMBERS]
    if unknown:
        raise ValueError(f"unknown member(s) {unknown}; choose from {', '.join(MEMBERS)}")
    return [m for m in MEMBERS if m in wanted]


def labels_for(members: list[str], attributed: bool, rng: random.Random) -> dict[str, str]:
    """member -> file label. Blind labels are letters in shuffled order."""
    if attributed:
        return {m: m for m in members}
    letters = [chr(ord("A") + i) for i in range(len(members))]
    rng.shuffle(letters)
    return dict(zip(members, letters))


def ask(args: argparse.Namespace) -> int:
    prompt_path = Path(args.prompt_file)
    if not prompt_path.is_file():
        print(f"prompt file not found: {prompt_path}", file=sys.stderr)
        return 2
    prompt = prompt_path.read_text()
    if not prompt.strip():
        print("prompt file is empty", file=sys.stderr)
        return 2
    try:
        members = select_members(args.members)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    out = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="council-"))
    out.mkdir(parents=True, exist_ok=True)

    quorum = effective_quorum(len(members), args.quorum)
    preflight_summary: dict[str, dict] = {}
    if not args.skip_preflight:
        probes = preflight(members, args.runner)
        print_preflight(probes, quorum)
        for r in probes:
            preflight_summary[r.member] = {"status": r.status, "seconds": r.seconds}
            if r.status != "ok":
                (out / f"preflight-{r.member}.log").write_text(r.log)
        usable = [r.member for r in probes if r.status == "ok"]
        if len(usable) < quorum:
            print(_quorum_failure(probes, quorum), file=sys.stderr)
            return 3
        dropped = [m for m in members if m not in usable]
        if dropped:
            print(f"  proceeding without {', '.join(dropped)}")
        members = usable
    if args.access == "repo":
        cwd = Path(args.cwd or os.getcwd()).resolve()
    else:
        cwd = Path(tempfile.mkdtemp(prefix="council-empty-"))
    workdir = Path(tempfile.mkdtemp(prefix="council-work-"))
    (out / "question.md").write_text(prompt)

    with ThreadPoolExecutor(max_workers=len(members)) as pool:
        results = list(pool.map(
            lambda m: run_member(m, prompt, args.access, cwd, workdir, args.timeout, args.runner),
            members,
        ))

    labels = labels_for(members, args.attributed, random.Random(args.seed))
    summary = {}
    for r in results:
        label = labels[r.member]
        (out / f"{label}.log").write_text(r.log)
        if r.status == "ok":
            (out / f"{label}.md").write_text(r.answer + "\n")
        summary[r.member] = {
            "status": r.status,
            "rc": r.rc,
            "seconds": r.seconds,
            "label": label,
            "answer_file": f"{label}.md" if r.status == "ok" else None,
            "hint": auth_hint(r.member) if r.status == "auth" else None,
        }
    (out / "key.json").write_text(json.dumps({labels[m]: m for m in members}, indent=2, sort_keys=True) + "\n")
    (out / "summary.json").write_text(json.dumps({"members": summary, "preflight": preflight_summary, "quorum": quorum}, indent=2) + "\n")
    shutil.rmtree(workdir, ignore_errors=True)

    print(f"council output: {out}")
    width = max(len(m) for m in members)
    for r in results:
        line = f"  {r.member:<{width}}  {r.status:<8}  {r.seconds:>6.1f}s"
        if r.status == "ok":
            line += f"  -> {labels[r.member]}.md"
        elif r.status == "auth":
            line += f"  (run: {auth_hint(r.member)})"
        elif r.status == "missing":
            line += "  (not on PATH)"
        else:
            line += f"  (see {labels[r.member]}.log)"
        print(line)
    answered = sum(1 for r in results if r.status == "ok")
    print(f"{answered}/{len(members)} answered." + ("" if args.attributed else " Labels are blind; key.json maps them after synthesis."))
    return 0 if answered == len(members) else 1


def members_cmd(_args: argparse.Namespace) -> int:
    print(f"{'member':<9} {'pref':>4}  installed")
    for i, m in enumerate(MEMBERS, start=1):
        print(f"{m:<9} {i:>4}  {'yes' if installed(m) else 'no'}")
    print("\nAuth is only discoverable by asking; a member that is installed but not logged in\n"
          "reports status `auth` from `ask`, with the login command to run.")
    return 0


def argv_cmd(args: argparse.Namespace) -> int:
    cwd = Path(args.cwd or os.getcwd()).resolve()
    try:
        argv = build_argv(args.member, args.access, "<PROMPT>", cwd, Path("<ANSWER_FILE>"))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(argv))
    return 0


def reveal_cmd(args: argparse.Namespace) -> int:
    key = Path(args.out) / "key.json"
    if not key.is_file():
        print(f"no key.json in {args.out}", file=sys.stderr)
        return 2
    for label, member in sorted(json.loads(key.read_text()).items()):
        print(f"{label}  {member}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="council.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("members", help="list members in preference order with install status").set_defaults(fn=members_cmd)

    p = sub.add_parser("argv", help="print the argv that `ask` would run for one member")
    p.add_argument("--member", required=True, choices=MEMBERS)
    p.add_argument("--access", default="repo", choices=ACCESS_MODES)
    p.add_argument("--cwd")
    p.set_defaults(fn=argv_cmd)

    p = sub.add_parser("preflight", help="probe each member with a PONG through its real argv; exit 3 under quorum")
    p.add_argument("--members", help="comma-separated subset; default all")
    p.add_argument("--quorum", type=int, default=None, help=f"minimum usable members (default {DEFAULT_QUORUM}, or all requested if fewer)")
    p.add_argument("--timeout", type=int, default=PROBE_TIMEOUT, help=f"seconds per probe (default {PROBE_TIMEOUT})")
    p.add_argument("--runner", default=os.environ.get("COUNCIL_RUNNER", "live"), choices=("live", "stub", "replay"))
    p.set_defaults(fn=preflight_cmd)

    p = sub.add_parser("ask", help="preflight the members, then send the prompt file and collect answers")
    p.add_argument("--prompt-file", required=True, help="file whose contents are sent verbatim")
    p.add_argument("--members", help="comma-separated subset; default all, always in preference order")
    p.add_argument("--access", default="repo", choices=ACCESS_MODES,
                   help="repo: read-only access to --cwd (default); none: an empty directory")
    p.add_argument("--cwd", help="repo root for --access repo (default: current directory)")
    p.add_argument("--out", help="output directory (default: a fresh temp dir)")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"seconds per member (default {DEFAULT_TIMEOUT})")
    p.add_argument("--attributed", action="store_true", help="name answer files by member instead of blind letters")
    p.add_argument("--quorum", type=int, default=None, help=f"minimum members that must pass preflight (default {DEFAULT_QUORUM}, or all requested if fewer)")
    p.add_argument("--skip-preflight", action="store_true", help="do not probe members first (you already ran `preflight`)")
    p.add_argument("--seed", type=int, default=None, help="seed for the blind-label shuffle (tests)")
    p.add_argument("--runner", default=os.environ.get("COUNCIL_RUNNER", "live"), choices=("live", "stub", "replay"),
                   help="stub: canned answers; replay: recorded transcripts from COUNCIL_REPLAY_DIR (tests)")
    p.set_defaults(fn=ask)

    p = sub.add_parser("reveal", help="print the blind-label -> member key for an output dir")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=reveal_cmd)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
