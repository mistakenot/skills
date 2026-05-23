---
name: task-feedback-analyser
description: "Use when the user wants to extract recurring patterns from completed task feedback into workflow rules. Scans feedback.md files and review threads, clusters by theme, and drafts rules with a strict 3-example minimum."
---

# Task Feedback Analyser

Extract recurring patterns from completed task feedback into generalizable workflow rules.

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

### Step 1: Scan feedback sources

- Read all `docs/tasks/*/feedback.md` files
- Read review comment threads from completed PRs (merged)
- Track which files have been processed to avoid re-scanning (check against existing rules file for "Evidence" task references)

### Step 2: Cluster by theme

Group observations by theme. Examples of themes:

- Missing tenant isolation
- Stale context references
- Tests that don't verify actual behavior
- Incomplete error handling in server functions

### Step 3: Filter to 3+ independent examples

A theme qualifies as a rule only when it appears in **3 or more independent examples** (different task folders). This minimum is strict -- never fabricate or stretch examples to meet the threshold.

Drop themes that don't meet the bar. Report dropped themes so the user knows they exist but aren't mature enough.

### Step 4: Draft rules

Write each rule in imperative form with a `use_when` trigger and verbatim evidence:

# Rule Template

```markdown
## RULE-$NNN: $imperative_statement

$explanation

**Use when:** $trigger_condition

**Evidence:**
- Task $A: $verbatim_excerpt
- Task $B: $verbatim_excerpt
- Task $C: $verbatim_excerpt
```

- `$NNN` is a sequential ID continuing from the highest existing rule
- The imperative statement is a clear, actionable directive (e.g. "Always add tenant_id filter to repository queries")
- `$verbatim_excerpt` is a direct quote from the feedback or review thread -- never paraphrase

### Step 5: Update rules file

- Read existing `docs/rules.md` (or create if it doesn't exist)
- Merge new rules with existing ones -- do not duplicate
- Assign sequential IDs continuing from the last rule
- Commit: `docs: add rules RULE-$NNN through RULE-$MMM from feedback analysis`

## Rules

- 3-example minimum is strict. Never fabricate examples.
- Use verbatim excerpts, not paraphrases.
- Track processed files to avoid re-scanning on subsequent runs.
- Report themes that fell below the 3-example threshold so the user can watch for them.
