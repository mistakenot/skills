---
name: delegate-task
description: "Dispatches task execution to an idle Claude Code pane in a background session, freeing the current session for other work. Use when 'delegate task', 'send to executor', or when the user wants to hand off a task to a background pane."
customize:
  runner:
    default: "ntm"
    enum: [ntm, herdr]
    description: "Agent runner: 'ntm' or 'herdr'. Selects the references/<runner>/ command guides."
---

# Delegate Task

Dispatch execution to an idle Claude Code pane in a background session.

> Read `references/{{ .runner }}/list-workers.md`
> first, before anything else below. If that directory does not exist, stop
> and report that the `runner` value is invalid — valid values are `ntm` and
> `herdr`.

> Part of the task planning workflow. See [references/workflow-overview.md](references/workflow-overview.md) for the full pipeline.

> **Ad-hoc work without task docs?** Use [/delegate](../delegate/SKILL.md) instead —
> it sends a freeform prompt to an idle pane without requiring planning documents.

> **Targeting non-Claude agents.** This skill dispatches `/execute-task` to a
> Claude Code pane. To discover agents and send to **Codex** or **OpenCode**
> panes (whose send/clear conventions differ), see
> [references/agent-conventions.md](references/agent-conventions.md).
>
> **Pool model.** This skill dispatches into the **workers** pool — worker
> panes run in worktrees and open PRs, separated by role label from the
> `planners` pool that commits to `main`. See
> [references/worker-pools.md](references/worker-pools.md).

## Input

Task ID (numeric) and optionally a session/pool name (defaults to the
project's worker pool — resolve the concrete name with
`references/{{ .runner }}/label-worker.md`, since the convention differs
per runner).

## Dispatch Workflow

### Step 1: Advance status to executing

Before finding a worker, mark the task as executing so the worker's fresh
worktree (created from `origin/main`) sees the right stage. See
[references/task-status.md](references/task-status.md): set `status="executing"`
on `<pd-doc>` in `plan.html`, then commit and push:

```bash
git commit -am "docs($ID): status executing" && git push origin main
```

This also satisfies the "task docs pushed" requirement below.

### Step 2: Find an eligible pane

Enumerate panes with `references/{{ .runner }}/list-workers.md`,
then inspect each candidate's recent output with `references/{{ .runner }}/read-output.md`.

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
one and wait until it is ready for input — see `references/{{ .runner }}/spawn-worker.md` and `references/{{ .runner }}/wait-for-ready.md`.
Set `$PANE` to the new pane. A freshly added pane starts on `main`, so it is
always eligible. Add **one** worker per dispatch; if spawning fails, report
and stop.

> **Warning:** A pane sitting in another task's worktree has a stale checkout. If dispatched there, the executor may read outdated task docs before creating its own worktree. Always ensure the target pane is on `main`.

### Step 3: Ensure task docs are pushed

Before dispatching, verify that the task's planning docs have been pushed to `origin/main`. The executor will create a fresh worktree from `origin/main` and needs access to the docs.

```bash
git log origin/main --oneline -5 -- tasks/$ID/
```

If the task docs are not on `origin/main`, push them first or warn the user.

### Step 4: Reset and send command

**Never use `/clear` to reset a reused pane** — it is a cooperative command that
silently queues behind in-flight work and detonates later (this wiped task 047).
Reset imperatively instead — see `references/{{ .runner }}/reset-worker.md`.

**Reused pane** (an existing pane confirmed idle on `main` with no open PR in
Step 2): reset it and dispatch `/execute-task $ID` in one step — see `references/{{ .runner }}/reset-worker.md`.
If the reset instead reports the pane as busy, **do not force it** — treat
the pane as ineligible and **add a fresh worker** (Step 2's spawn path),
then send to that fresh pane as below.

**Freshly added pane** (from Step 2's spawn path): it starts at zero context, so
it needs **no reset**. Send the command directly — see `references/{{ .runner }}/send-prompt.md`.

### Step 5: Verify kickoff, then rename

Capture the pane output to confirm execution started — see `references/{{ .runner }}/read-output.md`.
Check that the output shows the execute-task command was received and work
has begun. **Only once kickoff is confirmed**, set the pane title — sending
`/rename` now (rather than before kickoff) keeps it from queuing behind the
dispatch — see `references/{{ .runner }}/send-prompt.md`.

### Step 6: Report

Output which pane was selected, confirmation that the command was sent, and what the pane is currently doing.

Tell the user how to check on progress later — see `references/{{ .runner }}/read-output.md` and `references/{{ .runner }}/scan-output.md`.
