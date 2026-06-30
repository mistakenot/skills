# Context: Task 005 (v3-new-task)

Codebase grounding for the v3 overlap-model planning orchestrator. See [plan.html](plan.html).

## Key Files

### How skills are authored & compiled
- `src/compile.py:912-935` -- the `planning-workflow` module declaration. v3 is added here as one more `skill(...)` line (e.g. `skill("v3-new-task", refs=[overview, ...])`). The DSL: `skill(name, refs=[ref("file.md")], assets=[asset(src,dst)])`.
- `src/CLAUDE.md` -- module/templating spec. SKILL.md supports `{{ ref:<file> }}` (line-anchored, copies ref into compiled `references/`), `{{ skill:<name> }}` (inline, validated), `{{ pd-version }}`.
- `src/planning-workflow/skills/<name>/SKILL.md` -- source for each skill (YAML frontmatter `name`+`description`, then markdown body). Compiles to `skills/<name>/SKILL.md` + `references/`.
- Rendered SKILL.md must be **< 15,000 chars** (compile.py size check). Build with `make compile`, lint with `make lint`/`auto skill lint`.

### v2 skills whose logic v3 reuses as subagent instructions
- `src/planning-workflow/skills/new-task/SKILL.md` -- Requirements stage: scan skills, read docs, next task ID, create folder + plan.html (via planning-doc), write Requirements tab, resolve Open Questions, hard-stop.
- `src/planning-workflow/skills/new-solution/SKILL.md` -- Solution stage (this skill): Stage 1 context-gather (2 parallel subagents CB1 Code / CB2 Docs → `context.md`), Stage 2 Verification tab (gate 1), Stage 3 Solution tab (gate 2). Refs: `tab-verification.md`, `tab-solution.md`, `template-context.md`.
- `src/planning-workflow/skills/new-plan/SKILL.md` -- Plan stage: CB3 (History) subagent, enrich context.md, write Plan tab (`pd-stepper`/`pd-phase`), backfill `pd-ac` traceability (gate 3). Ref: `tab-plan.md`.
- `src/planning-workflow/refs/workflow-overview.md` -- shared pipeline overview ref (every planning skill includes it).
- `src/planning-workflow/refs/tab-{requirements,verification,solution,plan}.md` -- per-tab authoring rules. v3 reuses these verbatim as the spec its background subagents follow.

### Background-dispatch patterns already in the repo
- `src/planning-workflow/skills/request-council-review/SKILL.md` + `refs/delegating-to-agents.md` -- headless CLI fan-out: `claude -p --dangerously-skip-permissions "/cmd" < /dev/null > out 2> log &` launched in parallel, `wait`-ed, output parsed/merged. Single-writer rule: never let two agents edit one doc concurrently.
- `src/planning-workflow/skills/delegate/SKILL.md`, `delegate-task/SKILL.md`, `refs/ntm-agent-pools.md` -- tmux/ntm pane dispatch (`ntm status/add/send/copy --json`) for longer background execution into idle panes.
- `src/planning-eval/run.py` + `README.md` -- the A/B eval harness that will validate v3 (NTM-driven conversational replay; metrics via autoetl).

### planning-doc / plan.html manipulation
- plan.html shell: `<pd-doc title status pr generated next-prompt>` with a `<script type="application/json" id="pd-meta">` block (never move/modify it). Tabs: `<pd-tab name>` → `<pd-section id title>` → `<md><script type="text/plain">…</script></md>`.
- Gating: `<pd-question id status="open|answered" recommendedAnswer="…">` (open → lint fails, gates doc); answered carries `<pd-answer by>`. ACs: `<pd-ac id title phases tests>`; phases/tests backfilled by plan stage. Phases: `<pd-stepper>`/`<pd-phase n title files status>`.
- Lint: `node references/pd-lint.mjs plan.html` (bundled asset in planning-doc skill; flags `open-question`, `unplanned-file`, `dependency-cycle`, etc.).

## Patterns
- **Single orchestrator, subagent-as-stage:** the v2 per-stage *commands* become *subagent prompts* the orchestrator dispatches. The v2 `refs/tab-*.md` files are the shared spec both v2 and v3 subagents author against — reuse, don't fork.
- **Coexistence:** v3 is added alongside v2 in the same `planning-workflow` module; v2 skills are untouched. The eval installs each arm by *fully swapping* `.claude/skills/`, so v3 must be self-contained as a skills_dir.
- **Headless fan-out is the established background mechanism** (request-council-review). For the Claude-Code-first background version, the orchestrator dispatches `claude -p`/subagent jobs for the solution+plan stages and stays interactive; the synchronous fallback runs the same stage prompts in the foreground.
- **Questions are the steering wheel:** every load-bearing decision is a `pd-question` + `recommendedAnswer`; unanswered = proceed on the lean. This is already the autonomous convention in new-task/new-solution.

## Verification reality (drives the Verification tab)
- v3's "test" is the **A/B eval**, not unit tests. Harness exists: `src/planning-eval/` (NTM replay, outputs to `/tmp/planning-eval`, out of git).
- v2 baseline (from `docs/research/planning-eval-validation.md`): fixture 008 median ~865s wall / 17.3M tokens / 3–7 sessions over 3 trials; fixture 010 1339s / 14.2M tokens.
- **Noise floor ~1.8×** wall / 1.55× tokens, driven by variable subagent fan-out (3→7) — exactly v3 problem #8. → A/B needs **≥3 trials/arm, compare medians**, win = **quality-per-token** at equal-or-better completeness, not raw speed.
- Methodology discipline: `src/eval-engineer/` (generator≠verifier; calibrate noise floor before reading A/B; arms differ by exactly one variable).

## Related Tasks
- `docs/research/planning-workflow-v3.md` -- the design doc (9 numbered v2 problems; the 3-layer overlap model). Source of truth for v3 mechanics.
- `docs/research/v3-eval-spikes.md` -- feasibility spikes S0–S6 (NTM driving proven; skill isolation via compile-step swap).
- `docs/tasks/005-v3-new-task/plan.html` -- Requirements + resolved Q-1/Q-2/Q-3 (single orchestrator, aggressive overlap, Claude-Code-first + sync fallback).
