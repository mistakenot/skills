---
name: complete-task
description: "Use when the user wants to finalize a feature branch and merge to main. Addresses remaining feedback, runs tests, writes feedback.md, merges the PR, exits the worktree, and verifies the merge."
---

# Complete Task

Finalize feature branch and merge to main.

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

## Prerequisites

Verify all before starting:

- On a feature branch (not `main`)
- Clean working tree (`git status` shows no uncommitted changes)
- Open PR exists for this branch

If any prerequisite fails, report which one and stop.

## Process

### Step 1: Address remaining PR feedback

Check for unresolved review threads. If any exist, invoke the `address-feedback` skill to resolve them before continuing.

### Step 2: Run affected tests

- Typecheck: always run
- Unit tests: if test files were changed
- E2E tests: if frontend or server functions were changed

All must pass before proceeding.

### Step 3: Push fixes

If steps 1-2 produced new commits, push them.

### Step 4: Write task feedback

Create `feedback.md` in the task folder using the template below.

# Feedback Template

```markdown
# Feedback: Task $ID

## Problems faced
1. $obstacle -- $context_to_understand

## Reflections
- What was tricky?
- What would you tell yourself at the start?
- What did you almost do but didn't?

## Useful context
- $specific_resource_that_was_valuable
- $architecture_decision_that_helped
```

Commit and push feedback before merging:

```bash
git add docs/tasks/$ID-$NAME/feedback.md
git commit -m "add task feedback for $ID"
git push
```

### Step 5: Tear down worktree environment

Shut down any worktree-local services (dev servers, watchers, etc.).

### Step 6: Merge PR

```bash
gh pr merge --squash --delete-branch
```

### Step 7: Exit worktree

Switch back to main working tree.

### Step 8: Pull latest

```bash
git pull
```

### Step 9: Verify merge

Check `git log` for the squashed commit and verify key files are present.

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
