---
name: new-solution
description: "Write a solution design for an existing task. Use when the user asks to 'write a solution', 'design the solution', 'new solution', 'explore approaches', or after requirements have been approved. Don't use when requirements.md doesn't exist yet."
---

# New Solution

Read approved requirements, explore approaches, write `solution.md`.

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

## Guiding Principles

- If multiple approaches exist, surface them all with tradeoffs -- don't silently pick one.
- Bias toward the simplest approach. If a simpler option exists, say so even if it's less elegant.
- No speculative abstractions or "flexibility" that wasn't requested. The solution should be the minimum design that satisfies the acceptance criteria.
- If something in the requirements is ambiguous, stop and ask before designing around an assumption.

## Process

1. **Find task folder** -- identify the active task from recent context, user input, or by scanning `docs/tasks/` for the latest folder. Read `requirements.md`. Verify all Open Questions are resolved -- if not, resolve them first.
2. **Scan skills** -- check available skills for topic matches relevant to this task's domain. Load matched skills.
3. **Assess complexity**:
   - **Straightforward** (one obvious approach): go directly to step 5.
   - **Ambiguous** (multiple viable approaches): go to step 4.
4. **Explore options** -- spawn parallel subagents, one per candidate approach. Each subagent investigates feasibility by reading relevant code, checking patterns, and identifying risks. Collect results. Present a comparison table to the user with pros/cons for each option. Wait for the user to pick an approach.
5. **Write solution.md** -- use the template and rules below. Fill in Approach, Files, Test Coverage, Out of Scope, and Rejected Alternatives.
6. **Create artifacts** -- if the solution involves user-facing flows or complex architecture, create artifact files (wireframes, diagrams) in the task folder. Follow the artifact guidelines below.
7. **Hard-stop** -- present the completed solution.md to the user. Do NOT proceed to the plan stage. Tell them: "Review solution.md. When ready, run `/new-plan` to continue."

## Solution Template and Rules

# Solution Template

```markdown
# Solution: Task $ID

## Approach
1. High-level step
2. High-level step
3. ...

## Files
```
+ path/to/new/file.ts          # brief description
~ path/to/modified/file.ts     # what changes
```

## Test Coverage

| AC  | Test Type   | File                        |
|-----|-------------|-----------------------------|
| AC-1 | e2e        | e2e/tests/feature.spec.ts   |
| AC-2 | integration | src/__specs__/svc.spec.ts   |
| AC-3 | unit       | src/feature.test.ts          |

## Out of Scope
- (copy from requirements + add technical boundaries)

## Rejected Alternatives
- **Option B**: one-line reason it was rejected
- **Option C**: one-line reason it was rejected
```

## Rules

- Files section uses `+` for new files, `~` for modified, `-` for deletion
- Test Coverage table maps every AC to a test type and file
- Include bare-bones code outlines (types, signatures) in Files section for complex changes

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
