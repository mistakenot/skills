---
hash: "88b998ff"
id: "7fd7cb28"
read_when: "designing ambiguity or open-question detection for a planning/coding agent (choosing which underspecification signal to use), or reviewing the evidence behind sampling-divergence vs self-reported confidence"
summary: "Evidence review of externally-observable ways to detect ambiguity/underspecification in specs for LLM coding agents — sampling divergence, test concretization, generator–critic separation, value-of-information — and which are empirically backed vs under-tested."
title: "Detecting Ambiguity in Specs for LLM Coding Agents — Evidence Review"
---

# Detecting Ambiguity and Open Questions in Specs for LLM Coding Agents: What the Evidence Says

## TL;DR
- **The single best-supported "externally observable" ambiguity signal for coding tasks is sampling-based behavioral divergence — generating multiple candidate solutions and checking whether they disagree on concrete test inputs.** This is the core mechanism behind ClarifyGPT (FSE 2024), TiCoder (Microsoft Research), and semantic entropy (Farquhar et al., *Nature* 2024), and it reliably outperforms asking a model to self-report confidence, which is systematically overconfident and poorly calibrated (Xiong et al., ICLR 2024).
- **Of your six proposed methods, four have solid empirical backing** (sampling-variance/divergence, concretization-via-tests, generator–critic separation with an *external* verifier, and value-of-information/decision-relevance filtering); **grounding-before-escalating and structural-completeness checklists are intuitively sound and partially evidenced but under-tested as ambiguity *detectors* specifically.**
- **The biggest under-used levers you haven't listed:** (1) training/prompting for *selective* clarification so the agent knows *when not to ask* (Okanagan, ClarifyCoder, CLAM), (2) Bayesian-experimental-design / information-gain question selection (Kobalczyk et al., ICLR 2025 Spotlight), and (3) the mature requirements-engineering NLP literature on nocuous-vs-innocuous ambiguity, which directly formalizes "only flag ambiguity a real reader would trip over."

## Key Findings

1. **Self-reported confidence is the right thing to move away from.** Xiong et al. (ICLR 2024, "Can LLMs Express Their Uncertainty?", arXiv:2306.13063) find that when LLMs verbalize confidence, "the confidence levels primarily range between 80% and 100%, often in multiples of 5" while "the accuracy within each bin is much lower," and conclude that "consistency-based methods outperform the verbalized confidences in most cases, with particularly notable improvements on the arithmetic reasoning task." This directly validates the user's premise and points at sampling/consistency as the replacement.
2. **Sampling divergence works and is directly productized for code.** ClarifyGPT's "code consistency check" — sample N solutions, run them on generated test inputs, and treat output disagreement as the ambiguity signal — lifted GPT-4 Pass@1 from 70.96% to 80.80% on MBPP-sanitized.
3. **Concretization via tests is one of the strongest interventions.** TiCoder improved Codex Pass@1 on MBPP from 48.39% to 70.49% with a single user query (up to 85.48% with five), and a 15-programmer user study found participants "significantly more likely to correctly evaluate AI generated code" with "significantly less task-induced cognitive load."
4. **Self-critique alone is unreliable; external verification is what pays off.** Separating generation from verification helps only when the verifier is *sound* (tests, execution, a different tool), not when a model grades itself.
5. **Coding agents mostly *don't* ask when they should — but can be made well-calibrated.** On HumanEvalComm, base code LLMs generate code in over 63% of ambiguous cases without asking. Agent scaffolds and fine-tuning fix much of this.
6. **A rich, ignored literature exists in requirements engineering and IR/QA** — nocuous ambiguity, AmbigQA, clarifying-question generation, value-of-information — that directly addresses "which questions genuinely need a human."

## Details

### 1. Ambiguity as divergence / sampling variance (STRONG evidence)
The idea: generate a plan/answer multiple times (or across models) and use disagreement to localize underspecification.

