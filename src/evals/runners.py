"""The runner seam: how the agent process is actually run.

`live` spawns `claude -p`. `stub` writes a canned transcript and leaves the
artefacts the agent would have left, so every part of a run except the agent's
judgment is exercisable in milliseconds — offline, unbilled, and safe to loop on.
Ported from `run_agent_arm` in `src/assurance/evals/run.sh:92-155`, which already
solves this; this is the same seam in Python.

**The seam is placed as late as possible — at the process call itself.**
Everything that shapes the run directory (isolation canaries, the installed-skill
snapshot, result extraction, workspace copy-out) lives in `cell.py` and is shared
verbatim by both runners. A stub run is structurally indistinguishable from a
live one by construction, not by two implementations kept in sync by hand. If the
seam is ever widened to "a stub cell" and "a live cell", the shapes will drift
and the fast lane will start testing a layout that never ships.

**The stub's transcript is modelled on a recorded live run**, kept at
`tests/fixtures/live-stream.jsonl`; `tests/test_stream_parity.py` asserts the
event shapes still match it. The point is that the invocation parser
(skills-7k7.4) is exercised by real-looking `tool_use` blocks rather than by a
simplification that would let it pass here and fail in production.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path

LIVE = "live"
STUB = "stub"
CHOICES = (LIVE, STUB)
DEFAULT = LIVE

# Values the stub stamps into its canned transcript. Chosen to look like a real
# 2.1.260 run; none of them is a contract.
STUB_CLI_VERSION = "2.1.260"
STUB_TIMESTAMP = "2026-09-04T12:13:16.000Z"

# A plausible built-in skill floor, copied from a real `system/init` event on
# Claude Code 2.1.260. It exists so the stub's init event looks like the real
# thing. It is NOT a contract and nothing may assert against it: the floor drifts
# by CLI version *and* by environment, and agent self-report disagrees with the
# init event by 4-5 entries on the same binary. See "The irreducible floor" in
# docs/headless-claude-cli-evals.md. `test_stub_floor_is_not_load_bearing`
# rewrites this list and requires a stub run to be unaffected.
STUB_BUILTIN_SKILLS = (
    "batch", "claude-api", "code-review", "dataviz", "debug", "deep-research",
    "design-sync", "doctor", "fewer-permission-prompts", "handoff", "loop",
    "run", "run-skill-generator", "schedule", "simplify", "update-config",
    "verify", "workflow-authoring",
)

STUB_TOOLS = (
    "Task", "Bash", "Edit", "Glob", "Grep", "NotebookEdit", "Read", "Skill",
    "TodoWrite", "WebFetch", "WebSearch", "Write",
)


class RunnerError(RuntimeError):
    """The runner name is not one we know how to dispatch."""


@dataclass(frozen=True)
class Invocation:
    """Everything a runner needs. Built once in `cell.py`, used by both runners."""

    argv: list[str]
    cwd: Path
    env: dict[str, str]
    prompt: str
    model: str
    skill_name: str | None


def build_argv(prompt: str, model: str) -> list[str]:
    """The verified clean-room invocation (docs/headless-claude-cli-evals.md).

    Never add `--setting-sources ''`: it isolates, but it also silently
    suppresses discovery of the skill under test, so the with-skill arm quietly
    becomes a second baseline.
    """
    return [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--strict-mcp-config",
        "--permission-mode",
        "bypassPermissions",
        "--model",
        model,
    ]


def run_live(inv: Invocation, stdout, stderr) -> int:
    """Spawn `claude -p`. Costs money and minutes; needs the network."""
    completed = subprocess.run(
        inv.argv,
        cwd=inv.cwd,
        env=inv.env,
        stdin=subprocess.DEVNULL,
        stdout=stdout,
        stderr=stderr,
    )
    return completed.returncode


# --- the stub --------------------------------------------------------------


def _uid(seed: str, n: int) -> str:
    """A deterministic stand-in for a uuid: same inputs, same transcript."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"evals-stub:{seed}:{n}"))


def _usage() -> dict:
    return {
        "input_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 0},
        "output_tokens": 0,
        "service_tier": "standard",
        "inference_geo": "not_available",
    }


