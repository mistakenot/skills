# Tearing down a worker (herdr)

Reclaim a worker's resources when it's done.

```bash
herdr pane      close  <pane>              # close one pane (e.g. an agent split you added)
herdr workspace close  <id>                # reaps the workspace's panes AND its worktree together
herdr worktree  remove --workspace <id> [--force] [--json]   # explicit worktree removal
herdr session   stop   <name> [--json]     # stop a whole session (daemon); 'default' targets the default session
herdr session   delete <name> [--json]
```

## Worktree worker (Pattern A) — one call tears it all down

A worktree worker binds **one worktree ↔ one workspace ↔ one agent**. Because
of that binding, `herdr workspace close <id>` is the **whole teardown** — it
reaps the pane(s) and the git worktree in a single shot. Follow with
`git branch -D task/NNN` afterward if you don't also need to keep the branch.

## `agent start` worker (Pattern B) landed in a shared workspace

If the agent was started with `agent start` into an existing/shared workspace
(not its own dedicated worktree workspace), use `herdr pane close <pane>` to
remove just that agent's pane without disturbing sibling panes in the same
workspace.

## Explicit worktree removal

`herdr worktree remove --workspace <id> [--force]` removes the git worktree
tied to a workspace without going through `workspace close`. Use `--force` if
the worktree has uncommitted changes you're deliberately discarding.

## Session-level teardown

`herdr session stop <name>` stops a whole session's daemon (`default` targets
the default session). `herdr session delete <name>` removes a stopped
session's persisted state. Both accept `[--json]` per `herdr session --help`
on 0.7.1. These are session-wide operations, not per-worker teardown — reach
for `workspace close` / `pane close` for a single worker.

## Related config

`[session] resume_agents_on_restore = true` in `config.toml` lets herdr
**resume supported agents into their native conversation session** after a
server restart — agent continuity a bare-bash launch wouldn't have. This is
about surviving a herdr *restart*, not a substitute for tearing a worker down
when you're actually done with it.
