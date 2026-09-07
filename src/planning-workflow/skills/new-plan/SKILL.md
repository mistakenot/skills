---
name: new-plan
description: "Writes the Plan tab and backfills AC traceability for a task. Use when 'write a plan', 'new plan', 'create the plan', 'plan the task', or after solution is approved. Not applicable when solution doesn't exist yet."
---

# New Plan

Read plan.html and context.md, enrich context with git history, write the Plan tab, and backfill AC traceability.

> Part of the planning workflow. See [references/workflow-overview.md](references/workflow-overview.md) for the full pipeline.

{{ ref:stage-plan.md }}

### Phase 4: Hard-stop

7. **Hard-stop** -- present the Plan tab to the user. Tell them: "Review the Plan tab. The planning phase is now complete. When ready, run `/{{ skill:commit-task }}` to commit the task docs, then `/{{ skill:execute-task }}` to start implementation."
