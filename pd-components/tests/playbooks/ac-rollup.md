# ac-rollup: pill rollup, two-level disclosure, auto-open, click split, DOM-preservation, contract banner

Verifies T4 of the executable-completion-contracts epic: a `<pd-ac>` carrying
nested `pd-ac-check-*` children renders a status **pill** + an "n/m checks
passing" count derived purely from the authored child statuses (AC-1), folds the
body + checks into a collapse-by-default `<details>` that the header toggles
(AC-3), reveals each failing check's evidence + provenance at a second
disclosure level (AC-4), auto-opens on `contradicted` and honours an explicit
`open` (AC-5), keeps every authored check **element** in the DOM across toggles
(AC-6), splits clicks so a phase chip highlights traceability without toggling
the disclosure (AC-7), leaves a **check-free** card rendering exactly as today
(purely additive / G1, AC-8), and rolls every with-checks AC up into a
document-level `<pd-contract>` banner reading "n/m ACs proved" with a contract
pill (AC-9).

The authoritative assertions live in `tests/run.sh` under the `── ac-rollup ──`
block. This file is the human-readable spec.

## Fixture

`fixtures/ac-rollup.html` — one `<pd-contract>` banner plus five cards:

| id | checks | expected rollup |
|---|---|---|
| `AC-proved` | command (proved) + test (proved) | pill `proved`/green, `2/2`, closed |
| `AC-bad` | command (proved) + test (contradicted, w/ evidence + provenance) | pill `contradicted`/red, `1/2`, **auto-open** |
| `AC-pending` | command (no status) + file-exists (no status) | pill `pending`/neutral, `0/2`, closed |
| `AC-open` | command (proved) + file-contains (proved), card has `open` | pill `proved`/green, `2/2`, **open (explicit)** |
| `AC-free` | none | today's exact shape: head + body, no pill, no disclosure |

Contract maths: four with-checks ACs (m=4), two roll up to `proved` (n=2) →
`2/4 ACs proved`; the contract pill is `contradicted`/red while any AC is
contradicted. The check-free `AC-free` is excluded.

## Steps

```bash
agent-browser open "file://$FIXTURES/ac-rollup.html"
agent-browser wait 3000
```

### 1. AC-1 — pill text / colour / count are derived from authored child status

```bash
agent-browser eval "document.querySelector('pd-ac[id=\"AC-proved\"] .pd-ac-pill').textContent"
agent-browser eval "document.querySelector('pd-ac[id=\"AC-proved\"] .pd-ac-pill').classList.contains('pd-pill-ok')"
agent-browser eval "document.querySelector('pd-ac[id=\"AC-proved\"] .pd-ac-count').textContent"
```

- **expect:** `proved` · `true` · `2/2 checks passing`

```bash
agent-browser eval "document.querySelector('pd-ac[id=\"AC-bad\"] .pd-ac-pill').textContent"
agent-browser eval "document.querySelector('pd-ac[id=\"AC-bad\"] .pd-ac-pill').classList.contains('pd-pill-bad')"
agent-browser eval "document.querySelector('pd-ac[id=\"AC-bad\"] .pd-ac-count').textContent"
```

- **expect:** `contradicted` · `true` · `1/2 checks passing` (one proved + one contradicted → worst-wins)

```bash
agent-browser eval "document.querySelector('pd-ac[id=\"AC-pending\"] .pd-ac-pill').textContent"
agent-browser eval "document.querySelector('pd-ac[id=\"AC-pending\"] .pd-ac-pill').classList.contains('pd-pill-neutral')"
agent-browser eval "document.querySelector('pd-ac[id=\"AC-pending\"] .pd-ac-count').textContent"
```

- **expect:** `pending` · `true` · `0/2 checks passing` (null status normalises to pending; none proved)

Each check renders one `type · key-attr` row:

```bash
agent-browser eval "[...document.querySelectorAll('pd-ac[id=\"AC-proved\"] .pd-ac-check-label')].map(e=>e.textContent).join('|')"
```

- **expect:** `command · tsc --noEmit|test · returns 429 over limit`

### 2. AC-3 — collapsed by default; the header toggles the disclosure

```bash
agent-browser eval "document.querySelector('pd-ac[id=\"AC-proved\"] details.pd-ac-disclosure').open"
agent-browser eval "(() => { const d = document.querySelector('pd-ac[id=\"AC-proved\"] details.pd-ac-disclosure'); d.querySelector('summary').click(); return d.open; })()"
agent-browser eval "document.querySelector('pd-ac[id=\"AC-proved\"] .pd-ac-checks .pd-ac-check-row').getBoundingClientRect().height > 0"
agent-browser eval "(() => { const d = document.querySelector('pd-ac[id=\"AC-proved\"] details.pd-ac-disclosure'); d.querySelector('summary').click(); return d.open; })()"
```

- **expect:** `false` (closed at rest) → `true` (open after click) → `true` (rows now visible) → `false` (closed after second click)

### 3. AC-4 — a failing check exposes evidence + provenance at a second level

