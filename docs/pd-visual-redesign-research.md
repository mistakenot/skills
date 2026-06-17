---
hash: "7c55e3c0"
id: "f98ae1ff"
read_when: "planning the next batch of pd-components work, adding new engineering-specific components, or understanding the rationale behind the visual-first redesign direction"
summary: "Research diary for making planning-doc more visual and graphical: sources examined, findings, proposed new components, the derivation insight, and prioritised next steps."
title: "pd-components — Visual Redesign Research"
---

# pd-components — Visual Redesign Research

## Goal

Push planning-doc from text-heavy to scan-first: humans skim graphics, detail text collapses for machines/AIs to read. Two concrete requirements:

1. Each plan doc should be mostly graphical at first glance — diagrams, cards, visual structure.
2. Detail prose hides in collapsible sections so it doesn't bury the visuals, but remains in the HTML for agent consumption.

## Sources examined

### 1. auto-stack (mistakenot/auto-stack, `docs/tasks/*/plan.md`)

Six plan files read in full: tasks 001, 002, 010, 018, 019, 024.

These are markdown-based, agent-consumed implementation plans. Text-heavy (~85-95% prose), but have clear recurring structural patterns that could become visual components:

- **Changes table** — every plan has a `| Symbol | File | Description |` table (+/~/−). Currently markdown; could be a visual file-change card.
- **Execution sequence DAG** — ASCII art showing phase dependencies and parallelism. Example from task 024: phase 5 can run independently while phases 1-4 are serial. Currently a code block; should be a proper directed graph.
- **Links section** — every plan links to requirements, solution, context, loop-flow. Currently markdown links; could be a cross-doc nav component.
- **How to Test** — maps acceptance criteria (AC-N) to specific test files. Currently a checklist; could be a traceability matrix.
- **Seriality notes** — prose callouts like "Phases 1-4 all edit server.go — concurrent subagents leak writes (lesson from task 017). Only Phase 5 is independent." Currently buried in prose before phase definitions.
- **RESOLVED blocks** — HTML comments with `<!-- RESOLVED(P1/P2/P3): ... REVIEW: ... AUTHOR: ... -->` format. Invisible in the browser; effectively undocumented ADRs.
- **Open questions** — end section, usually "none — all resolved in review threads" or a short list of unresolved decisions.
- **Success criteria** — testable checklist with AC-N references and shell commands.

### 2. Compound Engineering (`compound-engineering-plugin`, `ce-plan/references/html-rendering.md`)

A 31KB reference document for an HTML-first planning system. Key ideas relevant to our work:

- **"Prose as authoritative over visualizations"** — diagrams are supplements, not replacements. But this is the opposite of our goal; we want visuals as the primary scan layer. Worth noting the tension.
- **Stats strips** — summary metrics (N phases, M files, K ACs) as a chip row at the top of the doc. Direct inspiration for `<pd-scope>`.
- **Collapsibles for secondary content** — exactly the "collapse prose, surface visuals" pattern we want. They call these "affordance idioms".
- **Implementation Units** — collapsible cards with a metadata strip (status, owner, estimate). Closer to our `<pd-phase>` but more self-contained.
- **Risks section pattern** — a structured risks register with likelihood/impact as attributes.
- **Inline SVG diagrams** — hand-authored, conceptual. Their rule: "prose remains complete without diagrams" — again, inverse of our goal, but useful for understanding where to draw the line.
- **Agent-consumability rules** — semantic HTML, field labels as visible text, IDs as visible text. Aligns with our existing approach.
- **Post-compose audit checklist** — useful model for a "did the agent do this right?" checklist in the skill instructions.

### 3. Existing pd-components inventory

Full component audit done against `pd-components/src/`. Key finding: the component library is richer than agents typically use. `<pd-mermaid>`, `<pd-wire>`, `<pd-stepper>` exist and work well but the skill instructions don't strongly mandate them. Most agent-generated docs use `<md>` prose everywhere.

The visual components that already exist but are underused:
- `<pd-mermaid>` — mermaid diagram renderer, bundled, no CDN fetch
- `<pd-wire>` / `<pd-note>` — wireframe placeholders
- `<pd-stepper>` / `<pd-phase>` — clickable phase walkthrough
- `<pd-files>` / `<pd-file>` — file-change tree with phase event integration

## Key insight: derivation from structured data

The most important finding: several proposed new components can be **fully derived** from structured data already present in existing component attributes, with no additional agent authoring.

### Fully derivable (zero new agent work)

**`<pd-scope>`** — a stats strip with no attributes. Reads the DOM:
- Phase count → count `<pd-phase>` elements
- File changes → tally `<pd-file change="+/~/−">` attributes
- AC count → count `<pd-ac>` elements
- Open thread count → already tracked by `<pd-tab>` badge logic

**`<pd-trace>`** — traceability matrix. `<pd-ac>` already carries `phases` and `tests` attributes:
```html
<pd-ac id="AC-3" phases="1,3" tests="rules_test.go,fold_test.go">
```
A `<pd-trace>` component scans all `<pd-ac>` elements and cross-references with `<pd-phase n>` to render an AC × Phase × Test matrix. All data already exists.

