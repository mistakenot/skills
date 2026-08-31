# Sending a prompt to a worker (herdr)

Drive an agent by typing text into its pane.

```bash
herdr pane send-text <pane> "<text>"     # writes LITERAL text, no Enter
herdr pane send-keys <pane> Enter        # send a key
herdr agent send <target> "<text>"       # literal text to an agent (no Enter)
herdr pane run  <pane> "<command>"       # command text + Enter (for a shell)
```

## To drive a TUI agent: `send-text` then a separate `send-keys Enter`

`send-text` and `agent send` **deliberately omit the newline**. To actually
submit a prompt to a TUI coding agent (claude/codex/opencode/…), you must
issue **two separate calls**:

```bash
herdr pane send-text <pane> "<prompt text>"
herdr pane send-keys <pane> Enter
```

A single `send-text` call leaves the text sitting in the input box, unsent.

## `pane run` is for shells, not TUI agents

`herdr pane run <pane> "<command>"` types command text **and** appends Enter
in one call — but it's meant for a plain shell pane (e.g. running a command in
a freshly-created worktree pane before the agent is launched, per
`spawn-worker.md` Pattern A). Do not use `pane run` to prompt a running TUI
agent; use the `send-text` + `send-keys Enter` pair instead.

## Slash commands are just text

Slash commands are sent the same way as any other prompt:

```bash
herdr pane send-text <pane> "/execute-task NNN"
herdr pane send-keys <pane> Enter
```

This is the same text+Enter path as a normal prompt — there's no special
slash-command primitive.

## Gotcha — confirm the input actually lands

Read the pane first if unsure whether an interstitial (a confirmation dialog,
a permission prompt, an in-progress turn) is swallowing your input instead of
receiving it as a new prompt. See `read-output.md`.

## `pane send-text` vs `agent send`

Both write literal text with no trailing newline. `pane send-text` targets a
pane id; `agent send` targets an agent (pane id, unique name, or detected
label). Functionally interchangeable for a pane that hosts a recognized
agent — pick whichever target form you already have on hand.
