# pd-components — dev context

Web component library for planning docs. See `README.md` for the release/CDN flow. This file covers the dev environment and gotchas you won't find there.

For background on the visual redesign direction and proposed new components, see [`docs/pd-visual-redesign-research.md`](../docs/pd-visual-redesign-research.md).

## Dev server

```bash
make pd-dev          # from repo root — preferred
bash dev.sh          # from pd-components/ directly
npm run dev          # esbuild watch only, no tailscale
```

- **Local:** `http://localhost:9173`
- **Tailscale:** `https://services.tailab2f7a.ts.net:8743` (registered on start, torn down on Ctrl+C)
- Port 9173 is chosen to avoid conflicts with other services on this machine. Do not change it to a common port (3000, 8080, 8766) — those are in use.

### Why a plain Node HTTP server (not esbuild serve)

esbuild's built-in `serve()` validates the `Host` header and rejects anything that isn't `localhost`. Tailscale proxies pass the external hostname, which causes a 403. `dev.mjs` uses Node's `http` module instead — no host restrictions.

### Live reload

Not implemented. esbuild watch rebuilds `preview/pd.min.js` on disk; refresh the browser manually after a rebuild. The console shows rebuild output. Adding SSE-based live reload is a future improvement.

## Fixture workspace

Fixtures live in `../planning-doc-workspace/` (one level up from `pd-components/`). The dev server serves that directory as its root.

Key fixtures at http://localhost:9173:
- `/` — index page linking to all fixtures
- `/preview/sample-task.html` — hand-built reference doc (rate-limiting scenario); the primary fixture for component dev
- `/preview/019-playbook-retrieval-loop.html` — realistic complex example (4 phases, ~30 files, 14 threads, decision log)
- `/preview/pd.min.js` — local bundle copy served from here; rebuilt by esbuild watch into this path

When you build with `npm run build`, output goes to `dist/pd.min.js` (for release). The dev watch writes directly to `../planning-doc-workspace/preview/pd.min.js`.

## Headless render check

```bash
node planning-doc-workspace/render-check.mjs <file.html>
```

Loads the HTML in headless Playwright, waits 2.5s, counts mounted component elements, screenshots, reports JSON. Requires the dev server to be running (rewrites `pd.min.js` src to `http://localhost:9173/preview/pd.min.js`).

## Adding a new component

1. Create `src/<name>.js` — export a custom element class, register with `customElements.define`
2. Import it in `src/index.js`
3. Add styles to `src/styles.css` scoped to the element selector
4. Add a section to `llms.template.txt` documenting the element for agents
5. Add usage examples to a fixture in `../planning-doc-workspace/preview/`
6. Update `render-check.mjs` counts if you want headless validation for the new element

## Component architecture

- Custom elements, light DOM only (no shadow DOM — Tailwind can't style shadow DOM)
- `util.js` — base class `PdElement`, open-thread counter, element factory
- `store.js` — pending-comment localStorage store
- `styles.css` — ~350 line light-DOM CSS, CSS variables for theming, scoped to `pd-*` selectors
- All components bundle into a single IIFE (`dist/pd.min.js`) with beautiful-mermaid and a curated highlight.js included

## Current component inventory

| Element | File | Purpose |
|---|---|---|
| `<pd-doc>` `<pd-tab>` `<pd-section>` | `doc.js` | Document shell, tab pages, anchored sections |
| `<pd-thread>` `<pd-comment>` `<pd-decisions>` | `threads.js` | Review threads, append-only comments, auto decision log |
| `<pd-files>` `<pd-file>` | `files.js` | File-change tree (listens to phase-selected events) |
| `<pd-stepper>` `<pd-phase>` | `stepper.js` | Clickable phase walkthrough, broadcasts `pd:phase-selected` |
| `<pd-mermaid>` | `mermaid.js` | Mermaid diagram renderer (bundled, no CDN fetch) |
| `<pd-code>` `<pd-api>` `<pd-member>` | `code.js` | Syntax-highlighted code, API outlines |
| `<pd-ac>` `<pd-wire>` `<pd-note>` | `misc.js` | Acceptance criteria cards, wireframe placeholders |
| `<md>` | `md.js` | Client-side markdown (marked, loaded from CDN on demand) |
