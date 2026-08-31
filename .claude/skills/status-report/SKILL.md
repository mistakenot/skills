---
name: status-report
description: "Monitors all executor panes in a background session, reports the status of running, completed, stuck, or idle tasks, and garbage-collects surplus idle panes. Use when 'status report', 'check executors', 'executor status', 'how are tasks going', 'reap idle panes', or when monitoring background task progress."
---

# Executor Status Check

Monitor all executor panes in a background session and report status.

> Read `references/ntm/list-workers.md`
> first, before anything else below. If that directory does not exist, stop
> and report that the `runner` value is invalid — valid values are `ntm` and
> `herdr`.

> Part of the task planning workflow. See [references/workflow-overview.md](references/workflow-overview.md) for the full pipeline.

> **Mixed agent types.** Panes may run Claude Code, Codex, or OpenCode, whose
> identification and `/clear` behaviour differ. See
> [references/agent-conventions.md](references/agent-conventions.md) for
> reliable agent identification and per-agent quirks.

> **Pool model.** Panes are organised as two role-separated pools —
> `planners` (commit to `main`) and `workers` (worktrees + PRs). This skill
> monitors and GCs the **workers** pool. See
> [references/worker-pools.md](references/worker-pools.md).

## Input

Optional session/pool name (defaults to the project's worker pool — resolve
the concrete name with `references/ntm/label-worker.md`, since the
convention differs per runner).

## Status Values

- **in progress**: agent actively working (text streaming, tool calls visible)
- **completed**: "Task complete" or PR URL visible with idle prompt
- **stuck**: errors with no recovery, permission prompts, context exhausted (95%+)
- **idle**: empty prompt, no streaming output

## Workflow

### Step 1: Get structured pane metadata

See `references/ntm/list-workers.md`.
Each pane's metadata includes context usage — use it to detect context
exhaustion (95%+ = stuck).

### Step 2: Scan for status markers across all panes

See `references/ntm/scan-output.md` to search all Claude panes at
once. Matches reveal task IDs, phase progress, errors, and completion
markers without capturing each pane individually.

### Step 3: Capture detail for ambiguous panes

For any pane whose status is unclear from the scan results, capture more
output — see `references/ntm/read-output.md`.

### Step 4: Extract per-pane status

For each pane, determine:

- **Task ID**: from `/execute-task NNN`, branch name `task/NNN-`, or file paths `docs/tasks/NNN-`
- **Description**: read first heading from task's `plan.md`
- **Last message**: summary of last agent output block
- **Suggested next step**:
  - completed + PR open -> `/address-feedback`
  - feedback resolved -> `/complete-task`
  - PR merged -> reap it (Step 6)
  - stuck -> describe the blocker

### Step 5: Present results

```
| Pane | Task | Description | Status | Context | Last Message | Next Step |
|------|------|-------------|--------|---------|--------------|-----------|
| 0    | 434  | Add widget  | completed | 8%  | PR #87 created | /address-feedback |
| 1    | 435  | Fix auth    | in progress | 42% | Running e2e tests | -- |
| 2    | --   | --          | idle   | 1%  | -- | -- |
```

### Step 6: Reclaim idle panes (garbage collection)

After reporting, shrink the pool back toward the warm **floor of 4** so idle
Claude panes (each a full `claude` process carrying several GB of memory)
don't accumulate after a burst of tasks.

Reap **only** panes that are **idle on `main` with no open PR** — never
in-progress, stuck, completed-with-PR, or feature-branch panes. The reap
mechanism (see `references/ntm/reap-worker.md`) reaps the
**highest-index pane first and is not busy-aware**, so only scale down by
the contiguous run of idle panes at the **top** of the index range:

- `cc_total` = number of Claude panes.
- `reapable_top` = idle-on-main panes counting **down from the highest index**,
  stopping at the first busy pane.
- `to_reap = max(0, min(reapable_top, cc_total - 4))`.

Re-confirm those top panes are still idle immediately before scaling, then
reap them — see `references/ntm/reap-worker.md`.

Report which panes were reaped and which idle panes were **kept** and why (floor
reached, or a busy pane sitting above them — that case reaps nothing this cycle).
Full policy: [references/worker-pools.md](references/worker-pools.md).
