"""The Harbor job: its config, and how it is launched.

The harness never imports `harbor`. It writes a `JobConfig` JSON (the same
schema `harbor run --config` reads and `harbor run --print-config` emits) and
runs the `harbor` CLI as a subprocess, so the exact command is reproducible by
hand and the config sits in the run directory as evidence. Harbor rewrites its
own resolved copy to `<run>/config.json` and the provenance — task digest, every
injected skill's content digest — to `<run>/lock.json`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from fixture import Fixture
from task import SCRIPTED, SIMULATED, BuiltTask

HERE = Path(__file__).resolve().parent
AGENT_IMPORT = "peval_agents:ClaudeCodeReplay"
CREDENTIALS = Path.home() / ".claude" / ".credentials.json"
HARBOR_MIN = (0, 23, 0)

# Matches src/evals' pinned default so a planning replay and a single-shot eval
# of the same skills are on the same model unless someone says otherwise.
DEFAULT_MODEL = "anthropic/claude-sonnet-4-6"


class JobError(RuntimeError):
    """The job cannot be launched. Raised before any token is spent."""


def harbor_bin() -> str:
    """The module's own `harbor`, or whatever is on PATH — checked for version.

    Simulated-user trials need >= 0.22 and this module was verified on 0.23;
    an older tool install (0.18 was found on this machine) silently lacks the
    flags and would fail after the image build.
    """
    venv = HERE / ".venv" / "bin" / "harbor"
    exe = str(venv) if venv.is_file() else shutil.which("harbor")
    if not exe:
        raise JobError(
            "harbor not found: run `uv sync --project src/planning-eval-harbor`"
        )
    out = subprocess.run([exe, "--version"], capture_output=True, text=True)
    ver = out.stdout.strip().split()[-1] if out.stdout.strip() else ""
    try:
        parts = tuple(int(p) for p in ver.split(".")[:3])
    except ValueError:
        raise JobError(f"could not parse harbor version {ver!r} from {exe}") from None
    if parts < HARBOR_MIN:
        raise JobError(
            f"{exe} is harbor {ver}; this harness needs >= "
            f"{'.'.join(map(str, HARBOR_MIN))} (simulated users, multi-step resume)"
        )
    return exe


def check_credentials() -> dict:
    """Fail fast if the credentials file is missing; report its expiry.

    The sandbox authenticates from a copy of this file (see peval_agents.py).
    An expired access token is not fatal — Claude Code refreshes it with the
    refresh token — so expiry is returned for the record rather than raised.
    """
    if not CREDENTIALS.is_file():
        raise JobError(f"{CREDENTIALS} not found; log in with `claude` first")
    try:
        data = json.loads(CREDENTIALS.read_text())
        expires_ms = int(data["claudeAiOauth"]["expiresAt"])
    except (OSError, ValueError, KeyError, TypeError):
        return {"path": str(CREDENTIALS), "expires_at": None}
    return {
        "path": str(CREDENTIALS),
        "expires_at": expires_ms,
        "expired": expires_ms < int(time.time() * 1000),
    }


def build_config(
    built: BuiltTask,
    fx: Fixture,
    jobs_dir: Path,
    job_name: str,
    trials: int = 1,
    model: str = DEFAULT_MODEL,
    concurrent: int = 1,
) -> dict:
    """A Harbor `JobConfig` for one arm of one fixture."""
    kwargs: dict = {}
    if fx.limits.max_budget_usd is not None:
        # Claude Code's own spend cap; Harbor passes it as --max-budget-usd.
        kwargs["max_budget_usd"] = f"{fx.limits.max_budget_usd:g}"
    agent: dict = {
        "import_path": AGENT_IMPORT,
        "model_name": model,
        "skills": [str(fx.skills_dir)],
        "kwargs": kwargs,
    }
    if built.operator == SCRIPTED:
        # One native session across every step: the conversation, not a series
        # of fresh agents each handed one message.
        agent["resume_trajectory"] = True
    cfg: dict = {
        "job_name": job_name,
        "jobs_dir": str(jobs_dir),
        "n_attempts": trials,
        "n_concurrent_trials": concurrent,
        "agents": [agent],
        "tasks": [{"path": str(built.dir)}],
        # The whole workspace, minus git internals. What the run *produced* is
        # worked out on the host afterwards by diffing against the seed tree
        # (results.produced_files), so no verifier is needed to capture it.
        "artifacts": [{"source": "/app", "destination": "app", "exclude": [".git"]}],
        "verifier": {"disable": True},
        "environment": {"type": "docker"},
    }
    if built.operator == SIMULATED:
        cfg["user_agent"] = {
            "import_path": AGENT_IMPORT,
            "model_name": model,
            "user_persona_path": str(built.dir / "persona.md"),
            "bridge": {"kind": "acp"},
        }
    return cfg


def write_config(cfg: dict, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2) + "\n")
    return path


def harbor_env() -> dict[str, str]:
    """The environment the harbor subprocess runs in.

    `PYTHONPATH` makes `peval_agents` importable by Harbor. No auth variable is
    exported: the agent seeds the credentials file itself, so the token never
    has to survive the shell hops inside the sandbox.
    """
    env = dict(os.environ)
    env["HARBOR_TELEMETRY"] = "off"
    env["PYTHONPATH"] = str(HERE) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return env


def argv(exe: str, config_path: Path, dry_run: bool = False) -> list[str]:
    cmd = [exe, "run", "--config", str(config_path), "--yes"]
    if dry_run:
        cmd.append("--dry-run")
    return cmd


def run_harbor(exe: str, config_path: Path, dry_run: bool = False) -> int:
    """Run the job, streaming Harbor's own progress to the terminal."""
    completed = subprocess.run(
        argv(exe, config_path, dry_run),
        env=harbor_env(),
        cwd=str(HERE),
        stdin=subprocess.DEVNULL,
    )
    return completed.returncode
