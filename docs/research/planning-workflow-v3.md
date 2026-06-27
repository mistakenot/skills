---
hash: "f87541a0"
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
