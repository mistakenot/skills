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

```bash
make pd-test                 # regression-test first
make release VERSION=0.5.0   # bump, build, commit, tag, push, purge, verify
```

`make release` (→ `release.sh`) runs the whole flow: bumps `package.json`,
builds (stamping the version + tag into the bundle and `llms.txt`), commits,
tags `pd-v<version>`, pushes `main` + tag, purges the `@main` CDN cache, and
verifies the tag serves the new bundle. It refuses to reuse an existing tag or
run on a dirty / non-`main` tree.

**Two gotchas it exists to prevent:**
- **Tags are immutable on jsDelivr.** Rebuilding under the same version does
  nothing for clients — you must *bump the version*. (The script enforces this.)
- **New docs inherit their tag from `llms.txt` on the `@main` path, which caches
  ~12h.** Without a purge, freshly generated docs keep pinning the *old* tag for
  up to ~12h. (The script purges it, so new docs pin the new tag immediately.)

Existing docs stay frozen on their pinned tag by design — bump a doc's
`@pd-v<old>` to `@pd-v<new>` in its `<script>` src only when you want it to move.

CDN URLs (tags immutable; `@main` refreshes ~12h or on purge):

```
https://cdn.jsdelivr.net/gh/mistakenot/skills@pd-v<version>/pd-components/dist/pd.min.js
https://cdn.jsdelivr.net/gh/mistakenot/skills@main/pd-components/dist/llms.txt
```

## Try it

Open `examples/sample-task.html` in a browser (uses the local `dist/` build).
