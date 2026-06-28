---
name: eval-engineer
description: "Builds, runs, validates, and manages A/B evals for repo skills — replay real tasks, compare skill versions on cost and quality. Use when 'eval this skill', 'is the new version better', 'set up/benchmark an eval', 'A/B the skills', or before trusting a non-trivial skill change. Not for ad-hoc one-off test runs (just run the skill)."
---

# Eval Engineer

Build an evaluation harness for a skill so its value is **measured, not assumed**. The job
is to answer "does this skill (or this change to it) actually help?" with evidence — and to
do it without fooling yourself.

Two ideas sit under everything here:

- **The generator must not be its own verifier.** A skill that judges its own output, or an
  author who eyeballs a single run, will see what they hope to see. Evidence comes from an
  independent comparison and a measuring stick you've checked.
- **Calibrate the instrument before you read it.** Agent runs are non-deterministic. Before
  trusting *any* A/B number, measure how much the *same* setup varies run-to-run (the noise
  floor). A difference smaller than the noise is not a finding — it's weather. This single
  step is what separates a real eval from theatre, and it's the one people skip.

This skill is a playbook. It routes you to the right harness for your skill type and keeps
you honest about validation. Its worked reference implementation lives in `src/planning-eval/`
(a conversational-replay A/B for the planning workflow), with the methodology recorded in
`docs/planning-eval-validation.md`.

## When to build an eval

Build one when a skill's value isn't obvious by inspection and you'll change it more than
once: workflow skills, anything with cost/quality tradeoffs, anything where "is the new
version better?" will keep coming up. Skip it for skills with trivially checkable output, or
one-off scripts you won't iterate on — the eval would cost more than it returns.

## Step 1 — Scope the eval (answer these five)

1. **What skill, and which arms?** An *arm* is one version under test. Usual A/B: current
   vs proposed (e.g. `v2` vs `v3`). The arms must differ by **exactly one thing** — the
   variable you're studying — and nothing else (same fixtures, same simulated user, same
   limits). Uncontrolled differences are how evals lie.
2. **What's the task?** Prefer **real historical tasks** replayed from this repo's or a
   sibling repo's history over synthetic prompts — they match how the skill is actually used.
   See [references/fixtures-from-history.md](references/fixtures-from-history.md).
3. **What does "better" mean?** Almost always two axes: **velocity** (wall-clock, tokens,
   tool-time, fan-out) and **quality** (does the output satisfy the task). Decide the win
   condition up front — usually **quality-per-token**, or "cheaper at equal quality", not raw
   speed (a skill can look fast by doing less).
4. **Who plays the human?** If the skill is interactive, something must answer its questions.
   Start with a hand-authored script; graduate to a simulated-user agent later.
5. **What's the budget?** Real agent runs cost real tokens and minutes. A validated A/B needs
   ≥3 trials per arm (Step 4) — price it before you start.

## Step 2 — Pick the harness by skill type

Don't build harness plumbing from scratch; match the skill's interaction shape to a pattern.
Full mechanics and reference implementations in [references/harnesses.md](references/harnesses.md).

| Skill shape | Harness | Reference in this repo |
|-------------|---------|------------------------|
| **Conversational / multi-turn** (planning workflows, interrogation) — needs a live agent you can talk to across turns | **NTM-driven replay A/B**: host the agent in tmux, drive it turn-by-turn, replay a scripted human | `src/planning-eval/` |
| **Single-shot transform / generation** (format a doc, extract data, one-pass output) | **Headless `claude -p` two-arm**: isolated clean-room, one prompt, capture output | `docs/headless-claude-cli-evals.md`, `src/assurance/evals/` |
| **Skill *triggering* / description quality** (does the right skill fire?) | **Trigger evals**: should-trigger / should-not-trigger query set | skill-creator's description optimizer |

The non-negotiables, whichever you pick: **isolate the arm** (install exactly the skill
version under test — fully replace, don't overlay — so arms differ only by the variable),
**run outside this repo and out of git** (a tmp workspace, never polluting the source tree),
and **guarantee teardown** (a crash mid-run must not orphan sessions or worktrees).

## Step 3 — Build fixtures from real tasks

A fixture pins a real task to a reproducible starting point: a target repo, an **immutable
start SHA** (the state *before* the task was done — so the answer isn't sitting in the
checkout), the opening prompt, the human's steering turns, and run limits. Two authoring
methods (session-mined vs requirements-derived) and how to find clean start points are in
[references/fixtures-from-history.md](references/fixtures-from-history.md). Start with 1–2 fixtures; prove the loop before scaling.

## Step 4 — Validate the eval BEFORE you trust it

This is the step that makes the rest mean anything. Full method in
[references/validating-the-eval.md](references/validating-the-eval.md). The short version:

- **Noise floor** — run the *same arm* on the *same fixture* ≥3 times. Measure the spread in
  tokens/wall/quality. That spread is your detection threshold: a v2-vs-v3 difference smaller
  than it is indistinguishable from noise. (In the planning-eval baseline this was ~1.5–1.8×,
  driven by variable subagent fan-out — so single-run comparisons there are worthless.)
- **Quality floor** — confirm the output is reliably *complete/valid* across those runs (e.g.
  lints clean, has the expected structure), so quality variance doesn't masquerade as a skill
  effect.
- **Generality** — prove the harness works on a *second* fixture, so you're testing the skill,
  not one lucky task.

Only once you know the noise floor do you know how many trials per arm you need and how big a
difference counts. Skipping this is the cardinal eval sin.

## Step 5 — Run the A/B and read it honestly

Run **≥3 trials per arm**, compare **distributions (medians), not single runs**. Report both
axes. The win is **quality held-or-improved at lower cost** (quality-per-token) — a cheaper
arm that produces a worse plan isn't a win, and a richer arm that costs 2× for marginal
quality isn't either. Surface the cheapest discriminating proxy you found (in planning-eval,
`session_count`/fan-out tracked both cost and the thing under study) so future runs are quick
to read. Keep the full transcript + artifacts + metrics for every run — an eval you can't
audit is an assertion.

## Step 6 — Manage runs

Make it a reusable tool, not a one-off: a small CLI (`run` / `list` / `clean`), a workspace
outside the repo, per-run provenance (which fixture, arm, start SHA, sessions), and metrics
aggregated from the session corpus (sum the parent run **and its subagents** — fan-out is
real cost). `src/planning-eval/run.py` is a working model of all of this.

## Anti-patterns (each one silently invalidates the eval)

- **Trusting a single run.** Non-determinism makes one number meaningless. Always ≥3.
- **Arms that differ in more than one thing.** Different fixtures, prompts, or limits per arm
  → you measured the wrong variable.
- **Letting the skill grade itself**, or judging quality with the same model in the same
  context that produced it. Use an independent check (lint, separate judge, human).
- **Measuring speed only.** A skill looks fast by doing less; without a quality axis you'll
  reward exactly that.
- **Contaminated checkout.** If the finished work (the plan, the implementation) is present at
  the start SHA, the agent can copy it. Start strictly *before* the task existed.
- **Polluting the repo.** Arm work belongs in a tmp workspace, out of git.
