# ac-checks: the five pd-ac-check-* elements register, expose .check, stay inert and additive

Verifies T1 of the executable-completion-contracts epic: the five
`pd-ac-check-*` tags upgrade to custom elements (AC-1), each exposes a read-only
`.check` parse of its authored attributes incl. the `test` portable identity
(AC-2), and the check **elements themselves** stay inert data-carriers — they add
no DOM of their own, have zero box, and fire no `pd:*` event on mount (AC-4). The
with-checks card preserves the same head shape (id chip, title, chips) and GWT
body as a check-free card, so existing head/chip/body authoring is unaffected
(AC-5).

(As of T4 / task 004 the **parent** `<pd-ac>` now renders a rollup pill +
two-level disclosure derived from these checks — proved in the `ac-rollup`
playbook. Here we assert only that the check elements stay inert and the head
shape is preserved, not that the parent renders nothing.)

## Fixture

`fixtures/ac-checks.html` — a check-free `<pd-ac id="AC-free">` and a sibling
`<pd-ac id="AC-checks">` carrying one nested check of each of the five types.

## Steps

```bash
agent-browser open "file://$FIXTURES/ac-checks.html"
agent-browser wait 3000
```

### 1. AC-1 — the five tags register as custom elements

```bash
agent-browser eval "['pd-ac-check-command','pd-ac-check-output','pd-ac-check-test','pd-ac-check-file-exists','pd-ac-check-file-contains'].every(t => typeof customElements.get(t) === 'function')"
```

- **expect:** `true`

```bash
agent-browser eval "(() => { const el = document.querySelector('pd-ac-check-test'); return el instanceof customElements.get('pd-ac-check-test'); })()"
```

- **expect:** `true` (an authored instance is `instanceof` its constructor)

### 2. AC-2 — `.check` exposes the normalised, parsed attributes

```bash
agent-browser eval "(() => { const c = document.querySelector('pd-ac-check-test').check; return c.type === 'test' && c.report === 'junit.xml' && c.name === 'returns 429' && c.suite === 'rate'; })()"
```

- **expect:** `true` (the `test` portable identity: `report` + `name` + `suite`)

```bash
agent-browser eval "(() => { const c = document.querySelector('pd-ac-check-test').check; return c.classname === null && c.file === null; })()"
```

- **expect:** `true` (absent attributes come back as `null`)

```bash
agent-browser eval "(() => { const c = document.querySelector('pd-ac-check-command').check; return c.type === 'command' && c.run === 'npm test' && c['expect-exit'] === '0'; })()"
```

- **expect:** `true`

### 3. AC-4 — inertness: the check elements add no DOM, zero box, no event

```bash
agent-browser eval "[...document.querySelectorAll('pd-ac[id=\"AC-checks\"] > [class*=\"check\"], pd-ac-check-command, pd-ac-check-output, pd-ac-check-test, pd-ac-check-file-exists, pd-ac-check-file-contains')].filter(el => el.tagName.startsWith('PD-AC-CHECK')).every(el => el.childElementCount === 0)"
```

- **expect:** `true` (each check element added **0 child elements** — assert on child element count, not raw `childNodes`, to tolerate parser text nodes)

```bash
agent-browser eval "(() => { const r = document.querySelector('pd-ac-check-test').getBoundingClientRect(); return r.width === 0 && r.height === 0; })()"
```

- **expect:** `true` (computed box is zero — `display:none`)

```bash
agent-browser eval "getComputedStyle(document.querySelector('pd-ac-check-test')).display"
```

- **expect:** `none`

```bash
agent-browser eval "window.__pdEvents = []; ['pd:phase-selected','pd:status-refresh','pd:check'].forEach(t => window.addEventListener(t, () => window.__pdEvents.push(t))); window.__pdEvents.length"
```

- **expect:** `0` (no `pd:*` event has fired on mount — the page already settled, so the count stays zero)

(The T1-era assertion that the parent `<pd-ac>` shows no rollup pill was retired
when T4 / task 004 introduced the with-checks render path — the pill is now
expected, and is proved in the `ac-rollup` playbook.)

### 4. AC-5 — purely additive: both cards render the same head / chips / body

```bash
agent-browser eval "document.querySelector('pd-ac[id=\"AC-free\"] .pd-ac-head .pd-chip-id').textContent"
```

- **expect:** `AC-free` (id chip)

```bash
agent-browser eval "document.querySelector('pd-ac[id=\"AC-checks\"] .pd-ac-head .pd-chip-id').textContent"
```

- **expect:** `AC-checks` (the with-checks card has the same id chip in its head)

```bash
agent-browser eval "document.querySelectorAll('pd-ac[id=\"AC-free\"] .pd-ac-head strong').length === 1 && document.querySelectorAll('pd-ac[id=\"AC-checks\"] .pd-ac-head strong').length === 1"
```

- **expect:** `true` (both cards render a title in the head)

```bash
agent-browser eval "document.querySelector('pd-ac[id=\"AC-free\"] .pd-ac-chips').children.length === document.querySelector('pd-ac[id=\"AC-checks\"] .pd-ac-chips').children.length"
```

- **expect:** `true` (both cards render the same chip count: 2 phase chips + 1 test chip)

```bash
agent-browser eval "!!document.querySelector('pd-ac[id=\"AC-free\"] md ul') && !!document.querySelector('pd-ac[id=\"AC-checks\"] md ul')"
```

- **expect:** `true` (both cards render their Given/When/Then body)

## Cleanup

```bash
agent-browser close
```
