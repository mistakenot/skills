# plan-review

Human open coding over plans that `/new-task-quick` generated. Fixtures are
replayed through [`planning-eval-harbor`](../planning-eval-harbor/README.md)
in Docker with the skills pinned to a commit. The resulting `plan.html` files
go into a corpus, and a reviewer reads them in a blind review app, writing
free-text notes on spans and a pass/fail/defer verdict per plan.
Nothing is scored automatically. The notes *are* the output: the raw material
for axial coding (grouping notes into named failure modes) and, after that,
for validating judges.

The `plan-review` skill (`src/eval-engineer/skills/plan-review/`) runs a
session: it serves the app, watches the notes, and logs theme saturation.

```
fixtures/*.json ─► generate ─► planning-eval-harbor (Docker, skills @ REF, stops at gate 1)
                                   │
                                   ▼  produced/docs/tasks/*/plan.html
                    ingest ─► runs/corpus.jsonl            (local, gitignored)
                                   │
                                   ▼  first time a plan is opened
                    serve ─► data/plans/<id>/               (committed)
                              data/notes.jsonl              (committed, append-only)
                              data/open-coding-log.jsonl    (committed, written by the agent)
```

## Quickstart

```bash
make plan-review ARGS='generate --dry-run'          # compile + validate every fixture; free
make plan-review ARGS='generate'                    # all fixtures, skills @ HEAD; bills tokens
make plan-review ARGS='generate f.json --skills-ref main~10 --trials 2'
make plan-review ARGS='ingest --all'                # pick up any existing Harbor runs
make plan-review ARGS='serve'                       # http://127.0.0.1:8765/
make plan-review ARGS='status'
```

Prerequisites are planning-eval-harbor's own: Docker, `~/.claude/.credentials.json`,
and `uv sync --project src/planning-eval-harbor`. A fixture with a local
`target_repo` needs that checkout on disk. A `repo_url` fixture is fetched on
first use into `~/.cache/planning-eval-harbor/repos/`.

## Fixtures

These are planning-eval-harbor fixtures, with three conventions:

- **One turn, stopping at the first gate.** `limits.max_turns = 1`, and the
  prompt ends with `corpus.STOP_SUFFIX` ("Stop after Stage 4 (self-check); do
  not run the Codex review."). Without that line, `new-task-quick` goes
  straight into a Codex review whenever it raised no open questions. The
  review app strips the line before showing the request. Ingest records
  whether Codex ran anyway (`checks.codex_ran`).
- **Arm = `{"skills_ref": "HEAD"}`**, usually overridden by
  `generate --skills-ref`. The arm is the compiled `skills/` tree at that
  commit, exported with `git archive` (`planning-eval-harbor/sources.py`). So
  older skill versions can be replayed without a checkout. It is always a
  *commit*: uncommitted skill edits aren't part of `HEAD`. Run
  `make compile` and commit first.
- **Three sources.** Record which one in `_provenance`:
  - **historic:** the operator's real opening message, at the parent of the
    commit that first added the task's docs.
  - **authored:** written in the operator's voice (use `auto search` to see
    how they phrase requests), and grounded in something real at the start
    commit.
  - **oss:** a real closed issue, verbatim, at the parent of the commit that
    fixed it. `repo_url` in place of `target_repo`. The fix commit is a
    reference answer for later.

| Fixture | Source | Repo | Size |
|---|---|---|---|
| `auto-stack-043-etl-registry-discovery` | historic | auto-stack (Go) | medium: config-driven repo discovery |
| `auto-stack-skill-filter-commas` | authored | auto-stack (Go) | small: CLI flag ergonomics |
| `pi-8133-per-model-compaction` | oss | earendil-works/pi (TypeScript) | medium: settings schema + lookup |

## The corpus

