# Reading output from one worker (herdr)

Capture recent terminal output from a single pane or agent.

```bash
herdr pane  read <pane>   --source visible|recent|recent-unwrapped [--lines N] [--format text|ansi]
herdr agent read <target> --source visible|recent|recent-unwrapped [--lines N] [--format text|ansi]
```

- `visible` = current screen; `recent` = scrollback tail; `recent-unwrapped` =
  scrollback without line-wrapping (use this for parsing long single lines,
  e.g. JSON, that the terminal has soft-wrapped).
- `--lines N` caps how much scrollback to return.
- `--format text|ansi` — `text` strips escape codes, `ansi` preserves them.

## Output-shape gotcha

`pane read` and `agent read` accept the same flags but return **different
envelopes**, verified live on 0.7.1:

- `herdr pane read <pane> ...` prints the **raw captured text directly to
  stdout** — no JSON wrapper, no `--json` flag exists for it.
- `herdr agent read <target> ...` prints a **JSON envelope**
  (`{"id":...,"result":{"read":{"text":"...", "truncated":false, ...}}}`) with
  the same captured text nested under `result.read.text`, again without any
  `--json` flag — it's just how this command always responds.

If you need the text to feed into a script for parsing/matching, prefer
`agent read` and pull `.result.read.text` with `jq`; `pane read`'s raw stdout
is meant for a human or for direct terminal display.

`target` for `agent read` accepts a pane id, unique agent name, or detected
agent label (same target resolution as other `agent *` commands).
