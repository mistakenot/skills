"""Repo and run-directory locations.

`runs/` accumulates: every run gets its own id and nothing is ever cleared. The
current assurance harness wipes its inspect dir on each run and keeps only the
last, which makes "what exactly was in that arm?" unanswerable a day later.
"""

from __future__ import annotations

import datetime as _dt
import re
import secrets
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent
REPO_ROOT = MODULE_DIR.parent.parent
RUNS_DIR = MODULE_DIR / "runs"
COMPILED_SKILLS_DIR = REPO_ROOT / "skills"
COMPILER = REPO_ROOT / "src" / "compile.py"

# The shape `new_run_id` produces. The tail is `{4,8}` rather than a fixed width
# so that runs made before the id gained its sub-second component are still
# recognised as runs — they are still evidence, and `list` and `clean` have to
# see them.
_RUN_ID_RE = re.compile(r"\d{8}-\d{6}-[0-9a-f]{4,8}")


def new_run_id() -> str:
    """A sortable, collision-resistant run id.

    Sortable *to the microsecond*, deliberately. `evals list` orders runs by
    sorting their names, and a whole-second stamp puts two runs made in the same
    second in random-tail order — which is to say, in no order at all. Three
    stub runs in a row is exactly the case where that shows.

    The two random hex digits stay on the end: they cost nothing and they settle
    the tie between two processes that genuinely landed in the same microsecond.
    """
    now = _dt.datetime.now()
    stamp = now.strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{now.microsecond:05x}{secrets.token_hex(1)}"


def cell_dir(runs_dir: Path, run_id: str, arm: str, trial: int) -> Path:
    """`runs/<run-id>/<arm>/<trial>/` — one agent invocation's evidence."""
    return runs_dir / run_id / arm / str(trial)


def run_dir(runs_dir: Path, run_id: str) -> Path:
    """`runs/<run-id>/` — one comparison's whole tree."""
    return runs_dir / run_id


def arm_dir(runs_dir: Path, run_id: str, arm: str) -> Path:
    """`runs/<run-id>/<arm>/` — one arm's cells and its provenance records."""
    return runs_dir / run_id / arm


def runs_root() -> Path:
    """`RUNS_DIR` looked up at call time, so tests can relocate it."""
    return RUNS_DIR


def list_runs(runs_dir: Path | None = None) -> list[Path]:
    """Every run directory, newest first.

    Run ids are `%Y%m%d-%H%M%S-<hex>`, so a reverse lexical sort *is* newest
    first and needs no stat call — but a directory whose name is not a run id
    has no such guarantee, so those sort after the real runs rather than
    interleaving with them on a name that means nothing.
    """
    root = runs_root() if runs_dir is None else runs_dir
    if not root.is_dir():
        return []
    entries = [p for p in root.iterdir() if p.is_dir()]
    return sorted(entries, key=lambda p: (is_run_id(p.name), p.name), reverse=True)


def is_run_id(name: str) -> bool:
    """Whether `name` has the shape `new_run_id` produces."""
    return bool(_RUN_ID_RE.fullmatch(name))
