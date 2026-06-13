---
name: v1-delegate-task
description: "Dispatches task execution to an idle Claude Code pane in a tmux session, freeing the current session for other work. Use when 'delegate task', 'send to executor', or when the user wants to hand off a task to a background pane."
---

# Delegate Task

Dispatch execution to an idle Claude Code pane in a tmux session using `ntm`.

> Part of the task planning workflow. See [references/workflow-overview.md](references/workflow-overview.md) for the full pipeline.

## Input

Task ID (numeric) and optionally a tmux session name (defaults to `$PROJECT--execute`).

## Dispatch Workflow

### Step 1: Check agent activity

```bash
ntm status $SESSION --json
```

Parse the JSON output. Each pane entry includes the agent type, current command, and activity state. A pane is idle when its state is not `busy` and the agent is a Claude instance on `(main)`.

If no panes are idle, report what each pane is doing and stop. Do not interrupt active work.

### Step 2: Send command

Use `ntm send` with `--smart` to auto-route to the best idle agent (least-loaded strategy):

```bash
ntm send $SESSION --smart --cc --json '/clear'
```

Wait 5 seconds, then send the execution command and rename:

```bash
ntm send $SESSION --pane=$PANE --json '/v1-execute-task $ID'
```

Wait 1 second:

```bash
ntm send $SESSION --pane=$PANE --json '/rename'
```

If the first `/clear` used `--smart`, note which pane index was selected from the JSON response and use `--pane=$PANE` for subsequent sends.

### Step 3: Verify kickoff

Capture the pane output to confirm execution started:

```bash
ntm copy $SESSION:$PANE --last 30 --quiet --output /dev/stdout
```

Check that the output shows the execute-task command was received and work has begun.

### Step 4: Report

Output which pane was selected, confirmation that the command was sent, and what the pane is currently doing.

Tell the user how to check on progress later:

```
To read recent output from this session:
  ntm copy $SESSION:$PANE --last 50
  ntm copy $SESSION:$PANE --code        # extract just code blocks
  ntm grep 'error\|warning' $SESSION    # search across all panes
  ntm watch $SESSION --pane=$PANE       # stream output live
```
