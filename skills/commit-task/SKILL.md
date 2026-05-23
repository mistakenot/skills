---
name: commit-task
description: "Verify and commit task planning docs to main. Use when the user asks to 'commit the task', 'finalize the task', 'commit task docs', or after all planning docs have been reviewed and approved. Don't use when implementation has already started or when the user wants to commit code changes."
---

# Commit Task

Verify completeness of all planning docs and commit them to `main`. This is the final planning stage -- it does NOT create a feature branch or start implementation.

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

### Step 1: Identify Task

Find the active task from user input or recent context. Locate the task folder under `docs/tasks/$ID-$NAME/`.

### Step 2: Verification Checklist

All checks must pass before committing:

- [ ] **All 4 files exist**: `requirements.md`, `solution.md`, `context.md`, `plan.md`
- [ ] **No unanswered Open Questions**: check Open Questions sections in requirements.md and plan.md -- all must be resolved or empty
- [ ] **All ACs addressed**: every acceptance criterion in requirements.md has corresponding test coverage in solution.md and plan steps in plan.md
- [ ] **Plan consistent with solution**: the approach in solution.md matches the phases and steps in plan.md
- [ ] **Context covers plan references**: files and patterns referenced in plan.md are documented in context.md
- [ ] **No unresolved P1 comments**: if review comments exist, no `UNRESOLVED(P1)` threads remain

If any check fails, report the failures and stop. Do not commit incomplete docs.

### Step 3: Commit

```bash
git add docs/tasks/$ID-$NAME/*
git commit -m "docs(tasks): add task $ID-$NAME planning docs"
```

### Step 4: Next Steps

After successful commit, tell the user:

"Task $ID planning docs committed to main. To begin implementation, run `/execute-task $ID`."

Do NOT create a feature branch. Do NOT start implementation.

## Commit Conventions

# Commit Conventions

Commits capture intent and decisions, not just what changed.

## Subject Line

Standard Conventional Commits format: `type(scope): description`

## Body -- Action Lines

Optional, for significant commits:

```
intent(scope): what user wanted and why
decision(scope): approach chosen when alternatives existed
rejected(scope): what was considered and discarded + reason
constraint(scope): hard limits/dependencies discovered
learned(scope): API quirks, undocumented behaviors
```

## Phase Commits (during execution)

```
feat($ID): phase N - $description

intent(task): $what_this_phase_accomplishes
```

## Plan Tracking Commits

```
docs($ID): mark phase N complete
```
