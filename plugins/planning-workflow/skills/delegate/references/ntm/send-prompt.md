# Sending a prompt to a worker

Deliver text or a slash command to a pane.

**By pane index — works for every agent type (the universal path):**

```bash
ntm send <session> --pane=<index> 'your prompt here'
```

**By agent type — convenience filters, but incomplete:**

```bash
ntm send <session> --cc  'prompt'   # all Claude Code agents
ntm send <session> --cod 'prompt'   # all Codex agents
ntm send <session>       'prompt'   # broadcast to ALL agent panes
ntm send <session> --all 'prompt'   # ALL panes, INCLUDING the user shell
```

> **Gotcha — there is no `--oc` type filter.** `ntm send` only exposes
> `--cc`, `--cod`, `--gmi`. The same holds for the global `--type` filter
> (`claude|codex|gemini|cursor|windsurf|aider`). **OpenCode can only be
> targeted by `--pane=<index>` / `--panes=<index>`** — never by type. Always
> resolve OpenCode's pane index from `ntm status --json` first (see
> [list-workers.md](list-workers.md)).

> **Gotcha — the default send path runs a CASS duplicate-check that can
> block.** By default `ntm send` checks CASS for similar past sessions and may
> stop on an interactive "duplicate work?" confirmation; it can also emit CASS
> errors to stderr (e.g. `search failed: … table not found: fts_messages`)
> that are noise, not failures. For unattended delegation, disable the check
> and bypass the gate:
>
> ```bash
> ntm send <session> --pane=<index> --no-cass-check 'prompt'
> ntm send <session> --pane=<index> --force-non-interactive 'prompt'
> ```
>
> `--no-cass-check` skips the lookup entirely; `--force-non-interactive` keeps
> the lookup but auto-declines the confirmation (destructive/ambiguous gates
> still fail closed). `--robot-send` does not run this gate.

**Programmatically, with delivery + acknowledgement (robust path):**

```bash
ntm --robot-send=<session> --panes=<index> --msg='your prompt' --track --timeout=50s
```

`--track` waits for the agent to acknowledge (echo-detected) and returns JSON
with `ack.confirmations[].latency_ms`. This works for **all three** agents,
including OpenCode (targeted by pane). Use it when you need to confirm the
message actually landed rather than fire-and-forget.
