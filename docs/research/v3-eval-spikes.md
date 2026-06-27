---
hash: "b51b9851"
id: "v3-eval-spikes"
read_when: "scoping the 006-v3-eval-harness task or the NTM-driven A/B replay eval design — what's already proven (NTM driving, session retrieval, autoetl metrics, git checkout) vs what 006 must build from scratch"
summary: "Feasibility tech spikes (S0-S6) de-risking the v3 planning-eval A/B replay harness: which primitives are proven and reusable, and why the auto-eval substrate is docs-only so 006 must build the plumbing itself."
title: "v3 planning-eval — feasibility spikes"
---

# v3 planning-eval — feasibility spikes

Quick tech spikes run before codifying the `006-v3-eval-harness` task, to de-risk the
NTM-driven A/B replay design. Verdict: **feasible — the foundational primitives (NTM
driving, session retrieval, autoetl metrics, git checkout) are all real and proven.** But
the orchestration substrate we'd hoped to reuse (`auto-eval`) is **unimplemented — docs
only**, so 006 must build that plumbing itself from its spec, not extend a binary.

## Results

| # | Question | Verdict | Key finding |
|---|----------|---------|-------------|
| S0 | Existing harness to reuse? | ⚠️ **Blueprint, not code** | `~/src/auto-stack/auto-eval` is **docs only** — a PRD + a v1 spike spec, **zero source files**, no `auto eval` command, git history is a single docs commit. It's a vetted *design* for compile→run→score that already anticipates "two-arm replay" — valuable as a blueprint that cuts design risk, but there is **nothing to extend**. 006 implements the substrate from this spec. |
| S1 | Can we recover the human's turns? | ✅ Yes, w/ caveat | `auto search session get <id>` renders full transcripts with clean `<user index=N>` delimiters. **Caveat:** human turns are interleaved with machine-injected slash-command/skill boilerplate — corpus extraction needs a filter to isolate genuine human utterances. |
| S2 | Clean prior-commit checkout? | ✅ Yes, w/ gotcha | Parent of a feature commit is contamination-free (no impl, no plan). **Gotcha:** plan docs are committed *squashed with the implementation*, so derive the checkout boundary from the **session timestamp**, not the plan file's git history. |
| S3 | Can NTM drive a multi-turn agent? | ✅ **Proven** | `--robot-send` → `--robot-wait --wait-until=idle` → `--robot-tail` round-trips a real Claude agent (sent a prompt, got `● PONG`, returned to idle). This is the core runner mechanic. |
| S4 | Turn-boundary / question detection? | ✅ Works, 2 nuances | `wait-until=idle` fires at turn end; states are `WAITING/GENERATING/THINKING`. **Nuance 1:** reply text must be scraped from TUI chrome (`●` lines). **Nuance 2:** race — `idle` can return *before* generation starts, so the loop must confirm a `GENERATING` transition first. |
| S5 | Velocity metrics for free? | ✅ Yes | autoetl captures per-session `duration_ms`, `tool_duration_ms`, `total_tokens`, `message_count`, `error_count` — queryable via `auto search` / SQL. Full velocity axis, no manual instrumentation. |
| S6 | Per-arm skill isolation? | ⚠️ Yes, via compile | NTM has **no native skill-isolation flag**. But isolation is the **compile step's job** (auto-eval already A/Bs context by compiling it into the branch): drop v2 vs v3 skills into each worktree's `.claude/skills/`. **Unverified:** whether `CLAUDE_CONFIG_DIR` env propagates through `ntm spawn` — one follow-up micro-spike. |

## What the build actually is

Proven-real primitives we assemble (all tested above, all implemented):
- **NTM** — live multi-turn agent driving (`robot-send`/`wait`/`tail`) + native velocity metrics.
- **auto search / autoetl** — session retrieval + per-session metrics (parquet).
- **git** — clean prior-commit worktree checkout.

To build for 006 (none of this exists yet):
1. **Compile → run → capture plumbing** — implement from auto-eval's v1 spec (worktree compile,
   pluggable launch, output capture). The design is done; the code is not.
2. **NTM conversation loop** with race-free turn detection (confirm `GENERATING` before `idle`;
   scrape `●` reply lines from TUI chrome).
3. **Intent-corpus extractor + simulated-human agent** (filter human signal from injected boilerplate).
4. **Plan-quality + velocity scoring** dimensions.

So this is more of a from-scratch build than the first draft implied — auto-eval saves *design*
time, not *implementation* time.

## Residual risks (not fully spiked — for the 006 pilot)

- **Corpus extraction quality** — separating genuine human signal from injected command/skill
  boilerplate. Needs a real extraction pass on one session.
- **Simulated-human fidelity** — does answering only what the corpus determines (blanks → v3's
  "use the lean") produce sensible runs? Methodological; needs the 2–3 task pilot.
- **`CLAUDE_CONFIG_DIR` propagation through `ntm spawn`** (S6 tail).
- **Replay cost.** Real planning sessions are large (a sampled auto-stack session: 632 msgs,
  ~20 h span, 4×10⁸ tokens — an outlier, but full replays × arms × trials will not be cheap).
  Budget a cost ceiling and start with the smallest viable plans.
