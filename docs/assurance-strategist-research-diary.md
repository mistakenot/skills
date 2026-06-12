---
hash: "d241a6a0"
id: "d56138fd"
read_when: "designing or extending the assurance-strategist skill, or looking up the technique catalog and composition frames behind it"
summary: "Research diary for the assurance-strategist skill: breadth-first catalog of testing/assurance techniques, composition frames for combining them, and open design questions."
title: "Assurance Strategist — Research Diary"
---

# Assurance Strategist — Research Diary

Working notes for the design of the `assurance-strategist` skill. Append new entries at the bottom; don't rewrite history — this is a diary, not a spec.

## 2026-06-12 — Initial brief and breadth-first technique fan-out

### The brief

New skill: `assurance-strategist`. A highly expert role that designs end-to-end assurance / conformance / testing workflows for software products. Domain context is mostly web apps, but should also cover CLI apps and dev tools.

Proposed architecture (from initial discussion):

- `SKILL.md` = high-level overview + a directory (index) of individual techniques + guidance on how they fit together.
- One dedicated reference file per technique with the detailed breakdown of how it should work.
- Language agnostic, or code examples in languages simple enough to mimic elsewhere.

Goal: go far beyond the usual testing pyramid (unit / integration / browser-driven). Pull in techniques from other fields — conformance testing, property-based testing, model-based testing, formal methods (Quint / TLA+), statecharts — so the LLM has a rich palette it can pick from and assemble, pushing automated agent-driven app testing to a new level.

Seed examples from the brief:

- Component library dev page in the app: each front-end component gets its own test page where you can step through transformations; screen-record these and verify offline.
- Screenshot taking and appending for PRs, including getting agents to look at the screenshots.
- Quint / TLA+ / etc. for verification of algorithm-heavy workflows.

### Technique catalog (breadth-first fan-out)

#### 1. Code-level verification

- **Property-based testing** (Hypothesis, fast-check) — invariants, round-trips, idempotence; shrinking gives minimal counterexamples, which agents are very good at acting on.
- **Metamorphic testing** — for when there's *no oracle*: you can't say what `search("shoes")` should return, but you can assert `search("shoes", filter=red) ⊆ search("shoes")`. Deserves its own reference file; it's the answer to half of "how do I test this fuzzy thing."
- **Mutation testing** (Stryker, mutmut) — tests the tests. Especially powerful in agent loops: "write tests until these mutants die" is a concrete, checkable objective, unlike coverage %.
- **Coverage-guided fuzzing** (libFuzzer, AFL, Jazzer) — for parsers, serializers, anything taking untrusted bytes.
- **Snapshot / golden-master / approval testing** — exact-output oracles; also the characterization technique for legacy code before refactoring.
- **Differential testing** — run two implementations (optimized vs naive reference, old vs new version, port vs original) on the same generated inputs and diff. Pairs beautifully with PBT generators.
- **Type-driven assurance** — making illegal states unrepresentable, branded types, exhaustiveness checks. Cheapest layer there is; agents under-use it.
- **Design by contract** — runtime pre/postconditions and invariant assertions that stay on in test/staging; turns every E2E run into thousands of micro-tests.

#### 2. Specification & formal methods

- **Formal specs + model checking** (TLA+, Quint, Alloy, FizzBee) — for protocols, sync engines, state machines with concurrency. Quint especially, since agents can write/run it easily.
- **Trace validation** — the underrated bridge: log structured events from the *real implementation*, replay them against the formal spec to check conformance. This is what makes a TLA+/Quint spec pay rent continuously instead of rotting.
- **Statecharts** (XState or hand-rolled) — model UI/workflow state explicitly, then derive tests from the model (model-based testing: generate all paths through the chart and execute each against the real UI).
- **SMT-solver verification of business rules** — encode pricing tiers / eligibility rules in Z3, prove no overlaps or gaps in the conditions. Niche but spectacular for rule-heavy domains.
- **Combinatorial testing** (pairwise/n-wise, PICT) — for config × flag × browser × role matrices too big to enumerate.
- **Decision-table testing** — business rules as explicit tables; the table is both spec and test input.

#### 3. Conformance & contract

- **Schema-first contract testing** — OpenAPI / JSON Schema / protobuf as the single source of truth; validate server responses against it, generate client mocks from it.
- **Schema-driven API fuzzing** (Schemathesis) — property-based testing derived automatically from the OpenAPI spec. Very high value-to-effort.
- **Consumer-driven contracts** (Pact) — when front-end and back-end evolve independently.
- **Executable conformance suites** — a versioned suite any implementation must pass (the Web Platform Tests model). Relevant for plugin systems, SDKs, multiple language clients.
- **External-spec conformance** — WCAG audits, OAuth/OIDC conformance suites, HTML validation: free, rigorous suites someone else maintains.
- **Analytics/event contract tests** — tracking events validated against a tracking-plan schema; one of the most commonly broken, least tested surfaces in web apps.
- **Migration round-trip tests** — up/down migrations against production-shaped snapshots; cross-version data compatibility.

#### 4. UI & front-end

- **Component lab pages** (seed example) — every component gets a dev page enumerating its states (loading/error/empty/overflow included), steppable, recordable. The lab page becomes the substrate for several other techniques below.
- **Visual regression diffing** (Playwright snapshots, Chromatic) — over the component lab, not just full pages, so diffs are small and attributable.
- **ARIA / accessibility-tree snapshots** — Playwright's aria snapshots are *text*, so they're stable across pixel noise and directly agent-readable. Often a better default assertion than screenshots.
- **Screenshot tours on PRs** (seed example) — generalize to **evidence bundles**: every PR attaches screenshots, recordings, traces; agents both produce them and vision-review them.
- **Agent-driven exploratory testing** — a computer-use agent given a charter ("try to corrupt cart state via back-button") and a session budget, filing structured findings. The modern incarnation of exploratory testing.
- **UI monkey/fuzz testing** (gremlins.js-style random event injection) plus deliberate race-condition tests (double-submit, rapid navigation).
- **Automated a11y scanning** (axe-core) + keyboard-only navigation scripts + contrast checks.
- **Network/condition simulation** — offline, slow-3G, mid-request navigation; browsers make this scriptable now.
- **Pseudo-localization** — catches hardcoded strings and layout breakage in one cheap pass.

