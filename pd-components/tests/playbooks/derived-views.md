# derived-views: scope, dag, trace, collapse, mirror

Verifies the derived/visual components compute themselves from existing
attributes: pd-scope counts, pd-dag dependency + conflict detection, pd-trace
coverage gaps, section/collapse disclosure, and the auto-injected Plan-tab file
mirror.

## Fixture

`fixtures/derived-views.html` — 4 phases in a diamond (2 and 3 parallel, both
touching `src/shared.ts` → a file conflict), 2 ACs (one untested → coverage
gap), files on the Solution tab, controls on the Plan tab.

## Steps

```bash
agent-browser open "file://$FIXTURES/derived-views.html"
agent-browser wait 3000
```

### 1. pd-scope derives counts and progress

```bash
agent-browser eval "document.querySelectorAll('pd-scope .pd-scope-tile').length"
```

- **expect:** `3` (phases, files, criteria — no open-thread tile, the fixture has none)

```bash
agent-browser eval "document.querySelector('pd-scope').innerText.replace(/\s+/g,' ').includes('4 PHASES')"
```

- **expect:** `true`

```bash
agent-browser eval "document.querySelector('pd-scope').innerText.replace(/\s+/g,' ').includes('1 untested')"
```

- **expect:** `true` (one AC has no test)

### 2. pd-dag builds the dependency graph

```bash
agent-browser eval "document.querySelectorAll('pd-dag .pd-dag-node').length"
```

- **expect:** `4`

```bash
agent-browser eval "document.querySelectorAll('pd-dag .pd-dag-edge:not(.pd-dag-conflict)').length"
```

- **expect:** `4` (1→2, 1→3, 2→4, 3→4)

### 3. pd-dag auto-detects the file conflict

```bash
agent-browser eval "document.querySelectorAll('pd-dag .pd-dag-conflict').length"
```

- **expect:** `1` (phases 2 and 3 are parallel but both touch src/shared.ts)

```bash
agent-browser eval "document.querySelector('pd-dag .pd-dag-conflicts').innerText.includes('shared.ts')"
```

- **expect:** `true`

### 4. pd-trace flags the coverage gap

```bash
agent-browser eval "document.querySelectorAll('pd-trace tbody tr').length"
```

- **expect:** `2`

```bash
agent-browser eval "document.querySelectorAll('pd-trace tbody tr[data-gap]').length"
```

- **expect:** `1` (the untested AC)

### 5. Section summary collapses the body; pd-collapse renders

```bash
agent-browser eval "!!document.querySelector('.pd-section-summary')"
```

- **expect:** `true`

```bash
agent-browser eval "document.querySelector('.pd-section-collapse').hasAttribute('open')"
```

- **expect:** `false` (collapsed by default)

```bash
agent-browser eval "!!document.querySelector('pd-collapse details')"
```

- **expect:** `true`

### 6. Plan-tab file mirror auto-injects and syncs

```bash
agent-browser eval "!!document.querySelector('pd-tab[name=\"Plan\"] .pd-files-mirror')"
```

- **expect:** `true` (files live on Solution, controls on Plan → mirror injected)

```bash
agent-browser eval "document.querySelectorAll('pd-tab[name=\"Solution\"] .pd-files-mirror').length"
```

- **expect:** `0` (not mirrored onto the tab that already has the canonical tree)

```bash
agent-browser eval "document.querySelectorAll('.pd-files-mirror .pd-tree-file').length"
```

- **expect:** `5`

Click the second DAG node (phase 2) and confirm its files highlight in the mirror:

```bash
agent-browser eval "document.querySelectorAll('pd-dag .pd-dag-node')[1].dispatchEvent(new MouseEvent('click',{bubbles:true})); 'clicked'"
agent-browser eval "[...document.querySelectorAll('.pd-files-mirror .pd-tree-file.pd-hl')].map(f=>f.dataset.path).sort().join(',')"
```

- **expect:** `src/api.ts,src/shared.ts`

### 7. AC traceability is bidirectional

Selecting phase 2 highlights the AC rows that cover it (forward):

```bash
agent-browser eval "document.querySelectorAll('pd-dag .pd-dag-node')[1].dispatchEvent(new MouseEvent('click',{bubbles:true})); [...document.querySelectorAll('pd-trace tr.pd-trace-hl')].map(r=>r.dataset.ac).sort().join(',')"
```

- **expect:** `AC-1` (AC-1 covers phases 1,2; AC-2 covers only phase 4)

Clicking an AC highlights the phases and files that satisfy it (reverse):

```bash
agent-browser eval "document.getElementById('AC-1').click(); [...document.querySelectorAll('pd-dag .pd-dag-node.pd-dag-on .pd-dag-n')].map(n=>n.textContent).sort().join(',')"
```

- **expect:** `1,2` (AC-1's phases light up in the graph)

```bash
agent-browser eval "[...document.querySelectorAll('pd-files .pd-tree-file.pd-hl')].map(f=>f.dataset.path).sort().join(',')"
```

- **expect:** `src/api.ts,src/core.ts,src/shared.ts` (union of phase 1 + phase 2 files)

## Cleanup

```bash
agent-browser close
```
