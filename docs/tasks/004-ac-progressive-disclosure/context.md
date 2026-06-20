# Context: Task 004 (ac-progressive-disclosure)

Codebase grounding for epic-001 **T4 — progressive-disclosure rendering + a pure
rollup** on the `<pd-ac>` component. See
[plan.html](./plan.html) for requirements/verification/solution.

## Key Files

- `pd-components/src/misc.js:17-50` — `PdAc.init()`. Today it prepends a
  `.pd-ac-head` (`.pd-chip-id` id, `<strong>` title, `.pd-ac-chips` with `phase N`
  + test chips), adds `.pd-ac-link` and a **whole-card** click that dispatches
  `pd:phase-selected`, and listens for that event to toggle `.pd-ac-hl`. **This is
  the element T4 extends.** It never queries its children today.
- `pd-components/src/misc.js:64-74` — `PdCollapse`: the disclosure primitive to
  reuse. Wraps children in `<details class="pd-collapse" [open]>` →
  `<summary class="pd-collapse-summary">` + `.pd-collapse-body`; **relocates**
  child nodes into the body (nodes stay in the DOM). T4's evidence level reuses
  this; the AC-level disclosure mirrors its `<details>/<summary>` shape.
- `pd-components/src/util.js:42-52` — `PdElement`: `init()` is deferred to
  `DOMContentLoaded` via `ready()` with a `this._pdInit` guard, so **children
  exist when `init()` runs**. `el(tag, attrs, children)` (`:28-40`) is the DOM
  factory (supports `class`, `on*` listeners, attrs); `define(name, cls)`
  (`:54-56`) registers idempotently; `filesForPhases(nums)` (`:66-75`) maps phase
  numbers → files for the `pd:phase-selected` detail.
- `pd-components/src/styles.css:5-20` — status colour CSS variables already exist:
  `--pd-ok`/`--pd-ok-bg` (green→**proved**), `--pd-bad`/`--pd-bad-bg`
  (red→**contradicted**), `--pd-warn`/`--pd-warn-bg` (amber→**weak/missing**),
  `--pd-neutral-bg`/`--pd-border` (grey→**pending**). **No new colour vars needed.**
- `pd-components/src/styles.css:198-204` — `.pd-chip` / `.pd-chip-id` /
  `.pd-chip-test`: the pill styling family the rollup pill reuses.
- `pd-components/src/styles.css:471-482` — `pd-ac`, `.pd-ac-head`, `.pd-ac-chips`
  (`margin-left:auto`), `.pd-ac-link` (cursor), `.pd-ac-hl` (accent highlight).
- `pd-components/src/styles.css:610-629` — collapse styling: custom chevron via
  `.pd-collapse > summary::before { content:'▸' }` rotating on `[open]`, marker
  hidden. T4's AC summary reuses this pattern.
- `pd-components/src/index.js:1-25` — import order; `misc.js` is imported mid-list;
  `mirror.js` then `lint.js` **must stay last**. A new `verify-core.js` is a pure
  module imported by `misc.js` (not registered as an element), so it needs no
  index entry of its own.
- `pd-components/build.mjs:8-48` — `npm run build` (esbuild, IIFE, CSS inlined) is
  the **only** syntax gate (no tsc/eslint). It also stamps
  `llms.template.txt`→`dist/llms.txt` (`{{VERSION}}`/`{{TAG}}`/`{{CDN_BASE}}`).
- `pd-components/tests/run.sh` — hand-wired browser suite (no auto-discovery):
  builds, then per playbook `agent-browser open file://… → wait → eval` + `assert`.
  A new playbook needs its own `── name ──` block.
- `pd-components/tests/lint-cli.test.mjs:1-30` — the Node unit-test pattern to
  model `verify-core.test.mjs` on: `node:assert` (strict) + a tiny `check()`
  wrapper, run directly via `node tests/…`.
- `pd-components/tests/fixtures/comment-workflow.html` +
  `pd-components/tests/playbooks/comment-workflow.md` — representative fixture +
  playbook pair to model the new browser test on.
