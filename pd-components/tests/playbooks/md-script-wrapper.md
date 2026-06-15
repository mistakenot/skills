# md-script-wrapper: HTML tag names in markdown don't break DOM

Regression test for commit f43315c. Markdown containing angle-bracket tag
names (`<textarea>`, `<script>`, etc.) inside backtick code must render
correctly when using the `<script type="text/plain">` wrapper. Without the
wrapper, the browser's HTML parser interprets these as real elements and
destroys the DOM structure.

## Fixture

`fixtures/md-script-wrapper.html` — three sections: two using the script
wrapper with HTML tag names, one plain `<md>` for comparison.

## Steps

```bash
agent-browser open "file://$FIXTURES/md-script-wrapper.html"
agent-browser wait 3000
```

### 1. HTML tag names render as inline code, not DOM elements

```bash
agent-browser eval "document.querySelectorAll('#html-tags md code').length"
```

- **expect:** `4` (textarea, select, script, iframe — each in a `<code>`)

```bash
agent-browser eval "document.querySelectorAll('#html-tags md li').length"
```

- **expect:** `4` (four list items)

```bash
agent-browser eval "document.querySelectorAll('#html-tags textarea').length"
```

- **expect:** `0` (no real textarea element — it's rendered as code text)

```bash
agent-browser eval "document.querySelectorAll('#html-tags iframe').length"
```

- **expect:** `0` (no real iframe element)

### 2. Code blocks with generics preserve angle brackets

```bash
agent-browser eval "document.querySelector('#angle-brackets md code').textContent.includes('Array<string>')"
```

- **expect:** `true`

```bash
agent-browser eval "document.querySelector('#angle-brackets md pre code').textContent.includes('Parser<T>')"
```

- **expect:** `true`

### 3. All three sections exist as siblings (DOM not corrupted)

```bash
agent-browser eval "document.querySelectorAll('pd-tab > pd-section').length"
```

- **expect:** `3` (the bug caused sections to nest inside each other)

### 4. Plain md (no wrapper) still works

```bash
agent-browser eval "document.querySelectorAll('#plain-md md li').length"
```

- **expect:** `2`

## Cleanup

```bash
agent-browser close
```