#### 5. Concurrency, distributed, async

- **Deterministic simulation testing** (FoundationDB/Antithesis style; turmoil, madsim) — simulated clock/network/disk, seed-replayable failures. The single most powerful technique for job queues, sync, webhooks.
- **Fault injection** (toxiproxy) — latency, partitions, connection resets at the network layer.
- **Linearizability checking** (Porcupine, Elle) — for anything claiming consistency guarantees.
- **Idempotency & retry tests** — every handler/job invoked twice with the same input; arguably the highest-ROI distributed-systems test for ordinary web apps.
- **Clock fuzzing** — fake timers, DST transitions, leap days, timezone matrix.

#### 6. Static & architectural

- **Architecture conformance tests** (dependency-cruiser, ArchUnit) — "UI never imports persistence" as an executable rule, not a review comment.
- **Custom lint/semgrep rules as regression memory** — every recurring bug class gets codified into a rule; this is how review feedback compounds instead of repeating.
- **Security static pass** — SAST, secret scanning, dependency audit; plus an **authz matrix test**: roles × endpoints × expected outcome, table-driven, exhaustive.

#### 7. Non-functional

- **Performance regression budgets** — benchmark suites (hyperfine, criterion) and Lighthouse/bundle-size budgets enforced in CI with thresholds, not vibes.
- **Load testing with SLO assertions** (k6) — pass/fail tied to latency percentiles.
- **DAST baseline** (ZAP) against preview environments.

#### 8. Runtime / production assurance

- **Synthetic monitoring** — the smoke suite running continuously against prod.
- **Shadow / scientist-pattern verification** — run old and new code paths in parallel on real traffic, diff results before cutover; differential testing in production.
- **Canary + automated rollback gates**, **runtime invariant monitors** (the design-by-contract assertions, kept on, feeding telemetry), **feature-flag matrix testing**.

#### 9. CLI & dev tools

- **Golden-file CLI tests** (trycmd, insta) — args + stdin → stdout/stderr/exit-code snapshots.
- **PTY/TUI harnesses** — tmux-driven scripts, asciinema recordings reviewed offline by an agent (the CLI analogue of the screen-recording technique).
- **Docs-as-tests** — every README example executed in CI; doctests. Conformance between docs and behavior.
- **Dogfood charters** — an agent given the tool and a realistic task, graded on completion; catches the "technically works, practically unusable" class.
- **Cross-platform/version matrix** with pairwise reduction.

#### 10. Agent-era meta-techniques (the differentiator)

- **Agent-legible failure artifacts** — structured failure reports, Playwright traces, seeds for replay; designing test *output* so the fixing agent needs zero human interpretation.
- **LLM-as-judge oracles** — for screenshots, prose, error-message quality; with rubrics, not vibes.
- **Self-verifying PR loops** — the PR isn't done until the evidence bundle exists and an agent has reviewed it.
- **Test-gap analysis loops** — mutation score + coverage diffs as the agent's objective function for "where do I write the next test."

### How techniques compose (the core of SKILL.md)

Don't present the catalog as a flat menu. Four organizing frames, which should become the core sections of SKILL.md:

**1. Select by oracle type.** The first question is never "which tool" but "where does truth come from?"

- Exact oracle → example/golden tests
- Relational oracle → properties/metamorphic
- Reference implementation → differential
- Spec → conformance / model-checking / trace validation
- Human judgment → LLM-judge with rubric

This single decision tree routes most technique choices.

**2. Layer by feedback latency.** Types/lint (ms) → unit/PBT (sec) → component/contract (sec–min) → E2E/visual/simulation (min) → canary/synthetics (prod). Rule: push every bug class to the *cheapest layer that can catch it*. Mutation testing is the audit that tells you whether the cheap layers are actually doing their job.

**3. One model, many derivatives.** The highest-leverage pattern: write the model *once* and derive everything.

- Statechart → implementation skeleton + MBT paths + component-lab states
- OpenAPI schema → validation + mocks + Schemathesis fuzzing + docs
- Quint spec → model checking + trace validation against prod logs

This is what prevents spec drift, and it's what agents are uniquely good at maintaining.

**4. Prescribe bundles by subsystem archetype.** Classify each part of the product, prescribe a stack:

| Archetype | Bundle |
|---|---|
| Algorithmic core (pricing, sync, CRDT) | PBT + differential vs naive reference + Quint/TLA+ with trace validation + mutation testing |
| Stateful UI workflow (wizard, editor) | Statechart + MBT + component lab + ARIA snapshots + visual diff |
| CRUD surface | Schema-first contracts + Schemathesis + authz matrix + thin E2E happy paths + migration round-trips |
| Async/distributed (jobs, webhooks) | Deterministic simulation + idempotency tests + fault injection |
| CLI/dev tool | Golden files + PTY harness + docs-as-tests + dogfood charter |
| Design system | Component lab + interaction tests + visual diff + a11y + pseudo-locale |

A final **coverage-matrix audit** technique (bug taxonomy × technique grid, find the empty cells) gives the skill a self-check step.

### Implications for skill architecture

- The proposed shape (overview SKILL.md + per-technique references) fits.
- The composition frames belong in SKILL.md itself — they're the routing logic.
- Some "techniques" are really *cross-cutting patterns* (evidence bundles, one-model-many-derivatives, agent-legible artifacts) and deserve their own reference files, distinct from technique files.
- Rough count: ~30–35 technique files if every bullet gets one, or ~20 if close siblings are merged (e.g., fuzzing + PBT stay separate, but snapshot/golden/approval merge into one).

### Open questions

1. Is production-stage assurance (canaries, shadow traffic, synthetics) in scope, or is the skill strictly pre-merge/CI? The name "assurance-strategist" suggests the broader scope. → **Resolved 2026-06-12: out of scope.** See scope-tightening entry below.
2. Catalog granularity: ~20 merged-siblings reference files vs ~35 fine-grained ones. Finer granularity helps routing but costs maintenance. → **Resolved 2026-06-12: fine-grained.** See decisions entry below.
3. Should reference files include runnable scaffolding (minimal Quint spec, Playwright ARIA-snapshot setup) or stay prose + pseudocode? Leaning TypeScript/Python for examples as the lingua franca, per the "simple enough to mimic" requirement. → **Resolved 2026-06-12: principles-first.** See decisions entry below.

