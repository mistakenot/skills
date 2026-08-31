# Reclaiming (reaping) workers

Tear down surplus panes with `ntm scale`.

```bash
ntm scale <session> --cc=$((cc_total - to_reap)) --force --json
```

`--cc=N` sets the target *count* of Claude panes to scale down to (not the
number to remove) — compute the target count from the current total minus how
many you intend to reap. `--force` skips any confirmation prompt.

**`ntm scale` reaps the highest-index (newest) panes first and is not
busy-aware.** It will kill whatever pane sits at the top of the index range
regardless of whether that pane is idle or mid-task — so only point it at a
target count you have already confirmed drops panes you've verified are idle.
It does not selectively spare a busy pane sitting above idle ones; if a busy
pane occupies the highest index, scaling down would kill it before reaching
any idle panes beneath it.
