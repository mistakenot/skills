---
hash: "a6758d42"
id: "2b3e572a"
read_when: "comparing our planning workflow to Compound Engineering, evaluating which CE features to adopt, or understanding architectural tradeoffs between single-artifact and multi-document planning approaches"
summary: "Feature-by-feature comparison of the ce-plan (Compound Engineering) skill ecosystem with our task planning workflow: document structure, execution model, knowledge loop, and feature presence table."
title: "Compound Engineering vs Our Planning Workflow"
---

# Compound Engineering vs Our Planning Workflow — Comparison

Research doc comparing the `ce-plan` skill (from the Compound Engineering plugin) with our task planning workflow. Based on thorough exploration of both systems as of 2026-06-16.

## Overview

Both systems are AI-agent-driven planning-to-execution workflows. They solve the same fundamental problem — structuring multi-step engineering work so an agent can plan it, a human can review it, and agents can execute it — but they make strikingly different architectural choices.

| Dimension | Compound Engineering (CE) | Our Workflow |
|-----------|---------------------------|--------------|
| **Unit of work** | Plan document (single artifact) | Task folder (4 separate documents) |
| **Planning depth** | Classified: Lightweight / Standard / Deep | Uniform (full workflow or mini-task) |
| **Progress tracking** | Derived from git (plan never mutated) | Checkboxes in plan.md (plan mutated during execution) |
| **Approval model** | Synthesis gates + post-generation menu | Hard-stop between every skill invocation |
| **Execution model** | ce-work reads plan, chooses strategy (inline/serial/parallel) | Coordinator dispatches one subagent per phase, follows DAG |
| **Knowledge loop** | docs/solutions/ with ce-compound (structured metadata, search) | feedback.md + task-feedback-analyser (rule extraction) |
| **Scope** | Full product lifecycle (strategy → ideation → requirements → plan → execute → review → learn) | Engineering delivery (requirements → plan → execute → review → merge) |
| **Cross-platform** | Authored once, converted for Codex/Gemini/Pi/OpenCode | Claude Code native (with Codex install target) |

## Document Structure Comparison

### CE: Two-artifact chain

```
docs/brainstorms/
  YYYY-MM-DD-<topic>-requirements.{md|html}    ← ce-brainstorm output

docs/plans/
  YYYY-MM-DD-NNN-<type>-<name>-plan.{md|html}  ← ce-plan output

docs/solutions/
  <category>/<slug>.md                          ← ce-compound output (learnings)
```

The plan is a single self-contained document carrying: Summary, Problem Frame, Requirements (with R-ID citations back to brainstorm), Key Technical Decisions, Implementation Units (U-IDs), and optional sections (High-Level Technical Design, Output Structure, Open Questions, System-Wide Impact, Scope Boundaries, Risks, Alternatives Considered, Sources & Research).

### Our workflow: Four-document task folder

```
docs/tasks/
  $ID-$NAME/
    requirements.md    ← /new-task output
    solution.md        ← /new-solution output
    context.md         ← /new-solution + /new-plan output (enriched across phases)
    plan.md            ← /new-plan output
    feedback.md        ← /complete-task output
```

Each document has a distinct purpose: requirements captures the problem and ACs, solution explores approaches and rejected alternatives, context gathers codebase intelligence (key files with line numbers, patterns, related tasks), and plan breaks execution into phases with an explicit DAG.

**Tradeoff:** CE's single-artifact approach is more portable (works as an issue body, review artifact, or team document without context-switching between files). Our four-document approach provides better separation of concerns and allows each document to be reviewed/approved independently, but creates cross-document consistency overhead (file paths, ACs, and approach must stay aligned across all four).

## What CE Has That We Don't

### 1. Product strategy layer

CE anchors all work in `STRATEGY.md` (created by `/ce-strategy`): target problem, approach, persona, key metrics, active tracks. Both `ce-brainstorm` and `ce-plan` read it when present. Our workflow has no equivalent — work starts at the requirements level with no explicit product-intent grounding.

### 2. Plan depth classification

