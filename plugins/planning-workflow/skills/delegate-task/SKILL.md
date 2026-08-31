---
name: delegate-task
description: "Dispatches /execute-task for a planned task to a fresh background worker (herdr), freeing this session. Use when 'delegate task', 'send to executor', 'hand off this task'."
---

# Delegate Task

Dispatch `/execute-task` for a planned task to a fresh background worker.

> Read `references/herdr/spawn-worker.md` before dispatching. Its permission
> section is not optional reading: a worker launched without the right flags
> comes up asking a human for approval on every tool call and silently stalls.

> Part of the task planning workflow. See
> [references/workflow-overview.md](references/workflow-overview.md) for the
> full pipeline.
>
> **Ad-hoc work without task docs?** Use
> [/delegate](../delegate/SKILL.md) instead.
>
> **Pool model.** Dispatches into the **workers** pool — workers run in
> worktrees and open PRs, distinct from planners which commit to `main`. See
> [references/worker-pools.md](references/worker-pools.md). For per-agent CLI
> behaviour, see
> [references/agent-conventions.md](references/agent-conventions.md).

## Prerequisites

herdr **0.8.2 or newer** (`herdr --version`), with the integration installed for
the target agent (`herdr integration status`). Earlier versions lack
`agent start --kind`, `agent prompt`, and blocked-startup detection; stop and
tell the user to upgrade rather than falling back to raw keystrokes.

## Input

Task ID (numeric), and optionally the agent to target — **Claude Code**
(default) or **Codex**.

## Dispatch workflow

### Step 1: Advance status to executing

Mark the task executing **before** creating the worker, so the worker's fresh
worktree (branched from `origin/main`) sees the right stage. Per
[references/task-status.md](references/task-status.md), set `status="executing"`
on `<pd-doc>` in `plan.html`, then:

```bash
git commit -am "docs($ID): status executing" && git push origin main
```

### Step 2: Confirm the task docs are on `origin/main`

The worker branches from `origin/main` and reads the docs from there.

```bash
git log origin/main --oneline -5 -- tasks/$ID/
```

If the docs are not on `origin/main`, push them first or stop and tell the user.
Step 1's push normally satisfies this.

### Step 3: Check for an existing worker on this task

Enumerate with `references/herdr/list-workers.md`. If a worker is already on a
`task/$ID` branch, **do not dispatch a second one** — report what it is doing
and stop. Two workers on one task means two PRs and a merge conflict.

### Step 4: Spawn a fresh worker

**Always spawn fresh. Never reuse an existing worker.** A worker that has run a
task carries its context, and there is no in-place reset: `/clear` is
cooperative and detonates mid-task, and permission mode is fixed at launch. See
`references/herdr/reset-worker.md`.

Use the **worktree pattern** in `references/herdr/spawn-worker.md` — a task
worker must never run in the primary checkout:

```bash
herdr worktree create --cwd <repo> --branch task/$ID --base origin/main \
  --label task-$ID --no-focus
```

Then launch the agent into the pane it returns, with the mandatory flags:

| Agent | Launch argv |
| ----- | ----------- |
| Claude Code | `claude --dangerously-skip-permissions` |
| Codex | `codex --dangerously-bypass-approvals-and-sandbox` |

Prefer **Pattern B** — pass `/execute-task $ID` as the final argv to
`agent start`, creating and dispatching the worker in one call. Name the agent
`task-$ID` so every later command can address it by name
(`references/herdr/label-worker.md`).

If `agent start` returns `agent_not_ready`, the agent hit a startup
interstitial. Read the pane, answer it deliberately with `agent send-keys`
(never a bare `enter`), and wait for it to settle — see
`references/herdr/spawn-worker.md`.

Spawn **one** worker per dispatch. If spawning fails, report and stop.

### Step 5: Verify the worker is fit

Run the health check in `references/herdr/verify-worker.md` before reporting
success:

- The pane runs the agent, not a shell.
- Its argv carries the permission flag. A bare `claude` or `codex` means manual
  approval mode — **reap and respawn**; it cannot be repaired in place.
- Its cwd is the **worktree** (`git-dir != git-common-dir`), not the primary
  checkout.

### Step 6: Confirm kickoff

Confirm `/execute-task $ID` was actually accepted rather than assuming it —
watch for the transition into `working` per
`references/herdr/wait-for-ready.md`. If it never reaches `working`, the prompt
did not land; see `references/herdr/send-prompt.md`.

Only **after** kickoff is confirmed, apply any display labels
(`references/herdr/label-worker.md`) — doing it earlier just queues behind the
dispatch.

### Step 7: Report

State the worker's name, workspace/pane, branch, worktree path, agent kind,
confirmation that the permission flags verified, and what it is doing now.

Tell the user how to follow progress — `references/herdr/read-output.md` and
`references/herdr/scan-output.md` — and that
[/status-report](../status-report/SKILL.md) covers the whole fleet.