### Derivable with small additions to existing components

**`<pd-dag>`** — add `depends-on="1,2"` to `<pd-phase>`:
```html
<pd-phase n="3" title="..." files="server.go,routes.go" depends-on="1,2">
```
Explicit dependency edges come from `depends-on`. Implicit seriality edges come from shared files across phases (auto-detected from `files` attributes). The DAG renders itself. No separate "execution sequence" section needed.

**`<pd-constraint>` annotations** — with `depends-on` on `<pd-phase>`, the stepper or dag can auto-render inline "⚠ file conflict: server.go shared with Phase 4" badges. No separate component needed.

### Cascading benefit

`<pd-files>` already listens to `pd:phase-selected` events from the stepper. With `depends-on` on phases, the DAG can emit the same events — file highlighting cascades through phase selection → DAG → file tree automatically.

### Requires genuinely new data

| Component | Why not derivable |
|---|---|
| `<pd-adr>` | Decisions are judgment calls not in any existing attribute |
| `<pd-risk>` | Risk assessment is new information |
| `<pd-links>` | Cross-doc references not in the DOM (could add `related` attr to `<pd-doc>`) |
| `<pd-collapse>` | Structural wrapper, no data |

## Proposed new components

### High priority

**`<pd-scope>`** — stats strip, zero new agent work, derives from existing DOM. Place at the top of any tab for an instant scan-level summary. No attributes.

**`<pd-dag>`** — phase dependency graph. Backed by mermaid or hand-authored SVG. Reads `<pd-phase depends-on>` attributes and auto-detects file conflicts from `<pd-phase files>`. Clicking a node highlights that phase in `<pd-stepper>` and dims non-phase files in `<pd-files>`.

**`<pd-trace>`** — AC × Phase × Test matrix. Fully derived from `<pd-ac phases tests>`. No new agent authoring. Shows coverage gaps at a glance.

**`<pd-collapse>`** — collapsible prose wrapper, collapsed by default. Agents wrap `<md>` blocks in it. Humans skip; machines open. This is the single highest-impact change for human readability. Usage:
```html
<pd-collapse summary="Rationale">
  <md>...three paragraphs nobody reads...</md>
</pd-collapse>
```

### Medium priority

**`<pd-adr>`** — Architecture Decision Record. Title, status (accepted/rejected/superseded), context, decision, consequences. Collapsed by default. Replaces the invisible `<!-- RESOLVED -->` HTML comment pattern from auto-stack. Machine-readable, human-skippable.

**`<pd-links>`** — cross-doc navigation. Add `related="requirements.html,solution.html"` to `<pd-doc>`; `<pd-links>` renders a card row with status badges. Every plan has a "Links" section; this makes it a standard visual component.

**`<pd-risk>`** — risk register item with likelihood/impact chips. Grouped in `<pd-risks>`. Collapsed by default.

## Skill instruction changes needed

Independent of component work, the SKILL.md instructions need two rules added:

1. **Visual-first sections** — every `<pd-section>` must open with a diagram, stepper, wireframe, or structured component before any prose. Prose goes in `<pd-collapse>`, never bare.
2. **Diagram defaults** — architecture → flowchart, data model → ER diagram, API/sequence → sequence diagram. "Describe in prose what could be a diagram" is explicitly banned.

These changes cost nothing to implement and would move agent output immediately.

## Prioritised next steps

| Step | Type | Effort | Impact |
|---|---|---|---|
| 1. Add `<pd-collapse>` | New component | Low | Highest — unlocks the skim-vs-read pattern everywhere |
| 2. Add `depends-on` to `<pd-phase>` | Attr addition | Trivial | Unlocks DAG and constraint derivation |
| 3. Add `<pd-dag>` | New component | Medium | "One picture = entire plan structure" |
| 4. Add `<pd-scope>` | New component | Low | Zero-effort scan summary, derives from existing data |
| 5. Add `<pd-trace>` | New component | Medium | Full traceability for free from existing `<pd-ac>` data |
| 6. Update SKILL.md instructions | Instruction change | Low | Immediate improvement, no component work needed |
| 7. Add `<pd-adr>` | New component | Low | Surfaces hidden RESOLVED comments |
| 8. Add `<pd-links>` | New component | Low | Standardises cross-doc navigation |
| 9. Add `<pd-risk>` | New component | Low | Risk register pattern from CE reference |
| 10. Retrofit 019 fixture | Fixture work | Medium | Demonstrates the full before/after contrast |

## Dev environment (as of this session)

- Dev server: `make pd-dev` → local `http://localhost:9173`, tailscale `https://services.tailab2f7a.ts.net:8743`
- esbuild watch rebuilds `planning-doc-workspace/preview/pd.min.js` on `src/` changes; manual browser refresh needed (no live reload yet)
- Primary dev fixture: `/preview/sample-task.html` (rate-limiting scenario, uses full current component set)
- Reference fixture: `/preview/019-playbook-retrieval-loop.html` (complex real-world example, good "before" baseline)
- Headless check: `node planning-doc-workspace/render-check.mjs <file.html>`
