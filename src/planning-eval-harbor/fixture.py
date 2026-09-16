"""Fixture loading.

A fixture is the same JSON `src/planning-eval/` uses — target repo, immutable
start SHA, opening prompt, the operator's `human_turns`, the arm's skills
directory, and limits — so one file can drive either harness and the two can be
compared on identical input. See `src/planning-eval/README.md` ("Authoring a
fixture") for how to mine one from a real task.

Two optional additions this harness reads and planning-eval ignores:

  * `limits.max_budget_usd` — a hard spend cap handed to Claude Code.
  * `persona` — text for the simulated operator (`--operator simulated` only).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent

# Verbatim from src/planning-eval/run.py, so the two harnesses hand the agent
# the same opening context and a comparison between them is fair.
HARNESS_PREAMBLE = (
    "[EVAL HARNESS] You are driven programmatically by an evaluation harness, not a live "
    "human at a terminal. Do NOT use interactive question tools or menus (AskUserQuestion) — "
    "they cannot be answered and will stall you. When a decision is needed, proceed on your "
    "best judgment and record genuinely load-bearing open decisions as pd-questions with a "
    "recommendedAnswer (the workflow's autonomous mode). If you must ask, ask in plain text "
    "and keep going; operator replies arrive as ordinary chat messages. Task follows:\n\n"
)

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class FixtureError(ValueError):
    """The fixture file cannot drive a run."""


@dataclass(frozen=True)
class Limits:
    max_turns: int = 12
    wall_clock_s: int = 1800
    per_turn_timeout_s: int = 600
    max_budget_usd: float | None = None


@dataclass(frozen=True)
class Fixture:
    id: str
    path: Path
    target_repo: Path
    start_sha: str
    prompt: str
    arm_id: str
    skills_dir: Path
    human_turns: tuple[str, ...]
    limits: Limits
    persona: str | None = None

    @property
    def messages(self) -> list[str]:
        """Everything the operator sends, in order, capped at `max_turns`.

        The first message carries the harness preamble, exactly as planning-eval
        prepends it; `max_turns` counts the opening prompt, as it does there.
        """
        msgs = [HARNESS_PREAMBLE + self.prompt, *self.human_turns]
        return msgs[: self.limits.max_turns]

    @property
    def shown_messages(self) -> list[str]:
        """The messages as a reader should see them — preamble stripped."""
        return [m.split("Task follows:\n\n")[-1] for m in self.messages]


def _require(d: dict, key: str, ctx: str) -> object:
    if key not in d:
        raise FixtureError(f"{ctx}: missing required key {key!r}")
    return d[key]


def _int(d: dict, key: str, default: int) -> int:
    v = d.get(key, default)
    if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
        raise FixtureError(f"limits.{key} must be a positive integer, got {v!r}")
    return v


def load(path: Path | str, repo_root: Path = REPO_ROOT) -> Fixture:
    """Read and validate a fixture. Every check here fails before a token is spent."""
    path = Path(path).resolve()
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise FixtureError(f"cannot read fixture {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise FixtureError(f"{path}: top level must be a JSON object")

    fid = _require(data, "id", str(path))
    if not isinstance(fid, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", fid):
        raise FixtureError(f"{path}: id must be a filename-safe string, got {fid!r}")

    fx = _require(data, "fixture", str(path))
    arm = _require(data, "arm", str(path))
    if not isinstance(fx, dict) or not isinstance(arm, dict):
        raise FixtureError(f"{path}: 'fixture' and 'arm' must be objects")

    sha = str(_require(fx, "start_sha", "fixture"))
    if not _SHA_RE.fullmatch(sha):
        # planning-eval refuses HEAD/main; this refuses anything that is not a
        # literal commit, for the same reason: a floating ref drifts between
        # runs and two runs a week apart stop being comparable.
        raise FixtureError(
            f"fixture.start_sha must be a literal 40-character commit sha, got {sha!r}"
        )

    target_repo = Path(str(_require(fx, "target_repo", "fixture"))).expanduser()
    if not (target_repo / ".git").exists():
        raise FixtureError(f"fixture.target_repo is not a git checkout: {target_repo}")

    prompt = _require(fx, "prompt", "fixture")
    if not isinstance(prompt, str) or not prompt.strip():
        raise FixtureError("fixture.prompt must be a non-empty string")

    arm_id = str(_require(arm, "id", "arm"))
    if not re.fullmatch(r"[A-Za-z0-9._-]+", arm_id):
        raise FixtureError(f"arm.id must be a filename-safe string, got {arm_id!r}")
    skills_dir = Path(str(_require(arm, "skills_dir", "arm")))
    if not skills_dir.is_absolute():
        skills_dir = repo_root / skills_dir
    skills_dir = skills_dir.resolve()
    if not skills_dir.is_dir():
        raise FixtureError(f"arm.skills_dir does not exist: {skills_dir}")
    bad = sorted(
        p.name for p in skills_dir.iterdir() if p.is_dir() and not (p / "SKILL.md").is_file()
    )
    if bad:
        # Harbor's skill loader takes a root whose immediate children are each a
        # skill; a stray directory there fails the trial after the image build.
        raise FixtureError(
            f"arm.skills_dir children without SKILL.md: {', '.join(bad)} ({skills_dir})"
        )

    turns = data.get("human_turns", [])
    if not isinstance(turns, list) or not all(isinstance(t, str) and t.strip() for t in turns):
        raise FixtureError("human_turns must be a list of non-empty strings")

    lim = data.get("limits", {})
    if not isinstance(lim, dict):
        raise FixtureError("limits must be an object")
    budget = lim.get("max_budget_usd")
    if budget is not None and (not isinstance(budget, (int, float)) or budget <= 0):
        raise FixtureError(f"limits.max_budget_usd must be a positive number, got {budget!r}")
    limits = Limits(
        max_turns=_int(lim, "max_turns", 12),
        wall_clock_s=_int(lim, "wall_clock_s", 1800),
        per_turn_timeout_s=_int(lim, "per_turn_timeout_s", 600),
        max_budget_usd=float(budget) if budget is not None else None,
    )

    persona = data.get("persona")
    if persona is not None and not isinstance(persona, str):
        raise FixtureError("persona must be a string")

    return Fixture(
        id=fid,
        path=path,
        target_repo=target_repo.resolve(),
        start_sha=sha,
        prompt=prompt,
        arm_id=arm_id,
        skills_dir=skills_dir,
        human_turns=tuple(turns),
        limits=limits,
        persona=persona,
    )