## 2026-06-12 — Scope tightening

Decided OUT of scope:

- **Performance-related testing** — benchmark regression budgets, load testing with SLO assertions, Lighthouse/bundle-size budgets.
- **Production-stage assurance** — synthetic monitoring, shadow/scientist-pattern verification, canaries, rollback gates, runtime invariant monitors in prod, feature-flag matrix testing in prod.

This deletes catalog categories 7 (non-functional) and 8 (runtime/production) almost entirely. DAST and authz-matrix testing survive: they are correctness/security checks that run pre-merge against ephemeral environments, not operational monitoring.

**Sharpened goal statement:** the skill designs *pre-merge functional correctness and conformance strategies* — the territory where verification is deterministic, repeatable, and agent-drivable in CI or locally. Operational qualities (latency, throughput, behavior under real traffic) have fundamentally different feedback loops and belong to a different discipline.

Implications:

- The "layer by feedback latency" composition frame now ends at the E2E/visual/simulation layer instead of extending into canary/synthetics.
- Reference file count drops by roughly 5–7.
- The skill name's "assurance" means *assurance of correctness before merge*, not operational assurance.

## 2026-06-12 — Granularity and reference-style decisions

**Question 2 — catalog granularity: fine-grained (one file per technique, ~30 files post scope cut).**
Rationale: the reader is an agent assembling a strategy. When it loads a reference file, *everything in that file should be relevant* to the technique it chose — merged-sibling files would pull partially-relevant ideas into context and dilute the signal. File count is not a real cost here; context pollution is.

**Question 3 — reference style: principles over runnable scaffolds.**
The skill must work across projects with different languages and frameworks (Go vs TypeScript, vitest vs jest, etc.), so reference files lead with architecture, ideas, and principles — what the technique is, what bug class it catches, how to recognize when it applies, how to structure it — rather than copy-paste scaffolding. Code examples are allowed but sparing, and the ideas in them must be generalizable: illustrate the *shape* of the technique, not a specific toolchain setup. Tool names appear as pointers ("e.g., fast-check in TS, Hypothesis in Python"), never as instructions tied to one stack.

Resulting reference-file template sketch:

1. What it is (2–3 sentences)
2. Bug classes it catches / oracle type it provides
3. When to reach for it — and when not to (boundaries against sibling techniques)
4. How it works — principles and structure, language-agnostic
5. One minimal, generalizable example (pseudocode or simple TS/Python)
6. Tool pointers per ecosystem (one line each)
7. How it composes — which techniques it pairs with, which frames it serves

## 2026-06-12 — Scaling assurance to project maturity; the self-verification invariant

### The invariant (always applies)

**AI agents building the product must ALWAYS be able to self-verify their own work, end to end.** The verification floor is never zero — what scales with project maturity is *rigor and repeatability*, not whether verification exists. Even a throwaway spike requires the agent to close the loop and produce evidence (a transcript, a screenshot), never "it compiles."

Corollary: every task/PR ends with an **evidence bundle appropriate to the maturity level** — playbook transcript + screenshots at low maturity; green CI + traces + snapshot diffs at high maturity. This connects to the existing evidence-bundles pattern in the catalog.

### Seed examples (from discussion)

- **Weekend hackathon web app**: needs some E2E verification but can be fast/loose. Solution: versioned markdown playbooks the coding agent runs via the `agent-browser` CLI, checking off each item. Intent-level assertions mean the playbook doesn't break when a text-box label changes, but still gives "good enough" E2E verification.
- **Enterprise product with customers**: needs repeatability and CI; much higher required certainty. Combination of unit, integration, Playwright, Quint conformance, model-based testing at design time.

Note: the markdown-playbook pattern is a real technique in its own right (**semantic E2E** — intent-level assertions interpreted by an agent, resilient to cosmetic churn) and gets its own reference file, not just a mention in scaling guidance. Caveats to capture there: playbooks must be versioned in the repo with a stable checklist structure (machine-discoverable), and checks must be phrased as *falsifiable expected observations* with evidence attached — agent-run verification is itself fallible.

### The two-axis model: Maturity × Certainty

Formalization so the architect can ask the user clear scoping questions.

**Axis 1 — Maturity (per project).** How repeatable and institutionalized verification must be. Determined from project facts: who uses it, consequences of an outage, team size, expected lifespan, CI presence.

- **M0 Throwaway spike** — ad hoc; agent self-checks interactively, evidence in the transcript.
- **M1 Hackathon / prototype** — versioned markdown playbooks, agent-browser semantic E2E, screenshots as evidence.
- **M2 Early users** — deterministic core suite in CI for critical paths; playbooks for the rest.
- **M3 Paying customers** — full deterministic CI: contracts, visual/ARIA regression, MBT where stateful.
- **M4 Regulated / critical** — formal specs with trace validation, conformance suites, coverage-matrix audits.

**Axis 2 — Certainty (per subsystem).** *Required confidence that this behavior is correct.* Determined from cost-of-being-wrong questions: "what happens if this is wrong — data loss, money, embarrassment, nothing?" ("Criticality" is the cause; certainty is the requirement. Whichever word we pick needs this one-line definition or users conflate it with maturity.)

- **C1 "It demos"** — happy path observed once.
- **C2 "It works"** — main flows + key edge cases verified.
- **C3 "It's solid"** — invariants hold across generated inputs (PBT, fuzzing), mutation-audited.
- **C4 "It's proven"** — model-checked / exhaustively conformant against a spec.

**Key insight: the axes apply at different levels.** Maturity is one answer per project; certainty is assessed per subsystem. A weekend hackathon with a gnarly scheduling algorithm still wants C3 on that algorithm (PBT + differential are cheap enough for a weekend) while the UI shell stays C1. A mature product adding a cosmetic banner doesn't need C4.

Composition with existing frames: **archetype picks the technique family, certainty picks how deep into it you go, maturity picks how repeatable the harness must be.**

Grid corners for intuition:

| | Low certainty | High certainty |
|---|---|---|
| **Low maturity** | Agent-run playbooks, semantic smoke checks | Playbooks for the shell + PBT/differential on the core |
| **High maturity** | Thin deterministic checks, lean on existing suite | Full bundle: CI contracts, MBT, formal specs + trace validation |

### The rigor dial and upgrade paths

