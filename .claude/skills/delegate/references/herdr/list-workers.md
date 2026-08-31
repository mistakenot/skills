# Discovering workers (herdr)

Enumerate the panes/agents herdr knows about and read their metadata.

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
  tracks as a first-class, named, status-reporting entity. A pane can host no
  agent (a plain shell — `agent` is `null` / absent), or one.

## Commands

```bash
herdr workspace list                              # workspaces (+ labels, agent_status)
herdr pane      list [--workspace <id>]           # every pane: pane_id, agent, agent_status, cwd, tab_id, workspace_id
herdr agent     list                              # only panes running a recognized agent
herdr agent     get <target>                      # one agent's full record
herdr worktree  list --cwd <repo> --json          # git worktrees for a repo, each with is_linked_worktree
```

**Correction to a common assumption:** `--json` is not universal. `pane list`,
`agent list`, `workspace list`, and `tab list` **reject** `--json`
(`unknown option: --json`, verified live on 0.7.1) and print a JSON envelope
unconditionally regardless. `worktree list` and `session list` **do** accept
(and need) `--json` — without it they print human-readable text. Check
`herdr <noun> --help` before assuming either way; don't add `--json` reflexively.

## Determining which agent occupies a pane

The `agent` field on a pane/agent record is the coding-agent's label
(`claude`, `codex`, `null` if the pane is a plain shell or the agent isn't
recognized yet). Detection is independent of *how* the process was launched —
herdr recognizes it from the running process plus an installed integration
hook, so even a plain shell that later runs `claude` gets picked up.

Useful fields on a pane/agent record:

| Field | Meaning |
| --- | --- |
| `agent` | coding-agent label (`claude`/`codex`/…), or absent for a plain shell |
| `agent_status` | `idle \| working \| blocked \| done \| unknown` |
| `cwd` | the process's working directory |
| `foreground_cwd` | cwd of whatever is currently running in the pane's foreground |
| `workspace_id` | owning workspace (`w1`, `w3`, …) |
| `tab_id` | owning tab (`w1:t1`, …) |
| `pane_id` | this pane (`w1:p1`, …) |
| `name` (agent list only) | the agent's name, set at `agent start <name>` or `agent rename` |
| `label` (pane list only) | the pane's label, set at create/split `--label` or `pane rename` |

**Targets** for `agent *` subcommands accept a **pane id** (`w4:p1`), a unique
agent **name**, or a detected agent **label** — not only indices.

## Gotcha — pane ids are not durable

Pane ids look like `w<workspace>:p<pane>` and **recompact as resources close**.
Never cache a pane id across calls that might have torn something down —
always re-resolve from a fresh `list` immediately before use.

## Verified live (read-only)

- `herdr workspace list` on a running 0.7.1 session with real live workspaces:
  confirmed it rejects `--json` (`usage: herdr workspace list`) and prints JSON
  unconditionally.
- `herdr pane list`, `herdr agent list`: same — both reject `--json` and print
  JSON unconditionally. `herdr tab list` also rejects `--json`.
- `herdr worktree list --cwd <repo> --json`, `herdr session list --json`: both
  accept and require `--json` for machine output.
- Confirmed a pane hosting an agent started as e.g. `lane1-vendor` shows
  `"label":"lane1-vendor"` in `pane list` and `"name":"lane1-vendor"` in
  `agent list` for the same `pane_id` — see `label-worker.md` for the nuance
  this implies about how naming is stored.
