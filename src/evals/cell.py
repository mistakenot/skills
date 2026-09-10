"""The cell: one agent invocation in a clean room.

Lifted from `run_agent_arm_live` in `src/assurance/evals/run.sh` — a recipe that
is verified working, not a redesign. The isolation contract it implements is
documented in `docs/headless-claude-cli-evals.md` (re-verified against Claude
Code 2.1.260 on 2026-09-04).

Two rules from that document are load-bearing and easy to undo by accident:

  * The workspace must be OUTSIDE the repo tree. Claude Code walks up from cwd
    and re-discovers a parent repo's project skills and CLAUDE.md regardless of
    `CLAUDE_CONFIG_DIR`. Canary 2 enforces it.
  * The workspace must have no `CLAUDE.md`/`.claude/` in any ancestor. The CLI's
    project-root walk-up is name-based: an empty `/tmp/.git` that git rejects
    still makes `/tmp` a project root, so a `CLAUDE.md` anywhere above cwd is
    loaded as project instructions. Canary 4 enforces it.
  * Never pass `--setting-sources ''`. It isolates, but it also silently
    suppresses discovery of the skill under test, so the with-skill arm quietly
    becomes a second baseline.

The agent process itself is the one swappable part (`runners.py`): `live` spawns
`claude -p`, `stub` writes a canned transcript offline. Everything in this module
runs identically either way, which is what makes a stub run's evidence directory
structurally indistinguishable from a live one.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import canaries, runners
from .paths import REPO_ROOT

DEFAULT_MODEL = "claude-sonnet-4-6"
CREDENTIALS = Path.home() / ".claude" / ".credentials.json"


class CellError(RuntimeError):
    """The cell could not be set up. Distinct from the agent failing."""


@dataclass(frozen=True)
class CellResult:
    out_dir: Path
    exit_code: int
    workspace: Path
    config_dir: Path
    runner: str = runners.LIVE


def _install_skill(
    config_dir: Path,
    skill_name: str,
    skill_src: Path | None,
    companions: dict[str, Path] | None = None,
) -> None:
    """Copy the arm's skill into the clean room, or install nothing at all.

    `skill_src is None` is the `none` arm, and it must leave *no* `skills/`
    directory behind — not an empty one. An empty directory is a different
    condition from an absent one, and the baseline arm has to be the plain
    absence of the skill. Companions follow the same rule: they go in beside
    the skill under test, and only there. A `none` arm that carried the
    companions would be a baseline of a different experiment.
    """
    if skill_src is None:
        return
    dest = config_dir / "skills" / skill_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(skill_src, dest)
    for name, src in (companions or {}).items():
        shutil.copytree(src, dest.parent / name)


def _check_credentials(runner: str) -> None:
    """Refuse a live run with no credentials, before anything is set up.

    The stub never authenticates anything, so it is exempt — that exemption is
    what keeps the fast lane hermetic and runnable on a machine with no Claude
    login.
    """
    if runner == runners.STUB:
        return
    if not CREDENTIALS.is_file():
        raise CellError(
            f"no credentials at {CREDENTIALS}; the clean room authenticates by "
            f"copying that file into the relocated config dir"
        )


def _place_credentials(config_dir: Path, runner: str) -> None:
    """Put a `.credentials.json` in the relocated config dir.

    The live runner copies the real one. The stub writes an empty placeholder:
    the config dir keeps the same shape, and no real credential is copied into a
    run that cannot use one.
    """
    dest = config_dir / ".credentials.json"
    if runner == runners.STUB:
        dest.write_text("{}\n")
    else:
        shutil.copy2(CREDENTIALS, dest)


def extract_result_text(stream_path: Path) -> str:
    """Pull the final result envelope's text out of a stream-json transcript.

    `result` is the final assistant message only — earlier turns and tool
    narration are not in it. Everything else stays in `stream.jsonl`.
    """
    text = ""
    for line in stream_path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("type") == "result":
            text = event.get("result") or ""
    return text


def run_cell(
    out_dir: Path,
    skill_name: str,
    skill_src: Path | None,
    prompt: str,
    model: str = DEFAULT_MODEL,
    runner: str = runners.DEFAULT,
    fixture: Path | None = None,
    companions: dict[str, Path] | None = None,
) -> CellResult:
    """Run one prompt in an isolated clean room, leaving evidence in `out_dir`.

    On return `out_dir` holds `skill/` (exactly what was installed), `ws/` (the
    workspace as the agent left it), `stream.jsonl`, `out.md` and `err.txt` —
    the same five entries whichever runner was used. `skill_src=None` is the
    `none` arm: nothing is installed and there is no `skill/` to snapshot, so
    that arm's evidence directory has four entries rather than five.

    `runner` selects the agent process: `live` spawns `claude -p`, `stub` writes
    a canned transcript offline (see `runners.py`). `fixture`, if given, is a
    directory whose contents seed the workspace before the agent starts.
    `companions` ({name: source dir}) are installed beside the skill under test
    on every arm that installs it, and snapshotted under `with/<name>/` — a
    sixth entry present only when companions were given, so a cell without
    them keeps its five-entry shape.
    """
    run_agent = runners.get(runner)
    _check_credentials(runner)

    out_dir.mkdir(parents=True, exist_ok=True)

    # Outside the repo tree — claude walks up from cwd and finds .git. mktemp
    # honours TMPDIR, so this is asserted rather than assumed (canary 2).
    base = Path(tempfile.mkdtemp(prefix="evals-"))
    config_dir = base / "config"
    workspace = base / "ws"
    config_dir.mkdir(parents=True)
    workspace.mkdir(parents=True)

    companions = dict(companions or {})
    _place_credentials(config_dir, runner)
    _install_skill(config_dir, skill_name, skill_src, companions)
    if fixture is not None:
        shutil.copytree(fixture, workspace, dirs_exist_ok=True)

    # Before the process call, so the stub lane cannot pass a cell a live run
    # would have refused. A cheap check skipped in the fast lane is no check.
    installed = {skill_name, *companions} if skill_src is not None else set()
    canaries.check_all(
        config_dir=config_dir,
        workspace=workspace,
        repo_root=REPO_ROOT,
        expected_skills=installed,
    )

    # Snapshot what was installed before the agent can touch it: "what exactly
    # was in that arm?" is the first question a surprising result provokes.
    if skill_src is not None:
        shutil.copytree(
            config_dir / "skills" / skill_name, out_dir / "skill", dirs_exist_ok=True
        )
        for name in companions:
            shutil.copytree(
                config_dir / "skills" / name, out_dir / "with" / name, dirs_exist_ok=True
            )

    env = dict(os.environ)
    env["CLAUDE_CONFIG_DIR"] = str(config_dir)

    invocation = runners.Invocation(
        argv=runners.build_argv(prompt, model),
        cwd=workspace,
        env=env,
        prompt=prompt,
        model=model,
        # The `none` arm has no skill to name. Naming one anyway would let a
        # runner narrate an invocation that could not have happened.
        skill_name=skill_name if skill_src is not None else None,
    )

    stream_path = out_dir / "stream.jsonl"
    err_path = out_dir / "err.txt"
    with open(stream_path, "wb") as stream_f, open(err_path, "wb") as err_f:
        exit_code = run_agent(invocation, stream_f, err_f)

    (out_dir / "out.md").write_text(extract_result_text(stream_path))
    shutil.copytree(workspace, out_dir / "ws", dirs_exist_ok=True)

    return CellResult(
        out_dir=out_dir,
        exit_code=exit_code,
        workspace=workspace,
        config_dir=config_dir,
        runner=runner,
    )