def _assistant(session: str, n: int, model: str, content: list[dict]) -> dict:
    return {
        "type": "assistant",
        "message": {
            "model": model,
            "id": f"msg_stub{n:04d}",
            "type": "message",
            "role": "assistant",
            "content": content,
            "stop_reason": None,
            "stop_sequence": None,
            "stop_details": None,
            "usage": _usage(),
            "diagnostics": None,
            "context_management": None,
        },
        "parent_tool_use_id": None,
        "session_id": session,
        "uuid": _uid(session, n),
        "timestamp": STUB_TIMESTAMP,
        "request_id": f"req_stub{n:04d}",
    }


def _tool_result(session: str, n: int, tool_use_id: str, content: str, result: dict) -> dict:
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {"tool_use_id": tool_use_id, "type": "tool_result", "content": content}
            ],
        },
        "parent_tool_use_id": None,
        "session_id": session,
        "uuid": _uid(session, n),
        "timestamp": STUB_TIMESTAMP,
        "tool_use_result": result,
    }


def _init_event(inv: Invocation, session: str, config_dir: str) -> dict:
    """The `system/init` event — ground truth for what the agent could see.

    The skill list is assembled from the built-in floor plus whatever the cell
    installed, so a `none` arm's stub init genuinely lacks the skill. Read it;
    never compare it to a constant.
    """
    skills = sorted({*STUB_BUILTIN_SKILLS, *([inv.skill_name] if inv.skill_name else [])})
    return {
        "type": "system",
        "subtype": "init",
        "cwd": str(inv.cwd),
        "session_id": session,
        "tools": list(STUB_TOOLS),
        "mcp_servers": [],
        "model": inv.model,
        "permissionMode": "bypassPermissions",
        "slash_commands": skills,
        "terminal_slash_commands": ["doctor", "color", "reload-plugins"],
        "apiKeySource": "none",
        "claude_code_version": STUB_CLI_VERSION,
        "output_style": "default",
        "agents": ["claude", "Explore", "general-purpose", "Plan"],
        "skills": skills,
        "plugins": [],
        "capabilities": ["interrupt_receipt_v1", "msg_lifecycle_v1"],
        "analytics_disabled": False,
        "product_feedback_disabled": False,
        "uuid": _uid(session, 0),
        "memory_paths": {"auto": f"{config_dir}/projects/-tmp/memory/"},
        "messaging_socket_path": f"{config_dir}/stub.sock",
        "fast_mode_state": "off",
        "fast_mode_disabled_reason": "sdk_opt_in_required",
    }


def _result_event(session: str, n: int, model: str, text: str, num_turns: int) -> dict:
    return {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "duration_ms": 0,
        "duration_api_ms": 0,
        "num_turns": num_turns,
        "result": text,
        "session_id": session,
        "total_cost_usd": 0.0,
        "usage": {
            "input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "output_tokens": 0,
            "output_tokens_details": {"thinking_tokens": 0},
            "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0},
            "service_tier": "standard",
            "cache_creation": {"ephemeral_1h_input_tokens": 0, "ephemeral_5m_input_tokens": 0},
        },
        "modelUsage": {},
        "permission_denials": [],
        "stop_reason": "end_turn",
        "terminal_reason": "completed",
        "api_error_status": None,
        "subagent_stats": {"spawned": 0, "completed": 0, "failed": 0},
        "queued_turn_count": 0,
        "ttft_ms": 0,
        "ttft_stream_ms": 0,
        "time_to_request_ms": 0,
        "first_content_frame_ms": 0,
        "fast_mode_state": "off",
        "fast_mode_disabled_reason": "sdk_opt_in_required",
        "uuid": _uid(session, n),
    }


STUB_ANSWER = "2+2=4\n"
STUB_RESULT_TEXT = "Wrote answer.md.\n"


