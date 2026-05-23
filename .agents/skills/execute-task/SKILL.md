---
name: execute-task
description: "Use when the user invokes /execute-task $ID to autonomously implement a planned task. Reads task docs, creates a worktree, dispatches subagents per phase, tracks progress, and opens a PR."
---

# Execute Task

Autonomous end-to-end implementation using the coordinator-subagent pattern.

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

Task ID (numeric, e.g. `042`).

## Startup

1. Find task folder matching ID under `docs/tasks/` (glob `docs/tasks/$ID-*`)
2. Read ALL files: `requirements.md`, `solution.md`, `context.md`, `plan.md`
3. Verify prerequisites:
   - All 4 docs exist
   - No unanswered Open Questions
   - Every AC is covered by plan steps
4. Create isolated worktree with branch `task/$ID-$NAME`
5. Parse `plan.md` for phases, steps, and the Execution Sequence DAG
6. Find first unchecked phase (supports session resumption)

## Coordinator-Subagent Pattern

Dispatch one subagent per phase. No nesting beyond two levels.

### What each subagent receives

- Absolute worktree path (critical -- subagents do not inherit coordinator cwd)
- Task folder path (absolute)
- Phase number and name to execute
- Instructions:
  - Read `plan.md`, `context.md`, `solution.md` before starting
  - Identify and use relevant skills before coding
  - Only touch files listed in plan.md -- don't "improve" adjacent code or refactor things that aren't broken
  - Match existing code style, even if you'd do it differently
  - State assumptions before coding. If the plan step is ambiguous, surface the ambiguity back to the coordinator rather than guessing
  - Fix routine failures (test bugs, type errors, lint) autonomously
  - Stop on fundamental issues (wrong architecture, missing prerequisites)
  - Commit at end: `feat($ID): phase N - description`

### What each subagent returns

- **Status**: pass or fail
- **Files changed**: list of paths
- **Verification results**: typecheck output, test summaries
- **Issues encountered**: even on pass

### Coordinator after each subagent

1. Read results
2. Update `plan.md` checkboxes: `- [ ]` -> `- [x]`
3. Commit: `docs($ID): mark phase N complete`
4. Decide next action:
   - Clean pass -> dispatch next phase (follow DAG for parallelism)
   - Routine failure subagent couldn't fix -> attempt resolution
   - Fundamental failure -> stop, record what happened, skip to PR
5. Maintain running list of problems encountered

### Parallel vs serial

- Follow the Execution Sequence DAG from `plan.md`
- Independent phases can run in parallel when DAG allows
- Core implementation phases -> serial to reduce conflicts
- When in doubt, go serial

## Session Resumption

If session ends mid-execution, a new session reads `plan.md` -- checked phases are done, resume from first unchecked phase. No additional state tracking needed.

## Open PR

After all phases complete (or after stopping on failure):

# PR Body Template

```bash
git push -u origin HEAD
gh pr create --title "feat($ID): $NAME" --body "$(cat <<'EOF'
## Summary
- [1-3 bullets from plan.md summary]

## Phases completed
- [x] Phase 1: name
- [x] Phase 2: name
- [ ] Phase 3: name (failed / skipped)

## Issues encountered
- [Bullet list or "None"]

## How to test
[Copy from plan.md]

## Links
- Task docs: docs/tasks/$ID-$NAME/
- Plan: docs/tasks/$ID-$NAME/plan.md

Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

## Worktree Conventions

# Worktree Conventions

## Branch Naming

Use `task/$ID-$NAME` format with dashes. Never use `+` in branch names -- it breaks some review tools.

## Worktree Isolation

- Planning happens on `main`. Implementation happens on feature branches in isolated git worktrees.
- Always create an isolated worktree for execution with branch name `task/$ID-$NAME`.
- After squash merge, worktree commits are already in main -- discarding is safe.

## Push Before Spawning Agents

Always `git push` to origin before spawning agents with worktree isolation. Agent worktrees branch from `origin/main`, not local.

## Subagent CWD

Subagents spawned inside worktrees do NOT inherit the coordinator's cwd. Always pass absolute paths to subagents, including:

- Absolute worktree path
- Task folder path
- Which phase to execute

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
