# Verification Tab Guidelines

The Verification tab defines how the task will be tested and what "done" means. It is the second tab in `plan.html`, created by `{{ skill:beta-new-solution }}` (stage 2).

## Structure

```html
<pd-tab name="Verification">
  <pd-section id="test-strategy" title="Test Strategy">
    <md>
Testing approach, tooling, and coverage philosophy.
    </md>
  </pd-section>

  <!-- Optional: coverage architecture diagram -->
  <pd-mermaid caption="Coverage Map">
  flowchart LR
    Unit --> Integration --> E2E
  </pd-mermaid>

  <pd-ac id="AC-1" title="Short description" phases="" tests="">
    <md>
- Given: precondition
- When: action
- Then: expected result
    </md>
  </pd-ac>

  <pd-ac id="AC-2" title="Short description" phases="" tests="">
    <md>
- Given: ...
- When: ...
- Then: ...
    </md>
  </pd-ac>

  <pd-section id="verification-gaps" title="Known Gaps &amp; Risks">
    <md>
- What isn't covered and why
    </md>
  </pd-section>
</pd-tab>
```

## Rules

- `pd-ac` id format: `AC-1`, `AC-2`, etc.
- Write acceptance criteria in Given/When/Then format inside `<md>` blocks.
- Leave `phases` and `tests` attributes empty — the Plan stage backfills these with traceability data.
- The `pd-mermaid` coverage map is optional. Include it when it clarifies the testing architecture.
- Scan available project skills for testing, verification, and assurance strategies before writing this tab.
- Use `&amp;` for `&` in attribute values (e.g. `title="Known Gaps &amp; Risks"`).