def run_stub(inv: Invocation, stdout, stderr) -> int:
    """Write a canned transcript and the artefacts the agent would have left.

    No network, no subprocess, no billing. The transcript carries real `Skill`,
    `Read` and `Bash` `tool_use` blocks and their `tool_result` replies, and the
    filesystem side effect it narrates (`answer.md`) is actually performed — so
    the workspace copy-out is exercised and the transcript does not describe a
    workspace that never existed.
    """
    config_dir = inv.env.get("CLAUDE_CONFIG_DIR", "")
    session = _uid(str(inv.cwd), -1)
    events: list[dict] = [_init_event(inv, session, config_dir)]

    # Inert noise a real stream carries. Reproduced so the invocation parser
    # meets an event type it does not model, here rather than in production.
    events.append(
        {
            "type": "rate_limit_event",
            "rate_limit_info": {"status": "allowed", "rateLimitType": "five_hour"},
            "uuid": _uid(session, 1),
            "session_id": session,
        }
    )
    events.append(
        {
            "type": "system",
            "subtype": "thinking_tokens",
            "estimated_tokens": 0,
            "estimated_tokens_delta": 0,
            "session_id": session,
            "uuid": _uid(session, 2),
        }
    )

    n = 3
    if inv.skill_name:
        tid = f"toolu_stub{n:04d}"
        events.append(
            _assistant(session, n, inv.model, [
                {"type": "thinking", "thinking": "Load the skill first.", "signature": "stub"},
            ])
        )
        n += 1
        events.append(
            _assistant(session, n, inv.model, [
                {
                    "type": "tool_use",
                    "id": tid,
                    "name": "Skill",
                    "input": {"skill": inv.skill_name},
                    "caller": {"type": "direct"},
                }
            ])
        )
        n += 1
        events.append(
            _tool_result(
                session, n, tid,
                f"Skill {inv.skill_name} loaded.",
                {"type": "skill", "skill": inv.skill_name},
            )
        )
        n += 1

        skill_md = f"{config_dir}/skills/{inv.skill_name}/SKILL.md"
        tid = f"toolu_stub{n:04d}"
        events.append(
            _assistant(session, n, inv.model, [
                {
                    "type": "tool_use",
                    "id": tid,
                    "name": "Read",
                    "input": {"file_path": skill_md},
                    "caller": {"type": "direct"},
                }
            ])
        )
        n += 1
        events.append(
            _tool_result(
                session, n, tid,
                f"     1\t---\n     2\tname: {inv.skill_name}\n",
                {"type": "text", "file": {"filePath": skill_md, "numLines": 2}},
            )
        )
        n += 1

    tid = f"toolu_stub{n:04d}"
    events.append(
        _assistant(session, n, inv.model, [
            {
                "type": "tool_use",
                "id": tid,
                "name": "Bash",
                "input": {"command": "ls -la", "description": "List the workspace"},
                "caller": {"type": "direct"},
            }
        ])
    )
    n += 1
    listing = "\n".join(sorted(p.name for p in inv.cwd.iterdir()))
    events.append(
        _tool_result(session, n, tid, listing, {"stdout": listing, "stderr": "", "interrupted": False})
    )
    n += 1

    answer = inv.cwd / "answer.md"
    tid = f"toolu_stub{n:04d}"
    events.append(
        _assistant(session, n, inv.model, [
            {
                "type": "tool_use",
                "id": tid,
                "name": "Write",
                "input": {"file_path": str(answer), "content": STUB_ANSWER},
                "caller": {"type": "direct"},
            }
        ])
    )
    n += 1
    answer.write_text(STUB_ANSWER)
    events.append(
        _tool_result(
            session, n, tid,
            f"File created successfully at: {answer}",
            {"type": "create", "filePath": str(answer), "content": STUB_ANSWER},
        )
    )
    n += 1

    events.append(_assistant(session, n, inv.model, [{"type": "text", "text": STUB_RESULT_TEXT}]))
    n += 1
    events.append(_result_event(session, n, inv.model, STUB_RESULT_TEXT, num_turns=n))

    for event in events:
        stdout.write((json.dumps(event) + "\n").encode())
    stderr.write(b"")
    return 0


RUNNERS = {LIVE: run_live, STUB: run_stub}


def get(name: str):
    """Look up a runner by name, or explain what the names are."""
    try:
        return RUNNERS[name]
    except KeyError:
        raise RunnerError(
            f"unknown runner {name!r}; expected one of {', '.join(CHOICES)}"
        ) from None
