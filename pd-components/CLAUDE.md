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

## Fixtures

**Committed examples** live in `examples/` and reference `../dist/pd.min.js` directly — no dev server needed, but you must `npm run build` first. `examples/sample-task.html` is the primary reference doc (rate-limiting scenario, full component set).

**Dev workspace** (`../planning-doc-workspace/`, one level up) is gitignored and won't exist in a fresh clone or worktree. The dev server serves this directory and esbuild watch writes the bundle to `../planning-doc-workspace/preview/pd.min.js`. Bootstrap it by copying from `examples/` if you need a live-reload dev environment.

When you build with `npm run build`, output goes to `dist/pd.min.js` (for release).

## Headless render check

```bash
node planning-doc-workspace/render-check.mjs <file.html>
```

Loads the HTML in headless Playwright, waits 2.5s, counts mounted component elements, screenshots, reports JSON. Requires the dev workspace to exist and the dev server to be running (rewrites `pd.min.js` src to `http://localhost:9173/preview/pd.min.js`). For checking committed examples, use the browser tests in `tests/` instead.

## Tests

Browser-based regression tests live in `tests/`. Each test is a pair:
- **`tests/fixtures/*.html`** — minimal HTML page exercising one component or behaviour
- **`tests/playbooks/*.md`** — step-by-step `agent-browser` commands with expected outcomes

Current tests: `md-dedent`, `md-script-wrapper`, `md-list-rendering`, `comment-workflow`, `sidenav`.

Run them via the `/pd-test` skill (invokes `tests/SKILL.md`) or manually with `make pd-test`. Fixtures load `../../dist/pd.min.js` via relative path — no dev server needed, but you must `npm run build` first.

When adding a new component, add a fixture + playbook pair. The fixture should be minimal (one component, one scenario). The playbook verifies rendered output and interactive behaviour using `agent-browser eval` to inspect the DOM.

`tests/sidenav.test.mjs` is a standalone Playwright test for the side navigation — run it directly with `node tests/sidenav.test.mjs`.

## Adding a new component

1. Create `src/<name>.js` — export a custom element class, register with `customElements.define`
2. Import it in `src/index.js`
3. Add styles to `src/styles.css` scoped to the element selector
4. Add a section to `llms.template.txt` documenting the element for agents
5. Add a committed example to `examples/` (reference `../dist/pd.min.js`; run `npm run build` to get the bundle)
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
| `<pd-unit>` `<pd-dep>` `<pd-fn>` `<pd-prop>` | `unit.js` | TS code-unit outline: identity, constructor deps, public surface |
| `<pd-ac>` `<pd-wire>` `<pd-note>` | `misc.js` | Acceptance criteria cards, wireframe placeholders |
| `<md>` | `md.js` | Client-side markdown (marked, loaded from CDN on demand) |
