# Plan Tab Guidelines

The Plan tab is the agent-consumed execution recipe. It is the fourth tab in `plan.html`, created by `{{ skill:beta-new-plan }}`.

## Structure

```html
<pd-tab name="Plan">
  <pd-section id="summary" title="Summary">
    <md>One sentence describing the implementation approach.</md>
  </pd-section>

  <pd-mermaid caption="Execution Sequence">
  flowchart LR
    P1[Phase 1] --> P2[Phase 2] --> P3[Phase 3]
  </pd-mermaid>

  <pd-stepper>
    <pd-phase n="1" title="Phase title" files="src/a.ts,src/b.ts" status="todo">
      <md>
- Step 1.1: description
- Step 1.2: description
- Step 1.3: Commit: `feat($ID): phase 1 — $title`
      </md>
    </pd-phase>

    <pd-phase n="2" title="Phase title" files="src/c.ts" status="todo">
      <md>
- Step 2.1: description
- Step 2.2: description
- Step 2.3: Commit: `feat($ID): phase 2 — $title`
      </md>
    </pd-phase>
  </pd-stepper>

  <pd-section id="success-criteria" title="Success Criteria">
    <md>
- Maps back to AC ids (e.g. "AC-1 through AC-3 pass")
    </md>
  </pd-section>
</pd-tab>
```

## Rules

- Each `pd-phase` has: `n` (number), `title`, `files` (comma-separated paths matching `pd-file` entries), `status="todo"`.
- Phase body goes in `<md>`. Each phase is atomic — one subagent handles it end-to-end.
- Every phase ends with a commit step. Every phase includes verification (typecheck, tests, lint).
- The `pd-mermaid` execution sequence shows the phase dependency DAG for parallel dispatch.
- `files` must reference paths already declared in the Solution tab's `pd-files`.

## AC Traceability Backfill

After writing the Plan tab, go back to the Verification tab and update each `pd-ac` card:
- Set `phases` to the comma-separated phase numbers that cover it (e.g. `phases="1,2"`).
- Set `tests` to the comma-separated test file paths from the solution (e.g. `tests="src/feature.test.ts"`).

This links acceptance criteria to the phases that implement them and the tests that verify them.
