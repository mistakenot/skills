# Spawning a worker (herdr)

Create a new coding-agent worker. herdr does **not** launch agents from a
registry — **you always supply the agent's launch command**; herdr wraps it
into a managed, tracked agent. Two paths.

## Pattern A — worktree worker (recommended for task execution)

One call makes the git worktree **and** a dedicated workspace+tab+pane, then
you launch the agent into that pane:

```bash
J=$(herdr worktree create --cwd <repo> --branch task/NNN --base main \
      --path <wt-path> --no-focus --json)
PANE=$(echo "$J" | jq -r .result.root_pane.pane_id)     # pane sits in the worktree's own workspace
herdr pane run "$PANE" "claude --dangerously-skip-permissions"
```

The agent lives in the worktree's **own** workspace, `cwd` = worktree. One
worktree ↔ one workspace ↔ one agent, cleanly bound; tear down with a single
`workspace close` (see `reap-worker.md`).

`worktree create` accepts `[--workspace ID | --cwd PATH] [--branch NAME]
[--base REF] [--path PATH] [--label TEXT] [--focus|--no-focus] [--json]`. It
returns `root_pane`, `tab`, `workspace`, and `worktree` in its JSON. The
created pane is a **plain shell** — there's no `--agent`/`--run` flag on
`worktree create`; launching the agent is a deliberate second step, exactly as
shown above.

## Pattern B — `agent start` (first-class launch)

```bash
herdr agent start <label> --cwd <path> [--workspace <id>] [--tab <id>] \
      [--split right|down] [--env KEY=VALUE] --no-focus -- claude --dangerously-skip-permissions
```

- The `argv` after `--` is **required** — it's the command herdr runs (there
  is no "launch claude by name").
- The agent becomes a named, tracked entity (`name=<label>`) from birth —
  `<label>` here is the same string that later shows up as `name` in
  `agent list` output (see `label-worker.md`).
- **Gotcha:** `--cwd` sets the *process* working directory (what git and any
  enforcement hook see), **not** herdr placement. Without `--workspace`/`--tab`
  the pane splits into the **currently-focused** workspace. Pass `--workspace`
  (and usually `--tab`) to place it where you intend — otherwise you orphan
  the agent in the focused workspace while its intended workspace sits empty.
- `--split right|down` controls split direction when landing in an existing
  tab (verified present in `herdr agent start --help` on 0.7.1; not documented
  in earlier notes).

## Lower-level building blocks

```bash
herdr workspace create [--cwd PATH] [--label TEXT] [--env KEY=VALUE] [--focus|--no-focus]
herdr pane split <pane> --direction right|down [--ratio FLOAT] [--cwd PATH] [--env KEY=VALUE] [--focus|--no-focus]
herdr pane run <pane> "<command>"     # types command + Enter into a pane's shell (shells only, not TUI agents — see send-prompt.md)
```

Use these directly only when neither Pattern A nor Pattern B fits (e.g. you
need a bare shell pane, or a workspace with no agent yet).
