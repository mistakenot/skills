# status-banner: lifecycle banner reflects stage, blocked overrides on open threads

Verifies the top status banner: executing is a single animated state (no
progress score), any unresolved comment thread overrides to blocked, and a
terminal stage shows complete once threads are closed.

## Fixture

`fixtures/status-banner.html` — status="executing", one comment thread that
starts resolved.

## Steps

```bash
agent-browser open "file://$FIXTURES/status-banner.html"
agent-browser wait 3000
```

### 1. Executing is a single state (no progress score)

```bash
agent-browser eval "document.querySelector('.pd-statusbar').dataset.kind"
```

- **expect:** `executing`

```bash
agent-browser eval "document.querySelector('.pd-statusbar .pd-sb-label').textContent"
```

- **expect:** `Executing`

### 2. An unresolved thread overrides to blocked

```bash
agent-browser eval "document.getElementById('blk').setAttribute('status','unresolved'); window.dispatchEvent(new Event('pd:status-refresh')); document.querySelector('.pd-statusbar').dataset.kind"
```

- **expect:** `blocked` (the declared status is still executing — blocked overrides it)

```bash
agent-browser eval "document.querySelector('.pd-statusbar .pd-sb-label').textContent"
```

- **expect:** `Blocked — 1 open comment thread`

```bash
agent-browser eval "document.querySelector('.pd-statusbar').classList.contains('pd-sb-clickable')"
```

- **expect:** `true` (clickable → jumps to the open thread)

### 3. Complete once threads are closed

```bash
agent-browser eval "document.getElementById('blk').setAttribute('status','resolved'); document.querySelector('pd-doc').setAttribute('status','complete'); window.dispatchEvent(new Event('pd:status-refresh')); document.querySelector('.pd-statusbar').dataset.kind"
```

- **expect:** `complete`

```bash
agent-browser eval "document.querySelector('.pd-statusbar .pd-sb-label').textContent"
```

- **expect:** `Complete`

## Cleanup

```bash
agent-browser close
```
