---
name: beta-new-task
description: "Creates a plan.html with Requirements tab for a new task. Use when 'beta new task', 'beta task', 'create beta task', 'beta requirements'. Not for markdown task docs (use new-task instead)."
---

# Beta New Task

Create `docs/tasks/$ID-$NAME/plan.html` with a Requirements tab.

> Part of the beta planning workflow. See [references/beta-workflow-overview.md](references/beta-workflow-overview.md) for the full pipeline.

## Guiding Principles

Before writing anything, apply these checks:
- State your assumptions explicitly. If uncertain about what the user wants, ask -- don't guess.
- If the request has multiple interpretations, present them and let the user pick.
- If the scope seems too large for a single task, say so and suggest splitting.
- Push back if something is unclear. Name what's confusing and ask.

## Process

1. **Scan skills** -- check available skills for topic matches relevant to the user's request. Load any matched skills before proceeding.
2. **Read project docs** -- find and read project documentation relevant to the domain (READMEs, how-to guides, concept docs, CLAUDE.md).
3. **Determine task ID** -- scan `docs/tasks/` for existing folders. Assign the next 3-digit sequential ID (e.g. if `042-*` exists, next is `043`). If `docs/tasks/` doesn't exist, start at `001`.
4. **Derive task name** -- create a short kebab-case name from the user's description (e.g. `add-team-settings`).
5. **Create task folder** -- `mkdir -p docs/tasks/$ID-$NAME`
6. **Create plan.html** -- use the boilerplate below to create `plan.html` in the task folder. Replace `$ID`, `$NAME`, and `$DATE` placeholders with actual values.

   See [references/html-boilerplate.md](references/html-boilerplate.md) for the starting HTML structure.

7. **Populate Requirements tab** -- add a `<pd-tab name="Requirements">` inside `<pd-doc>` with the sections defined in the content guidelines. Fill in Problem and Goals from user input. Add Out of Scope based on reasonable boundaries. List any unresolved questions in Open Questions.

   See [references/tab-requirements.md](references/tab-requirements.md) for the tab structure and rules.

8. **Resolve Open Questions** -- assume there are latent requirements the user hasn't communicated. Proactively surface unstated assumptions, clarify ambiguity, and resolve Open Questions by asking the user interactively (use `AskUserQuestion` tool if available). Update the doc with answers as they come in. Repeat until all questions are resolved or the user defers them.
9. **Hard-stop** -- present the completed plan.html to the user. Do NOT proceed to the solution stage. Tell them: "Review plan.html. When ready, run `/{{ skill:beta-new-solution }}` to continue."
