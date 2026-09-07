---
name: new-task
description: "Creates a plan.html with Requirements tab for a new task. Use when 'create a task', 'new task', 'start a task', 'write requirements', or when a user describes a feature/fix to plan. Not applicable when executing an existing task, reviewing existing docs, or planning every stage unattended (use new-task-quick)."
---

# New Task

Create `docs/tasks/$ID-$NAME/plan.html` with a Requirements tab.

> Part of the planning workflow. See [references/workflow-overview.md](references/workflow-overview.md) for the full pipeline.

{{ ref:stage-requirements.md }}
9. **Hard-stop** -- present the completed plan.html to the user. Do NOT proceed to the solution stage. Tell them: "Review plan.html. When ready, run `/{{ skill:new-solution }}` to continue."
