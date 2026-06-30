---
hash: "093f3735"
id: "881acaae"
read_when: "designing or building the strategy-quality eval for assurance-strategist (task 006) — its instrument, scenario dataset, judge, and validation"
summary: "Design for a scenario-driven, strategy-only quality eval of assurance-strategist. NOTE: §12 (2026-06-28, ADR-0001) supersedes the original instrument — a grilling replaced rubric-scoring against human answer keys with a blind with/without-skill differential judged holistically by a blind LLM expert (no answer keys, no decomposed dimensions). §§1–2 (strategy-only, markdown, calibration-is-the-thing) still hold. Plan only — not yet built."
title: "Assurance Strategy-Quality Eval — Design"
---

# Assurance Strategy-Quality Eval — Design

**Status:** design / plan only. Nothing built yet. Review before scaffolding.

Companion to [assurance-eval-system.md](assurance-eval-system.md) (the existing end-to-end differential harness) and the `eval-engineer` skill's methodology. This proposes a *second*, complementary eval that grades the **quality of the testing strategy the skill produces**, given a scenario, against a **human-curated dataset**.

## 1. What we're measuring, and why this is different

The existing eval asks *"does the agent end up building better tests when it has the skill?"* — it builds the app and grades the resulting test artifacts. That conflates **strategy quality** with **implementation quality**, carries heavy run-to-run variance (subagent fan-out + coding noise), and — critically — its grader rewards *more testing*, with no penalty for over-engineering.

This eval asks a narrower, sharper question:

> Given a project scenario, is the **testing strategy** the skill designs *good* — correctly diagnosed, right-sized, justified, actionable, **and well-documented**?

The last clause matters: the skill's deliverable is a *document* an autonomous agent must read and follow. A correct strategy buried in an unstructured wall of text fails in practice. So **documentation quality is a first-class graded dimension** — but it is graded on the **markdown the skill itself produces**, not on a rich HTML rendering. See §4.5.

**Why markdown, not `plan.html` (single-variable isolation).** Rendering the strategy as a rich `plan.html` would pull in the planning-doc skill + pd-components, so the arm would test a *composition* — assurance-strategist **+** planning-doc — not assurance-strategist alone. That is the eval-engineer cardinal anti-pattern: *arms that differ in more than one thing*. We keep the output as a single markdown document so the assurance-strategist skill is the only variable under test. Documentation quality is judged on the structure and communicativeness of *that* markdown (headings, the rung matrix as a markdown table, clarity, navigability) — all of which the skill produces unaided. Evaluating rich-HTML rendering, if we ever want it, is a *separate* eval of the assurance-strategist + planning-doc composition.

Three deliberate choices (from the scoping decisions):

- **Strategy-only.** The task tells the agent to produce the testing strategy *as a markdown document* and *stop* — no implementation. This isolates the skill's actual contribution and gives a much lower noise floor, so it's a better instrument for iterating on the skill.
- **Output is one markdown document, kept skill-pure.** Every scenario's graded artifact is a single markdown strategy doc produced by assurance-strategist *alone* — no planning-doc, no pd-components — so the eval measures the skill, not a composition.
- **Scored against a human-curated dataset.** Quality of a *design* isn't mechanically checkable, so the measuring stick is a set of scenarios each paired with a human-authored **answer key**. The dataset is the instrument; building and validating it is most of the work.

## 2. The central thing the current eval can't see: calibration

The skill's whole thesis is **graded prescriptions** — pick the *lightest rung that produces useful self-verification evidence* for the diagnosed axes. A strategy can fail in two opposite directions:

- **Over-engineering** — prescribing PBT + MBT + formal methods for a two-number calculator.
- **Under-engineering** — prescribing "add a couple of unit tests" for a payment ledger.

The current four dimensions (`tests_present`, `verify_command`, `test_quality`, `evidence`) only point one way: more = better. They'd score an over-engineered strategy *highly*. So the headline new dimension here is **calibration / right-sizing**, which penalizes *both* directions relative to a human-set expectation. This is the dimension that actually tests the skill's reason for existing.

## 3. The instrument: scenario dataset with answer keys

### 3.1 Scenario format

```
cases/strategy/<scenario>/
  scenario.md     # the build brief handed to the agent (the SUT description + context)
  answer-key.md   # human-authored reference standard (the "stick") — see 3.2
  meta.yaml       # axis labels + archetype tags, for slicing results
```

`meta.yaml` records the human's diagnosis so results can be sliced:

