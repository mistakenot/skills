# Spawning a new worker

Create a fresh Claude Code pane in an existing session.

```bash
ntm add <session> --cc=1 --json
```

**Re-discover the pane index from `ntm status` — do not trust `ntm add`'s own
output.** The `new_panes[].index` field in `ntm add --json` is unreliable: it
reported `0` while the real new pane was index `1`. Re-query and pick the
newly-added Claude pane (the `.command == "claude"` pane that wasn't there
before — in practice the highest-index `claude` pane):

```bash
ntm status <session> --json
```

See [list-workers.md](list-workers.md) for the `.panes[]` field shapes and how
to identify a pane's agent type from `.command`/`.type`.

`.command` flips to `claude` within ~2s of the pane being added, but the TUI
is not ready for input yet — block on idle before sending anything (see
[wait-for-ready.md](wait-for-ready.md)).

A freshly-spawned pane starts at zero context — it is clean by construction
(a brand-new `claude` process with empty context and its own systemd scope).
It needs no reset step: just send the task directly, targeting the new pane
explicitly by index (not a type-broadcast filter). See
[reset-worker.md](reset-worker.md) for why a *fresh* spawn is the only
reliable way to get a clean-context worker, as opposed to resetting an
existing pane.
