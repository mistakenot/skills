# Requirements Tab Guidelines

The Requirements tab captures the problem, goals, and scope. It is the first tab in `plan.html`, created by `{{ skill:beta-new-task }}`.

## Structure

```html
<pd-tab name="Requirements">
  <pd-section id="problem" title="Problem">
    <md>1-2 sentences describing what's wrong or what's needed.</md>
  </pd-section>

  <pd-section id="goals" title="Goals">
    <md>
- Bullet list of what this task achieves
    </md>
  </pd-section>

  <pd-section id="out-of-scope" title="Out of Scope">
    <md>
- Product-level boundaries (what this task explicitly does NOT do)
    </md>
  </pd-section>

  <pd-section id="open-questions" title="Open Questions">
    <md>
- [ ] Question 1 (answered: ...)
    </md>
  </pd-section>
</pd-tab>
```

## Rules

- All prose goes in `<md>` blocks. No raw HTML inside sections.
- Give every `pd-section` a stable, kebab-case `id`. Do not change ids after creation.
- No acceptance criteria here — those belong in the Verification tab.
- Open Questions must be resolved before proceeding to the next stage.
- Keep it to ~1 page. Split larger work into multiple tasks.
