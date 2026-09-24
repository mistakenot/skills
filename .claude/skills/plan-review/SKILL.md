---
name: plan-review
description: "Improves new-task-quick through a human-review loop: generate plans, blind open coding, failure-mode labels, change, regenerate, compare. Use when 'plan review', 'open coding', 'improve plan quality'. Not for one task's docs (use review-task)."
---

# Plan Review — the plan-quality improvement loop

This skill improves `/new-task-quick` using a person's judgement of the
plans it actually produces. A reviewer reads generated plans and notes what is
wrong. Those notes become named failure modes. Each skill change is tested by
regenerating plans with the old and new skills and counting the modes in each.

```
        ┌────────────────────────────────────────────────────────────────────┐
        ▼                                                                    │
  1 GENERATE ──► 2 OPEN CODING ──► 3 AXIAL CODING ──► 4 CHANGE ──► 5 REGENERATE ──► 6 COMPARE
  plans from      reviewer's free-    failure modes +     one skill     baseline +        report;
  fixtures at     text notes and      per-plan labels     edit, one     candidate, same   keep / revert
  skills@REF      verdicts (blind)    (taxonomy.json)     hypothesis    fixtures, blind   (iterations.md)
```

Steps 1–3 run once to build the baseline taxonomy. Each iteration then runs
4 → 5 → 2 → 3 → 6 on the new batch: the new plans are open-coded and labelled
before anything is compared.

The tooling is in `src/plan-review/` (its README documents the data model). Run
everything as `make plan-review ARGS='...'` from the repo root.

## Invariants

- **The reviewer judges; you draft and operate.** You never decide on your own
  that a plan is good or bad. You propose taxonomies and labels, and the reviewer
  confirms or overrides them.
- **Blind until labelled.** The review app hides the skills version, trial, model and
  cost. Don't reveal them during review. `report` unblinds, so run it only after the
  batch is fully labelled. When comparing versions, generate both arms in the same
  batch so the unreviewed set is mixed (see the iterate reference).
- **Don't prime.** During open coding, never suggest categories or point at
  instances. Your framing would replace theirs.
- **One change per iteration, and every arm is a commit.** `--skills-ref` sees only
  committed, compiled `skills/`. Two changes in one iteration can't be told apart.
- **Append-only evidence.** Never hand-edit `data/notes.jsonl` or `data/labels.jsonl`.
  The app and `label` write them. `data/` (plan snapshots, notes, logs, taxonomy,
  labels, iterations) belongs in git.
- **Spend is confirmed.** Every `generate` bills tokens (about $1–2.50 per plan so
  far, capped at $15 per plan). State the count and cost, and wait for a yes.
  `--dry-run` is free.
- **Interactive only.** A headless run (`claude -p`, `codex exec`) has no reviewer:
  run `status` and `report`, say where the loop stands, and stop. Never claim a
  review happened.

## Where are we? (run `status`, then pick the stage)

| State | Stage | Read |
|---|---|---|
| Corpus empty or too narrow; or starting an iteration's regeneration | Generate | [references/plan-review-generate.md](references/plan-review-generate.md) |
| Plans without a verdict | Open coding | [references/plan-review-open-coding.md](references/plan-review-open-coding.md) |
| Verdicts but no `data/taxonomy.json`, or reviewed plans missing labels | Axial coding | [references/plan-review-axial-coding.md](references/plan-review-axial-coding.md) |
| Everything labelled; no open entry in `data/iterations.md` | Iterate: pick a target, change the skill | [references/plan-review-iterate.md](references/plan-review-iterate.md) §1–4 |
| Open iteration entry; its batch is generated | Open coding, then axial coding, on the new plans | the two references above |
| Open iteration entry; its batch is fully labelled | Iterate: compare and decide | [references/plan-review-iterate.md](references/plan-review-iterate.md) §6–7 |

Read the reference for the stage you're entering. Each is self-contained. Tell the
user which stage you're in and what the next stage will be.

## Commands

| Command | Stage | Does |
|---|---|---|
| `generate [fx.json ...] [--skills-ref REF ...] [--batch ID] [--trials N] [--model M] [--dry-run]` | 1, 5 | Replays fixtures in Harbor at each skills@REF (repeat the flag for both arms) and ingests the plans under one batch id |
| `ingest <run-dir> ... \| --all [--batch ID]` | 1, 5 | Adds plans from existing Harbor runs |
| `serve [--port 8765]` | 2 | The blind review app: span notes, verdicts, progress |
| `status` | any | Plans, verdicts, note counts |
| `label <plan> <mode> present\|absent [--evidence IDs] [--reason ...]` | 3 | One failure-mode judgement against the current taxonomy |
| `report [--by version\|fixture] [--batch ID]` | 3, 6 | Verdicts and mode rates per skills version (unblinds); `--batch` restricts to one comparison |

## State files (`src/plan-review/data/`)

| File | Written by | Holds |
|---|---|---|
| `plans/<id>/` | the app, on first open | A snapshot of the plan. Plans can't be regenerated identically, so this is kept |
| `notes.jsonl` | the app | Span notes and verdicts (event log) |
| `open-coding-log.jsonl` | you, per verdict | New vs repeat themes per plan, used to judge saturation |
| `taxonomy.json` | you + reviewer | Failure modes, versioned |
| `labels.jsonl` | `label` | Present/absent per plan × mode × taxonomy version |
| `iterations.md` | you + reviewer | One entry per iteration: hypothesis, arms, result, decision |

## When to stop

Stop iterating when the remaining modes are rare or cheap, or when two iterations
in a row fail to move their target. At that point, write narrow automated judges for
the stable modes and validate them against `labels.jsonl`, so later iterations need
less hand labelling. New fixtures from new repos restart discovery: open-code them
before trusting the taxonomy on them.
