---
name: executor-status-check
description: "Use when the user wants to monitor all executor panes and get a status report of running, completed, stuck, or idle tasks."
---

# Executor Status Check

Monitor all executor panes in a tmux session and report status.

{{ ref:workflow-overview.md }}

## Input

Optional tmux session name (defaults to `$PROJECT--execute`).

## Status Values

- **in progress**: agent actively working (text streaming, tool calls visible)
- **completed**: "Task complete" or PR URL visible with idle prompt
- **stuck**: errors with no recovery, permission prompts, context exhausted (95%+)
- **idle**: empty prompt, no streaming output

## Per-Pane Extraction

For each pane, capture last 30 lines and extract:

- **Task ID**: from `/execute-task NNN`, branch name `task/NNN-`, or file paths `docs/tasks/NNN-`
- **Description**: read first heading from task's `plan.md`
- **Last message**: summary of last agent output block
- **Suggested next step**:
  - completed + PR open -> `/address-feedback`
  - feedback resolved -> `/complete-task`
  - PR merged -> `/clear`
  - stuck -> describe the blocker

## Probing

For panes running long or showing unclear progress, capture more output lines to determine actual state.

## Output Format

Present results as a table:

```
| Pane | Task | Description | Status | Last Message | Next Step |
|------|------|-------------|--------|--------------|-----------|
| 0    | 434  | Add widget  | completed | PR #87 created | /address-feedback |
| 1    | 435  | Fix auth    | in progress | Running e2e tests | -- |
| 2    | --   | --          | idle   | -- | -- |
```
