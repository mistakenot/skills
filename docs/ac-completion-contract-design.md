---
hash: "0fee0e5e"
id: "6fa813f1"
read_when: "designing or extending the `<pd-ac>` completion-contract mechanism, epic-001's check components, or the deferred pd-verify execution engine"
summary: "Design record for turning acceptance criteria into execution-time executable contracts — nested declarative check elements inside `<pd-ac>`, a check vocabulary, progressive-disclosure rendering, and the deferred pd-verify execution engine."
title: "Design: Executable Completion Contracts via `<pd-ac>` Checks"
---

# Design: executable completion contracts via `<pd-ac>` checks

Status: **design thoughts** — synced with `epic-001` after Codex review
(2026-06-20). **epic-001 is now descoped to HTML-first**: it builds only the
check components + progressive-disclosure rendering (this doc's "Core concept",
"Check vocabulary", and "Front-end rendering" sections). The execution engine —
everything in "Verifier: pd-verify CLI" plus producers/provenance/pytest — is
deferred to a follow-on epic; that material stays here as its design record.
Captures the design converged on in the borrow-from-oss autonomy pass.
Authoritative breakdown:
[docs/epics/epic-001-executable-completion-contracts.html](epics/epic-001-executable-completion-contracts.html).
Backlog home: idea `I010` in
[docs/research/opensource-ideas.yaml](research/opensource-ideas.yaml).

## Motivation

Today an acceptance criterion (`<pd-ac>`) is a **plan-time promise**: it lists
what must be true and backfills `phases="1,2"` / `tests="x.spec.ts"` pointers
(see `pd-components/src/misc.js`, `beta-new-plan`). Nothing reads those pointers
at execution time, and `tests="x.spec.ts"` is a pointer to *where verification
should live* — not proof it passed.

The goal (primary, per the autonomy steer) is to turn each AC into an
**execution-time executable contract**: a set of machine-runnable checks whose
status is the *deterministic output of running them against the live repo*, not
the agent's self-report. This is the keystone that collapses three loop-library
doctrine gaps into one mechanism:

