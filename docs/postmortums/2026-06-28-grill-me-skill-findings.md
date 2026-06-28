---
hash: "a545724e"
id: "null"
read_when: "improving the grill-me skill, or debugging why grill-me-generated ADRs/logs fail autodoc stale checks"
summary: "Findings postmortum from first live use of grill-me: a reproducible autodoc-frontmatter defect in generated ADR/log files, plus five method/tooling gaps (unused preview field, unimplementable skip-options advice, unnamed question-premise check, no decision-propagation step, leading-the-witness recommended nudge), with ranked remediation."
title: "grill-me skill: usability gaps and an autodoc integration defect surfaced by live use"
---

# grill-me skill: usability gaps and an autodoc integration defect surfaced by live use

## Executive Summary

A full grilling session was run with the `grill-me` skill to resolve three open questions on
task 006 (the assurance strategy-quality eval). The grilling **succeeded** — it produced a clean
decision, an ADR, and a reshaped design. This report is not about an outage; it captures the
**friction and gaps observed while using the skill**, recorded as a postmortum at the user's
request so the maintainer has a traceable artifact.

One item is a concrete, reproducible **defect**: the ADR and grilling-log files the skill
generates carry no autodoc front matter, so in this autodoc-enabled repo they immediately fail
`auto doc stale` and block the clean-tree check until a human backfills `title`/`summary`/
`read_when`. The remaining five items are **usability/method gaps**, the highest-value being that
the skill never teaches the AskUserQuestion `preview` field, which is the most effective
trade-off-surfacing tool available to a griller.

Most likely root cause of the defect: the skill's ADR/log templates were authored against a bare
markdown convention and never reconciled with this repo's autodoc front-matter requirement.

## Source Issue Trace

- **Trigger:** user invoked `/grill-me` to pressure-test task 006's open questions, then asked
  for maintainer feedback on the skill, then invoked `/postmortum` with "write this up".
- **Skill under review:** `grill-me` — source at `src/` (compiled to
  `.claude/skills/grill-me/`), references `references/grilling-method.md`,
  `references/grilling-log-format.md`, `references/adr-format.md`.
- **Session artifacts produced (evidence of the run):**
  - `docs/grilling/grilling-log.md` (three rounds, append-only)
  - `docs/adr/0001-strategy-eval-blind-differential-not-rubric.md`
  - downstream edits to `docs/tasks/006-assurance-strategy-eval/plan.html` and
    `docs/assurance-strategy-eval-design.md`
- **Repo integration point:** `auto doc` (autodoc) governs `docs/**`; CLAUDE.md documents the
  autodoc index and `auto doc stale` / `auto doc fixed` workflow.

## Impact

- **Developer experience only.** No user-facing, data, security, or availability impact.
- **Defect (autodoc):** every grilling that writes an ADR or a first-time log leaves the repo
  with `auto doc stale` failures. In a repo whose stop-hook / pre-commit enforces a clean doc
  tree, this either blocks the commit or silently ships stale docs. Cost: a manual frontmatter
  backfill per generated file (here: 2 files, ~2 minutes + two `auto doc fixed` invocations).
- **Usability gaps:** the skill works, but (a) leaves its strongest UI affordance unused, (b)
  ships one piece of guidance the mandated tool cannot implement, and (c) stops short of
  propagating decisions back to the artifacts it just invalidated — all of which a less careful
  operator would miss.

## Timeline

All 2026-06-28, single session, times approximate/relative:

1. `/grill-me` invoked on task 006's three open questions.
2. Round 1 (purpose) → Round 2 (independence) → Round 3 (lock instrument); each round logged to
   `docs/grilling/grilling-log.md` before the next was asked.
3. ADR `0001` written to `docs/adr/`.
4. `auto doc stale` reported **2 stale files** (the ADR and the grilling log) — defect observed.
5. Backfilled YAML front matter into both, ran `auto doc fixed` per file → "No stale files found."
6. User requested maintainer feedback (six findings given verbally), then `/postmortum`.

## Technical Context

- **autodoc contract:** every file under `docs/**` is expected to begin with YAML front matter
  carrying `title`, `summary`, `read_when` (autodoc manages `id` + `hash`). `auto doc stale`
  exits non-zero and lists offenders when a doc is missing front matter or has a drifted hash.
- **grill-me output contract:** `references/adr-format.md` specifies a deliberately tiny ADR
  template that begins `# {Short title}` with **no front matter**; `references/grilling-log-format.md`
  specifies a log that begins `# The grilling log` with **no front matter**. The two contracts
  are mutually unaware.
- **Tool affordance:** the grilling loop is driven by `AskUserQuestion`, which requires **2–4
  options per question** and always offers a free-type "Other". It also supports a per-option
  `preview` field (multi-line markdown shown when an option is focused).

## Symptoms and Evidence

**Defect — autodoc stale on generated files.** After writing the ADR:

```
$ auto doc stale
2 stale file(s). Run `auto doc fix` to see instructions.

$ auto doc stale --json
[
  { "path": "docs/adr/0001-strategy-eval-blind-differential-not-rubric.md",
    "issues": ["missing_frontmatter","stale_hash","default_title","empty_read_when"] },
  { "path": "docs/grilling/grilling-log.md",
    "issues": ["missing_frontmatter","stale_hash","default_title","empty_read_when"] }
]
```

Resolved only by hand-adding front matter and running `auto doc fixed <file>` once per file
(the command rejects multiple paths: `accepts 1 arg(s), received 3`).

**Usability findings (evidence = the skill text vs. what the session needed):**

