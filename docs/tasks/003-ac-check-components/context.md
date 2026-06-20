# Context: Task 003 — ac-check-components

Codebase grounding for adding the five `pd-ac-check-*` components + their frozen
schema (seam S1) to the pd-components library. Companion to
[plan.html](plan.html). Scope: HTML-first, inert, purely additive — no execution
engine.

## Key Files

### Component patterns to mirror
- `pd-components/src/util.js:43-56` — base class + registration. `PdElement`
  defers to `connectedCallback → ready() → init()` (guards double-init with
  `_pdInit`); `define(name, cls)` wraps `customElements.define` (no-op if already
  defined). `el(tag, attrs, children)` is the DOM factory.
- `pd-components/src/misc.js:62` — `class PdNote extends PdElement {}` — **the
  inert pattern**: empty body, no `init()`, adds no DOM, no visual treatment.
  `PdFile` (`src/files.js:13`) is the same. These are data-carriers parents read.
- `pd-components/src/misc.js:17-50` — `PdAc.init()`: reads `id/title/phases/tests`,
  prepends a `.pd-ac-head`, broadcasts/listens for `pd:phase-selected`. **It never
  queries for child elements**, so nesting new children leaves it untouched.
- `pd-components/src/misc.js:76-79` — registration block: one `define('pd-ac', …)`
  per tag at file end.
- `pd-components/src/index.js:6-25` — one `import './<name>.js';` per component
  file; `build.mjs` (entry = `src/index.js`, IIFE) pulls everything transitively.
  Adding a file = one import line.

### The pure-core precedent (the model for freezing S1)
- `pd-components/src/lint-core.js` — pure, DOM-agnostic, depends only on
  `querySelector(All)` + `getAttribute`; consumed by both `src/lint.js` (browser)
  and `src/cli/lint.js` (Node) so they **cannot drift**. This is exactly the
  shape a frozen, runtime-neutral schema/parse module should take.
- `pd-components/CLAUDE.md:67-83` — documents that split and the rule "when
  changing a check, edit lint-core.js only."

### Styling
- `pd-components/src/styles.css` — light-DOM CSS scoped to `pd-*` selectors, CSS
  vars for theming. Inert components get **no rule** (zero box) or an explicit
  `display:none` to guarantee no layout effect while staying in the DOM.

### Docs / authoring surface
- `pd-components/llms.template.txt:380-392` — per-component doc section: heading
  `### <tag attrs…>`, one-line description, attribute list, full HTML example.
- `pd-components/examples/sample-task-v2.html:27-40` — current `<pd-ac>` authored
  shape (`id/title/phases/tests` + `<md>` Given/When/Then body); examples
  reference `../dist/pd.min.js` (needs `npm run build`).

### Test conventions
- `pd-components/tests/lint-cli.test.mjs:1-66` — Node test harness: `execFileSync`,
  parse JSON, assert exit code + issue codes. Model for a **Node unit test of a
  pure module** (imports work only if the module is DOM-free).
- `pd-components/tests/fixtures/*.html` + `tests/playbooks/*.md` — browser test
  pairs (`agent-browser eval` asserts on the live DOM); minimal one-behaviour
  fixtures loading `../../dist/pd.min.js`. Model for asserting custom-element
  registration + inertness in a real browser.
- `pd-components/CLAUDE.md:58-64` — the canonical "adding a new component"
  checklist (src file → import → styles → llms section → example → render-check).

### Distribution
- `pd-components/README.md` — release via `make release VERSION=x.y.z`: bumps
  `package.json`, builds, tags `pd-vX.Y.Z`, pushes, purges CDN. Docs pin an
  immutable tag (`…@pd-v0.8.0/…/pd.min.js`). **Publishing these components needs a
  release bump**; this task's own `plan.html` pins `pd-v0.8.0` (predates them).
