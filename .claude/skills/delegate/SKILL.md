---
name: delegate
description: "Sends a freeform prompt to an idle agent pane in a background session, without requiring task planning docs. Use when 'delegate this', 'send this to an executor', 'run this in background', or when the user wants to hand off ad-hoc work. Not for planned tasks with docs (use delegate-task instead)."
---

# Delegate

Send a freeform prompt to an idle coding-agent pane in a background session,
without requiring task planning documents.

> Read `references/ntm/list-workers.md`
> first, before anything else below. If that directory does not exist, stop
> and report that the `runner` value is invalid — valid values are `ntm` and
> `herdr`.

> For delegating **planned tasks** with requirements/solution/plan docs, use
> [/delegate-task](../delegate-task/SKILL.md) instead.
>
> For agent discovery, type identification, and send conventions, see
> [references/agent-conventions.md](references/agent-conventions.md).
>
> Dispatches into the **workers** pool. For the planner/worker pool model and
> label rules, see [references/worker-pools.md](references/worker-pools.md).

## Input

A prompt describing the work to delegate, and optionally:
- A session/pool name (defaults to the project's worker pool — resolve the
  concrete name with `references/ntm/label-worker.md`, since the
  convention differs per runner)
- A target agent type preference (Claude Code, Codex, OpenCode)

If no prompt is given, ask the user what they'd like to delegate.

## Delegation Workflow

### Step 1: Find an eligible pane

Enumerate panes with `references/ntm/list-workers.md`,
then inspect each candidate's recent output with `references/ntm/read-output.md`.

A pane is eligible when **all** of the following are true:

1. **Not busy** — the pane output shows a prompt waiting for input, not an active task in progress.
2. **On `main`** — the pane's status line or prompt shows `(main)`, not a feature/worktree branch. A pane on a feature branch almost always means a prior task is in flight (open PR, awaiting review/merge). **Never target a pane that is not on `main`**, even if it appears idle — an open/unmerged PR or feature branch disqualifies it.
3. **No open PR** — there is no evidence of an unmerged PR from a prior task.

If a candidate is idle but on a feature branch, skip it and report why (e.g. "pane 2 skipped: on branch `task-505` with open PR").

If **no panes are eligible** — all busy, on feature branches, or only a plain
shell — **add a fresh worker** instead of stopping. Do not interrupt active
work. First check the **ceiling**: if the pool already has **6** Claude
panes (the cap) and none are eligible, every worker is genuinely busy —
report and stop (or wait and re-check); do not add a seventh. Otherwise add
one and wait until it is ready for input — see `references/ntm/spawn-worker.md` and `references/ntm/wait-for-ready.md`.
Set `$PANE` to the new pane. Add **one** worker per dispatch; if spawning
fails, report and stop.

### Step 2: Reset and send

**Never use `/clear` to reset a reused pane** — it is a cooperative command that
silently queues behind in-flight work and detonates later (this wiped task 047).
Reset imperatively instead — see `references/ntm/reset-worker.md`.

**Reused pane** (an existing pane confirmed idle on `main` with no open PR in
Step 1): reset it and dispatch the prompt in one step — see `references/ntm/reset-worker.md`.
If the reset instead reports the pane as busy, **do not force it** — treat
the pane as ineligible and **add a fresh worker** (Step 1's spawn path),
then send to that fresh pane as below.

**Freshly added pane** (from Step 1's spawn path): it starts at zero context, so
it needs **no reset**. Send the prompt directly — see `references/ntm/send-prompt.md`.

**Prompt construction:** Send the user's prompt as-is. Do not wrap it in a slash command or add preamble. If the prompt references files or paths, ensure they are absolute paths (the executor pane may have a different working directory).

### Step 3: Verify kickoff

Capture the pane output to confirm the prompt was received — see `references/ntm/read-output.md`.
Check that the output shows the agent received the prompt and work has begun.

### Step 4: Report

Output which pane was selected, confirmation that the prompt was sent, and what the pane is currently doing.

Tell the user how to check on progress later — see `references/ntm/read-output.md` and `references/ntm/scan-output.md`.
