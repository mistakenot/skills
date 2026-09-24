# Open coding — the reviewer reads, you keep the machinery running

The reviewer reads plans in the review app and writes down what they notice in their
own words: span notes on the text, plus a pass/fail/defer verdict with a plan-level
note. There are no categories yet. Your job is to keep the app running, watch the
notes, and track saturation. You do not interpret the notes for them.

## Do not prime the reviewer

During open coding:

- never suggest failure categories
- never summarise their themes back to them
- never point at instances in a plan

Framing from you becomes their framing, and then the notes stop being independent
evidence. Answer direct questions, then step back. The app hides the skills version,
trial, model and cost. Don't reveal them either (don't read `runs/corpus.jsonl` or
`report` output aloud during a session).

## Session

1. **Serve.** Run `make plan-review ARGS='serve'` in the background. Give the user
   `http://localhost:8765/`; in a devcontainer the port must be forwarded. Explain
   the controls in one line:
   - select text → type a note → Enter saves it
   - `1` / `2` / `d` = pass / fail / defer; the plan-level note is saved with it
   - `←` / `→` move between plans
   - Progress lists everything noted so far

   Plans without a verdict open first, in a stable shuffled order.
2. **Watch** `src/plan-review/data/notes.jsonl` by polling every 2 s (not filesystem
   events). In Claude Code, use the Monitor tool:
   `f=src/plan-review/data/notes.jsonl; n=$(cat $f 2>/dev/null | wc -l); while true; do m=$(cat $f 2>/dev/null | wc -l); [ "$m" -gt "$n" ] && tail -n $((m-n)) $f | cut -c1-240; n=$m; sleep 2; done`.
   Elsewhere, run the same loop in the background, appending to a log you read on
   each turn.
3. **On each `verdict` event:**
   - Read every note on that plan and compare it with the themes from earlier plans.
   - Append one line to `src/plan-review/data/open-coding-log.jsonl`:
     `{"plan_id": ..., "ts": ..., "new_codes": [...], "repeat_codes": [...]}`.
     Each code is a short label **in the reviewer's own words** (in-vivo), not a
     category you invented.
   - Tell the user one line, e.g. "plan #4: 2 new themes, 1 repeat", without the
     labels unless they ask.

   The app charts this log.
4. **Re-review.** Once about five plans have verdicts, suggest one pass back over
   the first two. Criteria drift as the reviewer sees more, and the earliest plans
   were read with the least-developed eye.
5. **Saturation.** When three consecutive reviewed plans add at most one new theme
   between them, open coding has saturated. Offer axial coding. If the themes all
   come from one repo or one task shape, offer more varied fixtures first.
6. **Close.** Stop the server. Report plans reviewed, notes taken, and themes per
   plan. The `data/` changes (plan snapshots, notes, log) are the durable record;
   they belong in git.

## Later rounds

Open coding is not one-off. In every iteration of the loop, the new plans are
open-coded again before they are labelled. That is how you find failure modes a
change *introduced*, which labels against the old taxonomy would never show.
