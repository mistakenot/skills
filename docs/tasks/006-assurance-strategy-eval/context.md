# Context: Task 006 — assurance-strategy-eval

Codebase grounding for building the blind-differential strategy-quality eval. See
[plan.html](plan.html); instrument decided in
[../../adr/0001-strategy-eval-blind-differential-not-rubric.md](../../adr/0001-strategy-eval-blind-differential-not-rubric.md);
design in [../../assurance-strategy-eval-design.md](../../assurance-strategy-eval-design.md) (§12).

The new eval is an **additive mode** on the existing assurance eval harness — almost everything is
reused; the new code branches at the arm-runner and grader layers.

## Key Files (existing harness — `src/assurance/evals/`)

- `src/assurance/evals/run.sh` — orchestrator (337 lines). Env knobs `MODEL` (default
  `claude-sonnet-4-6`), `AGENT_RUNNER` (`live`|`stub`), `CASE`. Per-arm clean room via
  `BASE=$(mktemp -d)` → `$BASE/config` (relocated `CLAUDE_CONFIG_DIR` + copied
  `.credentials.json`) and `$BASE/ws` (workspace).
- `run.sh:173-175` — **skill install, with-skill arm only**: `mkdir -p "$CFG/skills"; cp -r "$SKILL_DIR" "$CFG/skills/assurance-strategist"`. Baseline arm omits it. This single dir is the only variable between arms.
- `run.sh:198` — with-skill arm appends "invoke the assurance-strategist skill" to the prompt; baseline does not.
- `run.sh:201` — invocation: `CLAUDE_CONFIG_DIR="$CFG" claude -p "$prompt"` (+ json output, captured to `out.json`).
- `run.sh:224-295` — `run_grader`: embeds the rubric + both arms' `out.json` + `scorecard.json`, runs one `claude -p`, captures `grader.json`. **Grader currently sees arm labels and scorecards → not blind.**
- `run.sh` stub mode (`run_*_stub`, ~103-155, 238-244) — canned `out.json`/`grader.json` so the full pipeline runs offline with no API cost.
- `grade_report.py:265-266` — `dimensions = ["tests_present","verify_command","test_quality","evidence"]` + `dim_labels`. The hardcoded dimension list the report table renders (per docs/assurance-eval-system.md "adding a dimension").
- `grade_report.py:27-71` — `extract_json_object()` defensive grader-JSON parse (strips fences, balances braces); `130-147` handles the `claude -p` envelope (`.result`).
- `cases/<name>/{prompt.md,checks.sh[,rubric.md,fixture/,setup.sh]}` — per-case contract. `checks.sh <workspace>` emits one JSON object, **always exits 0**. Existing cases: `calculator-cli`, `uk-tax-calculator`, `tanstack-fullstack`.
- `graders/strategy-rubric.md` — current grader prompt (4 dims, 0-3, fixed JSON shape). `graders/gotchas.md` — G1–G3 mechanical anti-pattern probes.

## Patterns & constraints

