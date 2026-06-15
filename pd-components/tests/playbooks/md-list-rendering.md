# md-list-rendering: lists render visibly with Tailwind present

Regression test for Tailwind CSS preflight stripping list styles. Tailwind's
reset sets `list-style: none` and zeroes padding/margin on `ul`, `ol`, `li`.
Without explicit overrides in pd-components, markdown lists inside `<md>`
render as unstyled text blocks with no bullets, numbers, or indentation.

The fixture includes `@tailwindcss/browser@4` — same as real planning docs.

## Fixture

`fixtures/md-list-rendering.html` — four sections: basic unordered, basic
ordered, nested mixed, and list with surrounding paragraphs.

## Steps

```bash
agent-browser open "file://$FIXTURES/md-list-rendering.html"
agent-browser wait 4000
```

### 1. Unordered list has disc markers and padding

```bash
agent-browser eval "getComputedStyle(document.querySelector('#basic-ul md ul')).listStyleType"
```

- **expect:** `"disc"`

```bash
agent-browser eval "parseInt(getComputedStyle(document.querySelector('#basic-ul md ul')).paddingLeft) > 0"
```

- **expect:** `true` (non-zero padding — Tailwind default is 0)

```bash
agent-browser eval "document.querySelectorAll('#basic-ul md li').length"
```

- **expect:** `3`

### 2. Ordered list has decimal markers

```bash
agent-browser eval "getComputedStyle(document.querySelector('#basic-ol md ol')).listStyleType"
```

- **expect:** `"decimal"`

```bash
agent-browser eval "document.querySelectorAll('#basic-ol md li').length"
```

- **expect:** `3`

### 3. Nested lists render with hierarchy

```bash
agent-browser eval "getComputedStyle(document.querySelector('#nested-lists md ul ul')).listStyleType"
```

- **expect:** `"circle"` (nested unordered uses circle markers)

```bash
agent-browser eval "document.querySelectorAll('#nested-lists md li').length"
```

- **expect:** `6` (2 parents + 2 ul children + 2 ol children)

### 4. List with surrounding text — paragraphs and list coexist

```bash
agent-browser eval "document.querySelectorAll('#list-in-context md p').length"
```

- **expect:** `2` (intro + conclusion paragraphs)

```bash
agent-browser eval "document.querySelectorAll('#list-in-context md li').length"
```

- **expect:** `3`

### 5. List markers are actually visible (not clipped)

Accessibility tree includes ListMarker nodes when markers are rendered:

```bash
agent-browser snapshot -s "#basic-ul md"
```

- **expect:** `ListMarker` nodes present in the snapshot output

## Cleanup

```bash
agent-browser close
```
