# Getting a clean-context worker — spawn fresh, never `/clear`

"Reset a worker" means: get a worker back to a fresh, empty-context state so
it can be reused for a new task without inheriting the previous task's
conversation history. Two runners (herdr and ntm) independently converge on
the same answer here: **discard the worker and spawn a new one.** This is not
a herdr-specific workaround for a herdr-specific gap — it's the correct,
runner-agnostic answer, because the alternatives fail for reasons that live in
the agent CLI, not in the multiplexer.

## `/clear` (or any agent slash-command reset) — never

**Never** drive a worker's own reset via `send-text`/`send-keys`
(`herdr pane send-text <pane> "/clear"` then `send-keys Enter`) to "reset" an
existing pane. `/clear` is a **cooperative** command: the agent's TUI queues
it behind whatever the agent is currently doing and runs it later. Send it to
a pane you have merely *misread* as idle and it does not reject or no-op — it
silently queues and detonates mid-task. This destroyed a real task's work
(task 047). Its return value cannot tell you whether it actually ran.

This hazard belongs to the **agent CLI**, not to the multiplexer: herdr's
`send-text` delivers the identical keystrokes to the identical TUI that ntm
does, so the risk transfers to herdr **unchanged**. It is not a matter of
verifying `/clear` per-agent before trusting it — treat it as prohibited
regardless of which agent or which multiplexer is driving it.

## herdr has no native in-place reset primitive either

Searched exhaustively across `herdr agent --help`, `herdr pane --help`,
`herdr workspace --help`, `herdr tab --help`, `herdr session --help`, and
`herdr config --help` on 0.7.1 (live, read-only) for anything resembling
`reset`/`clear`/`restart`/`resume`. The only hits: `herdr config reset-keys`
(keybindings, unrelated) and the `resume_agents_on_restore` config flag (see
`reap-worker.md` — that's about surviving a herdr *server* restart, the
opposite of clearing context). There is no `herdr agent reset` or equivalent
in-place restart command to reach for even if `/clear` were safe.

(For comparison: ntm *does* expose in-place restart commands
(`--robot-smart-restart`, `respawn`, `--robot-restart-pane`), and all three are
verified broken on ntm 1.18.2 — see `refs/ntm/reset-worker.md`. So the two
runners land in the same place by different roads: ntm's in-place path exists
but is broken, herdr's doesn't exist at all. Either way, in-place reset is not
available — this is a converged, fundamental constraint, not a tool wart to
work around.)

## Spawn a fresh worker — the only supported path

Treat "reset" as reap + spawn, using only verified herdr mechanism:

1. `reap-worker.md` — close the pane (`pane close`) or, for a worktree
   worker, close the whole workspace (`workspace close`, which also removes
   the worktree).
2. `spawn-worker.md` — create a fresh worker (new worktree + Pattern A launch,
   or a fresh `agent start` call).

A newly spawned worker is clean by construction: a brand-new agent process
with empty context. There is no reset step for it — once spawned, you simply
[send](send-prompt.md) the task. Existing workers are never context-reset in
place; once a dispatched worker finishes its task its context is dirty, so it
is reaped rather than reused.
