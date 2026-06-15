# Task 002: beta-planning-workflow

## Problem

The current task planning workflow produces four separate markdown files per task (requirements.md, solution.md, context.md, plan.md). This creates fragmentation — the planning artifacts are scattered across files, review threads use a bespoke markdown comment syntax, and there's no structured metadata for tracking execution state. Meanwhile the `planning-doc` skill already produces rich, interactive single-file HTML documents with native review threads, but isn't integrated into the planning workflow.

We need a new "beta" variant of the planning workflow that consolidates planning artifacts into a single HTML planning doc (using pd-* components) plus a separate agent-consumed context.md, introduces Verification as a first-class planning stage, adds structured execution-state metadata, and uses template-derived skill name references so the eventual promotion from beta to primary requires only DSL renames.

## Goals

- Create a `src/beta-planning/` compiler module with three skills: `beta-new-task`, `beta-new-solution`, `beta-new-plan`.
- Each skill appends to a single `plan.html` file in the task folder (using pd-* web components), with tabs authored in stage order: Requirements → Verification → Solution → Plan.
- A companion `context.md` file (agent-consumed, not rendered in HTML) is created at the start of `/beta-new-solution` before any design work.
- Promote Verification to a first-class tab/stage: generated after context gathering but before solution design, with its own review gate. The verification agent may use any available project skills to inform its testing/conformance strategy.
- Add a structured JSON metadata block (`<script type="application/json" id="pd-meta">`) to the HTML doc for tracking execution state. Schema: `{ "id", "name", "status", "branch", "epic", "created", "pr" }`. Status values: `planning`, `executing`, `merged`. Fields not yet known are null.
- Replace the markdown comment review protocol (`<!-- RESOLVED(...) -->`) with the pd-thread mechanism (`<pd-thread>`, `<pd-comment>`) for all review conversations. Reviewer agents write `<pd-thread>` elements directly into the HTML file.
- Extend `src/compile.py` with a `{{ skill:<name> }}` directive that resolves to the compiled skill name from the same module (or cross-module via `{{ skill:module/name }}`). All inter-skill references in templates and reference docs use this directive instead of hard-coded names.
- Maintain the staged workflow with hard-stop review gates: after Requirements (end of `/beta-new-task`), after Verification (mid `/beta-new-solution`), after Solution (end of `/beta-new-solution`), and after Plan (end of `/beta-new-plan`).
- Soft-launch as a parallel alternative to the existing workflow; designed for eventual promotion to primary (rename skills in DSL, references auto-update).

## Acceptance Criteria

**AC-1**: Module compiles
- Given: `src/beta-planning/` exists with three skill templates and reference files
- When: `python3 src/compile.py` runs
- Then: `skills/beta-new-task/`, `skills/beta-new-solution/`, `skills/beta-new-plan/` are produced with all references copied