- **Additive mode seam.** Branch on a new `EVAL_MODE` (`current` default | `strategy-only`). Add `run_agent_arm_strategy` + `run_grader_blind` alongside the existing functions; `grade_report.py` switches report shape on the grader JSON keys (`winner`/prose vs dimensions). Existing mode untouched.
- **Clean-room isolation recipe** (`docs/headless-claude-cli-evals.md`, verified): `BASE=$(mktemp -d)` **OUTSIDE the repo** (Claude walks *up* from cwd and re-discovers this repo's skills/CLAUDE.md if `cwd` is inside it — `.tmp/` in-repo is wrong); copy `~/.claude/.credentials.json` into `$CFG`; with-skill arm copies the compiled skill into `$CFG/skills/assurance-strategist`; run `CLAUDE_CONFIG_DIR="$CFG" claude -p "$PROMPT" --output-format json --permission-mode bypassPermissions --model <pin>`. **Do NOT pass `--setting-sources ''`** — it silently breaks skill discovery.
- **JSON envelope:** `{result, num_turns, session_id, total_cost_usd, modelUsage}` — parse `.result` for the final message; keep the whole file as evidence.
- **eval-engineer non-negotiables:** isolate the arm (one skill version, full replace), run out-of-repo & out-of-git, guaranteed teardown, keep transcript+artifacts+metrics per run.
- **Validation before trust:** noise floor (≥3 same-arm runs; delta below the spread is noise) + a **blinding-leakage check** (ask the judge to guess which arm is the skill arm; if it reliably can, it may reward house style — discount/normalise). Replaces the design doc's judge↔human audit.
- **Scenario sourcing (hybrid):** `auto search` over indexed session history mines real build briefs — the real brief sits in user messages *before* a `/new-task` invocation (the raw `new-task` query returns skill internals). Working: `auto search search "create OR build OR implement" --role user --scope messages --since 90d --limit 30`, then `auto search session get <id>` and read the context above the invocation. Hand-author the two calibration traps (over/under) — they don't occur naturally.

## Deltas this task introduces

- New: `cases/strategy/<scenario>/{scenario.md[,meta.yaml]}` (brief + optional trap tag; **no answer-key.md**).
- New: `graders/holistic-judge.md` (blind A/B prompt → `{winner, verdict, weaknesses_a, weaknesses_b, guess_skill, guess_confidence}`).
- New runners in `run.sh` (strategy-only arm produces a markdown strategy doc and stops; blind grader anonymises both arms, drops scorecards/labels).

<!-- RESOLVED(P2): JSON shape in context.md mismatches plan.html
REVIEW: Context says judge JSON shape ends with `guess_skill_arm`. Plan (phases, D-3, ACs, graders add, validate) consistently specifies `{winner, verdict, weaknesses_a, weaknesses_b, guess_skill, guess_confidence}` (and `guess_skill` in the wrapper). I checked both files. Align the example here to match plan.html before implementation.
AUTHOR: Fixed the Deltas line above to `{winner, verdict, weaknesses_a, weaknesses_b, guess_skill, guess_confidence}`, matching plan.html (D-3, phases, ACs) and the wrapper's `guess_skill` aggregation.
-->

- `grade_report.py`: conditional blind-mode report (winner + prose weaknesses + leakage guess), reusing the defensive JSON parse.

## Git history & conventions (CB3)

- **Harness origin:** `f48028c` feat(001) created `run.sh` + `grade_report.py` + stub mode + first case. Later: `6e8b209` (skill-usage detection via `stream.jsonl`, out-of-repo inspect copy), `a9f78e2` (gotchas G1–G3), `bf7b0a8` (case-specific rubric fallback), `04464e9` (fixture/`setup.sh` case pattern).
- **Isolation unchanged since the skeleton** — the clean-room recipe at `run.sh:157-222` is stable; safe to build on. The grader (`run.sh:224-295`) is **currently not blind** (embeds arm labels + scorecards) — the blind path is net-new.
- **Smoke-test convention = stub mode.** There is **no pytest coverage of `run.sh`/`grade_report.py`** (only `src/assurance/tests/test_compiler.py`). The established offline check is `make eval-assurance AGENT_RUNNER=stub`; the new mode must ship its own stub branch so `AGENT_RUNNER=stub EVAL_MODE=strategy-only` smoke-tests it the same way. → walking-skeleton Phase 1 is exactly this. The added `test_blind_report.py` is *net-new* pytest coverage for the pure-Python blind core (`blind_grade.py`) — a strengthening, consistent with `make test`.
- **`make eval-assurance` depends on `compile`** (recompiles the skill before every run) — the with-skill arm always installs the freshly compiled skill, which now includes the model-based-testing card (`208f0b3`). The strategy-only mode will therefore judge strategies that can prescribe MBT.
- **Model-default inconsistency to fix while here:** the default model is recorded three ways — `run.sh:19` = `claude-sonnet-4-6`, but `README.md` and `grade_report.py:151` = `claude-sonnet-4-20250514`. Align any new-mode default to `run.sh` (`claude-sonnet-4-6`) and fix the stale doc refs in the docs-update step.

## Related tasks

- Task 001 (`001-assurance-skill-walking-skeleton`) — stood up the assurance-strategist skill + the original two-arm end-to-end eval this extends; established the load-bearing patterns (single-skill-dir delta between arms, out-of-repo clean room, JSON-envelope evidence, stub mode).
- Existing system: `docs/assurance-eval-system.md` — the current end-to-end differential harness (complementary; this task adds a second mode, does not replace it).