```yaml
criticality: C3        # per dominant subsystem
volatility: low
longevity: long
accountability: ci
archetypes: [stateful-protocol]
trap: under            # none | over | under  (is the obvious read mis-sized?)
```

### 3.2 Answer key, NOT a gold strategy

We do **not** author one canonical "correct strategy" — there are many good strategies, and grading against a single one punishes legitimate variation. Instead the key is a **structured rubric per scenario**:

- **Expected diagnosis** — the axis read a competent architect should reach (criticality/volatility/longevity/accountability), with one-line justification.
- **Expected rung *bands*** per relevant technique — a range, `min-acceptable .. max-appropriate` (e.g. "PBT: standard rung; unit-only is under, full stateful model-based conformance is over").
- **Must-include elements** — e.g. "states an evidence/self-verification mechanism", "names an upgrade trigger for at least one prescription".
- **Over-engineering traps** — techniques/rungs that would be *wrong* here (e.g. "formal model checking is over-kill; flag if prescribed without the distributed/interleavings justification").
- **Notes** — scenario-specific gotchas the grader should weigh.

This tolerates good variation while staying a fixed stick.

### 3.3 Worked examples (to make "trap" concrete)

- **Calibration-down trap — "internal admin CLI."** Brief reads like a trivial CLI ("a small script to bulk-delete records"), but it mutates production data irreversibly → actually **C4**. The correct strategy escalates (strong evidence, dry-run/confirmation, high-rigor checks). A strategy that treats it as a throwaway CLI is *under*-engineered. Tests whether the skill reads criticality from consequences, not surface size.
- **Calibration-up trap — "marketing landing page."** Sounds important (customer-facing, brand), but it's low-criticality, high-volatility UI. The correct strategy is light/loose (smoke + a few component checks). A strategy reaching for PBT/contract/formal here is *over*-engineered. Tests whether the skill resists ceremony.
- **Archetype-fit — "token-bucket rate limiter."** Stateful, C3, ordering-sensitive → should reach for stateful PBT / model-based testing. A unit-tests-only strategy misses the ordering bug class. Directly exercises the new MBT card.

The trap scenarios are the highest-signal cases — they're where calibration visibly separates a good strategy from a plausible-but-wrong one.

## 4. Quality dimensions (the rubric)

Each scored 0-3, graded **against that scenario's answer key**:

| Dimension | Question | Failure looks like |
|---|---|---|
| `axis_diagnosis` | Did it correctly read criticality/volatility/longevity/accountability? | Mis-reads a C4 as C1; ignores volatility |
| `calibration` | Is each rung the lightest that works for the diagnosed axes? (penalize over **and** under) | Formal methods on a landing page; unit-only on a ledger |
| `technique_fit` | Are the techniques right for the archetype? | Unit-only for a stateful protocol; no component tests for UI |
| `justification` | Does it justify each rung and name upgrade triggers? | Prescriptions with no "why" and no graduation condition |
| `actionability` | Could an autonomous agent follow it and produce evidence? (the self-verification invariant) | Vague "write good tests"; no evidence mechanism |
| `soundness` | Internally consistent, no hallucinated techniques outside the card set? | Invents a technique; contradicts itself |
| `documentation_quality` | Is the markdown strategy doc well-structured, navigable, and clearly communicated? | Wall of text; no section structure or tables; can't find the prescription for subsystem X |

`calibration` is the load-bearing one; the others guard the ways a well-sized strategy can still be bad.

**`actionability` vs `documentation_quality` — keep them distinct.** `actionability` is about *content* (does the strategy contain a followable, evidence-producing prescription); `documentation_quality` is about *presentation* (is that content structured and communicated so an agent can actually navigate and consume it). A strategy can be actionable but badly documented, or beautifully formatted but vacuous — the two dimensions catch different failures.

### 4.5 The strategy artifact (markdown)

Each scenario's graded output is a single markdown document produced by **assurance-strategist alone**. Everything the eval looks for is achievable in plain markdown — no HTML toolchain needed:

