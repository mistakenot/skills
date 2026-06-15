# Solution Tab Guidelines

The Solution tab describes the chosen approach and file changes. It is the third tab in `plan.html`, created by `{{ skill:beta-new-solution }}` (stage 3).

## Structure

```html
<pd-tab name="Solution">
  <pd-section id="approach" title="Approach">
    <md>
High-level description of the solution — what changes and why.
    </md>
  </pd-section>

  <pd-files>
    <pd-file path="src/example/new-file.ts" change="add">Brief description</pd-file>
    <pd-file path="src/example/existing.ts" change="edit">What changes</pd-file>
    <pd-file path="src/example/obsolete.ts" change="delete">Why removed</pd-file>
  </pd-files>

  <pd-section id="rejected-alternatives" title="Rejected Alternatives">
    <md>
- **Option B**: one-line reason it was rejected
- **Option C**: one-line reason it was rejected
    </md>
  </pd-section>

  <pd-decisions></pd-decisions>
</pd-tab>
```

## Rules

- Approach goes in `<md>`. Keep it high-level — implementation details belong in the Plan tab.
- `pd-files` uses `change` attribute: `add`, `edit`, or `delete`. One `pd-file` per affected file.
- `pd-decisions` auto-generates a decision log from all resolved `pd-thread` elements in the doc. Place it once, at the end of the Solution tab.
- Include rejected alternatives even for simple tasks — they document the decision space.
- File paths are relative to repo root. Include brief descriptions as text content.
