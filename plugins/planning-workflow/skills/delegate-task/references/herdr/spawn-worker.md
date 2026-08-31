# Spawning a worker (herdr)

Create a new coding-agent worker. herdr never picks the agent's flags for you:
**you always supply the launch arguments**, and getting them wrong is the single
most common delegation failure — see the permission section below before
anything else.

Requires **herdr 0.8.2 or newer** (`herdr --version`). Earlier versions lack
`agent start --kind`, `agent prompt`, and blocked-startup detection, and the
recipes here will not work on them.

## Permission flags are mandatory — never launch an agent bare

A background worker has nobody at the keyboard. Launched without an explicit
permission flag it comes up in its **interactive, ask-a-human-first** mode and
stalls on the first tool call, looking "idle" while doing nothing.

| Agent | Launch argv | Resulting mode |
| ----- | ----------- | -------------- |
| **Claude Code** | `claude --dangerously-skip-permissions` | `⏵⏵ bypass permissions on` |
| **Codex** | `codex --dangerously-bypass-approvals-and-sandbox` | `permissions: YOLO mode` |

Verified live: bare `claude` comes up in **`⏸ manual mode on`**, and
`shift+tab` **cannot** cycle out of manual into bypass — bypass is only
reachable via the launch flag. A pane that was launched bare is unrecoverable
for unattended work: **reap it and spawn a new one** rather than trying to
repair it.

`claude --permission-mode bypassPermissions` reaches the same mode and needs no
extra opt-in flag, so either form works; prefer
`--dangerously-skip-permissions` for consistency with Codex's single-flag form.

Always confirm the flags actually took effect after spawning — see
`references/herdr/verify-worker.md`. Re-confirm after any herdr **server
restart** too: `resume_agents_on_restore` (default true) relaunches agents as
`claude --resume <uuid>` and **does not carry the permission flag over**, so a
restart silently downgrades the whole fleet.

## Pattern A — worktree worker (recommended for task execution)

One call makes the git worktree **and** a dedicated workspace + tab + pane;
`agent start` then launches the agent into that pane.

```bash
J=$(herdr worktree create --cwd <repo> --branch task/NNN --base main \
      --label task-NNN --no-focus)
PANE=$(echo "$J" | jq -r .result.root_pane.pane_id)

herdr agent start task-NNN --kind claude --pane "$PANE" --timeout 90000 \
  -- --dangerously-skip-permissions
```

The agent lives in the worktree's **own** workspace with `cwd` = worktree — one
worktree ↔ one workspace ↔ one agent.

`worktree create` accepts `[--workspace ID | --cwd PATH] [--branch NAME]
[--base REF] [--path PATH] [--label TEXT] [--focus|--no-focus]` and returns
`root_pane`, `tab`, `workspace`, and `worktree` in its JSON. The pane it creates
is a **plain shell** — there is no `--agent`/`--run` flag on `worktree create`,
so launching the agent is always a deliberate second step.

## Pattern B — launch with the kickoff prompt as argv (fewest moving parts)

Both CLIs take an optional initial prompt as a positional argument, so a
worker can be created *and* dispatched in a single `agent start`:

```bash
herdr agent start task-NNN --kind claude --pane "$PANE" --timeout 90000 \
  -- --dangerously-skip-permissions "/execute-task NNN"

herdr agent start task-NNN --kind codex --pane "$PANE" --timeout 90000 \
  -- --dangerously-bypass-approvals-and-sandbox "/execute-task NNN"
```

Verified working for **both** agents. This is the most robust dispatch path
available: there is no separate text-delivery step, so none of the input-
delivery failure modes in `references/herdr/send-prompt.md` can occur. Prefer it
whenever the kickoff prompt is known at spawn time. Use
`references/herdr/send-prompt.md` for every *subsequent* prompt to the same
worker.

## `agent start` semantics

```
herdr agent start <name> --kind KIND --pane ID [--timeout MS] [-- <agent-args...>]
```

- **`--pane` is required and must already exist.** `agent start` never creates,
  splits, or moves layout — get a pane from `worktree create`,
  `workspace create`, `tab create`, or `pane split` first.
- The target pane must be an **available shell** — at its interactive prompt,
  no foreground command, editor, or agent running.
- `--kind` picks the integration used for status reporting. Valid kinds include
  `claude`, `codex`, `opencode`, `gemini`, `copilot`, `droid`, `amp`, `grok`;
  run `herdr agent` for the installed list.
- Everything after `--` is passed through to the agent CLI verbatim. This is
  where the permission flags go.
- `<name>` must match `[a-z][a-z0-9_-]{0,31}` and be unique among live agents.
  It becomes the agent's target handle for every later command.
- **It blocks until the agent is genuinely ready** and returns
  `agent_status` plus `interactive_ready: true`. There is no registration race
  to poll around — a successful return means you can prompt immediately.
  Startup defaults to a 30s timeout; raise it with `--timeout` on slow machines.

### Handling `agent_not_ready`

If the agent hits a startup interstitial, `agent start` returns immediately with

```json
{"error":{"code":"agent_not_ready","message":"agent <name> is blocked during startup and is not ready for prompts"}}
```

**This is not a failure to retry blindly.** The name stays bound to the pane, so:

1. Read the pane (`references/herdr/read-output.md`) to see *which* interstitial.
2. Answer it with `herdr agent send-keys <name> <key>...` — and pick the option
   deliberately, never a bare `enter` (see
   [references/agent-conventions.md](references/agent-conventions.md); Codex's
   update prompt defaults to "Update now", which drops the pane to a shell).
3. Wait for it to settle — `references/herdr/wait-for-ready.md`.

Interstitials seen live: Claude Code's *"Is this a project you trust?"* folder
prompt, Codex's *"Do you trust the contents of this directory?"* prompt, Codex's
*"Update available"* prompt, and Codex's *"Hooks need review"* prompt (triggered
by herdr's own agent-state hook on first run). Each is answered once and
remembered, so they mostly bite on a machine's first worker.

Claude Code does **not** re-prompt for trust in a git worktree of a repo it has
already trusted, so Pattern A rarely trips its folder dialog.

## Lower-level building blocks

```bash
herdr workspace create [--cwd PATH] [--label TEXT] [--env KEY=VALUE] [--no-focus]
herdr tab create [--workspace ID] [--cwd PATH] [--label TEXT] [--no-focus]
herdr pane split [<pane_id>|--current] --direction right|down [--cwd PATH] [--no-focus]
```

Read the new pane from `.result.root_pane.pane_id` (`workspace create`,
`tab create`) or `.result.pane.pane_id` (`pane split`). Use these only when
Pattern A does not fit — e.g. a worker that must not have its own worktree.

Split a wide pane `right` and a narrow or tall pane `down`, and avoid repeated
same-direction splits: panes narrower than ~80 columns wrap agent output badly
and make `read-output` hard to parse. Prefer a fresh tab or workspace per worker
over stacking many panes into one tab.

## Never run the herdr server from inside an agent session

A herdr server started from a shell **inside** a coding-agent session leaks that
session's environment into every pane it later creates. Observed live: panes
inherited `CLAUDE_CODE_CHILD_SESSION`, which silently disabled transcript saving
and changed the launched agent's default permission mode. Start the server from
a plain terminal.
