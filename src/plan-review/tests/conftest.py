"""Make the module importable and fake a finished planning-eval-harbor run."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

MODULE_DIR = Path(__file__).resolve().parent.parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

PLAN = """<!doctype html><html><head><title>t</title></head><body>
<pd-doc title="001: Thing">
<pd-tab name="Requirements"><p>The system must retry webhooks.</p>
<pd-question id="Q-1" status="open" title="Retry cap?" recommendedAnswer="5">why</pd-question></pd-tab>
<pd-tab name="Plan"><p>Phase 1: retry webhooks with backoff.</p></pd-tab>
</pd-doc></body></html>
"""


@pytest.fixture
def harbor_run(tmp_path: Path) -> Path:
    """`runs/<job>/` as planning-eval-harbor leaves it after a one-turn trial."""
    run = tmp_path / "harbor-runs" / "fx-1-skills-abc-scripted-20260101-000000"
    trial = run / "fx-1__trial1"
    task = trial / "produced" / "docs" / "tasks" / "001-thing"
    task.mkdir(parents=True)
    (task / "plan.html").write_text(PLAN)
    (task / "context.md").write_text("# context\nfiles read\n")
    (trial / "transcript.txt").write_text("=== turn 1\n> /new-task-quick ...\n")
    stream = trial / "steps" / "turn-01" / "agent"
    stream.mkdir(parents=True)
    (stream / "claude-code.txt").write_text('{"type":"system"}\n')
    (trial / "peval-result.json").write_text(json.dumps({
        "completion": "ok",
        "total_wall_ms": 1000,
        "turns": [{"skill_calls": ["new-task-quick"]}],
        "velocity": {"total_cost_usd": 1.25},
    }))
    (run / "peval.json").write_text(json.dumps({
        "fixture_id": "fx-1",
        "arm_id": "skills-abc",
        "skills_sha": "abc" * 13 + "a",
        "model": "anthropic/test",
        "target_repo": "/cache/repo",
        "repo_url": "https://example.com/repo.git",
        "start_sha": "f" * 40,
        "messages": ["/new-task-quick do it\n\nStop after Stage 4 (self-check); do not run the Codex review."],
    }))
    return run
