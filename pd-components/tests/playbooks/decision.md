# decision: pd-decision records and pd-decisions aggregation

Verifies the authored `<pd-decision>` ADR block renders (head badge + body) and
that `<pd-decisions>` aggregates authored decisions plus resolved/rejected
threads — in source order, excluding open threads.

## Fixture

`fixtures/decision.html` — two pd-decision blocks (D-1 accepted, D-2 proposed),
one resolved thread, one unresolved thread, and a `<pd-decisions>` log on the
Overview tab.

## Steps

```bash
agent-browser open "file://$FIXTURES/decision.html"
agent-browser wait 3000
```

### 1. pd-decision renders its head and body

```bash
agent-browser eval "document.querySelectorAll('pd-decision .pd-decision-head').length"
```

- **expect:** `2`

```bash
agent-browser eval "document.querySelector('#D-1 .pd-badge').textContent"
```

- **expect:** `accepted`

```bash
agent-browser eval "document.querySelector('#D-1 .pd-decision-meta').textContent"
```

- **expect:** `by agent`

```bash
agent-browser eval "!!document.querySelector('#D-1 .pd-decision-body md')"
```

- **expect:** `true` (children moved into the body wrapper)

### 2. Status drives the left-rail colour via the status attribute

```bash
agent-browser eval "document.querySelector('#D-2 .pd-badge').textContent"
```

- **expect:** `proposed`

```bash
agent-browser eval "document.querySelector('#D-2').getAttribute('status')"
```

- **expect:** `proposed` (CSS keys the border on pd-decision[status])

### 3. pd-decisions aggregates decisions + closed threads, in source order

```bash
agent-browser eval "document.querySelectorAll('pd-decisions .pd-decision-list li').length"
```

- **expect:** `3` (D-1, D-2, the resolved thread — the unresolved thread is excluded)

```bash
agent-browser eval "[...document.querySelectorAll('pd-decisions .pd-decision-list li a')].map(a=>a.textContent).join('|')"
```

- **expect:** `Token bucket over sliding window|Defer multi-region replication|Why not a queue?`

### 4. The log links each entry to its source element

```bash
agent-browser eval "document.querySelector('pd-decisions .pd-decision-list li a').getAttribute('href')"
```

- **expect:** `#D-1`

### 5. The outcome line uses summary for decisions, last comment for threads

```bash
agent-browser eval "document.querySelector('pd-decisions .pd-decision-list li .pd-decision-outcome').textContent"
```

- **expect:** `Token bucket: simpler, bursts within SLA.` (D-1's summary attribute)

```bash
agent-browser eval "[...document.querySelectorAll('pd-decisions .pd-decision-list li')].find(li=>li.textContent.includes('Why not a queue?')).querySelector('.pd-decision-outcome').textContent"
```

- **expect:** `Adds latency; the bucket is sufficient.` (the thread's last comment)

## Cleanup

```bash
agent-browser close
```