`ingest` reads a Harbor run (`peval.json` + each trial's
`peval-result.json` and `produced/`). It writes one line to
`runs/corpus.jsonl` per `docs/tasks/*/plan.html`, keyed by
`plan_id` = the first 12 hex characters of the sha256 of the plan's bytes.
Each entry records the fixture, request, start sha, arm, skills sha, model,
trial, cost and wall time, plus cheap checks: the question count, open
questions, `codex_ran`, and pd-lint codes (`open-question` doesn't block;
it's the gate).

Opening a plan in the app **snapshots** it. The plan, its `context.md` and
its corpus entry are copied to `data/plans/<plan_id>/`. Plans aren't
reproducible: the same fixture and skills produce a different plan every
run. A note is only meaningful while the exact document it annotates exists,
and snapshots keep it after the Harbor run is cleaned. Transcripts aren't
copied (they run to megabytes). The "transcript" link works only while the
run exists.

## The review app

- **Blind.** The list and the request panel show the fixture and request,
  never the arm, skills sha, trial, model or cost. Plans are shown in
  `plan_id` order: a content hash, so fixtures and versions are interleaved,
  and the order is stable between sessions.
- **The real document.** The plan renders exactly as produced, pd-components
  included, in a same-origin iframe sized to its content.
  Highlights use the CSS Custom Highlight API, so the plan's DOM is never
  modified. pd-doc's own comment controls are hidden, because feedback here
  goes to the review log, not to the doc.
- **Two kinds of note.**
  - **Span notes:** select text, write a note, press Enter. The note sits in
    the right margin next to its text. Notes on another tab are listed at
    the top of the margin with a button to switch tab.
  - **Plan verdict:** Pass / Fail / Defer (`1` / `2` / `d`) plus a free-text
    note on the whole plan.

  There are no categories, tags or dropdowns. Open coding is free text by
  design.
- **Anchoring by text, not offsets.** A span is stored as
  `{tab, quote, prefix, suffix}` and found again on every load by searching
  that tab's text. When the quote occurs more than once, the prefix and
  suffix pick the right occurrence. A note that can't be re-anchored is
  listed, never dropped.
- **Nothing lost.** Each change is POSTed as one event. If the server is
  down, the event waits in `localStorage` and is retried.
- **Progress view.** Verdict counts, the agent's new-themes-per-plan chart
  (from `data/open-coding-log.jsonl`), every plan with its plan-level note,
  and every span note, each linking back to where it was made.

It needs a browser with the CSS Custom Highlight API (Chrome/Edge 105+,
Safari 17.2+, Firefox 140+).

## Data

`data/notes.jsonl` is an append-only event log. The server stamps each event
with `ts` and `reviewer` (default: `git config user.name`):

| event | fields |
|---|---|
| `note.create` | `id, plan_id, tab, quote, prefix, suffix, text` |
| `note.update` | `id, text` |
| `note.delete` | `id` |
| `verdict` | `plan_id, verdict (pass\|fail\|defer), text`; latest wins |

`notes.fold()` turns the log into current state. The log is kept whole
because the history is evidence: the order in which the reviewer's reading
developed, and what they changed their mind about.

`data/open-coding-log.jsonl` is written by the agent running the session, one
line per reviewed plan:
`{plan_id, ts, new_codes: [...], repeat_codes: [...]}`. The labels use the
reviewer's words. When recent plans stop adding codes, open coding has
saturated.

## Not built yet

- **Axial coding:** group the notes into a versioned failure-mode taxonomy
  (`taxonomy.yaml`), then label each plan against it (`labels.jsonl`).
- **Suggest-then-confirm:** subagents that search the whole corpus for
  instances of one confirmed failure mode, for the reviewer to accept or
  dismiss.
- **Judges** for the top failure modes, validated against these labels.
- **Side-by-side review:** two plans for the same fixture from different
  skill versions, labels hidden.

## Tests

```bash
uv run pytest src/plan-review/tests/ -q      # offline: fake Harbor run, real HTTP on an ephemeral port
```
