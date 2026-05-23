---
name: new-plan
description: "Write context and execution plan for an existing task. Use when the user asks to 'write a plan', 'new plan', 'create the plan', 'plan the task', or after solution.md has been approved. Don't use when solution.md doesn't exist yet."
---

# New Plan

Read requirements + solution, gather codebase context, write `context.md` and `plan.md`.

{{ ref:workflow-overview.md }}

## Process

### Phase 1: Context Gathering

Spawn 3 parallel subagents to gather context. Each returns structured findings.

**CB1 (Code):**
- Search files, functions, types, and patterns relevant to the task
- Check file paths mentioned in solution.md -- verify they exist, note current signatures and structure
- Find similar implementations in the codebase for pattern reference

**CB2 (Docs):**
- Search project documentation for relevant how-tos, concept docs, and architecture guides
- Check for related rules or conventions that apply
- Note any documented constraints or patterns the implementation must follow

**CB3 (History):**
- Search git commits for related changes
- Check `docs/tasks/` for related completed tasks
- Note relevant decisions or patterns from past work

### Phase 2: Write context.md

Combine findings from all 3 subagents into `context.md` using the template below. Include only verified facts -- paths, snippets, descriptions grounded in actual code.

### Phase 3: Write plan.md

Using requirements.md, solution.md, and the freshly written context.md:

1. Break the solution into atomic phases (each phase = one subagent during execution)
2. Define the execution DAG -- which phases depend on which
3. List concrete steps within each phase, with checkboxes
4. Every step must have an explicit verify check (not just "run typecheck" but "verify: typecheck passes, new route returns 200")
5. End each phase with a commit step and verification (typecheck, tests, lint)
6. Define success criteria that map back to acceptance criteria
7. Create artifact files if needed (architecture diagrams, sequence diagrams for complex flows)

Strong success criteria let subagents loop independently. Weak criteria ("make it work") cause confusion and wasted cycles. Each step should be verifiable without human judgement.

### Phase 4: Hard-stop

Present both context.md and plan.md to the user. Do NOT proceed to execution or commit. Tell them: "Review context.md and plan.md. When ready, run `/review-task` for a review or `/commit-task` to finalize."

## Context Template and Rules

{{ ref:template-context.md }}

## Plan Template and Rules

{{ ref:template-plan.md }}

## Artifact Guidelines

{{ ref:artifact-guidelines.md }}
