# lint: the plan checks its own consistency and queues findings

Verifies the self-lint: it detects orphan files, untracked files, bad
dependency references, and cycles, renders a panel, and queues a single
idempotent pending comment for the agent.

## Fixture

`fixtures/lint.html` — a plan with four deliberate inconsistencies.

## Steps

```bash
agent-browser open "file://$FIXTURES/lint.html"
agent-browser wait 3000
```

### 1. The lint panel lists every issue

```bash
agent-browser eval "!!document.querySelector('.pd-lint')"
```

- **expect:** `true`

```bash
agent-browser eval "document.querySelectorAll('.pd-lint-list li').length"
```

- **expect:** `4` (orphan file, ghost file, bad dep, cycle)

```bash
agent-browser eval "[...document.querySelectorAll('.pd-lint-list li')].some(li => li.textContent.includes('orphan.ts'))"
```

- **expect:** `true`

```bash
agent-browser eval "[...document.querySelectorAll('.pd-lint-list li')].some(li => li.textContent.includes('cycle'))"
```

- **expect:** `true`

### 2. Findings are queued as one pending comment

```bash
agent-browser eval "JSON.parse(localStorage.getItem('pd-pending:'+location.pathname)||'[]').length"
```

- **expect:** `1`

```bash
agent-browser eval "JSON.parse(localStorage.getItem('pd-pending:'+location.pathname)||'[]')[0].lint === true"
```

- **expect:** `true` (tagged so it replaces itself, never accumulates)

### 3. Reloading does not duplicate the comment (idempotent)

```bash
agent-browser eval "location.reload(); 'reloaded'"
agent-browser wait 3000
agent-browser eval "JSON.parse(localStorage.getItem('pd-pending:'+location.pathname)||'[]').length"
```

- **expect:** `1` (still one — the prior lint comment was replaced, not appended)

## Cleanup

```bash
agent-browser close
```
