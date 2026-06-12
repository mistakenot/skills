# Task 001: assurance-skill-walking-skeleton

## Problem

The `assurance-strategist` skill bundle has a completed design (see the [research diary](../../assurance-strategist-research-diary.md)) but no implementation. Before authoring the full ~30-card technique library, we need to prove the infrastructure end-to-end with the smallest possible slice: one skill, one technique card, a working build, and one eval that compares agent output with and without the skill.

This task is itself the walking skeleton of the skill bundle — same doctrine the skill prescribes.

## Goals

- Create the `src/assurance/` module with the `assurance-strategist` skill template and exactly one technique card, compiled by the existing `src/compile.py` pipeline.
- Extend the compiler with the `{{ index:techniques }}` directive: the SKILL.md technique index is generated from card frontmatter at compile time.
- Extend compile-time validation: cards with missing/invalid frontmatter keys or missing required body sections fail the build with a clear error.
- Stand up the eval harness skeleton (`src/assurance/evals/`) with one case: "build a calculator CLI that can add numbers", run headless with and without the skill installed, producing a comparison report.
- Wire build + eval into the Makefile.

## Acceptance Criteria

**AC-1**: Module compiles
- Given: `src/assurance/` exists with the skill template and one technique card in `refs/`
- When: `python3 src/compile.py` runs
- Then: `skills/assurance-strategist/SKILL.md` is produced with a generated technique index, and the card is copied to `references/`, linked (not inlined)

**AC-2**: Index is generated, not authored
- Given: a compiled skill
- When: the card's frontmatter (e.g. its one-line summary) is edited and the compiler re-run
- Then: the SKILL.md index reflects the change with no manual SKILL.md edit

**AC-3**: Malformed cards fail the build
- Given: a card missing a required frontmatter key or required body section
- When: the compiler runs
- Then: compilation fails in the validation phase with an error naming the card and the missing element

**AC-4**: Eval runs with the skill
- Given: the compiled skill installed into a headless agent environment
- When: `evals/run.sh` executes the calculator-cli case with the skill
- Then: the agent's output project is captured, and mechanical checks (T1: expected harness files exist; T2: the project's test command runs and exits correctly) produce a scorecard

**AC-5**: Baseline comparison
- Given: the same case prompt
- When: run without the skill installed
- Then: the same checks run against the baseline output and a comparison report (with-skill vs without-skill) is produced

**AC-5b**: Grader-lite + human feedback loop
- Given: both arms' outputs and mechanical scorecards
- When: grading runs
- Then: a small grader-agent pass scores both arms against a short rubric, the comparison report presents mechanical + grader results side by side in a human-readable format, and the report has a designated place for a human verdict/notes that is preserved with the run results

**AC-6**: Make targets
- Given: the repo Makefile
- When: `make compile` / `make eval-assurance` (name TBD) run
- Then: build and eval are reproducible single commands

## Out of Scope

- The full technique card catalog (~30 cards) — only one card in this task.
- Full SKILL.md content (axes intake, composition frames, maturity presets) — depth decided in Open Questions; at minimum enough for the agent to use the one card sensibly.
- Full T3 grader tier (multi-dimension rubric, per-case expectations.yaml) — only the single grader-lite pass of AC-5b is in scope. T4 (downstream implementer simulation) entirely out.
- CI integration for evals; N=3 variance runs (single run per arm is fine for the skeleton).
- Publishing/installing the skill for real use; the planning-doc rich-doc output.
- Pre-existing uncommitted changes in the repo (pd-components etc.) — unrelated to this task.

## Open Questions

- [x] Q1: Which technique should the single walking-skeleton card cover? (answered: unit testing — simplest to validate mechanically; the task proves infrastructure, not the card)
- [x] Q2: How deep should SKILL.md go in this task? (answered: minimal stub — identity, self-verification invariant, generated index, "read the card before prescribing"; axes/frames land in a follow-up task)
- [x] Q3: Eval comparison method for v1? (answered: mechanical checks + grader-lite + human feedback — T1/T2 diff, one small grader-agent rubric pass over both arms, and the comparison report includes a recorded human verdict; see AC-5b)
- [x] Q4: Which headless runner for evals? (answered: `claude -p` only; structure run.sh so a codex runner can be added later without rework)
