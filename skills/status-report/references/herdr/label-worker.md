# Labeling / tagging a worker (herdr)

How to attach and query identifying metadata on a worker. This is the
mechanism only — what pool/role a label denotes (e.g. planner vs worker) is
policy and lives in the skill body, not here.

## No session-level tagging

`session list` exposes only `name`, `default`, `running`, `session_dir`,
`socket_path`; there is no `session rename` and no arbitrary metadata. A
session's only identity is the **name** chosen at creation
(`herdr --session <name>`), and it's immutable.

## Labels/names exist at workspace, tab, pane, and agent level

```bash
herdr workspace rename <workspace_id> <label>
herdr tab       rename <tab_id> <label>
herdr pane      rename <pane_id> <label>|--clear
herdr agent     rename <target> <name>|--clear
```

Set a label/name either at creation (`--label TEXT` on `workspace create` /
`tab create` / `pane split` / `worktree create`, or the required `<name>`
positional on `agent start`) or after the fact with the `rename` subcommands
above.

**Naming nuance (verified live via `list-workers.md`'s inspection, not by
running `rename` — see Unverified below):** the same underlying string shows
up under **different field names** depending on which list you query for the
same pane. A pane whose hosted agent was started as `agent start lane1-vendor
...` showed up as `"label":"lane1-vendor"` in `herdr pane list` and
`"name":"lane1-vendor"` in `herdr agent list`, for the identical `pane_id`.
Practically: query `agent list` → `.name` if you think in terms of "the
agent's name", and `pane list` → `.label` if you think in terms of "the
pane's label" — for an agent-hosting pane these read as the same value.

> **UNVERIFIED:** whether `pane rename <pane_id> <label>` on an agent-hosting
> pane also changes what `agent list` reports as that agent's `name` (and vice
> versa for `agent rename`), or whether the two are independently-stored
> fields that merely started out equal because `agent start`'s `<name>`
> argument happens to set both at creation time. Not tested because `rename`
> mutates live state and was out of scope for read-only verification. To
> settle: run `agent rename <target> <newname>` on a scratch pane, then check
> whether `pane list`'s `label` for that pane changed too.

## The only structured, non-display metadata: `--env`

`--env KEY=VALUE` (on `workspace create` / `tab create` / `pane split` /
`agent start`) is the only **structured** metadata and the only kind that
*does* something beyond display: it lands in the process environment, so a git
hook or the agent itself can read it (e.g. `--env HERDR_ROLE=worker`).

## `pane report-metadata` — richest channel, but transient and integration-facing

```bash
herdr pane report-metadata <pane_id> --source ID [--agent LABEL] [--applies-to-source ID] \
  [--title TEXT|--clear-title] [--display-agent TEXT|--clear-display-agent] \
  [--custom-status TEXT|--clear-custom-status] [--state-label STATUS=TEXT] [--clear-state-labels] \
  [--seq N] [--ttl-ms N]
```

This is how integrations push presentation state (title, custom status,
per-state labels) — it's **pane-scoped and transient** (note the `--ttl-ms`),
not a place for durable tags. There are sibling calls
`pane report-agent`/`pane report-agent-session`/`pane release-agent` used by
integration hooks to register/release an agent on a pane; these are the
plumbing behind status reporting, not something you'd call directly to label
a worker.

## Deriving role without any tag at all

For a planner/worker split specifically, prefer deriving role from
**worktree-ness** — `is_linked_worktree` on a `worktree list` entry (pure git:
linked worktree ⇒ worker, primary checkout ⇒ planner) — rather than a label.
It needs no metadata and works even outside herdr. Labels/names are then only
for human-readable organization.
