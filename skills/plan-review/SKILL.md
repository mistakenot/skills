---
name: plan-review
description: "Runs a blind open-coding review of new-task-quick plans generated in Harbor, via a note-taking app. Use when 'plan review', 'open coding', 'review generated plans'. Not for one task's docs (use review-task)."
---

# Plan Review — open coding over generated plans

A person reads plans that `/new-task-quick` produced and writes down, in their own
words, what is wrong (or right) with each. That is **open coding**: the first step of error
analysis, before anyone knows what the failure modes are. Grouping the notes into named
failure modes (**axial coding**) comes after and is not part of this skill yet.

The reviewer notices; you keep the machinery running and stay out of the way. Everything
lives in `src/plan-review/` (see its README for the data model).

## Invariants

- **Do not prime the reviewer.** During open coding never suggest failure categories, never
  summarise their themes back to them, never point at instances in a plan. Early framing from
  you becomes their framing and the notes stop being independent evidence. Answer direct
  questions, then step back.
- **Blind.** Never reveal which skills version, trial, model or cost produced a plan while a
  session is running. The app hides them; `runs/corpus.jsonl` does not — don't read it aloud.
- **Notes are append-only.** `data/notes.jsonl` is written only by the app, one event per line.
  Never edit or rewrite it; `data/plans/` and `data/open-coding-log.jsonl` are committed with it.
- **Interactive only.** In a headless run (`claude -p`, `codex exec`) there is no reviewer:
  run `status`, report, and stop. Never claim a review happened or that a server is still up.

## Commands

All via `make plan-review ARGS='...'` from the repo root:

| Command | Does |
|---|---|
| `status` | Corpus size, verdicts, notes per plan |
| `generate [fixture.json ...] [--skills-ref REF] [--trials N]` | Replays fixtures (default: all in `src/plan-review/fixtures/`) through Harbor with the skills at `REF`, then ingests. **Bills tokens** (~$5–15 per plan) — confirm with the user first; `--dry-run` is free |
| `ingest <harbor-run-dir> ... \| --all` | Adds plans from existing planning-eval-harbor runs |
| `serve [--port 8765]` | The review app |

## Session

1. **Corpus.** Run `status`. If it is empty or everything has a verdict, offer `generate`
   (state the cost, wait for a yes). Writing a new fixture: copy one in `fixtures/`; the prompt
   must end with the stop line (`corpus.STOP_SUFFIX`) so the run halts at the first gate.
2. **Serve.** Start `serve` in the background and give the user `http://localhost:8765/`
   (in a devcontainer the port must be forwarded). One line on use: select text → note
   (Enter saves); `1`/`2`/`d` = pass/fail/defer with a plan-level note; `←`/`→` move between
   plans; Progress shows everything noted so far.
3. **Watch** `src/plan-review/data/notes.jsonl` for new lines by polling every 2 s (not
   filesystem events). In Claude Code use the Monitor tool:
   `f=src/plan-review/data/notes.jsonl; n=$(cat $f 2>/dev/null | wc -l); while true; do m=$(cat $f 2>/dev/null | wc -l); [ "$m" -gt "$n" ] && tail -n $((m-n)) $f | cut -c1-240; n=$m; sleep 2; done`.
   Elsewhere run the same loop in the background, appending to a log you read each turn.
4. **On each verdict event**, read every note on that plan and compare it with the themes
   seen on earlier plans. Append one line to `src/plan-review/data/open-coding-log.jsonl`:
   `{"plan_id": ..., "ts": ..., "new_codes": [...], "repeat_codes": [...]}`, where each code is
   a short descriptive label **in the reviewer's own words** (in-vivo), not a category you
   invented. Tell the user one line — "plan #4: 2 new themes, 1 repeat" — without the labels
   unless they ask. The app charts this log.
5. **Re-review.** Once about five plans have verdicts, suggest one pass back over the first
   two: criteria drift as the reviewer sees more, and early plans are read with a thinner eye.
6. **Saturation.** When three consecutive reviewed plans add at most one new theme between
   them, say open coding is saturating and offer the next step: axial coding on the notes,
   or `generate` with more varied fixtures if coverage (repos, task shapes) is the gap.
7. **Close.** Stop the server. Report plans reviewed, notes taken, and themes per plan.
   `data/` changes (snapshots, notes, log) are the durable record — they belong in git.