```bash
agent-browser eval "!!document.querySelector('pd-ac[id=\"AC-bad\"] .pd-ac-check-row details.pd-collapse')"
agent-browser eval "(() => { const d = document.querySelector('pd-ac[id=\"AC-bad\"] .pd-ac-check-row details.pd-collapse'); d.open = true; return document.querySelector('pd-ac[id=\"AC-bad\"] .pd-ac-evidence-text').textContent.includes('received 500'); })()"
agent-browser eval "document.querySelector('pd-ac[id=\"AC-bad\"] .pd-ac-provenance').textContent.includes('abc1234')"
```

- **expect:** `true` (nested collapse exists) · `true` (multi-line evidence revealed) · `true` (provenance stamp carries the commit — full text `verified at abc1234, 2 files dirty, 3h ago`)

### 4. AC-5 — contradicted auto-opens; explicit `open` honoured; plain card closed

```bash
agent-browser eval "document.querySelector('pd-ac[id=\"AC-bad\"] details.pd-ac-disclosure').open"
agent-browser eval "document.querySelector('pd-ac[id=\"AC-open\"] details.pd-ac-disclosure').open"
agent-browser eval "document.querySelector('pd-ac[id=\"AC-proved\"] details.pd-ac-disclosure').open"
```

- **expect:** `true` (contradicted, no interaction) · `true` (explicit `open`, not contradicted) · `false` (plain proved card)

### 5. AC-6 — every authored check ELEMENT stays in the DOM across a toggle

```bash
agent-browser eval "document.querySelectorAll('pd-ac-check-command,pd-ac-check-output,pd-ac-check-test,pd-ac-check-file-exists,pd-ac-check-file-contains').length"
# toggle AC-proved open then closed
agent-browser eval "(() => { const d = document.querySelector('pd-ac[id=\"AC-proved\"] details.pd-ac-disclosure'); d.querySelector('summary').click(); d.querySelector('summary').click(); })()"
agent-browser eval "document.querySelectorAll('pd-ac-check-command,pd-ac-check-output,pd-ac-check-test,pd-ac-check-file-exists,pd-ac-check-file-contains').length"
```

- **expect:** the element count (8) is **unchanged** after the toggle — disclosure is visual only, relocation ≠ removal. (Count check tag elements, NOT raw childNodes.)

### 6. AC-7 — click reconciliation (header toggles, phase chip highlights)

```bash
agent-browser eval "(() => { window.__pe = 0; const h = () => window.__pe++; window.addEventListener('pd:phase-selected', h); const d = document.querySelector('pd-ac[id=\"AC-proved\"] details.pd-ac-disclosure'); const was = d.open; document.querySelector('pd-ac[id=\"AC-proved\"] .pd-ac-chip-link').click(); const res = window.__pe + '/' + (d.open === was); window.removeEventListener('pd:phase-selected', h); return res; })()"
```

- **expect:** `1/true` — the chip click fires exactly one `pd:phase-selected` and leaves `details.open` unchanged (`stopPropagation` + `preventDefault`).

```bash
agent-browser eval "(() => { window.__pe2 = 0; const h = () => window.__pe2++; window.addEventListener('pd:phase-selected', h); const d = document.querySelector('pd-ac[id=\"AC-proved\"] details.pd-ac-disclosure'); const was = d.open; d.querySelector('summary strong').click(); const res = window.__pe2 + '/' + (d.open !== was); window.removeEventListener('pd:phase-selected', h); return res; })()"
```

- **expect:** `0/true` — clicking the title toggles `details.open` natively and fires NO `pd:phase-selected`.

### 7. AC-8 — purely additive: the check-free card is unchanged (G1)

```bash
agent-browser eval "document.querySelector('pd-ac[id=\"AC-free\"] .pd-ac-pill') === null"
agent-browser eval "document.querySelector('pd-ac[id=\"AC-free\"] details.pd-ac-disclosure') === null"
agent-browser eval "!!document.querySelector('pd-ac[id=\"AC-free\"] > .pd-ac-head')"
agent-browser eval "document.querySelector('pd-ac[id=\"AC-free\"]').textContent.includes('looks identical to today')"
```

- **expect:** `true` (no pill) · `true` (no disclosure) · `true` (prepended head) · `true` (GWT body present/visible). The broader G1 proof is the rest of the suite staying green.

### 8. AC-9 — the document-level contract banner

```bash
agent-browser eval "!!document.querySelector('.pd-contract')"
agent-browser eval "document.querySelector('.pd-contract .pd-contract-count').textContent"
agent-browser eval "document.querySelector('.pd-contract .pd-ac-pill').textContent"
agent-browser eval "document.querySelector('.pd-contract .pd-ac-pill').classList.contains('pd-pill-bad')"
```

- **expect:** `true` (banner exists) · `2/4 ACs proved` (m=4 with-checks ACs, n=2 proved; check-free excluded) · `contradicted` · `true` (red while any AC is contradicted — `rollupContract` worst-wins)

## Cleanup

```bash
agent-browser close
```
