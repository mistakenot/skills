---
hash: "75a70efc"
id: "herdr-vs-ntm"
read_when: "evaluating or migrating the delegate/delegate-task/status-report worker-management skills from ntm/tmux to herdr; or needing the verified herdr 0.7.1 command surface, status mechanism, worktree behaviour, enforcement design, and gotchas"
summary: "Evaluation + live spike of herdr (terminal agent multiplexer) as a herdr-only replacement for ntm/tmux in the delegate-* worker skills: verified command surface, push-based status, worktree interaction, a tool-agnostic git-hook enforcement design, the ephemeral-worker redesign, an ntm feature-parity table, and gotchas."
title: "herdr vs ntm — worker management evaluation"
---

# herdr vs ntm — worker management evaluation

Working notes evaluating **herdr** ("terminal-native agent multiplexer") as a
replacement for **ntm/tmux** in our worker-management skills — `delegate`,
`delegate-task`, `status-report`. All claims below the
"Spike log" line were verified live against **herdr 0.7.1** on this machine
(2026-07-09); everything else is design.

**Decision so far:** spike-first (done, green), targeting **herdr-only** (no
ntm dual-support). The redesign is a net simplification. Not yet built.

Related: the current ntm-based model lives in the delegate skills' refs
(`delegating-to-agents.md`, `ntm-agent-pools.md`). The known-broken ntm restart
paths are the memory note `ntm-inplace-restart-broken`.

## Why look past ntm

The three delegate skills lean on ntm for: JSON pane discovery, send text +
slash commands, readiness wait, busy/idle detection, read/grep/watch across
panes, spawn/scale, and — critically — **labels driving git hooks** that keep
planners off feature branches and workers off `main`. Two ntm pain points are
already documented as unfixable in our environment:

- **In-place restart is broken** (ntm 1.18.2): `smart-restart`, `respawn`, and
  `restart-pane` all misbehave; the only clean-context path is spawning a fresh
  pane. This forces the warm-pool + `/clear` reuse model.
- **`ntm add`'s returned pane index is unreliable** — every dispatch must
  re-query `ntm status` to find the real index.