Most technique families aren't two separate worlds (loose vs strict) — they have a **rigor dial** that maturity turns:

| Technique family | Loose form (low maturity) | Strict form (high maturity) |
|---|---|---|
| E2E | Markdown playbook + agent-browser | Deterministic Playwright in CI |
| Visual | Agent eyeballs screenshot vs rubric | Pixel/ARIA snapshot diffs in CI |
| Invariants | A few hand-rolled asserts | Full PBT with shrinking, mutation-audited |
| Spec | Statechart sketch in markdown | Quint with trace validation |

**Principle: prefer loose forms with a known upgrade path.** A markdown playbook is a test plan in prose — when the project matures, an agent can transpile it into Playwright tests. The strategy should name **upgrade triggers** ("first external user → promote checkout playbook to CI suite"), making the assurance strategy a living artifact, not a one-time prescription.

### Implications for SKILL.md

- The intake/scoping step becomes explicit: architect asks maturity questions (project-level) and certainty questions (per subsystem) before selecting techniques.
- The composition frames gain a fifth member: scale by Maturity × Certainty.
- Reference files should note their position on the rigor dial and their loose/strict siblings (upgrade path).

## 2026-06-12 — From 2 axes to an orthogonal basis: the five-axis model

Stress-tested the Maturity × Certainty model. "Maturity" turned out to be a proxy bundle (longevity + churn + infrastructure + audience), and the constraint of exactly 2 axes was arbitrary. Re-derived the axes from first principles: list the independent design decisions the architect makes, give each decision exactly one input axis.

### The five axes

| Axis | Level | Intake question | Decision it drives |
|---|---|---|---|
| **Criticality** | per subsystem | "What breaks if this is wrong — money, data, trust, nothing?" | **Depth** of verification (C1–C4 ladder) |
| **Volatility** | per subsystem | "How fast is this surface changing?" | **Assertion precision**: semantic/loose ↔ exact/strict |
| **Longevity** | per project | "How long will this code live?" | **Harness durability**: ad hoc ↔ versioned playbook ↔ CI-institutionalized |
| **Autonomy** | per project | "How much human review backstops the agents?" | **Verification floor** + evidence-bundle requirements |
| **Accountability** | per project | "Who must be convinced — agent, team, auditors, external implementers?" | **Evidence formality**: transcript ↔ CI dashboard ↔ conformance suite |

### Demoted to observed classifications (diagnosed from the code, not asked)

- **Archetype** (CRUD surface, algorithmic core, async pipeline, …) → selects the technique *family*.
- **Oracle availability** (exact, relational, reference, spec, judgment) → selects the technique *within* the family.

### Orthogonality evidence

The earlier "rigor dial" conflated two independent dials:

- Markdown playbook **run in CI on every PR** = durable but loose (high longevity, high volatility).
- Precise Playwright test **run ad hoc by the agent** = strict but ephemeral (low longevity, low volatility).

Both quadrants are legitimate strategies → assertion precision and harness durability are separate axes. Other divergence cases: long-lived internal dev tool = high longevity, low criticality (durable-but-shallow tests); autonomous agent fleet on a throwaway prototype = low longevity, high autonomy (floor stays high though nothing persists); mature product with an area mid-redesign = high longevity, locally high volatility.

**Autonomy** is the agent-era novelty and the axis most worth defending: the self-verification invariant says agents always verify; autonomy sets *how strong* that floor is, independent of everything else.

### Maturity survives as a preset, not an axis

M0–M4 become **named presets over the project-level axes**: "weekend hackathon" → longevity=days, accountability=self; "enterprise with customers" → longevity=years, accountability=team+customers+auditors. Intake stays fast (one preset question + two per-subsystem questions + autonomy check); when a preset leaks, the architect adjusts the individual axis instead of fighting the model.

### Intake flow

Preset question → per-subsystem criticality + volatility → autonomy check → architect diagnoses archetype + oracle availability from the code → strategy.

(Supersedes the "2 axes + 2 modifiers" proposal from the previous entry: churn modifier → Volatility axis; autonomy modifier → Autonomy axis; maturity axis → preset.)

**Status: proposed, pending approval.**

## 2026-06-12 — Autonomy is a constant, not an axis

Correction from Charlie: **agent autonomy is ALWAYS 100% — that is the point of this skill.** There is no human backstop to scale against.

Consequences:

- The five-axis model reduces to **four axes: Criticality, Volatility, Longevity, Accountability.**
- Autonomy stops being an intake question and becomes a **design assumption of the whole skill**, folded into the self-verification invariant: every strategy is designed as if no human reviews the work, because none does.
- The verification floor is therefore always at its maximum setting — evidence bundles are unconditional at every maturity preset, not scaled by oversight level. Even M0/C1 work produces evidence an *agent* (not a human) can re-check.
- This sharpens the skill's identity: it designs assurance for **fully autonomous agent-driven development**, where verification artifacts are the only trust mechanism.

Updated intake flow: preset question → per-subsystem criticality + volatility → architect diagnoses archetype + oracle availability from the code → strategy.

## 2026-06-12 — Technique card schema

Each technique reference file ("card") follows a fixed schema so cards are scannable the same way and comparable field-by-field. Charlie's seed fields: when to use, pre-requisites, design principles, examples, works-well-with, signs-you're-using-this-wrong. Refined and extended:

### Machine-readable frontmatter (routing layer)

