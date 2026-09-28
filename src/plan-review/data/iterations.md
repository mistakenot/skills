# plan-review iterations

## Round 0 — sonnet-4-6 discovery corpus (closed, 2026-09-28)

- **Corpus:** 7 plans, 1 trial each, skills @ `9b21084`, **model sonnet-4-6** (harness default —
  a mistake: the operator plans with Opus 5.5). Batches: first batch (etl, commas, pi) and
  `corpus-2` (graph, jlogs, citty, sqlite).
- **Open coding:** 7/7 fail, 45 span notes. New themes per plan 8 → 3 → 1 → 1 → 0 → 0 → 0 (saturated).
- **Taxonomy v1:** prose-wall, file-map-not-first, implementer-level-detail, low-signal-content,
  open-questions-untagged, gwt-inline (`taxonomy.json`).
- **Status:** labels proposed, not yet recorded. Findings are Sonnet's; do not mix these plans into
  Opus comparisons. Re-check the taxonomy against Opus output before trusting it there.

## Backlog (parked, not lost)

- **Mechanical modes** (file-map-not-first, open-questions-untagged, gwt-inline, full code bodies):
  fix directly in one commit and verify with scripted checks rather than blind review.
  Evidence: every Solution tab leads with 83–196 words before `<pd-files>`; 6/7 plans never use
  `<pd-question>`; G/W/T lines without list markers render as one paragraph (4/7).
- **Substance blind spot:** no note in round 0 judged correctness. Add a review prompt
  ("would this produce the right fix?") and compare OSS-fixture plans with their reference fixes
  (sqlite-utils `221774f2`, citty `f40f1a25`).
- **rich-doc feature requests from review:** hover an interface reference → file tree highlights
  the file (note 3e15ca); a Before/After pair of numbered lists in ASD-STE100 Simplified Technical
  English (note 5dbfb5).
- **Review-app defects:** span quotes capture heading chrome (`#+ comment`) when a selection starts
  at a heading; two verdicts can be saved a minute apart for one plan (jlogs).
- **Skill doc defect:** `$1` in plan-review SKILL.md is substituted by Claude Code's argument
  expansion ("about $1–2.50" renders wrong).

## Iteration 1 — verbosity (open)

- **Target:** the verbosity cluster (prose-wall, low-signal-content, implementer-level-detail).
- **Hypothesis:** _TBD after the Opus baseline is reviewed._
- **Arms:** baseline `HEAD` vs candidate commit, both `--model anthropic/claude-opus-5-5`, same fixtures, ≥2 trials each, one batch.
