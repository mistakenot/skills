## Workflow Overview

This skill is part of a multi-stage task workflow. Here's the full pipeline:

```
Plan (on main)                Execute (on feature branch)         Review & Complete
─────────────────             ──────────────────────────          ─────────────────
/v1-new-task                     /v1-execute-task $ID                   /v1-address-feedback
  → requirements.md             → worktree + branch              /v1-code-review
/v1-new-solution                    → subagent per phase             /v1-complete-task
  → solution.md                  → PR                              → feedback.md
/v1-new-plan                                                          → merge
  → context.md + plan.md     /v1-delegate-task (optional)
/v1-review-task (optional)       /v1-executor-status-check (optional)
/v1-request-codex-review (optional)
/v1-resolve-comments (optional)
/v1-commit-task
```

**Conventions:**
- Task folder: `docs/tasks/$ID-$NAME/` (3-digit ID, kebab-case name)
- Branch: `task/$ID-$NAME`
- Planning happens on `main`. Execution happens in isolated worktrees.
- Each stage hard-stops for user review before proceeding to the next.