CE classifies every plan as Lightweight, Standard, or Deep based on scope signals, and right-sizes the artifact accordingly. Lightweight plans get 2-4 units with optional sections omitted. Deep plans get 4-8 units grouped into phases with analysis sections. Our workflow has a binary choice: full workflow (4 documents) or mini-task (single file) — nothing in between.

### 3. Confidence checking and deepening

After writing the plan, CE automatically evaluates whether it needs strengthening (Phase 5.3). This dispatches multi-persona confidence scoring on selected sections, then either applies findings directly (auto mode) or walks the user through each finding (interactive mode). Triggers include thin local grounding (<3 direct pattern examples) and load-bearing external research. Our workflow has no post-generation self-evaluation — quality depends on the upstream review skill being invoked manually.

### 4. Integrated document review with conditional personas

CE's `ce-doc-review` dispatches up to 7 parallel reviewer personas (coherence, feasibility, product-lens, design-lens, security-lens, scope-guardian, adversarial), applies safe fixes silently, and surfaces remaining findings for user judgment. This runs automatically at the end of plan generation. Our `/review-task` is a single-pass review that must be explicitly invoked and doesn't use specialized personas.

### 5. Scoping synthesis gates

CE has two gates (Phase 0.7 for solo plans, Phase 5.1.5 for brainstorm-sourced plans) that surface scope call-outs to the user *before* expensive research or plan-writing begins. This prevents wasted effort when the scope is wrong. Our workflow resolves open questions during `/new-task` and validates assumptions during `/new-solution`, but doesn't have an explicit pre-research scope confirmation.

### 6. External research agents

CE conditionally dispatches specialized researchers: `ce-best-practices-researcher` (implementation guidance), `ce-framework-docs-researcher` (documentation with exact framework versions), `ce-web-researcher` (landscape/option discovery), and `ce-spec-flow-analyzer` (edge cases and flow gaps). Dispatch is gated by a three-stage intent classifier. Our workflow does codebase research via subagents (CB1 for code, CB2 for docs, CB3 for git history) but has no external/web research capability.

### 7. Institutional learnings system

CE captures solved problems in `docs/solutions/` with structured YAML metadata (module, tags, problem_type), then `ce-learnings-researcher` searches and incorporates these into future plans. `ce-compound-refresh` maintains learnings over time. Our feedback loop (`feedback.md` → `/task-feedback-analyser` → `docs/rules.md`) extracts generalizable rules but doesn't structure knowledge for search-based retrieval during planning.

### 8. Plans as immutable decision artifacts

CE plans have no status fields, no checkboxes, no mutation during execution. Runtime progress is tracked in the platform's task list (TaskCreate/TaskUpdate), not the plan document. Session resumption works by inspecting file state against each unit's Verification criteria — if the work is already present, the unit is marked complete and skipped. This keeps the plan clean as a reviewable artifact and avoids the stale-checkbox problem. Our workflow mutates `plan.md` during execution — the executor checks off phases and commits progress. This aids session resumption (scan for first unchecked box) but means the plan document accumulates execution state.

### 9. Dual output formats

CE supports markdown (default) or HTML (single self-contained files) as an exclusive choice per plan. HTML plans are browser-viewable and shareable without tooling. Our workflow is markdown-only for the main flow, with a separate beta HTML implementation (pd-components) that isn't yet fully integrated.

### 10. Key Technical Decisions section

CE plans have an explicit KTD section capturing load-bearing architectural choices with rationale — format: `<decision>: <rationale>`. These are distinct from implementation steps. Our `solution.md` captures Rejected Alternatives, but doesn't have a dedicated section for the positive decisions that were made and why.

### 11. Universal planning (non-software)

CE handles knowledge-work planning (research, events, studies) via `references/universal-planning.md`, with plans marked `execution: knowledge-work`. Our workflow is software-delivery-specific.

### 12. Execution posture signals

CE carries lightweight per-unit signals like "Start with a failing integration test" or "Add characterization coverage before modifying this legacy parser" — test-first and characterization-first cues that flow from brainstorm through plan to executor. Our workflow doesn't carry execution-strategy hints at the unit level.

### 13. Stable cross-document IDs

