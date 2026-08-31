# Waiting for a worker to be ready (herdr)

Block until an agent reaches a given state, or until its output matches a
pattern. Status is **push-based** (from the integration hook), both queryable
and blocking-waitable.

## Two different status-wait commands — they are not interchangeable

herdr 0.7.1 has **two** commands that block on agent status, under different
namespaces, with different accepted values and different target semantics.
Verified live (both are read-only checks against real panes):

```bash
herdr agent wait <target> --status idle|working|blocked|unknown [--timeout MS]
herdr wait agent-status <pane_id> --status idle|working|blocked|done|unknown [--timeout MS]
```

- `herdr agent wait` takes an **agent target** (pane id, unique agent name, or
  detected label) and resolves it to an agent record on success:
  `{"result":{"agent":{...agent_status, cwd, pane_id, ...}}}`.
  **It rejects `--status done` outright** — confirmed live:
  `Error: Custom { kind: Other, error: "done is a UI attention state; use idle
  for CLI agent completion waits" }`. Use `--status idle` to wait for a turn to
  finish.
- `herdr wait agent-status` takes a **pane id specifically** (not a name/label
  — an invalid pane-id-shaped string fails with a decode error, not
  `agent_not_found`) and **does** accept `--status done`. On success it
  returns an event object: `{"event":"pane.agent_status_changed","data":{...}}`.

Prefer `herdr agent wait <target> --status idle` for "the agent finished its
turn" — it's the one that also accepts a name/label instead of a raw pane id,
and it's the one the `herdr agent --help` surface treats as canonical.

Also:

```bash
herdr agent get  <target>                                        # non-blocking snapshot: agent_status
herdr wait output <pane> --match PONG [--regex] [--raw] [--source visible|recent|recent-unwrapped] [--lines N] --timeout 60000
```

`wait output` blocks until a pane's captured text matches `--match` (literal
by default, `--regex` for a pattern).

## State vocabulary

`idle | working | blocked | done | unknown`.

- `idle` — no turn in progress; the agent is waiting for input. This is the
  state to wait for when you mean "ready for the next prompt" or "finished".
- `working` — a turn is actively running.
- `blocked` — a permission prompt or other stall is waiting on the human/driver.
- `done` — "finished a turn" as a **transient UI-attention signal**, distinct
  from `idle`; it is what `wait agent-status`/`pane list`/`agent list` can
  report as a momentary status, but `agent wait` explicitly refuses to treat
  it as a waitable target state (see above) — wait for `idle` instead.
- `unknown` — no status has been reported yet (e.g. a plain shell, or an agent
  whose integration hook hasn't fired).

## Gotcha — `agent wait` races registration

Right after launching an agent it isn't registered yet; `agent wait <pane>`
returns `{"error":{"code":"agent_not_found","message":"agent target <x> not
found"}}` (exact shape verified live against a nonexistent target). **Poll
`agent get`/`pane list` until the agent appears (`agent != null`) before
waiting on its status.**
