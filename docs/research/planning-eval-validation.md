---
hash: "108ab3e0"
read_when: "designing the v2-vs-v3 planning A/B, deciding trials-per-arm, or interpreting planning-eval run variance"
summary: "Noise-floor, quality-floor, and generality validation of the planning-eval harness before building the v3 arm: three identical v2 runs show 1.5-1.8x spread driven by fan-out variance, so the A/B needs >=3 trials/arm and quality-per-token comparison."
title: "planning-eval — baseline validation"
---

# planning-eval — baseline validation

Before building the v3 workflow arm, we validated that the `planning-eval` harness can
actually *discriminate* — i.e. that a v2-vs-v3 A/B would measure signal, not noise. Three
checks: noise floor, quality floor, and generality. Verdict: **the eval works, but single
runs are not trustworthy — use ≥3 trials per arm and compare distributions.**

## 1. Noise floor — three identical v2 runs of fixture 008

| run | wall | turns | sessions (fan-out) | tokens | AC cards |
|-----|------|-------|--------------------|--------|----------|
| 1 | 787s | 6 | 3 | 17.3M | 7 |
| 2 | 1390s | 6 | **7** | 26.3M | 12 |
| 3 | 865s | 6 | 4 | 17.0M | 9 |

**Spread on identical inputs: 1.55× tokens, 1.77× wall.** The driver is **subagent
fan-out** — run 2 spawned 7 sessions vs 3–4. This is not random jitter; it's variable
*thoroughness*, and it's correlated: run 2 was the outlier on every axis at once (more
sessions → more tokens → more wall → more AC cards). It is also exactly the problem v3
targets (planning-workflow-v3 #8: "0 explorers on some runs, 7 on others — no consistent
fan-out policy"). The noise in the baseline is itself a symptom of what v3 fixes.

## 2. Quality floor — same three runs

All three: **lint-clean, 4 tabs, 3 phases.** Structurally v2 reliably produces a *complete*
plan. What varies is depth (7 / 12 / 9 AC cards), tracking the effort/fan-out variance.

## 3. Generality — second fixture (010-autosearch-co-change)

Authored via the **requirements-derived** method (its planning thread was fragmented). One
v2 run: complete, lint-clean, 4 tabs, **24 AC cards, 7 phases, 1142 lines**, 14.2M tokens,
1339s. Confirms fixture authoring + the run loop generalize beyond task 008, and that a
bigger task scales cleanly.

## Consequences for the A/B

- **N ≥ 3 trials per arm; compare medians/distributions, never single runs.**
- A single-comparison v3 win must exceed **~1.8×** to clear the noise floor; smaller real
  effects need the multi-trial distribution.
- **Velocity and quality are coupled** (more spend → more AC cards), so the win condition is
  **quality-per-token**, or "cheaper at equal completeness" — not raw speed alone.
- The fan-out count (`velocity.session_count`) is the cheapest single proxy for the noise and
  for what v3 should stabilise — watch it.

## v2 baselines (for comparison once v3 exists)

| fixture | trials | wall (median) | tokens (median) | sessions |
|---------|--------|---------------|-----------------|----------|
| 008-commit-session-link | 3 | 865s | 17.3M | 3–7 |
| 010-autosearch-co-change | 1 | 1339s | 14.2M | 4 |
