# Scanning output across all workers (herdr)

Search for a pattern across every worker's output.

## No cross-pane grep

Unlike ntm's `ntm grep`, **herdr has no built-in fleet-wide search**. There is
no `herdr agent grep` / `herdr pane grep` / anything equivalent. This is a real
capability gap versus ntm, not a documentation gap — confirmed absent from
`herdr agent --help` and `herdr pane --help` on 0.7.1 (no `grep`/`search`
subcommand under either).

## The documented workaround: loop + filter in the caller

Enumerate agents, read each one's output, and filter yourself:

```bash
for target in $(herdr agent list | jq -r '.result.agents[].pane_id'); do
  text=$(herdr agent read "$target" --source recent --lines 200 | jq -r '.result.read.text')
  if echo "$text" | grep -q "PATTERN"; then
    echo "=== $target ==="
    echo "$text" | grep "PATTERN"
  fi
done
```

Notes on the loop:

- Use `agent list` (not `pane list`) to skip plain shells with no agent —
  unless you deliberately want to scan shell panes too, in which case use
  `pane list` and its `pane_id`s instead.
- Prefer `agent read` over `pane read` here because `agent read`'s output is
  JSON with the text nested at `.result.read.text`, which is straightforward
  to pull with `jq` inside a loop — see `read-output.md` for why `pane read`
  is less convenient for scripting (it prints raw text, no envelope).
- Re-fetch `agent list` fresh each time you run the loop; pane ids recompact
  and are not safe to cache across separate invocations (see
  `list-workers.md`).
- `--source recent-unwrapped` avoids false negatives/positives from terminal
  line-wrapping splitting your pattern across lines, if you're matching
  something long.

## Gotcha

For a fleet of any real size this is O(N) round-trips with no batching — there
is no bulk-read endpoint. Budget for that when scanning many workers.