CE uses R-IDs (requirements), A-IDs (actors), F-IDs (flows), AE-IDs (acceptance examples), and U-IDs (implementation units) that are stable across revisions — never renumbered, gaps preserved. These create unambiguous traceability from brainstorm through plan to execution. Our ACs (AC-1, AC-2) serve a similar purpose but aren't as systematically traced through to plan phases.

### 14. Broader ecosystem

CE has ~38 skills covering the full product lifecycle: `/ce-strategy`, `/ce-ideate`, `/ce-debug`, `/ce-product-pulse`, `/ce-promote`, `/ce-demo-reel`, `/ce-test-browser`, `/ce-test-xcode`, `/ce-slack-research`, `/ce-optimize`, `/ce-simplify-code`, and more. Our workflow is tighter — focused on the plan-execute-review-merge loop — and doesn't extend into product strategy, marketing, or platform-specific testing.

### 15. Cross-platform portability

CE skills are authored once and converted for Codex, Gemini CLI, Pi, and OpenCode via a Bun/TypeScript CLI. Platform-specific tool references use capability classes with per-platform hints. Our skills target Claude Code natively (with a Codex install target via `auto skill sync`), but don't have a conversion layer for other platforms.

## What We Have That CE Doesn't

### 1. Dedicated context document

Our `context.md` is a standalone artifact capturing key files (with paths and line numbers), codebase patterns, and related tasks — enriched across two phases (CB1+CB2 during solution, CB3 during plan). CE embeds context into the plan's body (Patterns to follow, Files per unit) but doesn't maintain a separate, reusable context document. The standalone format means context can be updated independently and is available to the executor without parsing it out of the plan.

### 2. Explicit execution DAG

Our `plan.md` includes an ASCII Execution Sequence DAG showing phase dependencies and parallelism opportunities. The coordinator uses this to determine which phases can run concurrently. CE's Implementation Units have dependency fields (which U-IDs must exist first), but ce-work decides the execution strategy at runtime (inline/serial/parallel) rather than following an author-declared DAG.

### 3. Checkbox-based session resumption

Our executor updates `plan.md` checkboxes (`- [ ]` → `- [x]`) as phases complete, enabling any new session to resume from the first unchecked phase. CE derives progress from git state, which is architecturally cleaner but requires the executor to inspect file existence and test state to determine what's done — there's no single glanceable progress indicator.

### 4. Coordinator-subagent pattern with explicit dispatch

Our `/execute-task` implements a structured coordinator pattern: one subagent per phase, each receiving the absolute worktree path, task folder, phase number, and detailed instructions. The coordinator reads results, updates progress, and decides next actions. CE's `/ce-work` also dispatches subagents but the dispatch pattern is less explicitly documented in the skill itself.

### 5. tmux-based delegation and monitoring

`/delegate-task` dispatches execution to idle Claude Code panes in a tmux session, and `/status-report` monitors all executor panes with a structured status table. This enables the user to keep working while tasks execute in background panes. CE has no equivalent multi-pane orchestration.

### 6. Inline review threading with append-only history

Our `/review-task` leaves structured inline comments directly in planning docs:
```html
<!-- UNRESOLVED(P1): Title
REVIEW: Description with evidence.
-->
```
These form append-only threads with REVIEW → AUTHOR replies and explicit status transitions (UNRESOLVED → RESOLVED/REJECTED). `/resolve-comments` processes them systematically. CE's `ce-doc-review` uses headless multi-persona review but applies fixes and surfaces findings rather than creating persistent inline threads with decision history.

### 7. Hard-stop approval gates between every phase

Each skill in our workflow hard-stops and waits for the user to explicitly invoke the next one. This creates 4-5 mandatory review points (requirements → solution → plan → [review →] commit → execute). CE has fewer gates — synthesis gates at Phase 0.7 and 5.1.5, plus the post-generation menu — but flows more continuously within a single invocation.

**Tradeoff:** Our approach gives the user maximum control and prevents runaway automation, but adds ceremony and context-switching. CE's approach is more fluid within a single planning session, relying on in-flight gates rather than full-stop handoffs.

### 8. Open question resolution protocol