- **Clear section structure** — the four-axis diagnosis, the per-subsystem prescriptions, and the evidence/acceptance contract as distinct, navigable headings rather than one stream.
- **The rung matrix as a markdown table** — technique × chosen rung × why-this-rung × upgrade trigger. The single most information-dense view of a graded prescription.
- **Embedded acceptance criteria** — the self-verification checklist an agent self-grades against, as a first-class checklist block.
- **Optional mermaid** — fenced ```mermaid blocks are fine (plain text, renderable) for a test-architecture or state-machine sketch, *as the skill's own output* — not via a planning-doc dependency.

Keeping the arm to a single variable (§1) is worth more than rich rendering. No planning-doc, no pd-components, no HTML in the clean room.

## 5. Grading: reference-guided judge + human audit

Pure human grading doesn't scale and is the bottleneck. Pure unguided LLM grading is taste-noisy. The middle path:

- **Reference-guided LLM judge.** The judge (skill-less, independent) sees: the scenario, the skill's strategy, **and the human answer key**. It scores each dimension *against the key*, with a one-line rationale per score. Anchoring to the key is what collapses judge variance — it's grading *conformance to a fixed standard*, not exercising its own taste.
- **Human agreement audit (the strategy-eval-specific validation).** Humans hand-score a sample of runs; we measure judge↔human agreement per dimension. If the judge tracks humans, scale to LLM grading. If a dimension disagrees, the fix is usually a sharper answer key, not a better prompt. Re-audit whenever the rubric or scenarios change.

This keeps humans in the loop where their judgment is irreplaceable (authoring keys, calibrating the judge) and automates the repetitive scoring.

## 6. Modes (one instrument, three uses)

1. **Absolute-vs-gold (primary).** Score the skill arm against the answer keys across the dataset. Answers "how good are the plans?" — the stated goal.
2. **Differential validity check (secondary).** Run a no-skill arm through the same judge. If the skill doesn't beat no-skill on the rubric, *the eval or the skill is suspect* — a cheap sanity check on the whole apparatus.
3. **Version A/B (later).** Swap skill versions (e.g. pre- vs post-MBT-card) through the identical harness to answer "did this change improve prescriptions?" Track tokens as the cost axis so we can read quality-per-token.

## 7. Validate before trusting (the cardinal step)

Per the eval-engineer playbook, calibrate the instrument before reading it:

- **Noise floor** — same scenario, same arm, ≥3 runs; measure per-dimension score spread. A version A/B delta smaller than this floor is weather, not signal. (Expect lower than the end-to-end eval, but non-zero — the strategy itself varies.)
- **Judge↔human agreement** — the §5 audit. *This* is the validation that matters most here, because the judge+dataset is the instrument.
- **Generality** — judge + rubric behave on ≥2 distinct scenarios before scaling the dataset.

## 8. Harness changes (mostly additive — reuse `run.sh`)

| Component | Delta |
|---|---|
| New case type | `cases/strategy/<name>/` with `scenario.md` + `answer-key.md` + `meta.yaml`; prompt instructs "produce the strategy as a single markdown document, do not implement" |
| Artifact capture | Capture the produced strategy `.md` per arm as a durable artifact (it's the graded object; keep it for audit like a transcript) |
| Grader | New reference-guided rubric: takes scenario + the strategy markdown + answer key → per-dimension JSON with rationales. `documentation_quality` scores the markdown's structure (headings, tables, checklist), so feed the judge the raw markdown so it sees that structure, not just the prose |
| `grade_report.py` | Add the seven dimensions + `meta.yaml` slicing (report scores by criticality band / trap type) |
| Stub mode | Canned strategy markdown + canned judge JSON so the pipeline is testable offline (as today) |
| Metrics | Capture tokens/wall per arm for the eventual quality-per-token read |

**No clean-room/isolation changes** — the existing recipe carries over unchanged. The arm installs assurance-strategist and nothing else, preserving single-variable isolation.

## 9. Authoring the dataset (the human-in-the-loop bit)

The risk with hand-written rubrics is armchair taste. Mitigate by **bootstrapping keys from real outputs**:

1. Draft scenarios — mine real projects / sibling repos / the existing three cases; deliberately span the axis matrix and include ≥2 trap scenarios.
2. Generate a few candidate strategies per scenario (with- and without-skill).
3. A human grades those candidates and writes the answer key *from what actually distinguished good from bad* — not from an a-priori ideal. This grounds the key in observed failure modes.
4. Lock the key. From then it's the fixed standard; changes trigger a re-audit.

Independence rule: the key author and the judge must be separate from the skill; the judge is reference-guided so it conforms to the human key rather than re-deriving taste.

## 10. Phased plan

- **Phase 0 — prove the loop.** 2 scenarios (one calibration-up trap, one calibration-down trap). Author keys via §9 bootstrap. Stand up the strategy-only arm (producing a markdown strategy doc) + reference-guided judge in stub mode.
- **Phase 1 — validate the instrument.** Live noise-floor (≥3×) + judge↔human agreement audit on those 2. Fix rubric/keys until the judge tracks humans and the floor is known.
- **Phase 2 — scale the dataset.** Grow to ~6–8 scenarios spanning the matrix (low-crit throwaway, C3 algorithmic, C3+ stateful/protocol, high-volatility UI, distributed/concurrent, long-lived institutional). Re-audit.
- **Phase 3 — wire version A/B.** Use it to retroactively score the MBT-card addition vs the prior skill.

## 11. Decisions for you before Phase 0

1. **Dimensions** — keep the seven in §4, or trim/add? (`calibration` and `documentation_quality` are the two load-bearing ones; the rest are adjustable.)
2. **Rung bands granularity** — bands per technique (richer, more authoring) vs a single overall calibration verdict per scenario (coarser, cheaper to author). Start coarse and refine?
3. **First two scenarios** — use the suggested admin-CLI (down) + landing-page (up) traps, or pick from real history you have in mind?
4. **Judge model** — same model as the skill arm, or a different one for independence? (Cost vs independence tradeoff.)

**Settled (non-goal):** rich-HTML output. The artifact is markdown so assurance-strategist is the only variable; folding in planning-doc/pd-components would make the eval test a composition. Evaluating the assurance-strategist + planning-doc rich-doc rendering, if ever wanted, is a separate eval — not this one.

---

## 12. Revision (2026-06-28): blind differential, not rubric scoring — supersedes §3–§5

> A grilling (`docs/grilling/grilling-log.md`) reshaped the instrument. **[ADR-0001](adr/0001-strategy-eval-blind-differential-not-rubric.md)** is the decision; this section records the delta. Sections 1–2 (strategy-only, markdown, calibration-is-the-thing) still hold. Sections **3 (answer-key dataset), 4 (decomposed rubric), and 5 (reference-guided judge) are superseded** by what follows. Section 1's `plan.html` discussion is already resolved to markdown.

**Why the change.** The eval's purpose is to **diagnose where the skill is weak**, run a few times during active development, and — decisively — its job is to defeat **self-delusion** about the skill's quality. That makes rubric-scoring self-defeating: grading against an answer key *we* wrote, scored by an LLM *we* prompted, is a mirror — it can only confirm the skill matches our taste, which is the delusion. Independence has to come from outside our judgment.

**The instrument (replaces §3–§5).**

- **Blind differential.** Per scenario, generate a strategy WITH and WITHOUT the skill (markdown, skill installed alone — §1's isolation unchanged), anonymise both arms.
- **Holistic blind judge.** A blind LLM playing "senior test architect" picks the better strategy and writes, *in prose*, where the weaker one falls down. No decomposed dimensions (§4 dropped); no per-scenario answer keys (§3 dropped); no reference-guided grading against a human key (§5 dropped).
- **Independence = baseline + blinding.** The no-skill arm is the stick that can't be rationalised away; the blinding removes our thumb from the scale. A blind LLM-expert is sufficient — independence is structural, not a matter of the judge's pedigree.
- **Output = a diagnosis.** Which arm wins across scenarios + the recurring weaknesses the judge flags, feeding a *find-a-weakness → fix → re-run* loop. This is the trust mechanism (per the grilling: trust is earned when the eval finds a real weakness you then fix).

**What survives.** Strategy-only + markdown + single-variable isolation (§1). Calibration as the quality that matters (§2) — but now *judged holistically by the blind expert*, not scored as a dimension. Hybrid scenario sourcing (§9: mine real briefs + hand-author traps) — the traps remain valuable as scenarios where a blind judge can reward the arm that resists over-/under-engineering. The phased plan (§10) and harness reuse (§8) hold, minus the answer-key/rubric authoring.

**Validation (replaces §7's judge↔human audit).** Noise floor still applies (≥3 blind A/B runs — does the verdict hold?). The judge↔human-agreement audit is replaced by a **blinding-leakage check**: ask the judge to guess which arm is the skill arm; if it reliably can, it may be rewarding the skill's house style (longer, explicit rungs) over substance. This is ADR-0001's accepted risk — mitigations: normalise formatting before judging, instruct the judge to score substance not length, or measure leakage directly and discount it.

**Open (for `/new-solution`).** The exact judge prompt and the house-style-leakage neutralisation; whether the lightweight-anchor fallback (§3.2 reduced to "expected criticality + traps") is ever needed if the blind judge proves unreliable.
