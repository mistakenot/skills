# Mini Plan Template

```markdown
---
workflow: mini
status: draft   # lifecycle: draft → pending → executing → complete
---

> **Mini-task** — compressed workflow. Single plan file, no separate requirements/solution/context docs.

# Mini-task: $ID — $NAME

## Acceptance Criteria
- [ ] AC-1: ...
- [ ] AC-2: ...

## Context
<!-- Populated by the creating agent with what it already knows, then enriched by the executor -->

## Executor Instructions
- [ ] Enter a new worktree (`task/$ID-$NAME`)
- [ ] Read AC and Context above
- [ ] Run context-gathering pass (MUST use subagent team to preserve coordinator context)
- [ ] Write Solution section below stating approach and files to touch
- [ ] Commit this file: `docs($ID): context and solution`
- [ ] Implement the solution
- [ ] Spin up sub-agent team for code review with fresh context
- [ ] Fix review findings, push, open PR
- [ ] Wait for CI, run `/address-feedback`

## Solution
<!-- Written by executor after context gathering -->
```

## Rules

- `workflow: mini` frontmatter is required — this is how `execute-task` detects mini-tasks
- Acceptance criteria use checkboxes so the executor can track completion
- The Context section is seeded by `/new-mini-task` with whatever the creating agent already knows, then enriched by the executor during context gathering
- The Solution section is left blank — the executor fills it in after its own context gathering pass
- Executor Instructions are checkboxes that track execution progress for session resumption
