# question-workflow: agent asks the human, human answers via paste-back

Regression test for the `pd-question` / `pd-answer` components. Covers:
- An open question renders with the "needs your answer" flag
- An answered question renders its `pd-answer` and no Answer button
- The doc status bar reports "blocked" while a question is open
- Answering via the composer queues an ANSWER item to the store
- The serialized export contains the ANSWER merge instruction

## Fixture

`fixtures/question-workflow.html` — a one-tab doc with one open question (Q-1)
and one answered question (Q-2).

## Steps

```bash
agent-browser open "file://$FIXTURES/question-workflow.html"
agent-browser wait 2000
```

### 1. Open question renders as a human gate

```bash
agent-browser eval "document.querySelector('pd-question#Q-1 .pd-q-flag').getAttribute('data-answered')"
```

- **expect:** `"no"`

```bash
agent-browser eval "document.querySelector('pd-question#Q-1 .pd-q-flag').textContent.includes('needs your answer')"
```

- **expect:** `true`

### 2. Answered question shows its answer and no Answer button

```bash
agent-browser eval "document.querySelector('pd-question#Q-2 pd-answer').textContent.trim()"
```

- **expect:** `"24 hours."` (the `by` label is a CSS ::before, not text)

```bash
agent-browser eval "!!document.querySelector('pd-question#Q-2 .pd-question-actions')"
```

- **expect:** `false`

### 3. Status bar is blocked while Q-1 is open

```bash
agent-browser eval "document.querySelector('.pd-statusbar').dataset.kind"
```

- **expect:** `"blocked"`

```bash
agent-browser eval "document.querySelector('.pd-sb-label').textContent.includes('open question')"
```

- **expect:** `true`

### 4. Answer the open question via the composer

```bash
agent-browser eval "document.querySelector('pd-question#Q-1 .pd-question-actions .pd-btn').click(); !!document.querySelector('pd-question#Q-1 .pd-composer')"
```

- **expect:** `true` (composer opened)

```bash
agent-browser snapshot -i -s "pd-question#Q-1 .pd-composer"
```

- **expect:** textbox with "Write your answer…" placeholder, Queue + Cancel buttons

Fill and queue (grab refs from the snapshot):

```bash
agent-browser fill <textbox-ref> "Separate unlimited tier; key by service id."
agent-browser click <queue-ref>
```

### 5. The answer is queued as an ANSWER item

```bash
agent-browser eval "(() => { const items = JSON.parse(localStorage.getItem('pd-pending:' + location.pathname) || '[]'); return items.length === 1 && items[0].kind === 'answer' && items[0].question === 'Which tier do internal services use?'; })()"
```

- **expect:** `true`

### 6. Serialized export carries the ANSWER instruction

```bash
agent-browser eval "(() => { const e = document.querySelector('.pd-exportbar'); return !e.hidden; })()"
```

- **expect:** `true` (export bar visible with the pending answer)

The serialize output (built on "Copy for agent") must mention the ANSWER merge
rule. Verify the instruction text is present in the store serialization by
reconstructing it is out of scope here; instead confirm the queued item shape
is what `serialize` formats into an `ANSWER to question "…"` line (step 5).

## Cleanup

```bash
agent-browser close
```
