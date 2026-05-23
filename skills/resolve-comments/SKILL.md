---
name: resolve-comments
description: "Resolve inline review comments in task planning docs. Use when the user asks to 'resolve comments', 'address comments', 'fix review comments', 'go through comments', or after a review has left comments on task docs. Don't use when the user wants to address PR code review feedback (use address-feedback instead)."
---

# Resolve Comments

Process inline comment threads in markdown planning docs -- resolve, reject, or continue each thread.

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

### Step 1: Find Files

Identify which files to process, in priority order:
1. Files explicitly mentioned by the user
2. If user gave a task ID: all docs in `docs/tasks/$ID-*/`
3. Files already read/edited in the current session
4. If unclear, ask the user

### Step 2: Parse Threads

For each file, find all review comment threads (HTML comments with status labels). Read the surrounding content to understand what each thread is about.

### Step 3: Resolve Each Thread

For each comment thread, decide one of:

**Resolve** -- the concern is valid and you can fix it:
- Make the requested content change in the doc
- Update the comment status to `RESOLVED`
- Add an `AUTHOR:` reply explaining what was changed

**Reject** -- the concern doesn't apply or the current content is correct:
- Keep content unchanged
- Update the comment status to `REJECTED`
- Add an `AUTHOR:` reply with rationale (cite evidence when possible)

**Continue unresolved** -- you need more information or can't resolve alone:
- Keep content unchanged (or make a partial fix)
- Keep the comment as `UNRESOLVED`
- Add an `AUTHOR:` reply with your question or blocker

### Step 4: Preserve Thread History

- Comments are append-only -- never delete prior entries in a thread
- Keep one thread per issue
- Maintain the original priority level unless the thread clearly reclassifies it

### Step 5: Summary

After processing all threads, report:
- How many resolved, rejected, continued unresolved
- Which files were changed
- Any threads that need user input to proceed

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