- **Self-consistency (Wang et al., 2022, arXiv:2203.11171):** sampling multiple reasoning paths and marginalizing boosts GSM8K +17.9%, SVAMP +11.0%, AQuA +12.2%. Establishes that sampling variance carries real signal about model uncertainty. Caveat: a 2025 analysis ("Self-Consistency Is Losing Its Edge," arXiv:2511.00751) argues returns are diminishing on frontier models because single-pass accuracy is now high.
- **Semantic entropy (Kuhn, Gal, Farquhar, ICLR 2023; Farquhar et al., *Nature* 2024, doi:10.1038/s41586-024-07421-0):** clusters multiple samples by *meaning* (bidirectional entailment) and computes entropy over meaning-clusters. Detects confabulations with no task-specific data and beats naive entropy and other baselines on AUROC. Cost: the *Nature* work used ~10 generations per prompt plus quadratic entailment checks; follow-ups (Semantic Entropy Probes, arXiv:2406.15927; Bayesian estimation, arXiv:2504.03579) reduce this.
- **Direct application to code — ClarifyGPT (Mu et al., FSE 2024 / PACMSE; arXiv:2310.10996):** the "code consistency check" samples N solutions for a requirement, runs them on type-aware mutated test inputs, and if outputs diverge, declares the requirement ambiguous and generates targeted clarifying questions. Human eval: GPT-4 Pass@1 70.96%→80.80% on MBPP-sanitized (relative +16.83%). Automated eval across benchmarks: GPT-4 avg 68.02%→75.75%, ChatGPT 58.55%→67.22%. This is essentially "ambiguity = behavioral divergence across samples."

**Verdict:** Best-validated externally-observable signal for coding specifically. Recommend as your primary mechanism.

### 2. Structural completeness checklists / decision taxonomies (MIXED / PARTIAL evidence)
Checking a spec against an enumerated list of required decisions (data model, error states, auth, concurrency).

- The RE community has a long tradition of checklist- and pattern-based completeness and "requirements smells" checking, plus model-based completeness checking (comparing requirements against domain models/UML). Arora, Sabetzadeh & Briand (2019, *Empirical Software Engineering*) showed UML class/domain models display **near-linear sensitivity** to detecting missing and under-specified requirements when omissions are simulated.
- **Luitel, Hassani & Sabetzadeh (*Requirements Engineering* journal, 2024; arXiv:2308.03784):** use BERT's masked-language-model to predict masked terms and flag likely-missing terminology. On 40 PURE documents, with 15 predictions per mask, predictions hinted at **~38% of omissions (Coverage)** with **~12% Accuracy**; an ML filter (Random Forest) improved to ~48% precision in a high-incompleteness scenario, and full-training-set classification reached 84.1% accuracy / 76.4% precision / 67.0% recall. Two PhD-student evaluators judged 75% and 87.5% of non-exact matches useful (Cohen's κ = 0.44). Authors explicitly call it "a necessary first step," not proof of end-user usefulness.

**Verdict:** Completeness checking is real and evidenced in RE, but as a *taxonomy/checklist* driver for LLM coding agents it's largely unproven; the LLM-based completeness work is early and modest in accuracy. Use as a complementary recall-booster (a decision-taxonomy prompt), not the primary detector.

### 3. Concretization via tests / examples (STRONG evidence)
Have the AI write acceptance tests / concrete I/O examples first; unfillable or divergent cases are the ambiguity signal.

- **TiCoder (Lahiri et al., 2022, arXiv:2208.05950; user study Fakhoury, Lahiri et al., 2024, arXiv:2404.10100; TSE 2024):** interactive test-driven intent formalization. Generates tests that prioritize *points of ambiguity* (inputs where candidate solutions diverge) and asks the user to approve/reject. On MBPP with Codex, Pass@1 rose "from 48.39% to 70.49% with a single user query, and up to 85.48% with up to 5 user queries." A mixed-methods user study with 15 programmers found participants "significantly more likely to correctly evaluate AI generated code" and reporting "significantly less task-induced cognitive load." Automated eval also showed absolute Pass@1 gains of 22.49–37.71% (MBPP) and 24.79–53.98% (HumanEval), and generation of a passing functional test within an average of 1.69 queries for 90.40% of examples.
- Specification-by-example / test-first thus double as an ambiguity detector: divergent candidate outputs on the same input = underspecification. This is mechanistically the same signal as ClarifyGPT.

