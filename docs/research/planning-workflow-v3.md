---
hash: "2238f7ec"
id: "planworkflow-v3"
read_when: "redesigning the planning workflow (new-task/new-solution/new-plan) for cross-stage context handoff, or reviewing the v3 problem analysis from the 11-run trace"
summary: "Working notes for a v3 planning-workflow redesign: problems found in the current new-task/new-solution/new-plan pipeline (no cross-stage context handoff, duplicate file reads) and proposed directions."
title: "Planning Workflow v3"
---

# Planning workflow v3

## Problem

What's wrong with the current planning workflow (from the 11-run trace):

- No cross-stage context handoff — #1. /new-task → /new-solution → /new-plan re-explore from scratch instead of consuming the prior stage's reports (same files re-read 4–6×).
- Intra-batch duplicate reads. Parallel explorers in one batch re-read the same hub files.
- Re-derivation of identical conclusions. Same fact recomputed by 2–3 explorers via separate work.
- No shared file/symbol index. Every explorer independently rebuilds its own map of the same domain — the repetition, not the search method, is the gap.
- Task-agnostic doc/convention bundles re-fetched per task. The same testing-architecture.md/backend-structure.md set pulled every run, never cached.
- Serial stragglers. Same-dimension explorers fire 15–20 min apart instead of as one parallel batch.
- Mega-prompt explorers. 12–18-item prompts → 3–4M tokens, full-file Reads where snippets suffice.
- No consistent fan-out policy. 0 explorers on some runs, 7 on others — no rule for when fan-out is warranted.
- Measurement gaps. totalTurnDurationMs=0 (can't isolate work-time); non-skill explorers have empty intent metadata.

We want to build a new version with these goals:
- Higher throughput, through efficiency, parallel execution, etc.
- Higher autonomy. The agent should only require human input on questions it can't answer itself.

What could this look like?

## Proposed improvements (ranked best → worst)

Mapped to the problem list above and the 2026 SDD research. Two coherent tracks: an
**efficiency** project (#1, #2, #4 — build the index once, consume it everywhere, fan out
by rule) and an **autonomy** project (#3, #5, #7 — calibrated gates + external verification
+ telemetry to trust them). Do them in that order.

<!-- UNRESOLVED(P1): Auto-proceed is ordered before its safety controls
REVIEW: The ranking says to do #3 before #5 and #7, but #3 widens the autonomous envelope while #5 supplies the independent analyzer and #7 supplies the success-rate/review-time telemetry needed to know whether widening is safe. Executed literally, this removes unconditional human gates before the replacement controls exist, which is exactly the DORA-style "more autonomous output + unchanged review = moved bottleneck" failure mode the doc later cites. The ordering should make the analyzer and measurement floor prerequisites for any auto-proceed rollout, or explicitly scope #3 to a non-production experiment until #5/#7 are in place.
-->

### 1. Persistent, cached context artifact every stage reads first ⭐
Fixes 6 of 9 problems: no cross-stage handoff (#1), duplicate reads, re-derivation,
task-agnostic bundles re-fetched, no shared index.

<!-- UNRESOLVED(P2): Problem coverage is overcounted
REVIEW: This claims six of nine problems are fixed, but the sentence names only five categories, and at least one of them is not actually fixed by a persistent artifact alone. A cached `context.md`/index can reduce duplicate reads and re-derivation, but it does not by itself stop intra-batch duplicate hub-file reads unless explorers are prevented from re-reading or the coordinator deduplicates their read plan. The mapping should distinguish "directly fixes" from "helps if combined with #2/coordinator policy"; otherwise #1 is ranked on inflated coverage.
-->

Today each stage (`new-task → new-solution → new-plan`) re-explores from scratch and
`context.md` is written but never consumed downstream. Two artifacts:

<!-- UNRESOLVED(P1): `context.md` consumption claim is false
REVIEW: The current workflow does consume `context.md` downstream. `.agents/skills/new-plan/SKILL.md` says "Read plan.html and context.md" in the summary, step 1 reads both files, step 2 merges history into `context.md`, and phase 2 designs execution phases using all tabs plus `context.md`. The real gap may be that `/new-solution` cannot reuse a prior context artifact because it creates the first one, or that subagent reports are not reused, but the statement as written invalidates the top-ranked diagnosis.
-->

- **Per-task `context.md`** with an explicit "known / missing" header. Every stage reads it
  and only fills gaps — append, never re-derive.
- **Repo-level persistent index** (DeepWiki/RAG-style, checked in, e.g. `docs/index/`): the
  file/symbol map plus task-agnostic bundles (testing-architecture.md, backend-structure.md).
  Built once, cached across tasks, refreshed on staleness — not pulled every run.

Mostly process discipline, not new infra. Backing: persistent version-controlled spec/context,
Explore-returns-summaries, Augment Context Engine.

<!-- UNRESOLVED(P2): Persistent repo index is treated as low-infra without addressing staleness
REVIEW: A checked-in repo-level symbol/context index is new infrastructure, not mostly process discipline: it needs generation ownership, invalidation rules for code/docs changes, merge-conflict behavior, provenance, and a policy for generated content in review. The doc names "refreshed on staleness" but does not define how staleness is detected or enforced. Without that, the index can become a high-trust stale summary that makes plans less accurate than direct source reads.
-->

### 2. One read-only Explore pass: single batched fan-out, snippets not full files
Fixes mega-prompts (3–4M tokens), intra-batch duplicate reads, serial stragglers.

Mirror Claude Code's Haiku Explore subagent: a coordinator builds the index once, hands the
same map to all explorers in a single parallel batch (no 15–20-min stragglers), explorers
return summaries/snippets not full-file Reads. ~40% main-session token savings reported.
Composes directly with #1.

### 3. Calibrate the two hard-stops by (uncertainty × blast radius); go on-the-loop ⭐
Fixes the autonomy goal directly.

Both gates (Verification, Solution) are currently unconditional human hard-stops. Replace with:
- **Low uncertainty × low blast radius** (reversible, additive) → auto-proceed with documented
  assumptions; emit the artifact for async comment, don't block.
- **High uncertainty or irreversible** (auth, schema/data migration, public API) → keep human
  sign-off.

Antigravity "comment-don't-block" + Thoughtworks "human-on-the-loop." Put gates behind flags so
the autonomous envelope widens as success rates climb. Adopt the principle, not the literal
Google-Doc UI (our CLI can't do live commenting).

<!-- UNRESOLVED(P2): Async comments need a CLI-specific backpressure model
REVIEW: The section acknowledges that the literal live-comment UI is unavailable, but it does not replace the missing mechanism. In Antigravity-style async review, comments can be incorporated while work continues; in this CLI/doc workflow, auto-proceed means reviewer feedback may arrive only after Solution, Plan, or even execution work has already built on the earlier artifact. The strategy needs an explicit tradeoff and control, such as a timeboxed comment window, branch/stage pause points, rework budget, or rule that async comments can only be non-blocking below a defined blast-radius threshold.
-->

### 4. Explicit fan-out policy
Fixes "0 explorers on some runs, 7 on others."

A ~5-line written rule: one explorer per independent dimension, scaled by (uncertainty × blast
radius); cap batch size; default to 0 for straightforward tasks. Trivial; kills the inconsistency.

### 5. Analyze gate + refutation subagent (external verifier)
Replaces line-by-line review; enforces generator ≠ verifier.

Add a cross-artifact consistency gate before handoff: schema/template validator → LLM-as-judge
in an isolated context against a rubric → a fresh subagent that tries to refute the plan/AC. We
already have `review-task` + `request-*-review`; formalize them into a named `analyze` gate. The
DORA caution (more autonomous output + unchanged review = moved bottleneck) is why this matters.

### 6. Self-validating plans: generate checks from acceptance criteria
Reduces human reading per plan.

We already have `<pd-ac>` and `assurance-strategist`. Tighten the link so AC (GIVEN/WHEN/THEN)
emit machine-checkable `<pd-verify>` checks automatically. A plan that ships its own checks needs
far less gatekeeping.

<!-- UNRESOLVED(P2): Self-validating plans overstate current primitives
REVIEW: The current completion-contract design uses `pd-ac-check-*` elements nested inside `<pd-ac>` plus a deferred `pd-verify` CLI; there is no `<pd-verify>` check element. More importantly, `docs/ac-completion-contract-design.md` and epic-001 explicitly say the execution engine, adapters, producers, freshness/provenance, pytest wiring, and executor gate are follow-ons. Framing this as "we already have `<pd-ac>` and assurance-strategist; tighten the link" understates a substantial safety-critical build, including command-execution safety and false-proof risks.
-->

### 7. Fix the measurement gaps (enabling, not direct)
Fixes `totalTurnDurationMs=0`, empty intent metadata.

Necessary to run #3 honestly — on-the-loop monitoring needs review-time-per-PR and
task-success-rate signals. Ranked here because it enables the autonomy moves rather than
improving the workflow itself.

### 8. Constitution discipline (3–5 principles per task) — low leverage for us
CLAUDE.md is already tight. One line: inject only task-relevant principles into each planning
prompt rather than the whole file. Don't over-invest.

### Worst / explicitly skip
- **Adopting OpenSpec or Spec Kit wholesale.** We already have the converged shape (`plan.html`
  as a persistent multi-tab artifact). Swapping harnesses is a rewrite for marginal gain — mine
  them for patterns (propose→apply→archive isolation, `validate --strict`), don't migrate.

<!-- UNRESOLVED(P2): OpenSpec pattern appears stale or cross-wired
REVIEW: The `validate --strict` example does not match the current Fission-AI/OpenSpec README I checked: the documented workflow is `/opsx:propose`, `/opsx:apply`, `/opsx:archive`, with verification surfaced as `/opsx:verify` in the expanded workflow, not `openspec validate --strict`. If `validate --strict` is meant to come from another SDD harness, name that source separately; otherwise this recommendation will send implementers looking for a command/pattern OpenSpec no longer documents.
-->

- **The literal Antigravity async-comment UI.** Not feasible in a CLI harness. Take the policy,
  drop the mechanism.

## Solution steps

[Ignore what is above if it contradicts this below, above is research gathering...]

Before:

**Legend:** 🛑 = human hard-stop gate · 🔀 = subagent fan-out · ▸ = action

0. ▸ User describes feature/fix
1. **`/new-task`**
   1. ▸ Scan skills + read project docs
   2. ▸ Create `plan.html` + Requirements tab
   3. ▸ Resolve Open Questions
   4. 🛑 **GATE — Hard-stop:** review Requirements
2. **`/new-solution`**
   1. *Stage 1 — Context gathering*
      1. 🔀 Fan-out: **CB1 Code** + **CB2 Docs** (2 parallel subagents)
      2. ▸ Write `context.md`
      3. ▸ Impact analysis
   2. *Stage 2 — Verification*
      1. ▸ Write Verification tab
      2. 🛑 **GATE — Hard-stop 1:** review Verification
   3. *Stage 3 — Solution*
      1. 🔀 Fan-out: 1 subagent per approach (parallel; ambiguous tasks only)
      2. ▸ Write Solution tab
      3. ▸ Validate assumptions
      4. 🛑 **GATE — Hard-stop 2:** review Solution
3. **`/new-plan`**
   1. *Phase 1 — Enrich context*
      1. 🔀 Fan-out: **CB3 History** (1 subagent)
      2. ▸ Impact analysis + merge into `context.md`
   2. *Phase 2 — Plan*
      1. ▸ Design phases + write Plan tab
   3. *Phase 3 — Traceability*
      1. ▸ Backfill `pd-ac` traceability
      2. 🛑 **GATE — Hard-stop 3:** review Plan — planning complete
4. ▸ Handoff → `/commit-task` → `/execute-task`

Four human hard-stops across three skills; three subagent fan-outs, none reusing the
others' raw reports. `context.md` is the only cross-stage carrier.

After (proposed — stage one):

Scope: the two no-risk velocity wins only — **batch the fan-outs** (kill serial
stragglers) and **preserve raw reports** (stop re-exploring). Gates stay human for now;
calibrated auto-proceed is deferred to stage two because it needs the external verifier
and telemetry in place first (see ranked items #3/#5/#7). Changes marked ✦.

**Legend:** 🛑 = human hard-stop gate · 🔀 = subagent fan-out · ▸ = action · ✦ = changed

0. ▸ User describes feature/fix
1. **`/new-task`** *(unchanged)*
   1. ▸ Scan skills + read project docs
   2. ▸ Create `plan.html` + Requirements tab
   3. ▸ Resolve Open Questions
   4. 🛑 **GATE — Hard-stop:** review Requirements
2. **`/new-solution`**
   1. *Stage 1 — Context gathering*
      1. ✦ ▸ **Fan-out sizing rule:** N explorers = independent dimensions, scaled by
         (uncertainty × blast radius); 0 for straightforward tasks; cap the batch
      2. ✦ 🔀 **Single batched fan-out** — fire all explorers (CB Code/Docs/…) in *one*
         parallel round, no 15–20-min stragglers
      3. ✦ ▸ Persist **raw reports** to `reports/` (not just the distilled `context.md`)
      4. ▸ Write `context.md` (distilled index over the raw reports)
      5. ▸ Impact analysis
   2. *Stage 2 — Verification*
      1. ▸ Write Verification tab
      2. 🛑 **GATE — Hard-stop 1:** review Verification
   3. *Stage 3 — Solution*
      1. ✦ 🔀 Single batched fan-out: 1 subagent per approach (ambiguous tasks only);
         reuses Stage-1 raw reports instead of re-exploring
      2. ▸ Write Solution tab
      3. ▸ Validate assumptions
      4. 🛑 **GATE — Hard-stop 2:** review Solution
3. **`/new-plan`**
   1. *Phase 1 — Enrich context*
      1. ✦ ▸ Read existing **raw reports** + `context.md` first; CB3 History fills only
         the git-history gap (no re-exploration of code/docs already covered)
      2. ▸ Impact analysis + merge into `context.md`
   2. *Phase 2 — Plan*
      1. ▸ Design phases + write Plan tab
   3. *Phase 3 — Traceability*
      1. ▸ Backfill `pd-ac` traceability
      2. 🛑 **GATE — Hard-stop 3:** review Plan — planning complete
4. ▸ Handoff → `/commit-task` → `/execute-task`

Net effect: same four gates (autonomy unchanged in stage one), but fan-outs collapse to
one parallel round each and downstream stages consume prior raw reports instead of
re-reading the codebase 4–6×. Velocity win is wall-clock (no stragglers) + fewer
redundant explores; risk is ~zero since no gate is removed.

After (proposed — overlap model):

The bigger swing. Core insight: **overlap machine work with human think-time.** Today
the agent stops dead while the user answers questions (hours of wall-clock). Instead, the
moment the questions are posed, the agent keeps working — light context scan now, deep
fan-out as soon as answers land — and collapses the four gates to **one** final review.
The human stays in the loop by *answering questions*, not by gatekeeping each stage.

Operating rules:

- **Questions are the steering wheel.** Agents write open questions into the Requirements
  tab as `pd-question` elements, each with a `recommendedAnswer` (the agent's lean).
- **No hanging.** The user reads all questions in one pass and answers what they care
  about. **Unanswered = "agent, do what you think is best"** → proceed on the
  `recommendedAnswer`. We never block waiting for a specific answer.
- **Stages auto-advance.** No explicit `/new-solution` or `/new-plan` invocation — once a
  stage's exit condition is met, the next begins automatically.
- **One gate, at the end.** The user reviews the finished Plan. If they're unhappy, or an
  answer invalidates part of the solution/plan, we **rerun only the affected parts** (see
  Phase B), not the whole pipeline.

**Legend:** 🛑 = the single human gate · ⟳ = auto-advance (no prompt) · ‖ = runs in
parallel · 🔀 = subagent fan-out · ▸ = action · ✦ = key change vs. today

1. **`/new-task`** — pose questions, work while the user thinks
   1. ▸ Scan skills + project docs
   2. ‖ ✦ **In parallel:**
      - ▸ Write `plan.html` + Requirements tab; open questions as `pd-question` +
        `recommendedAnswer`
      - 🔀 ✦ **Light context gather** (concurrent with the user reading questions): scan
        files/code, build a high-level "where to look" map → `context.md`
   3. ⟳ ✦ **Exit when** every question is answered *or* left blank (blank → use the
      `recommendedAnswer`). No `/new-solution` step — advance automatically.
2. **`/new-solution`** *(auto-triggered)* — deep fan-out, draft solution
   1. 🔀 ✦ Team of agents fan out **using the light map + the answers** (consume Stage 1's
      reports — don't re-explore)
   2. ▸ Agents may append new `pd-question`s with `recommendedAnswer`, but ✦ **do not
      wait** — proceed on the leans
   3. ▸ Draft Verification + Solution tabs
   4. ⟳ ✦ Auto-advance to plan (no gate here)
3. **`/new-plan`** *(auto-triggered)* — write the plan
   1. ▸ Design phases + write Plan tab; backfill `pd-ac` traceability
   2. 🛑 ✦ **THE GATE (only one):** user reviews the finished Plan
4. **On the gate:** ✦ if happy → handoff to `/commit-task` → `/execute-task`. If unhappy,
   or a late/changed answer invalidates part of the work → ⟳ **rerun only the affected
   parts** and re-present.

Build order:

- **Core — overlap + auto-advance (cheap, almost all of the value).** Parallelize the
  light scan with question-answering; auto-advance on the "all questions answered-or-blank"
  signal; one final gate; lean on `pd-question`/`recommendedAnswer` for the no-hang
  behavior. No dependency graph required — this is the whole model in practice.
- **Later, if needed — partial rerun.** When a late answer or gate edit invalidates part of
  the work, rerun only the affected parts. Start coarse (rerun the affected stage). In
  practice plans rarely get rewritten — first instinct is usually right — so this is a
  nice-to-have, not a prerequisite. Build on the `pd-ac` traceability skeleton if/when it
  earns its keep.

Why the single gate is fine: plans rarely get rewritten in practice, and the human still
steers continuously by answering questions, so a bad early assumption usually surfaces in
the answers — not at the end. The rare full-rewrite is cheap enough to absorb without
building dependency tracking up front.

Refinement — run solution + plan in the background, keep the main agent interactive:

This completes the overlap insight. Don't just overlap machine work with question-answering
time — overlap it with the user's **entire ongoing thought stream**. The agent the user
talks to stays interactive; the heavy solution + plan work runs in **background agents**.
The user keeps posting answers, ideas, and corrections while those agents work, and nobody
blocks. (This is the "comment-don't-block" pattern: the main agent is the doc you keep
commenting on; the background agents are the workers.)

- **Main agent = thin interactive orchestrator.** Stays responsive; routes the user's new
  messages into a steering buffer; spawns and monitors the background solution/plan work;
  fires reconciliation when it completes.
- **Background = `/new-solution` + `/new-plan`.** Run as background agents on the current
  answers/assumptions. They never wait on the user.
- **Deferred reconciliation, not mid-flight interruption.** Let background phases finish;
  collect the user's deltas during the run; at the end, **rerun only the phases whose
  inputs a late message changed.** Each phase records which answers/assumptions it consumed
  so the orchestrator can tell what a new message dirties (kept broad for now).
- **Why this is cheap:** wasted background compute when the user changes their mind costs
  tokens, not wall-clock — and the user is never blocked. Net velocity is the full
  solution+plan time folded under the user's think-time.

So the single gate becomes: present the finished Plan **plus** any phases the orchestrator
re-ran to absorb late input. Same one human checkpoint; the rest is background.

## Human notes

- I dont read the outputs of /new-plan
- I do care about the outputs of new-task and new-solution
- I want the context building to be async whilst im answering questions

So think new flow looks like, in psudocode

---
const requirements = userInput("/new-task [user requirements]")
const quickDocSweep = Explore("Find relevant docs for this task in ./docs...")
const quickCodeSweep = Explore({
  prompt: "Explore high level architecture, file structure, symbols that might be related to this task",
  additionalContext: [quickDocSweep]
});

const quickContext = quickDocSweep + quickCodeSweep

parallel([
  Agent({
    prompt: "Create new task directory with a plan.html file, fill in the requirements as you understand them so far",
    additionalContext: [quickContext]
  }),
  Agent({
    prompt: "Create a set of clarifying questions for the user, insert them into the doc, notify the user as soon as you're done",
    additionalContext: [quickContext]
  }) // this one must be able to notify the user, even before the top agent has finished
])

---
1. /new-task [user provides requirements]
2. Agent does quick high level context sweep, focussed on:
    - High level documentation (docs/concepts/, docs/meta.md, CLAUDE.md, etc)
    - High level code sweep ()
