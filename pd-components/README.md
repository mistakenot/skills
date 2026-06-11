# pd-components

Light-DOM web components for rich single-file HTML planning documents.
Consumed by the `planning-doc` skill; full agent-facing reference in
`dist/llms.txt` (generated from `llms.template.txt`).

- Vanilla custom elements, no framework. Light DOM only — the HTML source is
  the canonical data (and Tailwind can't style shadow DOM anyway).
- Bundled as a single classic IIFE script (`dist/pd.min.js`, beautiful-mermaid
  included) so docs work when opened via `file://` — module scripts are
  CORS-blocked there.
- `dist/` is committed: jsDelivr serves it straight from this repo.

## Build

```bash
npm install
npm run build   # → dist/pd.min.js + dist/llms.txt
```

## Release

Docs pin an exact git tag; `llms.txt` on `@main` tells agents the current one.

1. Bump `version` in `package.json`.
2. `npm run build` (stamps version + tag into the bundle and llms.txt).
3. Commit, then tag and push:
   `git tag pd-v<version> && git push origin main pd-v<version>`

CDN URLs (jsDelivr caches tags immutably; `@main` refreshes ~12h):

```
https://cdn.jsdelivr.net/gh/mistakenot/skills@pd-v<version>/pd-components/dist/pd.min.js
https://cdn.jsdelivr.net/gh/mistakenot/skills@main/pd-components/dist/llms.txt
```

## Try it

Open `examples/sample-task.html` in a browser (uses the local `dist/` build).