**Verdict:** Among the strongest and most directly actionable. Tests turn "silent assumptions" into observable pass/fail divergences.

### 4. Generator–critic separation (STRONG evidence, with an important caveat)
Use a separate critic pass to find gaps/assumptions.

- **Key caveat — self-critique is unreliable.** Stechly, Valmeekam & Kambhampati ("On the Self-Verification Limitations of LLMs on Reasoning and Planning," arXiv:2402.08115) found LLM self-verification often *worsens* performance due to false positives; gains come from a **sound external verifier**. Huang et al. found LLMs cannot reliably self-correct reasoning.
- **CRITIC (Gou et al., ICLR 2024):** LLMs self-correct well *only* when given external tool feedback (search API, interpreter, toxicity classifier); ablating the tool damages results. External verification, not introspection, is the active ingredient. CRITIC outperforms self-consistency on most tasks.
- **Generation–verification gap ("Mind the Gap," arXiv:2412.02674):** formalizes that verification is only reliably easier than generation with additional training; the gap is not universal.

**Verdict:** Adopt generator–critic separation, but the critic must be *grounded* (execution, tests, static analysis, a retrieval check) or a genuinely independent model/prompt — not the same model grading itself. This is well-supported.

### 5. Grounding before escalating (PLAUSIBLE, indirectly evidenced)
Resolve apparent ambiguity against the codebase/conventions before asking a human.

- **AmbigQA (Min et al., EMNLP 2020) and downstream work** show retrieved context materially improves handling of ambiguous questions; "Knowing but Not Showing" (2026) confirms retrieved context improves QA for both ambiguous and unambiguous queries.
- **Tree of Clarifications (Kim et al., EMNLP 2023, arXiv:2310.14696):** Retrieval-Augmented Clarification recursively disambiguates ambiguous questions using retrieved passages + self-verification pruning; beats fully-supervised baselines on ASQA Disambig-F1/ROUGE. Demonstrates that retrieval can *resolve* many apparent ambiguities without bothering the user.
- Direct evidence in the coding-agent setting (resolving against repo conventions specifically) is thin — this is more assumed than measured.

**Verdict:** Strongly plausible and consistent with the QA/RAG evidence; treat "grounding first" as a sound design principle but note the coding-specific empirical validation is limited.

### 6. Decision-relevance / value-of-information filtering (STRONG conceptual + growing empirical evidence)
Only ask if different answers would materially change the output.

- **Value of Information / Bayesian Experimental Design lineage:** Lindley (1956), Howard (1966), Russell & Wefald (metareasoning), Settles (active learning). Rao & Daumé III (2018) applied expected value of perfect information to rank clarification questions.
- **Active Task Disambiguation (Kobalczyk, Astorga, Liu, van der Schaar, ICLR 2025 Spotlight; arXiv:2502.04485):** frames clarifying-question selection as Bayesian Experimental Design — pick the question that maximizes expected information gain by *sampling the solution space* and seeing which questions best partition candidate solutions. Empirically beats reasoning "only in question space" on code generation (HumanEval, APPS) and a 20-questions task. This is exactly "ask only if answers change the plan," operationalized.
- **Modeling Future Conversation Turns (arXiv:2410.13788):** assign preference labels by simulating expected outcomes of future turns; +5% F1 on recovering interpretations and +3% accuracy on the *when-to-ask* judgment vs. context-only labeling.
- **SAGE-Agent / structured uncertainty (arXiv:2511.08798):** structured uncertainty for question selection gives 7–39% higher coverage on ambiguous tasks while *reducing* clarification questions 1.5–2.7×; uncertainty-weighted training boosted When2Call accuracy from 36.5%→65.2% (3B) and 36.7%→62.9% (7B). Introduces ClarifyBench.

