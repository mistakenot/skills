# Driving herdr

How to use **herdr** — a terminal-native agent multiplexer — to discover, spawn,
drive, and tear down coding-agent workers. This is the practical operator's
guide; for the herdr-vs-ntm evaluation and the migration rationale see
`docs/research/herdr-vs-ntm.md`.

Everything here was verified live against **herdr 0.7.1**. Prefer the JSON forms
(`--json`) everywhere — results nest under `result.*` and the fields are stable;
human output is not.

## Mental model

A hierarchy — remember it, because the commands mirror it:

```
session        one persistent herdr server (a daemon + Unix socket + attachable "desktop")
  └ workspace  a project / cwd context (its own working directory)
      └ tab     a subcontext within a workspace
          └ pane a terminal split; may run a shell or an agent
              └ agent  a coding-agent process (claude/codex/opencode/…) in a pane
```

Key consequences:

- **A session is project-agnostic.** One session holds workspaces for many
  projects at once (e.g. `skills` and `auto-stack` side by side) — the project
  boundary is a **workspace `cwd`**, not the session. So anything that enumerates
  "the work" must filter by repo (`worktree list --cwd <repo>`, or a pane's
  `cwd`) rather than assuming one session == one project.
- **An agent is not a pane** — it's the *process running in* a pane, which herdr
  tracks as a first-class, named, status-reporting entity.

## Setup & prerequisites

- **Server/client daemon.** A persistent server owns all state; the CLI talks to
  it over `~/.config/herdr/herdr.sock`. Check it: `herdr status`.
- **Control works from *outside* a herdr pane.** Every socket command
  (`… list`, `agent start`, `pane run`, …) runs from a plain shell with
  `HERDR_ENV` unset. `HERDR_ENV=1` is only set *inside* herdr-managed panes and
  is used by the agent-state hook (the reporting side) — you don't need it to
  drive herdr. So a coordinator can drive herdr from anywhere.
- **Integrations produce status.** Install the per-agent hook once so agents
  report their state:

  ```bash
  herdr integration install claude    # writes ~/.claude/hooks/herdr-agent-state.sh
  herdr integration status            # install state + version per agent
  ```

  Available: pi, omp, claude, codex, copilot, devin, droid, kimi, opencode,
  kilo, hermes, qodercli, cursor. **Status/detection are independent of how an
  agent was launched** — herdr recognizes the agent from its running process (an
  agent-detection manifest) plus the installed hook, so even a plain shell that
  later runs `claude` gets picked up as an agent.

## Discovery

```bash
herdr session   list --json                       # sessions (daemons)
herdr workspace list                              # workspaces (+ labels, agent_status)
herdr pane      list [--workspace <id>]           # every pane: pane_id, agent, agent_status, cwd, tab_id, workspace_id
herdr agent     list                              # only panes running a recognized agent
herdr agent     get <target>                      # one agent's full record
herdr worktree  list --cwd <repo> --json          # git worktrees for a repo, each with is_linked_worktree
```

**Targets** for `agent *` accept a **pane id** (`w4:p1`), a unique agent
**name**, or a detected agent **label** — not only indices. Pane ids look like
`w<workspace>:p<pane>` and are **not durable** (they recompact as resources
close) — always re-resolve from a fresh `list`, never cache.

Useful pane/agent fields: `agent` (`claude`/`codex`/`null`), `agent_status`
(`idle|working|blocked|done|unknown`), `cwd`, `foreground_cwd`, `workspace_id`,
`tab_id`, `pane_id`.

## Spawning an agent

herdr does **not** launch agents from a registry — **you always supply the
agent's launch command**; herdr wraps it into a managed, tracked agent. Two
paths:

### Pattern A — worktree worker (recommended for task execution)

One call makes the git worktree **and** a dedicated workspace+tab+pane, then you
launch the agent into that pane:

```bash
J=$(herdr worktree create --cwd <repo> --branch task/NNN --base main \
      --path <wt-path> --no-focus --json)
PANE=$(echo "$J" | jq -r .result.root_pane.pane_id)     # pane sits in the worktree's own workspace
herdr pane run "$PANE" "claude --dangerously-skip-permissions"
```

