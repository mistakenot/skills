---
name: new-plan
description: "Write context and execution plan for an existing task. Use when the user asks to 'write a plan', 'new plan', 'create the plan', 'plan the task', or after solution.md has been approved. Don't use when solution.md doesn't exist yet."
---

# New Plan

Read requirements + solution, gather codebase context, write `context.md` and `plan.md`.

## Workflow Overview

This skill is part of a multi-stage task workflow. Here's the full pipeline:

```
Plan (on main)                Execute (on feature branch)         Review & Complete
─────────────────             ──────────────────────────          ─────────────────
/new-task                     /execute-task $ID                   /address-feedback
  → requirements.md             → worktree + branch              /code-review
/new-solution                    → subagent per phase             /complete-task
  → solution.md                  → PR                              → feedback.md
/new-plan                                                          → merge
  → context.md + plan.md     /delegate-task (optional)
/review-task (optional)       /executor-status-check (optional)
/resolve-comments (optional)
/commit-task
```

**Conventions:**
- Task folder: `docs/tasks/$ID-$NAME/` (3-digit ID, kebab-case name)
- Branch: `task/$ID-$NAME`
- Planning happens on `main`. Execution happens in isolated worktrees.
- Each stage hard-stops for user review before proceeding to the next.

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

# Context Template

```markdown
# Context: Task $ID

One sentence describing what this file contains + link to solution.md.

## Key Files
- `path/to/file.ts:42` -- description of relevant code
- `path/to/other.ts:15-30` -- code snippet with explanation

## Patterns
- How similar features are implemented in this codebase
- Relevant conventions and constraints

## Related Tasks
- Task $OTHER_ID: what it did that's relevant here
```

## Rules

- Only facts from codebase: paths, snippets, descriptions
- Full paths relative to repo root
- Every code snippet needs a file path + line reference
- Never paste full files -- excerpts only

## Plan Template and Rules

# Plan Template

```markdown
# Plan: Task $ID

## Summary
One sentence describing the implementation approach.

## Changes
| Symbol | File | Description |
|--------|------|-------------|
| + | path/to/new.ts | New service for X |
| ~ | path/to/existing.ts | Add Y method |

## Links
- [Requirements](./requirements.md)
- [Solution](./solution.md)
- [Context](./context.md)

## How to Test
- [ ] `path/to/feature.test.ts` -- unit tests for service
- [ ] `e2e/tests/feature.spec.ts` -- e2e happy path

## Execution Sequence
```
Phase 1 (DB) --> Phase 2 (Backend) --> Phase 4 (E2E)
                                   \-> Phase 3 (Frontend) -/
```

## Plan

### Phase 1: Database Schema
- [ ] Step 1.1: Create migration for new table
- [ ] Step 1.2: Run migration, verify schema
- [ ] Step 1.3: Commit: `feat($ID): phase 1 - database schema`

### Phase 2: Backend Service
- [ ] Step 2.1: Create repository
- [ ] Step 2.2: Create service with business logic
- [ ] Step 2.3: Create server function
- [ ] Step 2.4: Run typecheck
- [ ] Step 2.5: Write and run unit tests
- [ ] Step 2.6: Commit: `feat($ID): phase 2 - backend service`

### Phase 3: Frontend
- [ ] Step 3.1: Create route
- [ ] Step 3.2: Create components
- [ ] Step 3.3: Wire to server function
- [ ] Step 3.4: Run typecheck
- [ ] Step 3.5: Commit: `feat($ID): phase 3 - frontend`

### Phase 4: E2E Tests
- [ ] Step 4.1: Write e2e test covering AC-1 through AC-3
- [ ] Step 4.2: Run e2e tests
- [ ] Step 4.3: Commit: `feat($ID): phase 4 - e2e tests`

## Success Criteria
- [ ] `typecheck` passes
- [ ] All unit tests pass
- [ ] All e2e tests pass
- [ ] Manual verification: $description

## Open Questions
- (empty if all resolved)
```

## Rules

- Each phase is atomic -- one subagent handles it end-to-end
- Every phase ends with a commit step
- Every phase includes verification (typecheck, tests, lint)
- Execution Sequence shows the dependency DAG for parallel dispatch
- Checkboxes track progress and enable session resumption

## Artifact Guidelines

# Artifact Guidelines

Artifacts are self-contained `.html` files stored in the task folder (or an `artifacts/` subfolder) and linked from plan.md. They are created during planning.

## When to Create Artifacts

- **Requirements stage**: user flow diagrams (if the feature involves user-facing flows)
- **Solution stage**: technical diagrams (architecture, sequence), wireframes

## Wireframes

Structural layouts, not polished UI. Show where elements go -- buttons, sections, headings -- without real content. Each element should just have a label describing what it is.

- Self-contained HTML page using the project's CSS framework CDN (e.g. Bootstrap, Tailwind)
- Structural only: grey boxes, placeholder labels, layout grid. No real content or styling beyond framework defaults.
- Match the project's UI framework so wireframes roughly reflect actual component structure
- One wireframe per `.html` file, linked from plan.md

## Diagrams (Mermaid)

Self-contained HTML files that render Mermaid diagrams via beautiful-mermaid. Use for flow diagrams, sequence diagrams, ERDs, etc.

- Use `renderMermaidSVG` from `esm.sh/beautiful-mermaid@1.1.3`
- OK to add short explanation text below the diagram (bullets work well)
- Split any diagram with more than 8 nodes into multiple diagrams
- One diagram per `.html` file, linked from plan.md

**Boilerplate:**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>[Diagram Name]</title>
  </head>
  <body>
    <div id="diagram"></div>
    <ul>
      <li>Brief note about the diagram</li>
    </ul>
    <script type="module">
      import { renderMermaidSVG } from 'https://esm.sh/beautiful-mermaid@1.1.3';

      const svg = await renderMermaidSVG(`graph TD
    A[Start] --> B[Step]
    B --> C[End]`);

      document.getElementById('diagram').innerHTML = svg;
    </script>
  </body>
</html>
```

## Linking Artifacts

Reference artifacts from plan.md Links section and from solution.md where relevant:

```markdown
## Links
- [Requirements](./requirements.md)
- [Solution](./solution.md)
- [Context](./context.md)
- [auth-flow.html](./auth-flow.html)
- [settings-wireframe.html](./settings-wireframe.html)
```
