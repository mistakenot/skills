# md-dedent: indented markdown renders correctly

Regression test for commit f43315c. Indented `<md>` content (nested inside
`<pd-section>`) must render as proper lists and paragraphs, not `<pre>` code
blocks.

## Fixture

`fixtures/md-dedent.html` — three sections with varying indentation depths.

## Steps

```bash
agent-browser open "file://$FIXTURES/md-dedent.html"
agent-browser wait 3000
```

### 1. Indented unordered list renders as `<ul>`

```bash
agent-browser eval "document.querySelectorAll('#indented-list md ul').length"
```

- **expect:** `1` (one `<ul>` element)

```bash
agent-browser eval "document.querySelectorAll('#indented-list md ul li').length"
```

- **expect:** `3` (three list items)

```bash
agent-browser eval "document.querySelectorAll('#indented-list md pre').length"
```

- **expect:** `0` (no code blocks — the bug rendered indented lists as `<pre>`)

### 2. Indented ordered list renders as `<ol>`

```bash
agent-browser eval "document.querySelectorAll('#nested-deeper md ol').length"
```

- **expect:** `1`

```bash
agent-browser eval "document.querySelectorAll('#nested-deeper md ol li').length"
```

- **expect:** `3`

### 3. Mixed content preserves structure

```bash
agent-browser eval "document.querySelectorAll('#mixed-content md h2').length"
```

- **expect:** `1` (heading inside md)

```bash
agent-browser eval "document.querySelectorAll('#mixed-content md strong').length"
```

- **expect:** `1` (bold text)

```bash
agent-browser eval "document.querySelectorAll('#mixed-content md code').length"
```

- **expect:** `1` (inline code)

```bash
agent-browser eval "document.querySelectorAll('#mixed-content md ul li').length"
```

- **expect:** `2` (bullet list)

## Cleanup

```bash
agent-browser close
```
