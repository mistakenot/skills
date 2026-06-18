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
- **The planning-doc skill fetches `llms.txt` from its pinned tag, not `@main`.**
  The release script recompiles the skill so its `{{ pd-version }}` pin tracks the
  new tag, then commits that alongside the release. Consumers pick up the new
  components by reinstalling the skill (`npx skills install …`) — no `@main`
  cache to go stale, so no purge step.

Existing docs stay frozen on their pinned tag by design — bump a doc's
`@pd-v<old>` to `@pd-v<new>` in its `<script>` src only when you want it to move.

CDN URLs (all immutable tags — reproducible, never cache-stale):

```
https://cdn.jsdelivr.net/gh/mistakenot/skills@pd-v<version>/pd-components/dist/pd.min.js
https://cdn.jsdelivr.net/gh/mistakenot/skills@pd-v<version>/pd-components/dist/llms.txt
```

## Try it

Open `examples/sample-task.html` in a browser (uses the local `dist/` build).