Plus the eligibility/status logic is **heuristic pane-scraping** ("does the
output show a prompt waiting?") — the flimsiest part of the skills.

## What herdr is

A **server/client daemon**. A persistent server owns the terminal state; clients
(and the CLI) talk to it over a Unix socket (`~/.config/herdr/herdr.sock`).
Consequences that matter here:

- **Persistence** is real: named sessions (`herdr session list/attach/stop/delete`)
  survive client disconnect, like tmux sessions. Refutes the initial worry that
  herdr panes die with the client.
- **The control path works from *outside* a herdr pane.** Every socket command
  (`session/workspace/worktree/agent/pane list`, etc.) runs from a plain shell
  with `HERDR_ENV` unset. `HERDR_ENV=1` is only needed by the *agent-state hook
  running inside a pane* (the reporting side), which the integration installs
  automatically. So a coordinator can drive herdr from anywhere — same as
  ntm→tmux.
- `herdr --remote <ssh-target>` attaches to a remote server over SSH.

**Structure:** `workspace` (a project/cwd context) › `tab` › `pane`. Worktrees
are first-class and bind to workspaces (see below).

**Agent integrations** are installed per agent CLI and are what produce status:

```
herdr integration install claude   # writes ~/.claude/hooks/herdr-agent-state.sh
herdr integration status           # shows install state + version per agent
```

On this machine, `claude` (v7), `codex` (v6), and `opencode` (v7) integrations
are **installed and current**. Others available: pi, omp, copilot, devin, droid,
kimi, kilo, hermes, qodercli, cursor.

## Command surface (verified subcommands)

```
herdr session   list|attach|stop|delete
herdr workspace list|create|get|focus|rename|close
herdr tab       create|close|... (labels supported)
herdr worktree  list|create|open|remove
herdr agent     list|get|read|send|rename|focus|wait|attach|start|explain
herdr pane      list|get|read|run|send-text|send-keys|split|close|move|
                report-agent|report-agent-session|release-agent|report-metadata|...
herdr wait      output|agent-status
herdr integration install|uninstall|status
```

Prefer `--json`; results nest under `result.*`. Targets for `agent *` accept a
**pane id**, a unique agent **name**, or an agent **label** (not only indices).

## Status mechanism (the standout feature)

Status is **push-based**, not scraped. The installed agent hook
(`~/.claude/hooks/herdr-agent-state.sh` for Claude Code) fires on session events
and reports state to the socket. States: **`idle | working | blocked | done |
unknown`**. `done` distinguishes "finished a turn" from mere `idle`.

Status is both queryable and **waitable**:

```bash
herdr agent get <target>                                   # includes agent_status
herdr agent wait <target> --status working --timeout 15000 # blocks until it transitions
herdr wait output <pane> --match PONG --timeout 60000      # blocks until output matches
```

This replaces the pane-scraping heuristics in the current skills with a real
signal — the single biggest ergonomic win.

## How herdr interacts with worktrees

Worktrees are a top-level subcommand family, not a pane side-effect:

```
herdr worktree list   [--cwd PATH | --workspace ID] [--json]   # each entry has is_linked_worktree
herdr worktree create [--branch NAME] [--base REF] [--path PATH] [--label TEXT] [--focus|--no-focus] [--json]
herdr worktree open   (--path PATH | --branch NAME) [--label TEXT]
herdr worktree remove --workspace ID [--force]
```

Verified behaviours:

- **`worktree create` is one call that does two things:** runs `git worktree add`
  (new `--branch` off `--base`, at `--path`) **and** opens a dedicated herdr
  **workspace + tab + pane** whose cwd is the worktree. Returns `root_pane`,
  `tab`, `workspace`, and `worktree` objects in its JSON.
- **The created pane is a plain shell** — there is no `--agent`/`--run` flag, so
  launching the agent is a deliberate second step.
- **`worktree list` exposes `is_linked_worktree`** per entry — herdr surfaces the
  primary-checkout-vs-worktree distinction structurally (the same signal our
  enforcement hook uses).
- **Unified teardown:** `herdr workspace close <id>` reaps the pane *and* the
  worktree together; `herdr worktree remove --workspace <id>` is the explicit
  form.

### Starting an agent inside a worktree — two patterns

**Pattern A — launch into the pane `worktree create` gave you (recommended):**

```bash
J=$(herdr worktree create --cwd <repo> --branch task/NNN --base main \
      --path <wt> --no-focus --json)
PANE=$(echo "$J" | jq -r .result.root_pane.pane_id)
herdr pane run "$PANE" "claude --dangerously-skip-permissions"
```

Agent lives in the worktree's **own** workspace, cwd = worktree. One
worktree ↔ one workspace ↔ one agent, cleanly bound; tears down with a single
`workspace close`. This is the pattern the PONG spike used.

**Pattern B — `agent start` with an explicit launch command:**

```bash
herdr agent start <name> --cwd <wt> --no-focus -- claude --dangerously-skip-permissions
```

Works, and the agent's `cwd`/`foreground_cwd` become the worktree — so git and
the enforcement hook correctly classify it as a **worker**. **Gotcha:** `--cwd`
sets the *process* working directory, **not** herdr placement. Without
`--workspace`/`--tab`, the pane splits into the **currently-focused** workspace.
In the spike this orphaned things: the worktree's workspace `w5` sat with an
empty shell while the agent landed as `w1:p3` in the live workspace. To keep them
together, pass `--workspace <id>` (and usually `--tab <id>`) too.

## Enforcement without ntm labels (tool-agnostic)

ntm couples pool enforcement to `ntm init`-installed hooks reading ntm **labels**.
herdr has **no git-hook enforcement layer** (`--label` on workspaces/panes/
worktrees is organizational only). But under a redesign we don't need to port
ntm's mechanism — role is derivable from **worktree-ness with pure git**:

- **primary checkout** ⇒ planner: `git-dir == git-common-dir`
- **linked worktree** ⇒ worker: `git-dir != git-common-dir`

A repo-shipped hook keyed on that (installed via `core.hooksPath`) enforces the
pool rules and works under herdr, ntm, or bare tmux — strictly better than
coupling enforcement to the multiplexer. Verified `pre-commit`:

```sh
#!/bin/sh
gd=$(git rev-parse --git-dir); cd=$(git rev-parse --git-common-dir)
branch=$(git rev-parse --abbrev-ref HEAD)
[ "$gd" != "$cd" ] && role=worker || role=planner
if [ "$role" = worker ]  && [ "$branch" =  main ]; then
  echo "BLOCKED: worker (worktree) may not commit to main" >&2; exit 1; fi
if [ "$role" = planner ] && [ "$branch" != main ]; then
  echo "BLOCKED: planner (primary checkout) may only commit on main" >&2; exit 1; fi
exit 0
```

All four cases behave correctly (verified in an isolated repo):

| case                | expected | result       |
| ------------------- | -------- | ------------ |
| planner / main      | allow    | ✓ committed  |
| planner / feature   | block    | ✓ BLOCKED    |
| worker / branch     | allow    | ✓ committed  |
| worker / main       | block    | ✓ BLOCKED    |

## Proposed redesign: ephemeral worker = worktree + agent

Drop the ntm warm-pool-of-reusable-panes model. Each task gets a fresh
worktree+agent, created and torn down per task:

- **Dispatch:** `worktree create --branch task/NNN --base origin/main` →
  `pane run <root_pane> "claude --dangerously-skip-permissions"` →
  `agent send`/`pane send-text` the kickoff (`/execute-task NNN`) →
  `wait output --match` to confirm start.
- **Enforce:** repo-shipped git hook (above), multiplexer-agnostic.
- **Monitor:** `agent list` / `agent get` for push-based status;
  `agent wait --status done` to detect completion; `agent read` for detail.
- **Reap:** on merge, `workspace close <id>` (reaps pane + worktree).

This eliminates three ntm pain points outright: broken in-place restart (no
reuse ⇒ nothing to restart), unreliable `add`-index, and the not-busy-aware
`scale` GC. **Trade-off:** ephemeral workers pay claude spawn latency per task
instead of reusing a warm pane. (The ntm warm floor of 4 / ceiling of 6 existed
to amortize that latency; under ephemeral workers the pool policy goes away.)

## Feature parity vs ntm

| Capability                         | ntm                        | herdr                                             |
| ---------------------------------- | -------------------------- | ------------------------------------------------- |
| Persistence                        | tmux sessions              | ✅ server/client daemon + named sessions           |
| Drive from outside a pane          | ✅ (tmux server)            | ✅ (socket; `HERDR_ENV` only for the in-pane hook) |
| Discovery JSON                     | `status --json`            | ✅ `pane/agent list --json`                         |
| Send text / slash commands         | `ntm send`                 | ✅ `pane send-text` + `send-keys Enter` / `pane run`|
| Readiness / status                 | scrape + `--robot-wait`    | ✅ **push-based** `agent_status` + `agent wait`     |
| Busy/idle/done/blocked signal      | heuristic                  | ✅ first-class states                               |
| First-class worktrees              | `--worktrees` flag         | ✅ `worktree` subcommand family                     |
| Agent addressed by name/label      | pane index only            | ✅ pane id **or** name/label                        |
| Remote/SSH                         | —                          | ✅ `--remote`                                       |
| Label→git-hook enforcement         | ✅ `ntm init` + labels      | ❌ none — replaced by worktree-detection git hook   |
| Cross-pane grep                    | ✅ `ntm grep`               | ❌ loop `agent read` in-skill                       |
| Scale / pool GC                    | ✅ `ntm scale`              | ❌ per-resource `workspace close`/`pane close`      |
| Per-pane context-token %           | ✅ `context_percent`        | ❌ (use `blocked`/`done` instead)                   |

The three ❌ gaps are all **mechanical to reimplement** and none block the model.
Under the ephemeral-worker redesign, `scale`/pool-GC is not even needed.

## Gotchas discovered

- **`agent wait` races agent registration.** Calling it right after launching
  claude returns `{"error":{"code":"agent_not_found"}}` — the agent isn't
  registered until its hook first reports. Poll `agent get`/`pane list` until the
  agent appears (`agent != null`) *before* waiting on status. (herdr analog of
  ntm's unreliable `add`-index.)
- **`agent start --cwd` ≠ herdr placement** — see Pattern B above; pass
  `--workspace`/`--tab` to avoid orphaning the pane in the focused workspace.
- **TUI input = `send-text` + `send-keys Enter`.** `agent send`/`pane send-text`
  write *literal* text (no newline); `pane run` appends Enter but is meant for
  shell command text. For a TUI agent, send the text then a separate `Enter`.
- **`worktree create` yields a shell, not an agent** — launch is a second step.
- Slash-command dispatch (`/execute-task NNN`) was **not** exercised end-to-end,
  but it is the same text+Enter path that delivered the PONG prompt — low risk,
  still worth confirming during migration.

## Spike log (evidence, herdr 0.7.1, 2026-07-09)

Everything below was run live and cleaned up; the user's live session (workspaces
`w1`/`w2`/`w3`) was left untouched.

1. **Server/socket/persistence** — `herdr status` shows server running (protocol
   14, socket at `~/.config/herdr/herdr.sock`); `session list` shows a persistent
   `default` session.
2. **Control path from outside a pane** — `session/workspace/agent/pane list` all
   returned JSON from a plain shell with `HERDR_ENV` unset.
3. **Push-based status is live** — `pane list` showed the pre-existing `w1:p1`
   claude agent as `agent_status: idle` with no scraping.
4. **Enforcement hook** — isolated repo; all four planner/worker × main/feature
   cases behaved correctly (table above).
5. **One-call worker** — `worktree create` produced git worktree
   (`is_linked_worktree: true`, branch `spike/herdr-status`) + workspace `w4` +
   tab + shell pane `w4:p1` in a single call.
6. **Status transition (Pattern A)** — launched claude via `pane run`; it went
   `unknown → idle` (registered), then on a "reply PONG" prompt
   `agent wait --status working` fired, then `agent wait --status idle` returned
   on `agent_status: done`; **PONG** confirmed in the pane's visible buffer.
7. **Explicit start in a worktree (Pattern B)** — `agent start spikeworker --cwd
   <wt>` started claude with `cwd` = worktree (git confirms linked worktree,
   role=worker) but placed the pane in the focused workspace `w1` (`w1:p3`),
   exposing the `--cwd`-vs-`--workspace` gotcha.
8. **Teardown** — `workspace close` reaped pane + worktree; branches deleted; `0`
   spike worktrees remained; pane list returned to the user's own set.

## Open questions / next steps

- Confirm slash-command kickoff (`/execute-task NNN`) end-to-end in a worker.
- Reimplement cross-pane scan (`ntm grep` → loop `agent read`) and any GC
  (`workspace close`) needed by `status-report`.
- Decide the enforcement-hook install mechanism (repo `core.hooksPath` vs global).
- Write the migration for `delegate`, `delegate-task`,
  `status-report` (and their refs) to herdr-only, plus whether the
  planners/workers **pool** vocabulary survives or is replaced by
  primary-checkout-vs-worktree.