- `src/compile.py:20-32,392-398` — `asset(src,dst)` copies pd-components build
  output (e.g. `dist/pd-lint.mjs`) into skills. **No asset change needed here** —
  new tags ship inside `pd.min.js`, not as a separate CLI bundle (that's T2).

## Patterns
- **Light DOM only, no shadow DOM** (Tailwind can't style shadow DOM).
- **Inert = empty class** (`extends PdElement {}`) — no `init()` side effects, no
  DOM, no visual treatment, no events. Schema/parse logic lives in a separate pure
  module, not in element rendering.
- **One pure core, thin adapters** (lint-core) prevents browser/CLI drift — the
  template for a frozen, testable S1.
- **Render generically from a registry** (design doc §"Implementation notes"): a
  `tag → schema` table means T4's renderer and T2's CLI add a row, not new code.

## Related Tasks
- Epic 001 (`docs/epics/epic-001-executable-completion-contracts.html`): this is
  **T1**, the schema-freeze foundation. **T4** (rendering + rollup) and the
  deferred **T2/T3/T5** (CLI, JUnit adapter, authoring+lint) all key off the S1
  schema this task freezes.
- Design record: `docs/ac-completion-contract-design.md` — check vocabulary
  table (§66-82), status vocabulary (§157-166), progressive disclosure (§167-215,
  all T4).

## History grounding (CB3, 2026-06-20)
- **The pure-core precedent is fresh.** `lint-core.js` (+ the browser/CLI split
  this task mirrors) landed in the *immediately preceding* release **pd-v0.8.0**
  (`9db99a3 Release pd-components pd-v0.8.0: CLI plan linter`). The
  `lint-core.js` → `lint.js`/`cli/lint.js` shape is current, not legacy — copying
  it for `ac-check-core.js` → `ac-check.js` is the right move.
- **No prior art to reconcile.** `git log --all` shows zero `ac-check`,
  `pd-verify`, or completion-contract commits — this is greenfield; no existing
  element, schema, or test to extend or avoid colliding with.
- **Path drift check: all clear.** Every file the Solution tab names exists at
  the cited path (`src/util.js`, `src/misc.js`, `src/index.js`, `src/lint-core.js`,
  `src/styles.css`, `tests/lint-cli.test.mjs`, `tests/run.sh`, `examples/`,
  `llms.template.txt`, `CLAUDE.md`). New files (`src/ac-check-core.js`,
  `src/ac-check.js`, the test pair, `examples/ac-checks.html`) do **not** yet
  exist — all `add`s are genuinely additive.
- **Build regenerates the agent doc.** `build.mjs:44-48` reads
  `llms.template.txt` and writes the version-stamped `dist/llms.txt`, so the
  llms-doc edit (Phase 4) is realised by `npm run build`, not a separate step.
- **Release cadence.** Every feature release is a discrete `Release pd-components
  pd-vX.Y.Z` commit (current `pd-v0.8.0`). Publishing T1 follows the same
  `make release` ritual — the ship phase, not part of the asserted ACs.

## Impact analysis (proposed changes)
- `src/ac-check-core.js` (add) — pure, DOM-free; imported by `ac-check.js` and
  (later) T2/T4. No runtime impact on existing bundle beyond +1 module.
- `src/ac-check.js` (add) — registers 5 new tags via `define()` (no-op if already
  defined, per `util.js`); cannot collide with existing tags (greenfield names).
- `src/index.js` (edit) — one `import './ac-check.js';`. The IIFE bundle grows;
  `mirror.js`/`lint.js` still import last, so ordering is safe (add the import
  *before* the `mirror.js`/`lint.js` lines, alongside `misc.js`).
- `src/styles.css` (edit) — one `display:none` rule on the five new tags only;
  cannot affect existing selectors (G1 / additive).
- `llms.template.txt` (edit) — additive section; `npm run build` re-stamps
  `dist/llms.txt`. **Concern folded into Verification:** the build must still
  succeed and `dist/llms.txt` must contain the new family (covered by Phase 4
  verify).
- `CLAUDE.md` (edit) — inventory table row + a one-line "edit ac-check-core.js
  only" note; docs-only, no runtime effect.
- `examples/ac-checks.html`, `tests/fixtures/ac-checks.html`,
  `tests/playbooks/ac-checks.md`, `tests/ac-check-core.test.mjs` (add) — new test
  surface only; the existing fixtures/playbooks and `lint-cli.test.mjs` are
  untouched and must stay green (AC-5 / G1 regression gate).
- **No `compile.py` / skill-asset change** — the new tags ship inside
  `pd.min.js`, not as a separate CLI bundle (that is T2). Confirmed against
  `src/compile.py` asset list.
