---
name: new-task
description: "Create a new task with requirements. Use when the user asks to 'create a task', 'new task', 'start a task', 'write requirements', or describes a feature/fix they want planned. Don't use when the user wants to execute an existing task or review existing docs."
---

# New Task

Create `docs/tasks/$ID-$NAME/requirements.md` from user input.

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
6. **Write requirements.md** -- use the template and rules below. Fill in Problem, Goals, and Acceptance Criteria from user input. Add Out of Scope based on reasonable boundaries. List any unresolved questions in Open Questions.
7. **Resolve Open Questions** -- for each open question, ask the user interactively (use `AskUserQuestion` tool if available). Update the doc with answers as they come in. Repeat until all questions are resolved or the user defers them.
8. **Hard-stop** -- present the completed requirements.md to the user. Do NOT proceed to solution stage. Tell them: "Review requirements.md. When ready, run `/new-solution` to continue."

## Requirements Template and Rules

# Requirements Template

```markdown
# Task $ID: $NAME

## Problem
1-2 sentences describing what's wrong or what's needed.

## Goals
- Bullet list of what this task achieves

## Acceptance Criteria

**AC-1**: $title
- Given: $precondition
- When: $action
- Then: $expected_result

**AC-2**: ...

## Out of Scope
- Product-level boundaries (what this task explicitly does NOT do)

## Open Questions
- [ ] $question (answered: $answer)
```

## Rules

- ~1 page max; split larger work into multiple tasks
- ACs use Given/When/Then or casual bullets (match team preference)
- Open Questions must be resolved before moving to solution stage