The strategist must not load 30 cards to pick 6. Filterable facts live in YAML frontmatter; the SKILL.md technique index is *generated* from it (fits the repo's compile-step culture, stays in sync automatically). Intake answers filter the catalog mechanically before any card is opened.

```yaml
oracle: relational          # exact | relational | reference | spec | judgment
archetypes: [algorithmic-core, async-pipeline]
criticality-min: C3         # depth tier this technique serves
volatility-fit: strict      # loose | strict | both
harness: ci                 # ad-hoc | playbook | ci
pairs-with: [differential-testing, mutation-testing]
upgrade-path: {looser: invariant-asserts, stricter: formal-spec-quint}
cost: {author: medium, maintain: low, run: fast}
```

`upgrade-path` encodes the rigor-dial siblings. `prerequisites` across cards form a dependency graph (no Schemathesis without schema-first contracts) — ordering information for the strategy.

### Body sections (fixed order — agents learn to jump to section N)

1. **What it is** — 2–3 sentences.
2. **What it catches / what it misses** — bug classes caught, oracle type, and *explicit non-coverage*. The misses-list guards against false confidence and feeds the coverage-matrix audit.
3. **When to use / when not to** — triggers + boundaries that *name the sibling technique* (the What→When→Don't discipline from skill descriptions, applied to cards). Boundaries prevent agents pulling partially-relevant cards.
4. **Prerequisites** — split: *artifacts* (schema exists, component lab exists) vs *infrastructure/properties* (CI, deterministic builds, seedable RNG).
5. **Design principles** — the language-agnostic how.
6. **Agent execution & evidence** — the autonomy-driven field: how an agent runs this end-to-end, what evidence artifact it emits, what a *legible failure* looks like (replay seed, trace, minimal counterexample). A technique an agent can't drive and can't produce evidence from doesn't belong in the library — this field enforces the invariant card-by-card.
7. **Example** — one minimal, generalizable example (principles-first decision).
8. **Works well with** — composition prose; frontmatter holds the slugs.
9. **Signs you're using it wrong** — each sign paired with its correction; corrections naturally reference the axes ("snapshots churning every PR → assertions too strict for this surface's volatility").
10. **Tool pointers** — one line per ecosystem.

### Considered and rejected

- "Metrics/health signals" section → folds into signs-you're-using-it-wrong as the inverse.
- Maturity-preset fit field → derivable from the axis fields.
- Multiple examples → context pollution; one principle-bearing example.

### Conventions

- ~~Target length ~100–150 lines per card.~~ **Revised 2026-06-12:** card bodies may be longer. Routing happens entirely at the SKILL.md index — an agent only opens a card after deciding via the index row to use that technique, so body depth is a feature, not context pollution. The hard requirement moves to the index row + frontmatter: they must carry enough signal that no card is ever opened speculatively. "When to use / when not to" stays near the top of the body as a cheap bailout for mis-routed agents.
- Fixed section ordering; schema is lintable (autoskill-style check: all ten sections present, frontmatter valid).

## 2026-06-12 — Build the master index via the repo's skill compiler

Decision: use the existing `src/compile.py` compilation step to generate the SKILL.md technique index from card frontmatter, so the index can never drift from the cards (same guarantee `install.sh` gets from the DSL).

### What already fits (no changes needed)

- `REF_LINK_PATTERN` (compile.py:50) lets SKILL.md *link* refs without inlining: `[references/card.md](references/card.md)` is validated and copied but not expanded. Cards stay on-demand; SKILL.md holds only the index. The 15k-char output limit is safe (~30 index rows ≈ 4–5k chars).
- Phase-1 validation is the natural home for card schema linting — malformed cards become compile errors, stronger than a separate lint step.

### Extensions required

1. **New directive `{{ index:techniques }}`** — at compile time, scan the skill's declared refs, parse each card's frontmatter, render the routing index (name, one-liner, oracle, archetypes, axis fit, link to `references/<file>`).
2. **Flatten card frontmatter** — `_parse_frontmatter` is flat key:value by design (no pyyaml). Card schema becomes flat keys: `upgrade-looser:` / `upgrade-stricter:` instead of nested `upgrade-path:`, `pairs-with:` as comma-separated string, `cost-author:` / `cost-maintain:` / `cost-run:` as separate keys. Keeps the compiler dependency-free; flat keys are easier to lint anyway.
3. **Card validation in Phase 1** — required frontmatter keys present, all ten body sections present in fixed order.

### Structure

- New module `src/assurance/` with `skill("assurance-strategist")`.
- Cards live as module `refs/` named `technique-<slug>.md` (e.g. `technique-property-based-testing.md`) — module-level so a future sibling skill (e.g. an assurance *auditor*) can share them.
- DSL declares all cards explicitly rather than globbing `refs/technique-*.md` — more typing, but matches the repo's declare-everything-validate-everything philosophy.

## 2026-06-12 — Card schema v2: from encyclopedia entry to executable playbook

Critiqued the original field list (when-to-use, prerequisites, principles, examples, works-well-with, misuse signs) and the 10-section v1 schema built on it. **Root flaw shared by both: every field *describes* the technique — knowledge for a reader who wants to understand. The actual consumer is an autonomous agent that already chose the technique (via the index) and must now execute an adoption of it in a specific codebase with no human checking the result.** Description doesn't operationalize.

Five specific gaps:

1. **Skips the hard part: derivation.** Writing a property test is trivial; *finding the properties* is the skill (likewise: finding metamorphic relations, choosing a model boundary, deciding what to snapshot). A lone code example is actively risky — agents copy examples literally. What transfers is the derivation reasoning (feature → test design) plus a heuristics catalog for the discovery step (for PBT: round-trip, invariant, oracle-comparison, idempotence, commutativity).
2. **No definition of done.** The agent can't grade its own adoption. Without an acceptance checklist, the self-verification invariant has a meta-level hole: who verifies the verification?
3. **No kill test.** Highest-leverage addition: before trusting any harness, plant a deliberate bug and confirm the technique catches it. A suite that has never failed proves nothing. Per-technique mutation testing, done once at adoption time; the kill-test record joins the evidence bundle.
4. **No economics.** Every card defines its **minimum viable instance** (the 20-minute version that already pays rent) vs full rigor. This is what makes strategies incrementally adoptable and how maturity presets cash out per technique.
5. **Composition is directional, not flat.** PBT generators *feed* differential testing; the component lab *is a substrate for* visual diffing. Upstream/downstream, not "works well with". And misuse signs need companions: **graduation and retirement triggers** (dial up, dial down, delete).

### The reframe

> A card is not something an agent reads to understand a technique. It's something an agent **executes, then grades itself against**. Playbook + built-in conformance test for its own adoption.

### Schema v2 (frontmatter unchanged from the routing-layer design)

1. **What it is & what it catches/misses** — orientation + explicit non-coverage
2. **When to use / when not** — bailout near the top, names siblings
3. **Prerequisites** — artifacts; infrastructure
4. **The derivation step** — how to FIND the properties/relations/model in this codebase; heuristics catalog
5. **Implementation moves** — ordered steps + constraints
6. **Minimum viable instance** — the 20-minute version vs full rigor
7. **Agent execution & evidence** — run loop, artifact emitted, legible failure
8. **Kill test** — plant a bug, prove detection, record it
9. **Definition of done** — checklist the agent self-grades against
10. **Composition** — upstream feeds / downstream consumers
11. **Failure modes & retirement** — sign → diagnosis → correction; graduation/retirement triggers
12. **Tool pointers** — one line per ecosystem

Sections 8–9 are the 10x: they extend the self-verification invariant to the assurance machinery itself. Supersedes the v1 ten-section schema above.

## 2026-06-12 — Course correction: this skill is the ARCHITECT, not the verifier

Clarification from Charlie: the skill creates the **architect** that designs and lays down the assurance framework *for other agents to follow*. Coding agents do NOT use this skill (or its cards) when validating day-to-day work — they follow the artifacts the architect generated. The skill's final workflow phase includes writing documentation, updating AGENTS.md/CLAUDE.md, and possibly generating a project-local skill that downstream agents use to actually run verification.

Schema v2's framing ("the agent executes the adoption and grades itself") addressed the wrong persona. Repositioning, not discarding: the kill test, definition-of-done, and run loop become things the architect **prescribes into the generated artifacts**, which implementing agents execute later. The cards are the architect's private design library.

What was genuinely missing: a **"what to lay down"** section per card — the prescription emitted when adopting a technique.

### Skill workflow (end to end)

1. **Intake** — axes + maturity preset questions.
2. **Diagnose** — archetypes, oracle availability, existing harnesses, from the code.
3. **Select & compose** — via the index + cards + composition frames.
4. **Generate the framework** — assurance strategy doc, AGENTS.md/CLAUDE.md updates, optional project-local "verify-your-work" skill for coding agents, playbooks, CI wiring.
5. **Handoff** — upgrade/retirement triggers recorded; strategy is a living document.

### Card schema v3 (architect-facing; supersedes v2)

1. **What it is & what it catches/misses** — unchanged
2. **When to prescribe / when not** — axes fit, names sibling techniques
3. **Prerequisites** — what the architect must ensure exists first
4. **Design decisions** — what the ARCHITECT must decide: scope, boundaries, model granularity, where it applies
5. **Derivation guidance** — heuristics the architect embeds in the prescription so implementers can find properties/relations/states themselves
6. **Minimum viable instance vs full rigor** — economics for scoping the prescription
7. **What to lay down** — the prescription: harness scaffolding to create, docs section, AGENTS.md lines, runner-skill content, CI wiring
8. **Acceptance criteria to embed** — DoD checklist + kill-test requirement that implementing agents must satisfy (written into generated artifacts)
9. **Composition** — upstream/downstream, unchanged
10. **Failure modes & retirement triggers** — feeds the strategy's living-document section
11. **Tool pointers** — unchanged

### Key consequence

**The skill's real output is not a strategy document — it's the operating environment for downstream agents.** AGENTS.md tells them what verification is mandatory; the generated project skill tells them how; CI enforces it; the strategy doc records why, for the next architect session.

## 2026-06-12 — The standard harness model; "Harness changes" card section (schema v3.1)

Charlie: each card should include a "what harness changes should you update" section — e.g. update CLAUDE.md AND AGENTS.md to link the testing doc, append a section to the testing doc, write a bash script to run all tests end to end. The architect designs and sets up the harness so that "dumb" agents later just follow the guardrails.

Refinement adopted: don't let 30 cards emit 30 freeform prescriptions (→ sprawl). **SKILL.md defines a fixed set of named harness components once; every card's "Harness changes" section expresses deltas against that fixed set.**

### Standard harness components

| Component | Role |
|---|---|
| `AGENTS.md` / `CLAUDE.md` | Entry points — short, mandate verification, link to the testing doc |
| `docs/testing.md` | The assurance doc — strategy rationale + one section per adopted technique |
| `make verify` (or `scripts/verify.sh`) | **The keystone guardrail**: one command runs everything; per-layer subcommands (`verify-unit`, `verify-e2e`, …) |
| `docs/playbooks/*.md` | Agent-run semantic E2E playbooks |
| CI workflow | Runs `make verify` and nothing else — local and CI cannot drift |
| Project-local skill(s) | e.g. `verify-work` — the dumb agent's interface to all of the above |
| Evidence conventions | Where artifacts land (`.evidence/`, PR comments) and what counts as proof |

Example delta table (property-based testing card): append §PBT to docs/testing.md; add `verify-properties` target wired into `make verify`; AGENTS.md line "core-module changes require property runs, see docs/testing.md§PBT"; add derivation heuristics to the verify-work skill.

### What this buys

- **Uniformity across projects** — downstream agents always know: read AGENTS.md → run `make verify` → drop evidence in the standard place.
- **Composability** — adopting N techniques = merging N deltas into one fixed component set.
- **Idempotent re-runs** — stable addresses mean the returning architect updates sections instead of duplicating them.

The single `make verify` command is the load-bearing guardrail: a dumb agent needs exactly one affordance, and "the only command CI runs is the command you run" closes the local/CI drift hole.

### Schema v3.1

Same as v3, with §7 renamed and concretized: **7. Harness changes** — delta table against the standard harness components. (§8 "Acceptance criteria to embed" stays separate: §7 is *where things go*, §8 is *what counts as done*.)

## 2026-06-12 — docs/testing-strategy.md as single source of truth (steelmanned)

Proposal from Charlie: each architect run produces a single `docs/testing-strategy.md` (overview + how-tos for implementing agents), linked from project root memory files with instructions to read it when designing a new feature or validating an existing one. The doc is the source of truth.

**Steelman:** (1) agents fail at routing, not reading — one canonical address linked from memory files is the most reliable context-injection pattern; staleness is visible when there's exactly one place to be wrong. (2) Clean ownership → idempotent regeneration; one-file diffs for strategy changes; "Generated by assurance-architect" header. (3) The sleeper benefit is *design-time* injection: the per-subsystem map tells feature-planning agents what assurance their plan must include — assurance planned in, not bolted on. (4) Scales down honestly for M0–M1.

**Strawman:** (1) Prose can't be a source of truth — only executables can. If the doc mandates what CI doesn't check, the doc is fiction; silent drift. (2) Conflates two audiences/moments: design-time guidance vs validation-time runbook → 1,000-line doc and context pollution for the small-fix agent. (3) "Read whenever designing or validating" is an unconditional context tax on every task. (4) Living-document content (upgrade/retirement triggers, axis assessments) addresses a third audience — the next architect run.

**Verdict — adopted with two amendments:**

1. **Hub, not monolith.** `docs/testing-strategy.md` is the single narrative source of truth and the only thing memory files link. Short load-bearing top (per-subsystem map, "validation = run `make verify`", evidence conventions); detail below or in linked spokes (playbooks, per-technique how-tos). M0–M1: literally one file. M3+: hub-and-spokes, hub remains canonical. Artifact set scales with maturity preset.
2. **Executables enforce; the doc explains.** Truth hierarchy: `make verify` + CI are the source of truth about *enforcement*; the doc is the source of truth about *intent*; architect's definition-of-done includes their correspondence ("nothing mandated in the doc that isn't enforced or evidenced") — and kill tests prove the match.

This simplifies the standard harness component table: memory files link ONE doc; the doc links everything else.

**Addendum — two further critiques (2026-06-12, later):**

3. **Regeneration/hand-edit collision.** Run one creates the doc cleanly; run two meets hand-edits from humans or other agents. Wholesale regeneration clobbers them; timid merging accumulates cruft. The doc needs explicit ownership semantics — either a "generated, edit by re-running the architect" banner with hand-edits forbidden, or clearly marked generated vs free-form sections. Ambiguity is worse than either choice.
4. **The doc is the easiest deliverable to fake.** Eloquent prose is the cheapest output of an architect run; a working harness is the expensive one. Guard: the skill's own definition of done is harness-first — the doc describes what was *built and proven* (kill tests passed, evidence produced), and any doc section without a corresponding enforced check is a defect of the run itself.

## 2026-06-12 — Walking skeletons; refined architect workflow (schema v3.2)

The architect's run includes **scaffolding the test infrastructure and proving it works end-to-end** with two fake tests per technique: one that fails (`assert(false == true)`) and one that passes (`assert(true == true)`).

### Walking skeleton vs kill test — two checks, two moments, two owners

- **Walking skeleton (architect, scaffold time): proves the plumbing.** The *failing* fake is the critical half — it proves failures propagate: non-zero exit codes bubble through `make verify`, CI goes red, evidence artifacts are emitted even on failure. The silent killer in test infra is the harness that swallows failures (unpropagated exit codes, vacuously-passing async assertions, `continue-on-error` CI steps); `assert(false)` is the only thing that catches it. The passing fake proves the green path and that evidence lands where the strategy doc says.
- **Kill test (implementers, when real tests exist): proves detection power.** Planted bug in real code, caught by real tests. Architect prescribes it via the acceptance-criteria section; never runs it itself.

Skeleton run results (red AND green, with CI links/screenshots) join the architect's own evidence bundle — this also closes critique 4 above: the architect cannot satisfy its run with prose, because its DoD includes demonstrated red and green per adopted technique.

### New card section: "How to get to a walking skeleton"

Steps expected for that technique: scaffold the harness → write the fail-fake and pass-fake → run locally → run via `make verify` → confirm CI red/green → confirm evidence artifact emitted on both outcomes → remove the fakes (or park the fail-fake behind an opt-in self-test target, e.g. `make verify-selftest`).

**Schema v3.2** = v3.1 with the new section inserted after §7 Harness changes:
…6. Minimum viable instance, 7. Harness changes, **8. How to get to a walking skeleton**, 9. Acceptance criteria to embed (incl. kill test), 10. Composition, 11. Failure modes & retirement, 12. Tool pointers.

### Refined architect workflow

a. **Read skills** (cards via index)
b. **Get context from project** (diagnose: archetypes, oracles, existing harnesses)
c. **Design the testing strategy** — scope may be a single feature or a brand-new app (feature-scoped runs merge deltas into the existing hub doc + `make verify`; whole-app runs create them)
d. **Implement walking skeletons** for each adopted technique (red + green proven)
e. **Author the resources** implementer agents need to use the infra: docs (testing-strategy.md hub), scripts, AGENTS.md/CLAUDE.md links, optional verify-work skill.

## 2026-06-12 — Research fan-out digest (6 web-research agents)

Six cheap (Haiku) research agents swept: agent-native testing practices, lightweight formal methods, testing-strategy frameworks, UI/browser agent tooling, test-quality verification, and prior art. **Caveat: citations below are agent-reported and unverified — verify load-bearing ones before they shape final cards.**

### Validations of our design

- **Oracle taxonomy is literature-backed** — academic oracle classifications (specification/metamorphic/expected-output/verdict) map onto our exact/relational/reference/spec/judgment axis. Risk-based testing taxonomies (ISO 29119, RST/Bach/Bolton) validate criticality+volatility decomposition.
- **Kill tests / mutation-as-gate are established at scale** — Google: diff-based probabilistic mutation analysis on ~30% of all diffs; Meta ACH: LLM-generated problem-specific mutants, 73% developer acceptance, equivalent-mutant recall 0.47→0.96 with preprocessing. Supports "mutation score, not coverage %" in acceptance criteria.
- **`agent-browser` is real** — vercel-labs/agent-browser: Rust CLI, structured accessibility-tree snapshots with stable semantic refs (@e1) that survive UI refactors; markdown playbooks are an emerging convention. Validates the semantic-E2E playbook card.
- **Apparently novel (no prior art found):** (1) technique card library with machine-readable routing frontmatter; (2) single-pass strategy→CI-wiring→generated-skill pipeline; (3) formalized harness self-validation (our walking-skeleton fail/pass fakes) — "frameworks don't commonly enforce assert-false/assert-true scaffolding tests".
- Walking skeleton traces to Alistair Cockburn (97 Things); our usage (proving the *test* infra, not the app architecture) is a twist on it worth acknowledging in the card.

### Corrections to absorb

1. **Trace validation: hard boundaries needed (MongoDB case study).** Trace-checking internal multithreaded state was economically infeasible (~10 weeks/spec); **test-case generation from TLA+ specs** was the success story (100% branch coverage, real bugs found). Card boundary: trace validation only for message-level/network logging; prefer deriving test cases from the spec.
2. **LLM-written specs need a conformance loop.** SysMoBench: LLM-written specs are syntactically correct but semantically wrong → any spec-authoring prescription requires a conformance feedback loop (spec validated against implementation behavior, never trusted standalone). FizzBee (Python-like syntax) has practitioner momentum (Jack Vanlightly's Kafka work pairs TLA+ + FizzBee) and is worth a mention as an alternative. **Decision (Charlie, 2026-06-12): Quint stays first-class** — research agents found little industry traction, but firsthand project experience confirms good developer ergonomics (typed, familiar syntax, CLI/REPL), which are exactly the qualities that matter for agent-written specs. FizzBee = alternative, not replacement.
3. **Separate evaluator principle (Anthropic harness guidance).** Builder agents grading their own work are reliably over-positive; prescribe an evaluator role distinct from the implementer. Under 100% autonomy this becomes a structural requirement of the generated harness: evidence is produced by the implementer but *judged* by a separate evaluator agent/process. Add as cross-cutting pattern (likely its own card).
4. **Flakiness management missing from our catalog.** Atlassian quarantine-first model: 1–2% flakiness healthy, >5% intervention; flakiness metrics emitted by the runner. New card needed: flaky-test management; note that flakiness in walking-skeleton runs = harness-validation failure.

### Ideas to steal

- **Playwright test agents** (1.56+): planner/generator/healer role split; **healer** repairs locator drift — directly relevant to the volatility axis (healing = automated response to volatile surfaces).
- **Artifacts-on-disk over streaming** (Playwright CLI writes ARIA snapshots to disk; ~4x token efficiency) — validates `.evidence/` directory convention; generated harnesses should write snapshots/traces to disk and return paths.
- **Hardening vs catching tests (Meta JiTTest)** — regression-prevention vs bug-discovery roles; useful vocabulary for acceptance criteria.
- **Vacuous-test & assertion-message linting** — prescribe in acceptance criteria (assertion-free test detection; failure messages must state expected vs actual).
- **Storybook 9 as component-lab substrate** — play functions + Vitest + a11y panel + Chromatic from one story file; the component-lab card should default to stories rather than hand-rolled pages where the stack allows.
- **Eval the skill itself** — anthropics/skills evals.json + grader-agent pattern; assurance-strategist should ship evals testing strategy-generation quality.
- **Graduated trust tiers** — smoke checks fully autonomous, higher-stakes gates need stronger evidence; adapt to autonomy=100% as: deterministic gates vs agent-judged checks carry different evidentiary weight.
- **Compliance drivers** (SOC2/HIPAA/PCI) — fold into Accountability axis presets.
- **Reward-hacking watch:** research gap noted on agents "engineering around" kill tests rather than fixing root causes — acceptance criteria should require kill-test *reproducibility* (seeded, re-runnable), not one-shot.

### New/changed catalog items

- ADD card: flaky-test management (quarantine, metrics, retry policy).
- ADD cross-cutting card: separate evaluator pattern.
- ADD/ADJUST: test-healing for locator drift (within semantic-E2E / visual cards).
- ADJUST: formal-spec card → Quint first-class (per Charlie's experience), FizzBee/TLA+ as alternatives; spec-conformance feedback loop mandatory.
- ADJUST: trace-validation card → message-level boundary; prefer spec-derived test generation.

## 2026-06-12 — Eval harness design (deeper than normal)

Charlie: this skill needs deeper-than-normal evals — test cases that inject a prompt to an agent with the skill and grade what it produces.

**Scope clarification (Charlie): these evals are for THIS repo, at skill-design time.** They are development infrastructure for iterating on the skill — same category as `autoskill lint` and the compile step. They live in source (`src/assurance/evals/`), are excluded from compiled `./skills/` output, and are never shipped to or seen by agents consuming the skill. (Distinct from the walking-skeleton/kill-test machinery, which IS part of the skill's prescriptions.)

**Key insight: the skill is unusually evaluable because its deliverables are executable.** Grade by *running* what the architect built, not reading it. Pleasing recursion: apply the skill's own doctrine to the skill — walking skeletons (generated harness goes red/green), kill tests (generated environment catches a planted bug), evidence bundles (transcripts + scorecards per eval run).

### Structure

```
src/assurance/evals/
  cases/<case-id>/
    fixture/            # minimal target repo (or fixture.sh generator)
    prompt.md           # injected user prompt
    expectations.yaml   # must_adopt / must_not_adopt techniques, expected axis
                        #   elicitation, required files
    checks.sh           # case-specific mechanical assertions
  run.sh                # orchestrator: copy fixture → headless agent (claude -p) → grade
  graders/strategy-rubric.md
  results/              # scorecard JSON, model + skill version pinned
```

Initial case list = coverage matrix over the design: hackathon-webapp, enterprise-crud, cli-tool, algorithmic-core (should reach for PBT/Quint), feature-scoped-rerun (fixture already has a harness; tests merge/idempotency), overengineering-bait (static site; pass = restraint, fails if Quint appears). 6–8 cases initially.

### Four grading tiers (cheap → expensive)

- **T1 Static (seconds):** files exist per the harness model — testing-strategy.md, AGENTS.md links it, `make verify` present, evidence conventions declared. Pure shell.
- **T2 Executable (minutes, decisive):** run the generated harness. `make verify` exits 0 on clean fixture; reintroduced fail-fake exits non-zero (failure propagation proven); architect re-run on own output → no duplicated sections (idempotency). Objective, no LLM judgment.
- **T3 Grader agents (rubric):** technique-selection fitness vs expectations.yaml; doc-vs-enforcement correspondence ("anything mandated but unenforced?"); axis elicitation (did it ask, or assume?).
- **T4 Downstream simulation (milestones only):** a separate dumb implementer agent gets a small feature task in the post-architect fixture, no knowledge of the skill. Grade: found guardrails via AGENTS.md → ran `make verify` → produced evidence bundle. Then the full-pipeline kill test: implementer introduces a subtle bug — does the generated environment catch it? Tests the operating environment, not the prose.

### Mechanics

- Headless runs in temp fixture copies, transcripts kept as evidence.
- **N=3 runs per case minimum** — score distributions, not single points; nondeterminism lies.
- expectations.yaml is per-case ground truth, authored at case-design time — forces explicitness about what correct architecture means per cell of the axis grid (likely improves the skill design itself).
- Format compatible with anthropics/skills evals.json + grader-agent convention where possible; T2/T4 deliberately exceed it.