**Verdict:** This is the principled frame for "which questions genuinely need a human." Strongly recommended; combine with sampling divergence (the samples give you the hypothesis space to compute information gain over).

### 7. Clarifying-question generation in NLP/IR/dialogue (STRONG, mature field)
- **AmbigQA (Min et al., EMNLP 2020):** ~50% of NQ-open questions are ambiguous; introduced disambiguated-rewrite task and AmbigNQ (14,042 questions).
- **CLAM (Kuhn, Gal, Farquhar, 2022, arXiv:2212.07769):** two-step selective clarification — first classify if ambiguous, only then ask. Closes most of the accuracy gap between ambiguous and unambiguous questions; models rarely ask spontaneously.
- **CLAMBER (ACL 2024, arXiv:2405.12063):** benchmark showing current LLMs fail to ask high-quality clarifying questions due to poor knowledge-boundary awareness.
- **Learning to Ask / NoisyToolBench (arXiv:2409.00557):** "Ask-when-Needed" prompting improves tool use under unclear instructions.
- **Preference elicitation, recommendation, "Ask-before-Plan" proactive agents:** growing subfield on when/what to ask.

### 8. Requirements-engineering ambiguity detection (STRONG, decades-deep, underused by ML practitioners)
- **Nocuous vs. innocuous ambiguity (Chantree, Nuseibeh, De Roeck, Willis, RE'06; Willis et al. 2008; Yang et al. 2010/2011):** the key concept — *nocuous* ambiguity is text different readers interpret differently; *innocuous* ambiguity has a shared reading and needs no clarification. This is precisely the "which ambiguities matter" filter the user wants. Heuristics (coordination matches, distributional similarity, collocation) build classifiers against multi-reader judgments.
- **Ezzini et al. (ICSE 2021):** domain-specific corpora detect coordination & PP-attachment ambiguity with **~80% precision, ~89% recall**, interpretation accuracy ~85% — ~33% better detection accuracy than generic-corpus baselines.
- **Ezzini et al. (ICSE 2022, TAPHSIR):** anaphoric ambiguity — best detector ~60% precision at 100% recall; best anaphora resolution ~98% success (SpanBERT).
- **Requirements Ambiguity Detection with LLMs — Industrial Study (Bashir, Ferrari et al., RISE/Mälardalen):** in-context learning with small open LLMs (Qwen-2.5 1.5B, Phi3-mini 3.8B, Llama-3 8B) on 3 railway datasets. 10-shot gave a **20.2% average improvement** over 0-shot; best F1 ~75.2% (Phi3-mini); human experts rated explanations ~3.84/5 on average.
- **ReqEval 2020 (NLP4RE):** shared task on referential ambiguity, 200-sentence dataset annotated by 5 annotators using the nocuous-ambiguity criterion. (Best-system leaderboard scores could not be verified.)

### 9–10. Benchmarks and coding-agent-specific findings (STRONG and growing)
- **HumanEvalComm (Wu & Fard, TOSEM 2025; arXiv:2406.00215):** modifies HumanEval to inject inconsistency, ambiguity, incompleteness; metrics = Communication Rate and Good Question Rate. "State-of-the-art Code LLMs generate code outputs in over 63% of ambiguous scenarios without seeking necessary clarifications" (with Pass@1 and Test Pass Rate dropping ~35–52% and ~17–35%). The **Okanagan** agent (ChatGPT-3.5) "increased Communication Rate and Good Question Rate by an absolute 59% and 5%, respectively," which "resulted in an increase in Test Pass Rate and Pass@1 by 25% and 15%, respectively." Key tension: agents that ask too much hurt clean tasks (Okanagan dropped Pass@1 from 65% to 27% on standard, well-specified problems).
- **ClarifyCoder (Wu & Fard, arXiv:2504.16331):** clarification-aware fine-tuning so a model learns *when to ask and when not to* — among the first to do both.
- **QuestBench (Google DeepMind + MIT, arXiv:2503.22674):** formalizes underspecification as a CSP missing one variable; models must pick the minimal necessary question. SOTA models saturate GSM-Q/GSME-Q but only reach **40–50% on Logic-Q and Planning-Q** — being able to solve a well-specified problem does *not* imply knowing what to ask.
- **Ask or Assume? (Edwards & Schuster, Univ. of Vienna, arXiv:2603.26233):** underspecified variant of SWE-bench Verified. An uncertainty-aware multi-agent scaffold (OpenHands + Claude Sonnet 4.5) that decouples underspecification detection from code execution hit **69.40% resolve rate vs. 61.20% single-agent**, nearly matching the fully-specified upper bound (70.80%), and showed *well-calibrated* asking (asks more on hard tasks, refrains on easy).
- **ClarEval, Dialogue SWE-Bench, ClarifyBench:** newer benchmarks specifically for clarification skill in coding/tool agents.

### 11. Semantic entropy / semantic uncertainty
Covered in §1 — Farquhar et al. (*Nature* 2024) and Kuhn et al. (ICLR 2023) are the anchors; the meaning-clustering step is what makes it work for free-form generation. Directly usable to score which parts of a plan are genuinely uncertain vs. cosmetically varied.

### 12. Other emerging techniques you haven't listed
- **Abstention / learning-to-defer:** "Know Your Limits" survey (arXiv:2407.18418), AbstentionBench (arXiv:2506.09038), ReDAct uncertainty-aware deferral for agents (arXiv:2604.07036), selective prediction (Geifman & El-Yaniv). Frames "ask a human" as a reject/defer option with formal machinery.
- **Structured uncertainty for tool-calling** (SAGE-Agent, §6).
- **Clarification timing** ("Ask Early, Ask Late, Ask Right," arXiv:2605.07937): *when* in a long-horizon trajectory to ask matters, not just whether.
- **Multi-turn bottleneck warnings:** "Clarification Is Not Enough" (arXiv:2605.25204) and "LLMs Get Lost in Multi-Turn Conversation" — even good clarification doesn't help if post-clarification answering is weak.

## Recommendations

**Stage 1 — Replace confidence scores with behavioral divergence (highest ROI, do first).**
Generate N (start with 3–5) candidate plans/solutions. For coding tasks, derive concrete test inputs and compare outputs (ClarifyGPT/TiCoder mechanism). Divergent behavior on a given input = a genuine open question; convergent behavior = resolve silently. Benchmark against your current confidence-score baseline on a held-out set of specs. *Threshold to change approach:* if divergence produces too many low-value questions, add Stage 3.

**Stage 2 — Make the critic external, not introspective.**
Add a separate gap-finding pass that is grounded: run the generated tests, do static/type checks, and retrieve repo conventions before surfacing anything. Do NOT rely on the same model self-grading (evidence says it adds false positives).

**Stage 3 — Add value-of-information filtering to decide *which* divergences become human questions.**
Use the sampled candidate solutions as your hypothesis space and select the question that best partitions them (Kobalczyk et al.'s information-gain approach). Only escalate a question if the candidate answers would materially change the plan. *Benchmark:* track "Good Question Rate" and unnecessary-question rate à la HumanEvalComm; watch that clean-task performance doesn't drop (the Okanagan failure mode).

**Stage 4 — Ground before escalating.**
Resolve apparent ambiguity against the codebase, existing conventions, and retrieved context first (Tree-of-Clarifications-style). Only questions that survive grounding go to the human.

**Stage 5 — Add a completeness taxonomy as a recall backstop.**
Prompt the critic with an explicit decision checklist (data model, error/edge states, auth/z, concurrency, persistence, API contracts, non-functional constraints) to catch *silent* omissions that divergence sampling misses (because all samples share the same blind spot). Import the RE "nocuous vs. innocuous" filter so you only surface omissions a real implementer would diverge on.

**Metrics to adopt:** Communication Rate, Good Question Rate (HumanEvalComm); question efficiency/coverage (SAGE-Agent); calibration of asking (Ask or Assume?); Pass@1 lift after clarification (TiCoder/ClarifyGPT).

## Caveats
- **Recency and provenance:** several of the most on-point items (Ask or Assume?, ClarEval, SAGE-Agent, Dialogue SWE-Bench, some 2026-dated arXiv IDs) are very recent preprints; treat their exact numbers as preliminary and not yet peer-reviewed. Farquhar/*Nature*, Wang/self-consistency, Min/AmbigQA, Kim/ToC, Lahiri/TiCoder, Mu/ClarifyGPT, Xiong/confidence, and Kobalczyk/ICLR are peer-reviewed or archival-stable.
- **Frontier-model drift:** self-consistency's edge is reportedly shrinking as single-pass accuracy rises; sampling-divergence may need calibration per model.
- **Cost:** sampling N solutions + running tests + a critic pass is materially more expensive than one confidence score. The evidence says it's worth it for correctness, but budget accordingly (semantic-entropy-probe-style cheap approximations exist).
- **The "ask too much" failure mode is real and measured** (Okanagan on clean tasks, dropping Pass@1 from 65% to 27%). Selective/decision-relevance filtering is not optional polish — it's what keeps the system usable.
- **ReqEval 2020 best-system scores are unconfirmed;** treat only the dataset design (nocuous-ambiguity criterion) as established.
- No single technique is sufficient; the evidence favors a *pipeline* (divergence → grounding → VoI filtering → external critic → completeness backstop).

This is a sharp question, and it cuts to something the previous research threads only touched obliquely. Let me pull what the literature actually says about *ranking* / *relative ordering* by uncertainty, as distinct from producing calibrated absolute grades — because the two come apart in an important way.This confirms the central distinction I want to draw out. Let me get one more angle on the specific ranking-vs-grading framing and how it plays with pairwise comparison.I have enough to give you a well-grounded answer. Let me synthesize this, because there's a clean and useful story here.

## The short version

The research draws a sharp line between two things LLM confidence scores are asked to do, and LLMs are much better at one than the other:

- **Calibration** (absolute grading): does "high confidence" actually mean ~90% correct? LLMs are bad at this — overconfident, clustered at round numbers, degraded by RLHF. This was the thrust of your first research sweep.
- **Discrimination / ranking** (relative ordering): if you sort items by the model's confidence, do the ones it's *more* confident about tend to actually be more correct than the ones it's *less* confident about? LLMs are meaningfully better at this.

These are measured by different metrics and they come apart empirically. Calibration is measured by Expected Calibration Error (ECE); ranking quality is measured by **AUROC** — literally the probability that a uniformly random correct example is ranked above a uniformly random incorrect example. Crucially, AUROC is independent of base accuracy and independent of any specific threshold — it only cares about ordering. And the two metrics don't move together: calibration (measured by ECE) evaluates the alignment between predicted uncertainty and actual correctness, while selective classification (measured by AUROC) evaluates how well uncertainty separates correct from incorrect predictions, and studies find these can diverge — some high-accuracy models (e.g., GPT-4.1) are poorly calibrated while still ranking reasonably.

The cleanest statement of the split comes from the identity-perturbation medical QA study: discrimination and calibration capture different failure modes, so a model may maintain (or even improve) ranking ability while its probability estimates become miscalibrated. That sentence is basically the answer to your question. Ranking survives conditions that wreck calibration.

## Why this matters for your workflow specifically

Your actual task is not "attach a trustworthy 73% to this open question." It's *triage* — decide which open questions to route to a human. Triage is a ranking-and-thresholding problem, not a calibration problem. You want the questions the model is genuinely least sure about to float to the top of the queue. That's exactly what discrimination measures, and it's the thing LLMs are comparatively good at.

This is formalized as **selective prediction** / the accuracy-rejection curve. The idea: selective prediction performance assesses a method's ability to discriminate between correct and incorrect grading decisions based on estimated confidence, using a curve that plots the accuracy of retained predictions as a function of the rejection rate. In your terms: as you send more of the top-uncertainty questions to a human, how fast does the accuracy of what's left (auto-accepted) climb? A model with good discrimination but terrible calibration will still give you a steep, useful curve. The absolute confidence numbers can be nonsense while the *ordering* still does real work.

So the reframe from your earlier messages holds up and gets sharper: don't ask "is this label calibrated," ask "does confidence rank-order my open questions well enough that skimming the top-k catches most of the real ambiguity." That's an AUROC/AUARC question, and it's the favorable regime.

## The stronger move: make it relative on purpose

Here's the part that's genuinely actionable and underused. If ranking is the strength, you can lean into it by asking the model for *relative* judgments rather than *absolute* ones — and the evidence says this is generally more reliable.

The core finding across LLM-as-a-judge research: relative judgments are easier than absolute ones, and pairwise prompting is known to reduce calibration variance relative to absolute scoring. The reason is structural and worth internalizing — absolute scores suffer from a per-rater offset problem that comparisons cancel out. As one treatment puts it, the invariance to additive shifts makes them fundamentally more reliable than absolute ratings for subjective quality assessment. A model (like a human annotator) has a "generous" or "strict" baseline that corrupts absolute numbers but washes out when you only ask which of two is more uncertain.

There's even a direct head-to-head in a record-matching task: they compared (1) ask the LLM to output confidence scores directly alongside its match decision, or (2) sort all proposed matches by running pairwise comparisons, and the sorting approach yields large gains over embedding similarity as a confidence measure. The key insight into *why* is that these two approaches differ in what information they exploit. Direct confidence scoring evaluates each query-candidate pair independently — whereas comparison forces the model to actually weigh items against each other.

So instead of "label each open question high/medium/low," a stronger design is: **have the model sort its open questions from most-need-human to least**, or do pairwise "which of these two is more likely to change the plan if answered wrong." You don't need all N² comparisons — you can build a full ranking from sparse comparisons using a Bradley-Terry / Elo-style aggregation, which is the same machinery Chatbot Arena uses, and there's active work on doing this from sparse pairwise comparisons with uncertainty-aware selection of which comparisons are even worth making.

One honest caveat so you don't over-rotate: relative isn't a free lunch in every framing. In information-retrieval labeling, one recent paper found prior work on LLM ranking has underestimated the performance of pointwise scoring, and that fully listwise methods can actually *decrease* AUROC of the resulting per-item labels. The lesson is that pairwise/comparative is the robust win; forcing everything into one giant listwise ranking is more fragile. For your case — a handful of open questions per plan — pairwise or small-set comparative ranking is the sweet spot.

## How this fits everything from the prior threads

Putting the whole arc together: your first sweep established that absolute confidence labels are poorly calibrated. Conformal prediction was one fix but leans on the exchangeability assumption you rightly distrust. The ambiguity-as-external-signal reframe (divergence across samples, completeness checklists, critics) sidesteps self-report entirely. This ranking finding is the connective tissue — it explains *why* the sampling/divergence methods work even when confidence labels don't: they're all ways of extracting a reliable *ordering* over "which questions are shakiest" without ever needing a trustworthy absolute number.

Concretely, a robust design that respects all of it:

1. Surface candidate open questions via an external signal (sampling divergence or a completeness checklist), not self-reported doubt.
2. Rank them — ideally via pairwise/comparative prompting, aggregated with Bradley-Terry — rather than grading each with high/medium/low.
3. Threshold on the ranking for triage (send top-k to humans), and validate the threshold with an accuracy-rejection curve on your own logged data rather than trusting any absolute cutoff.
4. Optionally recalibrate the absolute numbers later if you ever truly need them — but for triage you mostly won't.

Want me to sketch the pairwise-ranking prompt-and-aggregation scheme concretely (how to elicit the comparisons, how to turn sparse comparisons into a single ranked queue, and how to plot the accuracy-rejection curve to set your human-routing threshold)? That's the piece that turns this into something you can drop into the workflow.
