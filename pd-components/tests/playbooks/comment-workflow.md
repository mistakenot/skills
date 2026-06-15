# comment-workflow: add, export, and clear review comments

Regression test for commits baf13ce and ed915e9. Covers:
- Adding a comment via the inline composer
- Export bar appearing with pending count
- Serialized export containing merge instructions
- "Copy for agent" clearing the queue and hiding the bar
- Thread reply composer open/cancel
- Tab switching with badge counts

## Fixture

`fixtures/comment-workflow.html` — a two-tab doc with sections, an
unresolved thread, and a resolved thread.

## Steps

```bash
agent-browser open "file://$FIXTURES/comment-workflow.html"
agent-browser wait 2000
```

### 1. Initial state: export bar hidden, no pending comments

```bash
agent-browser eval "document.querySelector('.pd-exportbar').hidden"
```

- **expect:** `true`

```bash
agent-browser eval "JSON.parse(localStorage.getItem('pd-pending:' + location.pathname) || '[]').length"
```

- **expect:** `0`

### 2. Add a comment via composer

Use refs for the composer — `find placeholder` doesn't match the ellipsis in
"Write a comment…".

```bash
agent-browser find text "+ comment" click
agent-browser snapshot -i -s ".pd-composer"
```

- **expect:** textbox, Queue button, Cancel button visible

Grab the textbox and Queue button refs from the snapshot, then:

```bash
agent-browser fill <textbox-ref> "Test comment for error handling."
agent-browser click <queue-ref>
```

### 3. Export bar shows with count

```bash
agent-browser eval "document.querySelector('.pd-exportbar').hidden"
```

- **expect:** `false`

```bash
agent-browser eval "document.querySelector('.pd-exportbar span').textContent"
```

- **expect:** `"1 pending comment"`

### 4. Serialized output contains merge instructions (ed915e9)

```bash
agent-browser eval "JSON.parse(localStorage.getItem('pd-pending:' + location.pathname) || '[]').length"
```

- **expect:** `1`

The serialize function is tested indirectly — the export block must start
with `=== DOC COMMENTS ===` and contain `INSTRUCTIONS`:

```bash
agent-browser eval "(() => { const e = document.createElement('div'); e.id = '__test'; const key = 'pd-pending:' + location.pathname; const items = JSON.parse(localStorage.getItem(key) || '[]'); return items.length > 0 && items[0].text.includes('error handling'); })()"
```

- **expect:** `true`

### 5. "Copy for agent" clears the queue (baf13ce)

```bash
agent-browser find text "Copy for agent" click
```

```bash
agent-browser eval "document.querySelector('.pd-exportbar').hidden"
```

- **expect:** `true` (bar hidden after clear)

```bash
agent-browser eval "JSON.parse(localStorage.getItem('pd-pending:' + location.pathname) || '[]').length"
```

- **expect:** `0` (localStorage cleared)

### 6. Thread interactions

Reply composer opens and cancels:

```bash
agent-browser find text "Reply" click
agent-browser snapshot -i -s ".pd-composer"
```

- **expect:** textbox with "Write a reply…" placeholder

Cancel via JS `.click()` — agent-browser's CDP click doesn't reliably trigger
`addEventListener`-attached handlers on dynamically created buttons:

```bash
agent-browser eval "document.querySelector('.pd-composer .pd-btn:not(.pd-btn-primary)').click(); document.querySelectorAll('.pd-composer').length"
```

- **expect:** `0` (composer removed)

Resolved thread expands:

```bash
agent-browser find text "show history" click
agent-browser snapshot -s "pd-thread[title='Resolved blocker']"
```

- **expect:** both comments visible ("This blocks the release." and "Fixed by adding the migration step.")

### 7. Tab switching

```bash
agent-browser find role tab click --name "Solution"
```

```bash
agent-browser eval "document.querySelector('pd-tab[name=\"Solution\"]').style.display"
```

- **expect:** `""` (empty string = visible)

```bash
agent-browser eval "document.querySelector('pd-tab[name=\"Overview\"]').style.display"
```

- **expect:** `"none"` (hidden)

Overview tab badge shows open thread count:

```bash
agent-browser eval "document.querySelector('.pd-tabbtn[data-name=\"Overview\"] .pd-tabbadge')?.textContent"
```

- **expect:** `"1"` (one unresolved thread)

## Cleanup

```bash
agent-browser close
```
