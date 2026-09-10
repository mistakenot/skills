# auto-stack-multi-host-epic

An epic-sized planning task over a real monorepo, for A/B-ing `new-epic`.

```bash
make evals ARGS='run --skill new-epic --with rich-doc --arm HEAD --arm WORKTREE \
    --scenario auto-stack-multi-host-epic --n 2'
```

`--with rich-doc` is required: `new-epic` loads it to build the document.

## Ground truth

The initiative was planned for real as auto-stack epic 003 (2026-06-18) and
implemented as ten tasks over the following ten days. Compare each arm's
output against:

- `docs/epics/003-multi-host-architecture/epic.html` on auto-stack `main` —
  the human-authored epic: five named seams, eight functional and eight
  non-functional guard rails, a ten-task DAG, four decisions.
- `docs/tasks/{028,030,031,038,039,040,041,042,045,046,047}-*/feedback.md` —
  what the executors hit. In particular task 042's `doc.raw` shape mismatch
  (base64 from autowatch vs raw bytes at the browser contract): a seam that
  drifted because it was named but not specified.

## What to judge

Read `REPORT.md` in its own order (did the skill fire, then the table, then the
outputs). Then, for each arm's `epic-003-*.html`:

1. **Seams on dependency edges.** For every `depends-on` between tasks, is
   there a contract concrete enough for the downstream task to build against
   before the upstream one lands — shape, not a sentence? Would it have
   caught the 042 mismatch?
2. **Assumption register.** Are the load-bearing assumptions listed, with what
   depends on each? (The real epic's review threads caught two: cross-host
   project identity collisions, and cross-user unix-socket permissions.)
3. **DAG shape.** Walking skeleton first, then shallow and wide — or a chain?
   Does task 1 touch every seam?
4. **Invalidation.** Is there any statement of what happens when an assumption
   fails mid-flight — which tasks replan, which continue?
5. **Altitude.** Did it stay at containers and contracts, or drop into files?

Expect run-to-run spread of the same arm to be large; `--n 2` or more, and read
every trial before concluding anything.
