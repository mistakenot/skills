# Labelling workers

How `ntm` labels are applied to sessions/panes and how sessions end up named
by label. This is the mechanism only — for what the `planners`/`workers` pools
mean and which operations each is allowed to perform, see the policy in
`references/worker-pools.md` and the delegate-family skill bodies.

## Applying a label when spawning or adding

```bash
ntm spawn <project> --label planners --cc=2 --cod=2
```

```bash
ntm add <project> --label workers --cc=1
```

```bash
ntm spawn <project> --label workers --cc=2 --worktrees
```

`--label` accepts an arbitrary label string; it is not restricted to
`planners`/`workers`. `--worktrees` gives each spawned agent its own git
worktree automatically.

## Why labels matter (mechanism)

Git hooks (installed by `ntm init`) read a pane's **label** to decide which
git operations it may perform. A pane spawned **without** a label gets none of
the label-keyed hook rules applied — the hooks have nothing to key off. Always
pass `--label` when spawning or adding panes if you want hook enforcement to
apply.

## Session naming

Labelled sessions are named `<project>--<label>`, e.g. `auto-stack--planners`
and `auto-stack--workers`. Address a labelled session directly by that
composite name — the label is part of the session identifier, not a separate
query parameter.

## Targeting a labelled session

Send/list operations take the `<project>--<label>` session name exactly like
any other session name, and can still be combined with the type filters from
[send-prompt.md](send-prompt.md):

```bash
ntm send auto-stack--planners "review the auth module and write findings"
ntm send auto-stack--workers "implement the auth refactor from task 042"
ntm send auto-stack--planners --cc "focus on the Go packages"
```

```bash
ntm list --project auto-stack     # both labelled sessions for one project
```
