---
name: new-mini-task
description: "Creates a mini-task with acceptance criteria and a single plan.md, compressing the full planning pipeline into one step. Use when 'new mini task', 'quick task', 'mini task', or for smaller tasks that don't need the full requirements/solution/plan ceremony. Not applicable for complex tasks needing detailed design docs."
---

# New Mini Task

Create `docs/tasks/$ID-$NAME/plan.md` — a compressed single-file alternative to the full planning pipeline.

> Part of the task planning workflow. See [references/workflow-overview.md](references/workflow-overview.md) for the full pipeline.

## When to Use

- Smaller tasks where the acceptance criteria are straightforward
- Tasks where the user doesn't need to review a separate solution design
- Work that can be delegated to an executor without extensive upfront planning

If the task is complex enough to benefit from separate requirements, solution, and context docs, use `/new-task` instead.

## Process

1. **Determine task ID** — scan `docs/tasks/` for existing folders. Assign the next 3-digit sequential ID (e.g. if `042-*` exists, next is `043`). If `docs/tasks/` doesn't exist, start at `001`.
2. **Derive task name** — create a short kebab-case name from the user's description.
3. **Create task folder** — `mkdir -p docs/tasks/$ID-$NAME`
4. **Draft acceptance criteria** — write clear, testable AC from the user's input. Each AC should be verifiable without human judgement.
5. **Write initial plan.md** — use the template below. Fill in the AC. Leave Context and Solution sections as placeholders.
6. **Hard-stop for confirmation** — present the acceptance criteria to the user using `AskUserQuestion`. Do NOT proceed until the user confirms the AC look right. If they want changes, update and re-present.
7. **Dump existing context** — write everything you currently know that's relevant into the Context section. This is NOT a new exploration pass — just dump what's already in your context (conversation history, files you've read, patterns you've noticed). The executor will do its own thorough exploration later.
8. **Add executor instructions** — add the checkbox list from the template.
9. **Commit** — commit plan.md on main.
10. **Push** — push to origin so the executor can access the docs from a fresh worktree.
11. **Report** — tell the user: "Run `/execute-task $ID` or `/delegate-task $ID` to start execution."

## Mini Plan Template

{{ ref:template-mini-plan.md }}