The agent lives in the worktree's **own** workspace, `cwd` = worktree. One
worktree ↔ one workspace ↔ one agent, cleanly bound; tear down with a single
`workspace close`.

### Pattern B — `agent start` (first-class launch)

```bash
herdr agent start <label> --cwd <path> [--workspace <id>] [--tab <id>] \
      [--env KEY=VALUE] --no-focus -- claude --dangerously-skip-permissions
```

- The `argv` after `--` is **required** — it's the command herdr runs (there is
  no "launch claude by name").
- The agent becomes a named, tracked entity (`name=<label>`) from birth.
- **Gotcha:** `--cwd` sets the *process* working directory (what git and the
  enforcement hook see), **not** herdr placement. Without `--workspace`/`--tab`
  the pane splits into the **currently-focused** workspace. Pass `--workspace`
  (and usually `--tab`) to place it where you intend — otherwise you orphan the
  agent in the focused workspace while its worktree workspace sits empty.

### Lower-level building blocks

```bash
herdr workspace create [--cwd PATH] [--label TEXT] [--env KEY=VALUE] [--no-focus]
herdr pane split <pane> --direction right|down [--cwd PATH] [--env KEY=VALUE] [--no-focus]
herdr pane run <pane> "<command>"     # types command + Enter into a pane's shell
```

## Waiting for readiness & status

Status is **push-based** (from the integration hook), both queryable and
**blocking-waitable**:

```bash
herdr agent get  <target>                                    # snapshot: agent_status
herdr agent wait <target> --status working --timeout 15000   # block until it transitions
herdr agent wait <target> --status idle    --timeout 90000   # returns on idle/done
herdr wait output <pane> --match PONG [--regex] --timeout 60000   # block until output matches
```

States: `idle | working | blocked | done | unknown`. `done` means "finished a
turn" (distinct from `idle`); `blocked` covers permission prompts / stalls.

**Gotcha — `agent wait` races registration.** Right after launching an agent it
isn't registered yet; `agent wait <pane>` returns
`{"error":{"code":"agent_not_found"}}`. **Poll `agent get`/`pane list` until the
agent appears (`agent != null`) before waiting on its status.**

## Sending input

```bash
herdr pane send-text <pane> "<text>"     # writes LITERAL text, no Enter
herdr pane send-keys <pane> Enter        # send a key
herdr agent send <target> "<text>"       # literal text to an agent (no Enter)
herdr pane run  <pane> "<command>"       # command text + Enter (for a shell)
```

- **To drive a TUI agent (claude/codex/opencode): `send-text` then a separate
  `send-keys Enter`.** `send-text`/`agent send` deliberately omit the newline.
- **Slash commands are just text** — `send-text <pane> "/execute-task NNN"` then
  `send-keys <pane> Enter`. (This is the same text+Enter path verified to deliver
  a normal prompt; confirm end-to-end for a real `/execute-task` during use.)
- Confirm interstitials aren't swallowing input — read the pane first if unsure.

## Reading output

```bash
herdr pane  read <pane>   --source visible|recent|recent-unwrapped [--lines N] [--format text|ansi]
herdr agent read <target> --source visible|recent|recent-unwrapped [--lines N]
```

- `visible` = current screen; `recent` = scrollback tail; `recent-unwrapped` =
  scrollback without line-wrapping.