1. **`preview` never taught.** `grilling-method.md` and `grilling-log-format.md` cover options
   and the "(Recommended)" first option, but never mention AskUserQuestion's `preview`. In this
   session, putting each option's *consequences* in `preview` ("pick this → here's the design
   implication") was the single most effective move for trade-off-forcing. The skill leaves its
   best affordance undiscovered.
2. **"Skip options for open questions" is unimplementable with the mandated tool.** The method
   says: *"Skip options when the question is genuinely open … let the user free-type."* But
   `AskUserQuestion` requires 2–4 options; there is no optionless mode. The advice has no
   mechanism unless the griller drops to plain text for open questions.
3. **Taking the user's framing at face value is an unnamed failure mode.** The highest-leverage
   move here was *refusing* to answer the three questions as asked because they were downstream of
   an unpinned purpose. The method's "use-cases-before-architecture (for a new feature)" guidance
   only partially covers this; the general pattern — *test whether the question is answerable at
   all before grilling it* — is not named.
4. **No "propagate decisions to the grilled artifact" step.** The skill ends at log + ADR +
   verbal summary. The grilling invalidated task 006's `plan.html` and the design doc, but nothing
   in the workflow prompts updating them — the user had to ask explicitly.
5. **"(Recommended)" can lead the witness in a *discovery* grilling.** The method ties the
   recommended option to the user's intent — but when the grilling's purpose is to *uncover*
   intent, "Recommended" is a guess that biases an interrogation meant not to lead. No caveat
   exists for the intent-unknown case.

## Reproduction

**Defect (deterministic):**

1. In a repo where `auto doc` governs `docs/**` (e.g. this repo).
2. Run a grilling that produces a decision: `/grill-me <subject>`; answer enough to clear the
   ADR bar.
3. Let the skill write `docs/adr/NNNN-slug.md` and (first time) `docs/grilling/grilling-log.md`
   per its templates (no front matter).
4. Run `auto doc stale`.
5. **Expected by skill:** clean tree. **Actual:** non-zero exit, both files flagged
   `missing_frontmatter` / `stale_hash`.
6. Cleanup: add `title`/`summary`/`read_when` front matter to each; `auto doc fixed <file>` per
   file.

**Usability findings:** not "reproduced" mechanically — they are observations from one full
session; evidence is the skill text quoted above against the session transcript.

## Root Cause Analysis

- **Defect (confirmed):** the ADR/log templates in `references/adr-format.md` and
  `references/grilling-log-format.md` predate or ignore the autodoc front-matter convention, and
  the skill emits files directly into `docs/**` where autodoc enforces that convention. Two
  contracts over the same directory, neither aware of the other. Confidence: high — observed
  directly, and the template files explicitly show front-matter-less examples.
- **Usability gaps (hypotheses, confidence medium):** the method was written before/independently
  of the `preview` affordance and without reconciling its "skip options" advice against
  `AskUserQuestion`'s actual constraints; the workflow scopes itself to "interrogate + record"
  and deliberately stops before editing downstream artifacts.

## What Was Ruled Out

- **Not an autodoc bug.** `auto doc stale` behaved correctly; the generated files genuinely lack
  required front matter. The gap is in the skill's output contract, not the tool.
- **Not a griller (operator) error for the defect.** The skill's own templates prescribe
  front-matter-less files; following them faithfully produces the stale state.
- **Not a one-off.** The defect recurs on every ADR-producing grilling in an autodoc repo; it is
  structural, not incidental to this session.

## Remediation Guidance

Ranked by value:

1. **Teach `preview`** (cheapest, highest value). Add to `grilling-log-format.md` /
   `grilling-method.md`: use AskUserQuestion's per-option `preview` to show each option's
   *consequence* for trade-off-forcing and edge-case questions.
2. **Fix the autodoc defect.** Either (a) add `title`/`summary`/`read_when` front matter to the
   ADR and grilling-log templates in the reference files, or (b) document a post-write step ("if
   the repo uses autodoc, run `auto doc fixed`"), or (c) have the skill detect autodoc and emit
   front matter conditionally. Option (a) is simplest and self-contained. Files to change:
   `src/.../grill-me/references/adr-format.md`, `…/grilling-log-format.md` (then recompile).
3. **Name the "don't grill the question as asked" move** in `grilling-method.md` as a general
   archetype (test the premise of the user's question before grilling it), generalizing the
   existing use-cases-first guidance.
4. **Add a closing "propagate decisions" step** to the skill workflow: after the summary, offer
   to update the artifact(s) the grilling changed.
5. **Reconcile "skip options for open questions"** with AskUserQuestion: either say "ask open
   questions as plain text" or acknowledge "Other" is the only free-type path.
6. **Caveat the "(Recommended)" nudge** for discovery grillings: when intent is not yet pinned,
   base the nudge on situational evidence or suppress it, to avoid leading the witness.

Tests / verification: after editing the templates, re-run a grilling in an autodoc repo and
confirm `auto doc stale` stays clean with no manual backfill.

## Open Questions

- Should ADRs and grilling logs be autodoc-indexed at all, or live in an autodoc-ignored path?
  (If the maintainer prefers them *out* of the index, the fix is an ignore rule, not front
  matter.)
- Is the "skip options for open questions" advice meant for a different ask-tool than
  AskUserQuestion in some host agents? If so, the constraint is host-specific and should be
  labelled as such.

## Appendix

- Decision produced by the session: `docs/adr/0001-strategy-eval-blind-differential-not-rubric.md`.
- Full interrogation trail: `docs/grilling/grilling-log.md` (three rounds).
- Downstream artifacts updated as a result: `docs/tasks/006-assurance-strategy-eval/plan.html`,
  `docs/assurance-strategy-eval-design.md` (§12 revision).
- `auto doc fixed` single-arg constraint observed: `accepts 1 arg(s), received 3`.