- **I010 completion contract** — done only when every requirement is *proved*;
  otherwise a named terminal state. "Budget exhaustion never counts as success"
  becomes *enforceable* (the verifier's exit code decides, not the agent).
- **I011 generator ≠ approver** — the deterministic checker is the independent
  approver. The agent proposes; the script disposes. No second model session
  needed for the structural gate.
- **I012 prove-the-test** — checks can assert a *named* test exists and passed
  (not skipped/renamed/vacuously green), and negative checks assert guards bite.

The same artifact then serves three audiences from one source: authored at plan
time (`beta-new-solution`/`beta-new-plan`), executed at run time (`pd-verify`),
rendered for the human (the `pd-ac` component).

## Core concept

Nest declarative check elements inside an `<pd-ac>`:

```html
<pd-ac id="AC-1" title="Rate limit applies and is tested" phases="1,2">
  <ul><li>Given… When… Then…</li></ul>

  <pd-ac-check-test    report="junit.xml" name="returns 429 over limit"/>
  <pd-ac-check-output  run="curl -s localhost:3000/x -w '%{http_code}'" matches="429"/>
  <pd-ac-check-command run="tsc --noEmit" expect-exit="0"/>
</pd-ac>
```

An AC is **proved** only when *all* its checks pass; the document's contract is
satisfied only when *all* ACs are proved.

## Check vocabulary — starting set (5 components)

Guiding principle: **adapt to output *contracts*, not to tools.** The drift
surface is the number of distinct formats parsed, not the number of tools
supported. Corollaries: use the exit code as oracle wherever it is faithful
(build/typecheck/lint/migrate have no skip/rename failure mode → no parsing, no
drift); reserve structured parsing for named tests, and parse a *format* (JUnit
XML), not a tool.

| Component | Oracle | Drift surface |
|---|---|---|
| `pd-ac-check-command` | run cmd, assert exit code (`expect-exit`, default `0`) | none (shell) |
| `pd-ac-check-output` | run cmd, stdout matches `matches` (regex) | none (shell) |
| `pd-ac-check-test` | look up a testcase + status in a **JUnit XML** `report` by a *portable identity* (`name` + optional `suite`/`classname`/`file`); zero-or-many matches = **non-proof** | one (JUnit schema, de-facto frozen) |
| `pd-ac-check-file-exists` | `path` exists | none |
| `pd-ac-check-file-contains` | `path` matches `pattern` | none |

One `test` adapter (JUnit XML) covers vitest, jest, pytest, Playwright, and Go
(via `gotestsum --junitfile`) — five runners, one parser. The tool-specific part
(the `--reporter=junit` flag, the report path) lives in the **consumer
project's** config, never in the component, so a runner changing its CLI does not
touch the component.

### Stack coverage (TS/Vite, Postgres, web, Python, Go, Playwright, lint)

| Stack item | Check |
|---|---|
| TypeScript `tsc --noEmit`, Vite build | `command` |
| Vitest / Jest / pytest / Go / Playwright tests | `test` (project emits JUnit XML) |
| eslint / ruff / golangci-lint / `go vet` | `command` |
| HTTP endpoint behaviour | `output` (curl) |
| PostgreSQL query / migration | `output` (`psql -c`) or `command` (`migrate up`) |

### Deliberately deferred (build only when a generic check proves insufficient)

- DB-native checks (`pd-ac-check-sql query=… expect-rows=…`) — needs a
  connection/secrets adapter; `output` via `psql -c` suffices for now.
- Per-framework JSON adapters (`-vitest`, `-pytest`) — only if JUnit XML loses
  information we actually need (e.g. parametrised sub-tests).
- A second *format* adapter (TAP) — only if `node:test` is adopted heavily. Two
  format adapters is the ceiling; per-tool adapters is the trap.

## Verifier: `pd-verify` CLI

Reuse the *split* established by the plan linter (`lint-core.js` →
`src/cli/lint.js` → bundled `dist/pd-lint.mjs` → copied into the planning-doc
skill as a skill asset) — but be precise about what can be shared. **The browser
bundle cannot run shell, touch the filesystem, or read the repo**, so check
*execution* must not live in a core shared with the browser (lint-core is
portable only because it reads DOM data). Two seams (epic S2/S3):

- **Result/rollup core** (`verify-core.js`) — *runtime-neutral, pure*: check
  *results* in → AC + contract status + rollup out. No I/O. This is the only
  piece genuinely shared by the CLI and the browser component.
- **Execution adapter registry** (`cli/`) — *Node-only*: each `check-type →
  runner` performs the actual shell/filesystem/JUnit-parse work and yields
  `{status, evidence}`. Lives **only in the CLI**, never in the browser bundle.
- `dist/pd-verify.mjs` — the CLI: parses the HTML with `node-html-parser`, runs
  the execution adapters, **writes status + evidence + provenance back into the
  HTML**, emits JSON, exits non-zero unless the whole contract holds. Distributed
  exactly like `pd-lint.mjs` (epic seam S5): bundled and copied into the
  planning-doc skill; the `pd-verify` spelling is UX shorthand for
  `node "$CLAUDE_SKILL_DIR/scripts/pd-verify.mjs"`.
- the `pd-ac` browser component *renders* the written-back results — it never
  executes.

**Report producer (epic S4).** A `test` check declares a **producer** (a command,
run once per report, with timeout/failure semantics) plus the report path.
pd-verify *invokes* the producer to generate fresh XML and then reads it — it
never trusts a pre-existing report it didn't just produce. So "runs every check
against the live repo" means pd-verify *triggers* the producer; this resolves the
earlier run-vs-read ambiguity in favour of **always produce, then read**.

**Round-trip:** `pd-verify run plan.html` →
1. parse; group `test` checks by `report`; for each report, run its producer once
   (the batching win — one suite run feeds many checks from one snapshot);
2. run every check; for `test`, resolve the portable identity against the
   report's testcase map (zero-or-many matches → non-proof);
3. write `status` + a captured `evidence` snippet + **provenance** (commit SHA +
   dirty-tree fingerprint + timestamp) back onto each check element;
4. roll up to each AC and to the document; exit 0 iff all ACs proved.

**Authority & freshness (epic G7).** The authoritative verdict is a *fresh CLI
exit code*. Written-back status is **last-run evidence, not live truth**: it
carries the provenance stamp, and the rendered status shows a visible **stale**
state when the current tree no longer matches the stamp. A code change therefore
can't leave a silently-green doc, and a hand-edited attribute is detectable (its
provenance won't verify). This still makes the doc a resumable baton (**I014**) —
a resuming session re-runs the CLI to re-establish truth rather than trusting the
stored stamp.

### Status vocabulary (maps to the contract's native language)

| Check result | AC/contract status |
|---|---|
| all checks pass | **proved** (green) |
| any check fails | **contradicted** (red) |
| present but skipped/todo | **weak** (amber) |
| named test/file absent | **missing** (amber) |
| not yet run | **pending** (grey) |

## Front-end rendering: progressive disclosure

The check elements add a lot of detail to a card. Rendering must keep the
**scan layer clean** while keeping **all detail in the DOM** (agents read the raw
HTML; `pd-verify` parses it). So disclosure is a *visual* layer only — it never
removes nodes.

**Collapsed (default).** An AC renders top-level only: id chip, title, the
existing phase/test chips, and a new **status rollup** — a coloured pill
(proved / contradicted / weak / pending) plus an `n/m checks passing` count. The
Given/When/Then body and the nested checks are hidden behind the disclosure.

**Expanded (on click).** Reveals:
- the Given/When/Then body, and
- the check list — one row per `pd-ac-check-*`: a status glyph (✓ / ✗ / – / ⏳),
  a human label derived generically from `tagName` + key attributes
  (e.g. `test · returns 429 over limit`, `command · tsc --noEmit`), and, for
  failures, the captured `evidence`.

**Second level.** A failing check's `evidence` (stdout/exit tail) sits in a
nested `pd-collapse` so long output stays out of the way until clicked —
i.e. two-level progressive disclosure (AC → checks → evidence).

### Implementation notes

- Use native `<details>/<summary>` (as `pd-collapse` already does): the summary
  is the scan layer, the body **stays in the DOM** while collapsed (light DOM,
  consistent with the repo's "body stays in the DOM for agents" rule). Do **not**
  conditionally render checks out — only hide them.
- **Render generically.** The check-row renderer reads `tagName` + attributes
  from a small registry (`{ tag → {label, attrsToShow} }`); adding a new check
  type needs a one-line registry entry, not new render code. (Same anti-drift
  spirit as the vocabulary itself.)
- **Resolve the existing click conflict.** `pd-ac` currently uses a card click
  to broadcast `pd:phase-selected` (reverse traceability highlight). Proposal:
  the header/disclosure toggle becomes the primary click (expand/collapse); move
  the phase-highlight trigger onto the phase chips specifically. Keeps both
  behaviours, removes ambiguity. (Open question — confirm during build.)
- **Auto-open failures.** Default collapsed, but auto-expand an AC whose status
  is `contradicted`, so problems surface to the human's eye without a click.
  Honour an explicit `<pd-ac open>` to pin a card open.
- Status colours via existing CSS variables; the rollup pill reuses the
  `pd-chip` styling family.
- **Render provenance, don't validate it.** The browser has no git access, so it
  cannot check the stored verdict against the live tree. It *displays* the
  provenance stamp ("verified at `abc123`, 2 files dirty, 3h ago") and renders a
  muted **stale**/last-run treatment so green never reads as live truth. Actual
  staleness enforcement happens on the next CLI run (epic G7).

## Authoring rule (the load-bearing guardrail)

A contract of `file-exists` checks is theatre — it proves files exist, not that
the feature works. Therefore: **every AC must carry at least one *behavioural*
check** (`test` / `output` / a negative `command`), not only existence/contains
checks; and **prefer a `test` (JUnit) check over a bare `command` when a named
test exists**, because the exit code alone misses skipped/renamed/vacuous-green.
`beta-new-solution`/`beta-new-plan` should enforce this when authoring ACs; a
`pd-verify` lint mode can flag ACs that have only structural checks.

## Resolved by the epic-001 Codex review

- **Run vs read** → **always produce, then read** (report producer, seam S4).
- **Report freshness** → producer runs once per report per verify run +
  provenance stamp; only a fresh CLI exit is authoritative (G7).
- **Shared-core feasibility** → split into a runtime-neutral result core +
  Node-only execution adapters (G5/S2/S3); the browser never executes.
- **CLI distribution** → bundle + copy into the skill, à la `pd-lint.mjs` (S5).
- **Test identity** → portable identity with ambiguous = non-proof (S1/T1).

## Still open (carried to task planning)

- **Scope boundary.** This epic is foundation-only; wiring `pd-verify` into an
  autonomous executor as a completion gate is a deliberate follow-on epic. The
  beta-HTML vs markdown-workflow bridge (`execute-task`/`commit-task`/
  `review-task` don't yet support beta HTML) is the real lift there.
- **Evidence storage shape.** Attribute (`evidence="…"`, simple round-trip) vs a
  child node (handles multi-line stdout). Leaning child element for failures.
- **Producer declaration site.** Per-check `produce=` (repetitive) vs a
  doc-level report declaration referenced by `report=` id (DRY) vs consumer
  project config. Affects the S1 schema.
- **Parametrised tests.** "Ambiguous = non-proof" is safe but blocks suites where
  one logical assertion legitimately emits many testcases — may need a match-mode
  later.
- **Click reconciliation.** `pd-ac` currently uses a card click for phase
  highlight; proposal is header-click = expand, phase-chips = highlight.
- **Command-exec safety (G6).** How much pd-verify sandboxes doc-authored
  commands vs relying on operator trust.

## Related backlog ideas

`I010` (this), `I011` (independent gate — subsumed by the deterministic checker),
`I012` (prove-the-test — the negative/named-test checks), `I014` (resumable baton
— the recomputed-from-repo doc), `I001` (drift-check — generalised: status is
self-auditing because it is recomputed, never stored as a claim).