- **No cross-pane grep** (unlike ntm's `ntm grep`). To scan a fleet, loop
  `agent list` → `agent read` per agent and filter in the caller.

## Worktrees

```bash
herdr worktree list   [--cwd PATH | --workspace ID] [--json]
herdr worktree create [--branch NAME] [--base REF] [--path PATH] [--label TEXT] [--no-focus] [--json]
herdr worktree open   (--path PATH | --branch NAME) [--label TEXT] [--no-focus]   # attach existing
herdr worktree remove --workspace ID [--force]
```

- **`create` = `git worktree add` + open a herdr workspace+tab+shell-pane** in
  one call. Its JSON returns `root_pane`, `tab`, `workspace`, and `worktree`.
- The created pane is a **plain shell** — there's no `--agent`/`--run` flag;
  launching the agent is a deliberate second step (Pattern A).
- **`is_linked_worktree`** on each list entry distinguishes a linked worktree
  (a *worker*) from the primary checkout (a *planner*) — herdr surfaces the role
  signal structurally.
- **`open`** attaches an already-existing worktree/branch into a workspace.

## Lifecycle & teardown

```bash
herdr pane      close  <pane>              # close one pane (e.g. an agent split you added)
herdr workspace close  <id>               # reaps the workspace's panes AND its worktree together
herdr worktree  remove --workspace <id>   # explicit worktree removal
herdr session   stop   <name>             # stop a whole session (daemon); 'default' targets the default
herdr session   delete <name>
```

- For a Pattern-A worker, **`workspace close <id>` is the whole teardown** — it
  reaps the pane and the git worktree in one shot. Follow with
  `git branch -D task/NNN` if you don't need the branch.
- For a Pattern-B agent that landed in a shared workspace, `pane close <pane>`
  removes just that agent without disturbing siblings.
- Config `[session] resume_agents_on_restore = true` lets herdr **resume
  supported agents into their native conversation session** after a restart —
  agent continuity a bare bash launch can't give.

## Metadata & tagging

- **No session-level tagging.** `session list` exposes only `name`, `default`,
  `running`, `session_dir`, `socket_path`; there is no `session rename` and no
  arbitrary metadata. A session's only identity is the **name** chosen at
  creation (`herdr --session <name>`), and it's immutable.
- **Labels** (single freeform string) exist on **workspace / tab / pane** — set
  with `--label` at create or `<level> rename <id> <label>`.
- **`--env KEY=VALUE`** (on `workspace create` / `tab create` / `pane split` /
  `agent start`) is the only **structured** metadata and the only one that *does*
  something: it lands in the process environment, so a git hook or the agent can
  read it (e.g. `--env HERDR_ROLE=worker`).
- **`pane report-metadata`** (title, `display-agent`, `custom-status`,
  `--state-label STATUS=TEXT`, `--ttl-ms`) is the richest channel but is
  **pane-scoped, integration-facing, and transient** — it's how integrations push
  presentation state, not a place for durable tags.

For a planner/worker split, prefer deriving role from **worktree-ness** (pure
git: linked worktree ⇒ worker, primary checkout ⇒ planner) rather than a tag —
it needs no metadata and works even outside herdr. Session names / workspace
labels are then only for human organization.

## Gotchas (quick list)

- **Pane ids recompact** — re-resolve from a fresh `list`, never cache.
- **`agent wait` races registration** — poll until the agent exists first.
- **`agent start --cwd` ≠ placement** — pass `--workspace`/`--tab` too.
- **TUI input = `send-text` + `send-keys Enter`** (two calls; text has no newline).
- **`worktree create` yields a shell, not an agent** — launch is a second step.
- **One session spans projects** — filter enumerations by repo/cwd.
- **No cross-pane grep, no `scale`** — loop `agent read`; teardown per-resource.
- **You always supply the launch command** — herdr has no agent registry.

## Command reference

| Task | Command |
| --- | --- |
| Health / socket | `herdr status` |
| List sessions | `herdr session list --json` |
| List workspaces | `herdr workspace list` |
| List panes | `herdr pane list [--workspace <id>]` |
| List agents | `herdr agent list` |
| List worktrees | `herdr worktree list --cwd <repo> --json` |
| Install status hook | `herdr integration install claude` |
| New worktree worker | `herdr worktree create --cwd <repo> --branch task/NNN --base main --path <p> --no-focus --json` |
| Launch agent (Pattern A) | `herdr pane run <root_pane> "claude --dangerously-skip-permissions"` |
| Launch agent (Pattern B) | `herdr agent start <label> --cwd <p> --workspace <id> --no-focus -- claude --dangerously-skip-permissions` |
| Wait ready / done | `herdr agent wait <target> --status idle --timeout 90000` |
| Wait for output | `herdr wait output <pane> --match <text> --timeout 60000` |
| Send a prompt | `herdr pane send-text <pane> "<text>"` then `herdr pane send-keys <pane> Enter` |
| Read output | `herdr pane read <pane> --source recent --lines 50` |
| Reap a worker | `herdr workspace close <id>` |
| Close one agent pane | `herdr pane close <pane>` |
| Stop a session | `herdr session stop <name>` |