**AC-2**: Skill-name directive resolves
- Given: a SKILL.md template containing `{{ skill:beta-new-solution }}`
- When: the compiler runs
- Then: the rendered output contains the literal string `beta-new-solution` (resolved from the module's skill declarations)
- And: if the skill is renamed in the DSL to `new-solution`, recompilation produces `new-solution` in all references without manual edits

**AC-3**: Cross-module skill references resolve
- Given: a template containing `{{ skill:rich-docs/planning-doc }}`
- When: the compiler runs
- Then: the rendered output contains `planning-doc`
- And: referencing a non-existent module or skill fails validation with a clear error

**AC-4**: `/beta-new-task` creates HTML with Requirements tab
- Given: a user invokes `/beta-new-task` with a feature description
- When: the skill completes
- Then: `docs/tasks/$ID-$NAME/plan.html` exists with a `<pd-tab name="Requirements">` containing the requirements content, a `<script type="application/json" id="pd-meta">` block with status "planning" and all schema fields present (nulls for branch/pr), and no other tabs yet

**AC-5**: `/beta-new-solution` produces context, Verification, and Solution
- Given: a task folder with `plan.html` containing only a Requirements tab
- When: `/beta-new-solution` is invoked
- Then:
  - `context.md` is created with codebase facts (same format as current context.md)
  - A `<pd-tab name="Verification">` is added to plan.html with testing/conformance strategy
  - The skill hard-stops for review of the Verification tab
  - After user approval, a `<pd-tab name="Solution">` is added with the approach, file changes, and rejected alternatives
  - The skill hard-stops for review of the Solution tab

**AC-6**: `/beta-new-plan` adds the Plan tab
- Given: a task folder with plan.html containing Requirements, Verification, and Solution tabs
- When: `/beta-new-plan` is invoked
- Then: a `<pd-tab name="Plan">` is added with phased execution steps (using `<pd-stepper>`, `<pd-phase>`, etc.) and the skill hard-stops for review

**AC-7**: pd-thread review structure is supported
- Given: a plan.html with content in any tab
- When: a reviewer manually inserts `<pd-thread>` and `<pd-comment>` elements
- Then: the doc renders threads correctly, resolution/rejection is tracked via `status` attributes, and `<pd-decisions>` surfaces resolved threads
- Note: automated reviewer skill integration (teaching `/review-task` to emit pd-threads) is a follow-up task

**AC-8**: Meta JSON schema is correct and extractable
- Given: a plan.html with `pd-meta` JSON block created by `/beta-new-task`
- When: the block is read by an agent or script
- Then: it contains all documented fields (`id`, `name`, `status`, `branch`, `epic`, `created`, `pr`), status is `"planning"`, and unknown fields are null
- Note: automated status updates by `/execute-task` and `/complete-task` are a follow-up task

**AC-9**: HTML is agent-readable
- Given: a completed plan.html with all four tabs
- When: an agent reads the raw HTML file
- Then: it can identify and extract content from each tab (the HTML is semantic enough for agent consumption without special parsing)
- Note: teaching `/execute-task` to consume plan.html instead of plan.md is a follow-up task

## Out of Scope

- Migrating existing tasks from the old workflow to the new format.
- Changes to `/execute-task`, `/complete-task`, or other downstream skills (they continue to work with the old format; beta integration is a follow-up).
- The pd-components library itself (assumed stable; use existing components as-is).
- A dedicated `/beta-review-task` skill — reuse the existing review pattern with pd-threads written directly.
- Full replacement of the old workflow — this is a soft launch. Promotion is a separate future task (rename in DSL + remove old module).

<!-- RESOLVED(P1): AC-7/AC-8/AC-9 depend on downstream skills that Out of Scope explicitly defers
REVIEW: Out of Scope says "Changes to /execute-task, /complete-task, or other downstream skills ... beta integration is a follow-up" — they "continue to work with the old format". But three ACs require exactly those skills to understand the new HTML format:
- AC-7 (review via pd-threads): `/review-task`, `/request-claude-review` are downstream skills. Verified src/planning-workflow/skills/review-task/SKILL.md:21 reads `requirements.md, solution.md, context.md, plan.md` and writes `<!-- -->` markdown comments — it has no knowledge of plan.html or pd-threads.
- AC-8 (meta updated to "executing"/"merged"): requires `/execute-task` and `/complete-task` to write the pd-meta block. Verified src/planning-workflow/refs/execute-task-full.md:10 reads the 4 markdown files and parses plan.md — it never touches plan.html.
- AC-9 (executor consumes the HTML): same — execute-task parses plan.md (execute-task-full.md:16), not plan.html.
As written, AC-7/8/9 cannot pass without modifying skills the task declares out of scope. Either move these ACs to the follow-up task, or pull the minimal downstream changes into scope. The plan.md has no steps addressing AC-7/8/9, which confirms the gap.
AUTHOR: Rewrote AC-7/8/9 to scope them to what this task actually delivers: the HTML structure supports pd-threads (AC-7), the meta schema is correct and extractable (AC-8), and the HTML is agent-readable (AC-9). Each AC now includes a "Note" deferring the automated downstream integration to a follow-up. The ACs are now testable within this task's scope.
-->

<!-- RESOLVED(P2): AC-8 manual test ("simulate execute-task") cannot validate the AC as stated
REVIEW: AC-8's "Then the meta block is updated to status: executing" describes behavior of execute-task, but execute-task is unchanged (Out of Scope). The test coverage entry ("simulate execute-task, verify meta status updates") would only verify that a human hand-edits the JSON — not that the workflow does it. Reword AC-8 to test the schema/lifecycle contract (the block exists with the documented fields and legal status values), and defer the actual write behavior to the follow-up.
AUTHOR: Rewrote AC-8 to test the schema contract (all fields present, correct initial status, nulls for unknowns) rather than downstream write behavior. Deferred automated status updates to follow-up. Solution.md test coverage table updated accordingly.
-->


## Open Questions

- [x] Q1: Should the `{{ skill: }}` directive also work inside reference files (e.g. `beta-workflow-overview.md`), or only in SKILL.md templates? (Answered: yes, works in refs too — the workflow overview doc references skill names in its pipeline diagram.)
- [x] Q2: For the Verification tab, what pd-components should be used? (Answered: `<pd-section>` + `<md>` for test strategy prose, `<pd-ac>` cards for acceptance criteria with forward-traceability via `phases`/`tests` attributes filled in during later stages, `<pd-mermaid>` for coverage maps when useful, `<pd-code>` for example test signatures. A "Known Gaps & Risks" section captures what isn't covered. No new components needed.)
- [x] Q3: Should the meta JSON block be a `<script type="application/json">` in `<head>` or in `<body>`? (Answered: `<head>` — it's metadata not content, extractable with a simple regex/DOM query.)