- `pd-components/llms.template.txt:380-392` — the existing `### <pd-ac …>` section
  to expand with the rollup/disclosure behaviour.
- `pd-components/examples/sample-task.html:1-30` — example convention (Tailwind
  optional, `../dist/pd.min.js`, `<pd-ac phases tests>` already used).
- `planning-doc-workspace/render-check.mjs:27-38` — counts mounted elements incl.
  `pd-ac .pd-ac-head`; optionally add a rollup-pill count.

## Patterns

- **One pure core, thin adapters.** The lint feature is the template:
  `src/lint-core.js` (pure, DOM-agnostic) consumed by `src/lint.js` (browser) and
  `src/cli/lint.js` (Node). T4 mirrors this for the rollup: a runtime-neutral
  `verify-core.js` (epic seam **S2**) that `misc.js` consumes now and the deferred
  `pd-verify` CLI consumes later — so the rollup math can never diverge (epic
  **G5**). See `pd-components/CLAUDE.md` "Plan linter (browser + CLI, one core)".
- **Light DOM only, no shadow DOM** (Tailwind can't style shadow DOM; agents read
  the raw HTML). Disclosure must **hide, never remove** nodes.
- **Custom elements** extend `PdElement`, build DOM with `el()`, register with
  `define()`; status colours come from the existing CSS variables.
- **Tests are pairs**: a minimal `fixtures/*.html` + a `playbooks/*.md` of
  `agent-browser` steps, hand-wired into `tests/run.sh`; pure cores get a Node
  `*.test.mjs` run directly.

## Related Tasks

- **Task 003 / epic T1 (ac-check-components)** — the hard dependency
  (`depends-on=T1`). It delivers the five inert `pd-ac-check-*` elements, the
  frozen **S1** schema (`AC_CHECK_SCHEMA`) and the pure `parseAcCheck(node)` in
  `src/ac-check-core.js`, plus the reserved `status` / evidence-child /
  provenance (`commit`/`dirty`/`at`) write-back shape. **These files do not exist
  yet** (T1 is planned, not implemented) — T4 is built on the merged T1. T4 reads
  each check via `parseAcCheck(child)` and rolls the `status` values up; it adds
  no check types and does not touch the S1 schema.
- **Epic-001** ([docs/epics/epic-001-executable-completion-contracts.html]) — T4
  honors **G1** (purely additive) and **G5** (shared rollup core; browser renders,
  never executes). G2/G6/G7 (truthful verdict, exec safety, freshness) bind the
  deferred CLI follow-on, not this task; T4 only *renders* provenance, never
  validates it.

## History (git)

- **Lint-core split = the model for `verify-core.js`.** Commit `9db99a3`
  ("Release pd-components pd-v0.8.0: CLI plan linter") introduced
  `src/lint-core.js` (pure) + `src/cli/lint.js` (CLI adapter) +
  `dist/pd-lint.mjs` + `tests/lint-cli.test.mjs` — the exact "one pure core, two
  adapters that never re-implement the rules" shape T4 mirrors for the rollup.
- **`misc.js` is low-churn** (2 commits, `<pd-ac>` stable) — low rebase risk.
  `tests/run.sh` and `llms.template.txt` are moderately active but pattern-stable.
- **T1 (003) implementation has NOT started.** Its planning docs are committed
  (`791684d`), but `src/ac-check-core.js` / `src/ac-check.js` do not exist on any
  branch. T4 (`depends-on=T1`) must be executed on a branch cut **after** T1
  merges, or its `parseAcCheck` import won't resolve at build.
- **Conventions.** Commits are small/focused, prefixed `pd-components: …` (or
  `feat(pd-components): …`). Task work uses `task/NNN-name` branches off protected
  `main`; T4 → `task/004-ac-progressive-disclosure`. Publishing is a post-merge
  `make release VERSION=x.y.z` step (not an execution phase).
