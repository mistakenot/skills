# Worker pools — planners and workers

How agent panes are organised into two **role-separated pools** — **planners**
and **workers** — so that git hooks can enforce which operations each pool is
allowed to perform. This is the *pool model*: how panes/worktrees are
organised and role-labelled. It holds regardless of which runner is driving
the panes — the runner-specific mechanics live in `references/<runner>/`, and
this file's own `{{ .runner }}` placeholders resolve there.

For the mechanics of discovering panes, identifying each agent's type, and
sending text or slash commands once you have a runner selected, see
[references/agent-conventions.md](references/agent-conventions.md) and
`references/{{ .runner }}/`. The delegate family —
[/delegate](../delegate/SKILL.md),
[/delegate-task](../delegate-task/SKILL.md), and
[/status-report](../status-report/SKILL.md) — carries the `runner`
variable and dispatches into the **workers** pool described here.

## Why roles matter

Roles are not cosmetic. Git hooks (installed by the runner's own init step)
read a pane/worktree's **role label** to decide which operations it may
perform. A pane created **without** a role label gets none of the pool rules
applied. **Always apply a role label when spawning or adding a pane** —
otherwise planners could push feature branches, or workers could commit
straight to `main`, and nothing would stop them. See `references/{{ .runner }}/label-worker.md`
for how to set the label under the selected runner.

## Pool model

| Pool         | Role label  | Default count         | Works on   | Allowed operations                                          |
| ------------ | ----------- | ---------------------- | ---------- | -------------------------------------------------------------- |
| **Planners** | `planners`  | 4 (2 cc + 2 cod)       | `main`     | Read code, analyse, write planning docs, commit to `main`      |
| **Workers**  | `workers`   | 0 (added on demand)    | worktrees  | Check out branches, create worktrees, open PRs                 |

**Planners** do deep analysis and write planning docs. They work directly on
`main` — since they rarely touch the same files, conflicts are uncommon. The
planning, review, and commit skills (`new-task`,
`new-solution`, `new-plan`, `review-task`,
`commit-task`) run in a planner pane.

**Workers** execute tasks in isolated worktrees with their own branch and
tooling, and open PRs when complete. `execute-task` runs in a
worker pane. **Workers must never work in the primary checkout** — always a
worktree (see [references/worktree-conventions.md](references/worktree-conventions.md)).

## Prerequisites

- The selected runner installed and on PATH.
- A project directory under the runner's configured project base.
- The runner initialised in the project directory — this sets up the config
  and git hooks that enforce the role rules above. Without it, role labels
  carry no enforcement.

## Bringing up the planner pool

Spawn one pane per planner and apply the `planners` role label as you go.
See `references/{{ .runner }}/spawn-worker.md` for spawning and
`references/{{ .runner }}/label-worker.md` for applying the role label.

## Adding workers on demand

Workers start as an empty pool — add capacity only when a task is
dispatched, rather than pre-allocating a large pool. Add **one** worker per
dispatch (never spawn repeatedly in a loop), and always apply the `workers`
role label — see the same two references above. The warm-floor / ceiling GC
policy for the worker pool (don't shrink below 4, never exceed 6, reclaim
surplus idle panes in `status-report`) is documented in
`status-report` itself; the reap mechanism per runner is `references/{{ .runner }}/reap-worker.md`.

## Sending prompts to a pool

Address the target pool by its project and role. See
`references/{{ .runner }}/send-prompt.md` for the per-runner send
mechanism, including how to target a whole pool versus a single pane.

## Listing pools

See `references/{{ .runner }}/list-workers.md` for the per-runner discovery
commands. Prefer their JSON output forms when parsing programmatically —
human-readable tables are not stable across runner versions.

## Key points

- **Always apply a role label when spawning or adding a pane.** Hooks read
  role labels to enforce pool rules — without one, the rules don't apply.
- **Planners commit directly to `main`. Workers use branches and open PRs.**
- **Workers never work in the primary checkout** — always a worktree.
- **Add workers incrementally** as tasks are dispatched, rather than
  pre-allocating a large pool.
