# Reading output from one worker

Capture the recent output of a single pane — used to confirm an agent's state
(e.g. a `❯` input prompt showing, an interstitial dialog, or a completed
response) when you don't want to wait on `--robot-wait` or need to see the
actual text.

```bash
ntm copy <session>:<index> --last 20 --quiet --output /dev/stdout
```

`--last N` controls how many trailing lines to dump; `--quiet` suppresses
extra ntm chrome; `--output /dev/stdout` writes the captured text straight to
stdout instead of a file.

**When in doubt, read the pane.** This is the fallback for any ambiguity about
what an agent is doing — it dumps exactly what's on screen rather than relying
on inferred state.
