---
hash: "54460864"
read_when: "picking up a past grilling session, or checking what was decided (and why) under interrogation"
summary: "Append-only log of grill-me pressure-testing sessions: each round's questions, the answers given, and the decisions/ADRs they produced."
title: "Grilling log"
---

# Grilling log

Append-only. Newest at the bottom. One section per round.

## 2026-06-28 — assurance-strategy-eval (task 006): what is the eval for?

**Context:** Grilling task 006's three open questions (grader dimensions, answer-key
granularity, judge-model independence). The user couldn't answer them, so we reframed: those are
*architecture* questions, unanswerable until the eval's *purpose* is pinned. Intent: uncover what
the user actually wants the eval to be for. Round 1 attacks purpose, not architecture.

**Q — What decision does the eval's output drive?:** Diagnose where the skill is weak — wants a
per-dimension, per-scenario breakdown pointing at specific weaknesses (rich dimensions,
per-technique granularity; human reads the detail, automation matters less).

**Q — How often will it run?:** A few times during active dev, then rarely — a development aid,
not a permanent gate; can tolerate more manual effort per run.

**Q — What bad outcome is it preventing?:** Self-delusion about quality — "I've talked myself
into the skill being great with zero independent evidence." The eval is a reality check.

**Reading:** Resolves Q-1 toward *keep rich dimensions* and Q-2 toward *per-technique
granularity* (both opposite to the plan.html's "start coarse" lean). But Q3 (self-delusion)
collides with Q-3's recommendation (same-model reference-guided judge): grading against a rubric
the user wrote, scored by an LLM the user prompted, may just mirror the user's taste back — the
exact delusion feared. Independence of the measuring stick is now the load-bearing assumption.
Round 2 attacks it.

## 2026-06-28 — assurance-strategy-eval: where does the independent signal come from?

**Context:** Round 1 exposed that the eval grades against a rubric the user authored — a mirror,
not independence, which the self-delusion fear makes fatal. Round 2 attacks the independence of
the measuring stick and what evidence would actually earn trust.

**Q — Where does the independent signal come from?:** Blind differential vs no-skill — generate
strategies with and without the skill, anonymise, grade blind. The no-skill baseline (not the
user's rubric) is the independent stick.

**Q — What evidence would earn trust (win condition)?:** "It found a weakness I then fixed" —
trust comes from the diagnostic loop actually working once, not from a passing score.

**Q — Is right-sizing the quality you care about?:** No — real quality = "a senior test
architect would endorse this strategy": a holistic verdict, NOT six decomposed dimension scores.

**Reading:** Big pivot from the plan.html / design-doc instrument. Independence now comes from
*blind differential vs no-skill* + a *holistic expert judge*, NOT from human-authored answer
keys — which may now be unnecessary. The three task-006 open questions largely DISSOLVE: Q-1
(7 dimensions) → no, one holistic verdict + prose weakness-flagging; Q-2 (key granularity) →
moot, no per-scenario keys; Q-3 (judge independence) → yes, strongly (blind, ideally a different
model). BUT a contradiction to resolve: Round 1 wanted a rich per-dimension/per-technique
breakdown; Round 2 wants a single holistic verdict, not decomposed scores. Round 3 resolves the
contradiction + whether the answer-key dataset survives + who the "expert" is.

## 2026-06-28 — assurance-strategy-eval: lock the instrument

**Context:** Round 3 resolves the Round-1-vs-Round-2 contradiction (decomposed dimensions vs
holistic verdict), and confirms whether answer keys and a human judge survive the pivot to blind
differential.

**Q — Decomposed dimensions or holistic verdict?:** Holistic verdict + prose weaknesses — the
diagnosis is the expert naming what's weak in prose, NOT a 7-number grid. The two rounds
reconcile: the "breakdown" is prose, not scores.

**Q — Do the per-scenario answer keys survive?:** Drop them. The dataset is just the scenarios
(briefs); independence = blind baseline + expert judge. Kills the most taste-laden authoring —
which was the self-delusion risk anyway.

**Q — Is a blind LLM-expert enough, or human-in-loop?:** Blind LLM-expert is enough.
Independence comes from the blinding + the baseline comparison, not the judge's pedigree.

**Outcome:** Decision-complete. New instrument: per scenario, generate a strategy WITH and
WITHOUT the skill → anonymise → a blind LLM judge playing senior test architect picks the better
one and writes, in prose, where the weaker falls down. Output is a diagnosis (which arm wins +
recurring weaknesses) feeding a find-a-weakness→fix→re-run loop, run a few times during active
dev. No answer keys, no decomposed rubric. Recorded as ADR 0001. The three plan.html open
questions are answered by dissolution. Known accepted risk: blinding leakage (the skill's
house-style may let the judge tell the arms apart) — logged in the ADR.
