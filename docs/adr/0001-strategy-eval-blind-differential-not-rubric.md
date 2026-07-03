---
hash: "9af33f44"
id: "8e58737e"
read_when: "revisiting how the assurance strategy-quality eval (task 006) scores strategies, or why answer keys and dimension rubrics were dropped"
summary: "Decision to grade assurance-strategist via a blind with/without-skill differential judged by a holistic blind LLM expert — dropping human answer keys and decomposed dimension rubrics — because independence (baseline + blinding) is the only escape from self-delusion about the skill's quality."
title: "ADR-0001: Strategy eval — blind differential, not rubric scoring"
---

# Strategy-quality eval: blind differential + holistic expert judge, not rubric scoring

**Context.** Task 006 (`docs/tasks/006-assurance-strategy-eval`) and its design doc
(`docs/assurance-strategy-eval-design.md`) proposed grading assurance-strategist's strategies
against human-authored per-scenario answer keys on 6–7 decomposed dimensions, via a
reference-guided LLM judge. A grilling (`docs/grilling/grilling-log.md`, 2026-06-28) established
that the eval's purpose is to **diagnose where the skill is weak**, run a few times during active
development, and — most decisively — that the fear it hedges is **self-delusion** about the
skill's quality.

**Decision.** Replace rubric-scoring with a **blind differential + holistic expert judge**. Per
scenario, generate a strategy WITH and WITHOUT the skill, anonymise both, and have a blind LLM
judge playing "senior test architect" pick the better one and write — in prose — where the weaker
one falls down. The output is a diagnosis (which arm wins, plus recurring weaknesses), feeding a
find-a-weakness → fix → re-run loop. **Drop the human-authored answer keys** and the **decomposed
dimension rubric** entirely; the dataset is just the scenarios (hybrid-sourced: mined real briefs
+ hand-authored calibration traps).

**Why.** Grading against a rubric the author wrote, scored by an LLM the author prompted, is a
mirror — it can only confirm the skill matches the author's taste, which is exactly the
self-delusion feared. Independence has to come from outside the author's judgment: the **no-skill
baseline** is a stick that can't be rationalised away (if a blind judge can't prefer the skill
arm, the skill isn't adding value), and a **blind** A/B removes the author's thumb from the
scale. The author chose a holistic verdict + prose weakness-flagging over decomposed scores, so
the rubric machinery (and its hardest, most taste-laden authoring) is unnecessary.

**Considered options.** (1) Independent judge = a different model or a person with no rubric —
rejected as primary: a different LLM may share blind spots, a person is expensive; the *blinding +
baseline* does the independence work. (2) Outcome-based grading (does the strategy catch a real
bug?) — rejected: expensive, slow, and re-introduces implementation, the variable we cut. (3)
Keep lightweight answer-key anchors as a judge sanity-check — not adopted now, but the cheapest
fallback if the judge proves unreliable.

**Consequences.**
- The task 006 plan.html open questions (dimension count, key granularity, judge independence)
  are answered by dissolution, not by choosing among their options. The plan.html and design doc
  need rewriting to the new instrument.
- We lose per-dimension diagnostic precision and a fixed per-scenario stick; we accept prose
  weakness-flagging as the diagnosis instead.
- **Accepted risk — blinding leakage.** The skill's output likely has a recognisable house style
  (longer, more structured, explicit rungs/upgrade-triggers), so a blind judge may identify which
  arm is the skill arm and be swayed by style over substance. Mitigations to consider during
  build: normalise formatting before judging, instruct the judge to score substance not length,
  or measure leakage by asking the judge to guess which arm is which. If leakage proves
  material, revisit the lightweight-anchor fallback.