Our `/new-task` requires all Open Questions to be interactively resolved before the skill completes. `/new-solution` has an explicit assumption validation gate. CE handles outstanding questions in Phase 2 but the gating is softer — questions that don't materially affect architecture/scope/sequencing can be deferred.

### 9. Task feedback and rule extraction

Our `/complete-task` writes `feedback.md` (problems faced, reflections, useful context) and `/task-feedback-analyser` extracts generalizable rules requiring 3+ independent examples with verbatim evidence. The rules accumulate in `docs/rules.md`. CE's learning loop (`ce-compound` → `docs/solutions/`) captures individual solved problems but doesn't aggregate patterns across multiple tasks into generalizable rules.

### 10. Git history research during planning

Our `/new-plan` spawns a CB3 subagent that searches git commits for related changes, checks `docs/tasks/` for related completed tasks, and notes relevant decisions. This enriches `context.md` with historical context. CE's `ce-learnings-researcher` searches `docs/solutions/` but doesn't systematically mine git history during planning.

### 11. Epic support

Our workflow supports optional `epic:` YAML frontmatter in `requirements.md` that propagates to all four documents with consistency enforcement. CE has no explicit epic/grouping mechanism for related tasks.

### 12. PR feedback lifecycle

Our `/address-feedback` uses GraphQL to fetch unresolved PR review threads, fixes code, replies via REST API, and resolves threads programmatically. `/complete-task` handles squash merge, worktree teardown, and post-merge verification. CE's `/ce-resolve-pr-feedback` exists but the lifecycle is less integrated — ce-work doesn't push or create PRs by default (the user owns the push decision).

### 13. Mini-task shortcut

`/new-mini-task` creates a single `plan.md` with `workflow: mini` frontmatter — compressed planning for smaller work. The executor detects this and uses a different workflow (context gathering → solution → implement → review → PR). CE's closest equivalent is the Lightweight plan depth, but that's still the same ce-plan skill and artifact shape, just with fewer sections.

### 14. Worktree conventions document

Our workflow has an explicit `worktree-conventions.md` reference covering branch naming (`task/$ID-$NAME`), worktree isolation guarantees, push-before-spawning rules, and subagent CWD handling. CE's `/ce-worktree` handles worktree mechanics but the conventions are embedded in the skill rather than being a standalone reference.

### 15. Structured commit conventions with action lines

Our `commit-conventions.md` defines structured commit bodies with semantic action lines:
```
intent(scope): what user wanted and why
decision(scope): approach when alternatives existed
rejected(scope): considered and discarded + reason
constraint(scope): hard limits/dependencies discovered
learned(scope): API quirks, undocumented behaviors
```
CE uses conventional commits (`feat:`, `fix:`, etc.) with component scopes but doesn't have structured body conventions beyond standard practices.

## Philosophical Differences

### Plan identity

CE treats plans as **decision artifacts** — they capture what was decided and why, but not execution state. The plan is written once (plus optional deepening) and never edited during execution. Runtime progress lives in the platform's task tracker (TaskCreate/TaskUpdate). Session resumption works by inspecting file state against each unit's Verification criteria — not by reading git log as a changelog. Commits are incremental and judgment-based (per logical unit, not per change), guided by the heuristic: "Can I write a commit message that describes a complete, valuable change?"

Our workflow treats plans as **living execution documents** — they evolve during execution as checkboxes are marked, and their state is the canonical progress record. This makes progress visible at a glance but conflates the plan's roles as design record and execution tracker.

### Gate philosophy

CE flows continuously within a planning session, using in-flight synthesis gates to catch scope issues before expensive work. The main user decision point is the post-generation 5-option menu.

Our workflow enforces full stops between every skill, treating each document as a reviewable deliverable that must be approved before the next phase begins. This is more conservative but adds more ceremony.

### Knowledge compounding

CE's learning system is search-oriented: structured metadata (module, tags, problem_type) in `docs/solutions/` enables `ce-learnings-researcher` to find relevant prior art during future planning. Knowledge is organized by category and problem type.

Our learning system is rule-oriented: feedback from multiple completed tasks is synthesized into generalizable rules (`RULE-NNN: imperative statement` with 3+ evidence examples). Knowledge is organized as actionable directives.

### Execution autonomy

