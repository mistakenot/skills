---
name: review-task
description: "Review task planning docs and leave inline comments. Use when the user asks to 'review task docs', 'review the plan', 'review task 042', 'check the planning docs', or provides a task ID/folder for doc review. This reviews planning documents (requirements.md, solution.md, context.md, plan.md), not code. Don't use when the user wants a code review of implementation changes."
---

# Review Task Docs

Review all planning documents for a task and leave structured inline comments flagging problems, questions, and improvements. This is a planning review -- you use the full codebase as ground truth to verify claims in the docs.

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

## Input

The user provides a task ID (e.g. `042`) or a task folder name (e.g. `042-add-team-settings`). If ambiguous, check `docs/tasks/` for a matching folder.

## Process

### Step 1: Load Context

1. Find the task folder under `docs/tasks/` matching the provided ID
2. Read ALL docs: `requirements.md`, `solution.md`, `context.md`, `plan.md`
3. Read any project docs referenced by the task docs (linked concept docs, how-to guides)

### Step 2: Codebase Verification

For each doc, verify claims against the actual codebase:

**requirements.md**
- Are acceptance criteria testable and unambiguous?
- Do referenced features/pages actually exist?
- Are there implicit dependencies not mentioned?
- Does "Out of Scope" make sense, or will the task be incomplete without those items?

**solution.md**
- Do listed file paths exist (for `~` modified files) or make sense as new files (`+`)?
- Do referenced types, functions, and services have the described signatures?
- Does the approach match established project patterns?
- Are there security concerns -- auth, tenant isolation, input validation?
- Does the test coverage table cover all acceptance criteria?

**context.md**
- Are code snippets accurate to the current state of the files?
- Are line number references correct?
- Are important related files or patterns missing?

**plan.md**
- Will the execution sequence work? Are phase dependencies correct?
- Are commands correct (test paths, npm scripts, workspace flags)?
- Do success criteria verify all acceptance criteria?
- Are there missing steps the implementer will need to figure out?

### Step 3: Cross-Document Consistency

- Every AC in requirements.md maps to test coverage in solution.md and plan steps in plan.md
- File paths are consistent across solution.md, context.md, and plan.md
- Types/interfaces in context.md match what solution.md proposes to use
- The approach in solution.md matches the plan steps in plan.md

### Step 4: Leave Comments

Insert comments directly into the task docs using the Edit tool. Place each comment directly below the content it addresses, with a blank line above and below.

**You are a reviewer. Your only edit action is inserting comment blocks.** Do NOT change the author's content -- describe issues in comments, and the author resolves them.

Use tools (grep, glob, read, bash) to gather evidence before commenting. Comments backed by "I checked the file and the signature is actually X" are far more valuable than "this might be wrong."

Only comment on actual problems, genuine ambiguities, or missing information. Do not comment on formatting, correct content, or style preferences.

### Step 5: Summary

After leaving all comments, provide:
- Total comment count by priority (P1/P2/P3)
- The most critical issues to resolve before implementation
- Overall assessment: ready to execute, or needs another revision?

## Comment Format

# Review Comment Format

## Comment Syntax

Comments use markdown HTML comments with status, priority, and role tags.

### Raising an issue (UNRESOLVED)

```markdown
<!-- UNRESOLVED(P1): Title of issue
REVIEW: Description of the concern with evidence.
-->
```

### Resolving an issue (RESOLVED)

```markdown
<!-- RESOLVED(P1): Title of issue
REVIEW: Original concern.
AUTHOR: What was changed to address it.
-->
```

### Rejecting an issue (REJECTED)

```markdown
<!-- REJECTED(P1): Title of issue
REVIEW: Original concern.
AUTHOR: Why this doesn't apply, with reference.
-->
```

## Priority Levels

- **P1**: Blocking -- must be fixed before proceeding
- **P2**: Important -- should be fixed, but not a hard blocker
- **P3**: Minor suggestion -- nice to have

## Roles

- **REVIEW**: The reviewer's comment (the concern or question)
- **AUTHOR**: The author's response (fix description or rejection rationale)

## Rules

- Comments are **append-only** (track full decision history, never delete or overwrite previous entries)
- **One thread per issue** -- don't combine multiple concerns into a single comment
- Place comments directly below the offending content with blank lines above and below
- Only comment on real issues (structure, security, assumptions), not formatting
