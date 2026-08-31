# Getting a clean-context worker — spawn fresh, never `/clear` or in-place restart

A new task must run in a pane with **clean context**. Two tempting ways to
reset an *existing* pane both fail; only spawning a fresh pane is reliable.

**1. `/clear` — never.** `/clear` is a *cooperative* command: the TUI queues
it behind whatever the agent is doing and runs it later. Send it to a pane you
misread as idle and it does not reject or no-op — it silently queues and
detonates mid-task. This is what wiped task 047. Its return value can't tell
you whether it actually ran.

**2. In-place process restart — broken here, do not use.**
`--robot-smart-restart`, the `respawn` subcommand, and `--robot-restart-pane`
all kill the agent and re-run its launch command in the same pane. Verified on
**ntm 1.18.2** (2026-06-27) with a single-Claude throwaway session:

- `ntm --robot-smart-restart=<session> --panes=<n>` → `FAILED`,
  `can't find window: <n>` — it treats the flat pane index as a tmux *window*
  index (addressing bug). `--hard-kill` fails too (`tmux list-panes failed`).
- `ntm respawn --panes=<n> --force` → the relaunched `claude` starts, then
  **crashes back to a bash shell** within seconds (the re-run launch line
  reuses a `systemd-run --scope` whose name the exiting process still holds).
- Worse, `ntm --robot-restart-pane=<session> --panes=<n>` reports
  `success / prompt_sent / process_alive:true` **anyway** and sends the
  `--restart-prompt` **into the bash shell**, where it runs as a shell
  command. A silent failure that misroutes the dispatch — strictly worse than
  `/clear`.

**3. Spawn a fresh pane (`ntm add`) — the only reliable reset.** A newly
added pane is clean by construction: a brand-new `claude` with empty context
and its own systemd scope (so it survives). Verified: a fresh pane answers
`NO_CONTEXT` to a prior pane's codeword. Existing panes are never
context-reset in place — see [spawn-worker.md](spawn-worker.md) for the spawn
procedure. Once a dispatched pane finishes its task its context is dirty, so
it is *reaped* rather than reused — see [reap-worker.md](reap-worker.md).
There is no reset step for a fresh pane: after spawning, you simply
[send](send-prompt.md) the task.

> If a future ntm release fixes in-place restart (a clean relaunch that
> survives and only sends the prompt once the agent is back up), it can
> replace the spawn-fresh step — but re-verify the codeword/`NO_CONTEXT` check
> first before relying on it.