CE gives ce-work significant autonomy in choosing execution strategy (inline vs serial vs parallel subagents) and doesn't prescribe the exact dispatch pattern. The plan provides decisions; the executor provides tactics.

Our workflow is more prescriptive: the plan's execution DAG specifies parallelism, the coordinator follows an explicit dispatch protocol, and each subagent receives structured instructions.

## Summary Table: Feature Presence

| Feature | CE | Ours | Notes |
|---------|:--:|:----:|-------|
| Product strategy anchor | Y | - | STRATEGY.md |
| Ideation before requirements | Y | - | ce-ideate |
| Requirements exploration | Y | Y | ce-brainstorm vs /new-task |
| Solution design | embedded | Y | CE puts approach in plan; we have separate solution.md |
| Dedicated context document | - | Y | context.md with line numbers |
| Plan depth classification | Y | - | Lightweight/Standard/Deep |
| Confidence check + deepening | Y | - | Auto + interactive modes |
| Multi-persona doc review | Y | partial | 7 personas vs single-pass |
| Scoping synthesis gates | Y | - | Pre-research scope confirmation |
| External research agents | Y | - | Web, best-practices, framework-docs |
| Institutional learnings | Y | Y | docs/solutions/ vs docs/rules.md (different approach) |
| Plans as immutable artifacts | Y | - | No checkboxes, progress from git |
| Dual output (md/html) | Y | beta | Ours is in beta (pd-components) |
| Key Technical Decisions section | Y | - | Explicit load-bearing choices |
| Non-software planning | Y | - | Knowledge-work, research, events |
| Execution posture signals | Y | - | Test-first, characterization-first per unit |
| Stable cross-document IDs | Y | partial | R/A/F/AE/U-IDs vs AC-N |
| Cross-platform conversion | Y | - | Codex, Gemini, Pi, OpenCode |
| Execution DAG | - | Y | ASCII DAG with parallelism |
| Checkbox session resumption | - | Y | Glanceable progress |
| tmux delegation + monitoring | - | Y | /delegate-task, /status-report |
| Inline review threading | - | Y | Append-only decision history |
| Hard-stop phase gates | - | Y | 4-5 mandatory review points |
| Open question resolution | partial | Y | Required vs soft gating |
| Task feedback + rule extraction | - | Y | 3+ evidence threshold |
| Git history research | - | Y | CB3 subagent mines commits |
| Epic support | - | Y | Frontmatter propagation |
| PR feedback lifecycle | partial | Y | GraphQL thread resolution |
| Mini-task shortcut | - | Y | Single-file compressed planning |
| Structured commit action lines | - | Y | intent/decision/rejected/constraint/learned |
| Broader ecosystem (strategy, marketing, debug) | Y | - | ~38 skills vs ~15 |

## Potential Takeaways

Worth considering (not recommendations — just observations for discussion):

1. **Plan depth classification** could reduce ceremony for small tasks without the full/mini binary. A "Lightweight" mode that still uses our 4-doc structure but skips optional sections and shortens each document could fill the gap between full and mini.

2. **Confidence checking** is a compelling quality mechanism. Automatic post-plan self-evaluation with conditional deepening could catch issues our workflow only catches if the user remembers to run `/review-task`.

3. **Plans as immutable artifacts** is architecturally clean but trades away glanceable progress. A hybrid — checkboxes for progress display but treating the plan's *design content* as immutable — might capture both benefits.

4. **Key Technical Decisions** as a first-class section would strengthen our `solution.md`. We capture Rejected Alternatives but don't have a dedicated place for the positive decisions and their rationale.

5. **Execution posture signals** (test-first, characterization-first) are lightweight additions that could meaningfully improve our executor's autonomy without adding ceremony.

6. **Our tmux delegation and monitoring** is a genuine differentiator for power users running multiple tasks concurrently. CE has no equivalent.

7. **Our inline review threading** with append-only decision history provides better audit trails than CE's apply-and-surface approach. Worth preserving.

8. **Our rule extraction** from feedback (3+ evidence threshold) is a more rigorous learning mechanism than individual solution capture — it only promotes patterns that recur independently. CE's search-based retrieval is complementary, not competing.
