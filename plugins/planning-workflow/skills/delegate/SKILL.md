---
name: delegate
description: "Hands a freeform prompt to a fresh background coding-agent worker (herdr). Use when 'delegate this', 'send to an executor', 'run this in background'. Not for planned tasks with docs (use delegate-task)."
---

# Delegate

Hand a freeform prompt to a background coding agent running under **herdr**,
without requiring task planning documents.

> Read `references/herdr/spawn-worker.md` before dispatching. Its permission
> section is not optional reading: a worker launched without the right flags
> comes up asking a human for approval on every tool call and silently stalls.

> For delegating **planned tasks** with requirements/solution/plan docs, use
> [/delegate-task](../delegate-task/SKILL.md) instead.
>
> Dispatches into the **workers** pool. For the planner/worker model, see
> [references/worker-pools.md](references/worker-pools.md). For how each agent
> CLI behaves in itself, see
> [references/agent-conventions.md](references/agent-conventions.md).

## Prerequisites

herdr **0.8.2 or newer** (`herdr --version`), with the integration installed for
the agent you are targeting (`herdr integration status`). Earlier versions lack
`agent start --kind`, `agent prompt`, and blocked-startup detection; stop and
tell the user to upgrade rather than falling back to raw keystrokes.

## Input

A prompt describing the work, and optionally:

- A target agent: **Claude Code** (default) or **Codex**.
- A repo, if the prompt is not about the current one.

If no prompt is given, ask the user what they'd like to delegate.

## Dispatch workflow

### Step 1: Survey existing workers

Enumerate with `references/herdr/list-workers.md`, filtered to the repo in
question. You are looking for whether a fresh worker is warranted, and for work
already in flight that the user may not want duplicated.

Report anything already running on this repo before spawning — if a worker is
mid-task on the same area, say so and let the user decide.

### Step 2: Spawn a fresh worker

**Always spawn a fresh worker. Never reuse an existing one.** An agent that has
already run a task carries that task's context, and there is no way to clear it
in place — `/clear` is cooperative and detonates mid-task, and permission mode
is fixed at launch. See `references/herdr/reset-worker.md` for why this is a
hard rule rather than a preference.

Create the worker per `references/herdr/spawn-worker.md`. For ad-hoc work that
does not need branch isolation, a workspace with the repo as its cwd is enough;
for anything that will edit files, use the worktree pattern so the work is
isolated and reviewable.

**Launch flags are mandatory:**

| Agent | Launch argv |
| ----- | ----------- |
| Claude Code | `claude --dangerously-skip-permissions` |
| Codex | `codex --dangerously-bypass-approvals-and-sandbox` |

Prefer **Pattern B** — pass the user's prompt as the final argv to
`agent start`, so the worker is created and dispatched in one call with no
separate text-delivery step.

If `agent start` returns `agent_not_ready`, the agent hit a startup
interstitial. Do not retry blindly — read the pane, answer the dialog
deliberately with `agent send-keys` (never a bare `enter`), and wait for it to
settle. Full procedure in `references/herdr/spawn-worker.md`.

**Prompt construction:** send the user's prompt as-is. Do not wrap it in a slash
command or add preamble. Convert any file or directory references to **absolute
paths** — the worker's working directory is a worktree, not yours.

### Step 3: Verify the worker is fit

Before considering the dispatch done, run the health check in
`references/herdr/verify-worker.md`:

- The pane is running the agent, not a shell.
- Its argv carries the permission flag. A bare `claude` or `codex` means manual
  approval mode — **reap it and spawn again**; it cannot be repaired in place.
- Its cwd is where you intended.

### Step 4: Confirm kickoff

Confirm the agent actually took the prompt rather than assuming it did — watch
for the transition into `working` per `references/herdr/wait-for-ready.md`.

When dispatching a *second* prompt to a worker already running (rather than via
Pattern B), use `agent prompt` and handle `agent_blocked` and
`agent_prompt_stalled` as described in `references/herdr/send-prompt.md`.

### Step 5: Report

State the worker's **name**, its workspace/pane, its branch or cwd, the agent
kind, confirmation that the permission flags verified, and what it is doing now.

Tell the user how to check on it later — `references/herdr/read-output.md` for
one worker, `references/herdr/scan-output.md` for the fleet — and how to reap it
when done (`references/herdr/reap-worker.md`), noting that removing the worktree
is a separate step from closing the workspace.
