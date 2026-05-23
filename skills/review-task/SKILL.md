---
name: review-task
description: "Review task planning docs and leave inline comments. Use when the user asks to 'review task docs', 'review the plan', 'review task 359', 'check the planning docs', 'review this task', or provides a task ID/folder for doc review. This is a PLANNING doc review skill -- it reviews requirements.md, solution.md, context.md, and plan.md, NOT code. Use proactively when the user mentions reviewing or checking a task's planning documents before implementation begins."
---

# Review Task Docs

Review the planning documents for a task and leave structured inline comments that flag problems, ask questions, and suggest improvements. This is a planning review, not a code review -- but you use the full codebase as ground truth to verify claims made in the docs.

## Input

The user provides a task ID (e.g. `359`) or a task folder name (e.g. `359-manager-dashboard-real-teams`). If ambiguous, check `docs/tasks/` for a matching folder.

## Comment Format

You MUST read `docs/how-to/communicate-during-plan-reviews.md` before leaving any comments. That file is the authoritative spec for comment syntax, roles, and resolution flow. Do not paraphrase or guess the format -- read it every time.

Priority levels:
- **P1** -- Blocking. Will cause implementation failure, security issue, or incorrect behavior.
- **P2** -- Important. Convention violation, missing edge case, unclear spec that will slow down the implementer.
- **P3** -- Minor. Suggestion, nitpick, or improvement that could be skipped.

## Review Process

### Phase 1: Load Context

1. Find the task folder under `docs/tasks/` matching the provided ID
2. Read ALL docs in the task folder: `requirements.md`, `solution.md`, `context.md`, `plan.md`
3. **Read `docs/how-to/communicate-during-plan-reviews.md` first, before writing any comments.** This is mandatory -- it defines the exact comment syntax you must use. Do not skip this step or rely on memory of the format.
4. Read any project docs referenced by the task docs (linked concept docs, how-to guides, etc.)

### Phase 2: Codebase Verification

This is where the real value is. The planning docs make claims about the codebase -- file paths, function signatures, table schemas, middleware behavior, test patterns. Verify them against reality.

For each doc, check:

**requirements.md**
- Are the acceptance criteria testable and unambiguous?
- Do referenced features/pages actually exist?
- Are there implicit dependencies or prerequisites not mentioned?
- Do the "out of scope" items actually make sense to exclude, or will the task be incomplete without them?

**solution.md**
- Do the listed file paths exist (for modified files) or will they be created (for new files)?
- Do the referenced types, functions, and services actually have the signatures described?
- Does the approach match established project patterns? Check similar domains for precedent.
- Are there security concerns -- auth middleware, tenant isolation, input validation?
- Does the test coverage table actually cover all acceptance criteria?
- Are rejected alternatives genuinely inferior, or was a better option missed?

**context.md**
- Are code snippets accurate to the current state of the files? Read the actual source and compare.
- Are line number references still correct?
- Are there important related files or patterns that were missed?
- Do the described types/interfaces match what's actually in the codebase?

**plan.md**
- Will the execution sequence actually work? Are dependencies between phases correct?
- Are the commands correct? (e.g., test paths, npm scripts, workspace flags)
- Do the success criteria actually verify the acceptance criteria?
- Are there missing steps that the implementer will need to figure out on their own?
- Is the phase ordering efficient, or could things be parallelized better?
- Are there edge cases in the plan steps that aren't addressed (empty states, error handling, cleanup)?

### Phase 3: Cross-Document Consistency

Check that the docs agree with each other:
- Every acceptance criterion in requirements.md should map to test coverage in solution.md and plan steps in plan.md
- File paths should be consistent across solution.md, context.md, and plan.md
- Types and interfaces described in context.md should match what solution.md proposes to use
- The approach in solution.md should match the plan steps in plan.md

### Phase 4: Leave Comments

Use the Edit tool to **insert** comments directly into the task docs. Place each comment:
- Directly below the content it addresses
- With a blank line above and below
- Using the `<!-- UNRESOLVED(Pn): Title -->` format

**You are a reviewer. Your only edit action is inserting comment blocks. You must NOT:**
- Change the author's content (text, code snippets, plan steps, headings)
- Fix issues you find -- describe them in a comment instead
- Remove or modify existing comments, annotations, or prior review artifacts
- Rewrite plan steps to reflect what you think they should say

If you spot something wrong (e.g. the plan says `authenticationMiddleware` but should say `requirePermissions`), leave a comment explaining the issue. Do not change the plan step itself -- that's the author's job when they resolve your comment.

Use your tools -- grep, glob, read, bash -- to gather evidence before commenting. Comments backed by "I checked the file and the function signature is actually X" are far more useful than "this might be wrong."

When something looks correct and well-done, don't comment. Only comment on actual problems, genuine ambiguities, or missing information. The goal is to help the implementer succeed, not to demonstrate thoroughness.

### Phase 5: Summary

After leaving all comments, provide a brief summary:
- Total comment count by priority (P1/P2/P3)
- The most critical issues that should be resolved before implementation begins
- An overall assessment: is this plan ready to execute, or does it need another revision?

## What NOT to Comment On

- Formatting or markdown style (that's what tidy-docs is for)
- Things that are clearly correct and well-specified
- Code style preferences that don't affect correctness
- Suggestions that would expand scope beyond what requirements.md defines
- Issues that will be caught by typecheck, linting, or tests during implementation

## Verification Tools

Use these freely during the review:

```bash
# Check if a file exists
ls web/src/server/some-domain/some-file.ts

# Check a function signature
grep -n "functionName" web/src/server/some-domain/some-file.ts

# Check table schema
grep -n "tableName" web/src/server/db/schema.ts

# Check existing patterns
grep -rn "similar pattern" web/src/server/

# Check npm scripts
cat package.json | jq '.scripts'

# Check test command format
npm run test -w web -- --help 2>&1 | head -5
```
