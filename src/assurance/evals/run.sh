#!/usr/bin/env bash
# Two-arm eval harness for the assurance-strategist skill.
#
# Runs a baseline arm (no skill) and a withskill arm (assurance-strategist),
# then grades the difference. Produces results/<run-id>/report.md.
#
# Environment variables:
#   MODEL          - model to pin (default: claude-sonnet-4-20250514)
#   AGENT_RUNNER   - "stub" for deterministic/offline mode (default: live)
#   CASE           - case directory name (default: calculator-cli, or
#                    strategy/marketing-landing-page in strategy-only mode)
#   EVAL_MODE      - "current" (default) two-arm dimension eval, or
#                    "strategy-only" blind-differential strategy-quality eval
#
# Usage:
#   make eval-assurance                       # live mode
#   make eval-assurance AGENT_RUNNER=stub     # stub mode (no API calls)
#   make eval-assurance EVAL_MODE=strategy-only CASE=strategy/<name>
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
MODEL="${MODEL:-claude-sonnet-4-6}"
AGENT_RUNNER="${AGENT_RUNNER:-live}"
EVAL_MODE="${EVAL_MODE:-current}"
if [ "$EVAL_MODE" = "strategy-only" ]; then
  CASE="${CASE:-strategy/marketing-landing-page}"
else
  CASE="${CASE:-calculator-cli}"
fi
RUN_ID="run-$(date +%Y%m%d-%H%M%S)"
RESULTS_DIR="$SCRIPT_DIR/results/$RUN_ID"
CASE_DIR="$SCRIPT_DIR/cases/$CASE"
SKILL_DIR="$REPO_ROOT/skills/assurance-strategist"

# ── Preflight ────────────────────────────────────────────────────────────────

if [ ! -d "$CASE_DIR" ]; then
  echo "Error: case directory not found: $CASE_DIR" >&2
  exit 1
fi

if [ "$EVAL_MODE" = "strategy-only" ]; then
  # Strategy cases carry a scenario.md brief and no prompt.md / checks.sh.
  if [ ! -f "$CASE_DIR/scenario.md" ]; then
    echo "Error: scenario.md not found in $CASE_DIR" >&2
    exit 1
  fi
elif [ ! -f "$CASE_DIR/prompt.md" ]; then
  echo "Error: prompt.md not found in $CASE_DIR" >&2
  exit 1
fi

if [ "$AGENT_RUNNER" = "live" ] && [ ! -f "$HOME/.claude/.credentials.json" ]; then
  echo "Error: ~/.claude/.credentials.json not found (required for live mode)" >&2
  echo "Hint: run with AGENT_RUNNER=stub for offline/deterministic mode" >&2
  exit 1
fi

if [ "$AGENT_RUNNER" = "live" ] && [ ! -d "$SKILL_DIR" ]; then
  echo "Error: compiled skill not found at $SKILL_DIR (run make compile first)" >&2
  exit 1
fi

INSPECT_DIR="$REPO_ROOT/.tmp/eval-assurance"
rm -rf "$INSPECT_DIR/baseline" "$INSPECT_DIR/withskill"
mkdir -p "$INSPECT_DIR/baseline" "$INSPECT_DIR/withskill"
mkdir -p "$RESULTS_DIR/baseline" "$RESULTS_DIR/withskill"

echo "=== Assurance Eval Harness ==="
echo "Mode:    $AGENT_RUNNER"
echo "Case:    $CASE"
echo "Model:   $MODEL"
echo "Run ID:  $RUN_ID"
echo "Results: $RESULTS_DIR"
echo ""

# ── Helpers ──────────────────────────────────────────────────────────────────

extract_result_md() {
  local out_dir="$1"
  if [ -f "$out_dir/out.json" ]; then
    jq -r '.result // ""' "$out_dir/out.json" > "$out_dir/out.md"
  fi
}

check_skill_used() {
  local arm="$1"
  local out_dir="$2"
  local skill_name="assurance-strategist"

  if [ ! -f "$out_dir/stream.jsonl" ]; then
    echo "  [check] No stream.jsonl for $arm — cannot verify skill usage"
    return
  fi

  if grep -q "\"name\":\"Skill\"" "$out_dir/stream.jsonl" &&
     grep "\"name\":\"Skill\"" "$out_dir/stream.jsonl" | grep -q "\"skill\":\"$skill_name\""; then
    echo "  [check] $arm: skill '$skill_name' was INVOKED ✓"
  else
    echo "  [check] $arm: skill '$skill_name' was NOT invoked ✗"
  fi
}

# ── Runner seam ──────────────────────────────────────────────────────────────

run_agent_arm() {
  local arm="$1"       # "baseline" or "withskill"
  local out_dir="$2"   # where to write out.json

  if [ "$AGENT_RUNNER" = "stub" ]; then
    run_agent_arm_stub "$arm" "$out_dir"
  else
    run_agent_arm_live "$arm" "$out_dir"
  fi
}

run_agent_arm_stub() {
  local arm="$1"
  local out_dir="$2"

  echo "  [stub] Writing canned out.json for $arm"

  # Pre-populate workspace from fixture if the case provides one
  local ws_dir="$out_dir/workspace"
  if [ -d "$CASE_DIR/fixture" ]; then
    cp -r "$CASE_DIR/fixture" "$ws_dir"
  else
    mkdir -p "$ws_dir"
  fi

  if [ "$arm" = "withskill" ]; then
    cat > "$out_dir/out.json" <<'STUBEOF'
{
  "result": "I've built a calculator CLI with tests.\n\nCreated files:\n- calculator.py - main CLI\n- tests/test_calculator.py - unit tests\n- Makefile - with test target\n- TESTING.md - testing documentation\n\nRan `make test` and all 3 tests pass.",
  "num_turns": 5,
  "session_id": "stub-withskill-session",
  "total_cost_usd": 0.0
}
STUBEOF
    # Overlay mock test artifacts for non-fixture cases
    if [ ! -d "$CASE_DIR/fixture" ]; then
      mkdir -p "$ws_dir/tests"
      echo '#!/usr/bin/env python3\nimport sys\nprint(int(sys.argv[1]) + int(sys.argv[2]))' > "$ws_dir/calculator.py"
      echo 'def test_add(): assert 1 + 2 == 3' > "$ws_dir/tests/test_calculator.py"
      cat > "$ws_dir/Makefile" <<'MKEOF'
test:
	echo "tests pass"
MKEOF
      echo '# Testing' > "$ws_dir/TESTING.md"
    else
      # For fixture cases in stub mode, add mock test artifacts on top
      mkdir -p "$ws_dir/tests"
      echo 'import { describe, it, expect } from "vitest"; import { addExpense } from "../app/lib/store"; describe("addExpense", () => { it("creates an expense", () => { const e = addExpense({ description: "Test", amount: 100, category: "food", date: "2026-01-01" }); expect(e.id).toBeDefined(); }); });' > "$ws_dir/tests/store.test.ts"
      echo '# Testing\n\nUnit tests for the store layer using vitest.' > "$ws_dir/TESTING.md"
    fi
  else
    cat > "$out_dir/out.json" <<'STUBEOF'
{
  "result": "I've built a calculator CLI.\n\nCreated files:\n- calculator.py - main CLI that adds two numbers\n\nYou can run it with: python calculator.py 2 3",
  "num_turns": 3,
  "session_id": "stub-baseline-session",
  "total_cost_usd": 0.0
}
STUBEOF
    if [ ! -d "$CASE_DIR/fixture" ]; then
      echo '#!/usr/bin/env python3\nimport sys\nprint(int(sys.argv[1]) + int(sys.argv[2]))' > "$ws_dir/calculator.py"
    fi
  fi
}

run_agent_arm_live() {
  local arm="$1"
  local out_dir="$2"

  # Workspace must be outside the repo tree (claude walks up and finds .git)
  local BASE
  BASE=$(mktemp -d)
  local CFG="$BASE/config"
  local WS="$BASE/ws"
  mkdir -p "$CFG" "$WS"

  # Copy credentials
  cp "$HOME/.claude/.credentials.json" "$CFG/.credentials.json"

  # With-skill arm: drop the compiled skill into the config dir
  if [ "$arm" = "withskill" ]; then
    mkdir -p "$CFG/skills"
    cp -r "$SKILL_DIR" "$CFG/skills/assurance-strategist"
    echo "  [live] Skill installed at $CFG/skills/assurance-strategist/"
  fi

  # Pre-populate workspace from fixture if the case provides one
  if [ -d "$CASE_DIR/fixture" ]; then
    cp -r "$CASE_DIR/fixture/." "$WS/"
    echo "  [live] Fixture copied to $WS"
  fi
  if [ -f "$CASE_DIR/setup.sh" ]; then
    echo "  [live] Running setup.sh..."
    ( cd "$WS" && bash "$CASE_DIR/setup.sh" ) 2>&1 | tail -5
  fi

  echo "  [live] Running $arm arm (workspace: $WS)"

  # Run the agent
  local prompt
  prompt=$(cat "$CASE_DIR/prompt.md")

  # The with-skill arm is instructed to invoke the skill. This eval judges the
  # quality of the skill's guidance, not the model's organic routing to it — the
  # baseline arm has no such skill and proceeds with its default approach.
  if [ "$arm" = "withskill" ]; then
    prompt="$prompt"$'\n\n'"Before you begin, invoke the assurance-strategist skill (run /assurance-strategist) and follow its guidance throughout this task."
  fi

  ( cd "$WS" && CLAUDE_CONFIG_DIR="$CFG" claude -p "$prompt" \
      --output-format stream-json \
      --verbose \
      --strict-mcp-config \
      --permission-mode bypassPermissions \
      --model "$MODEL" \
      < /dev/null > "$out_dir/stream.jsonl" 2> "$out_dir/err.txt" ) || true

  # Extract the final result envelope (same shape as --output-format json)
  grep '"type":"result"' "$out_dir/stream.jsonl" | tail -1 > "$out_dir/out.json" 2>/dev/null || true

  # Run mechanical checks against the workspace
  if [ -f "$CASE_DIR/checks.sh" ]; then
    echo "  [live] Running checks.sh against $WS"
    bash "$CASE_DIR/checks.sh" "$WS" > "$out_dir/scorecard.json"
  fi

  # Copy workspace to inspect dir so it survives after the run
  cp -r "$WS" "$INSPECT_DIR/$arm/ws"

  echo "  [live] $arm arm complete (inspect: $INSPECT_DIR/$arm/ws)"
}

run_grader() {
  local results_dir="$1"

  if [ "$AGENT_RUNNER" = "stub" ]; then
    run_grader_stub "$results_dir"
  else
    run_grader_live "$results_dir"
  fi
}

run_grader_stub() {
  local results_dir="$1"

  echo "  [stub] Writing canned grader.json"
  cat > "$results_dir/grader.json" <<'STUBEOF'
{
  "result": "{\"baseline\":{\"tests_present\":0,\"verify_command\":0,\"test_quality\":0,\"evidence\":0},\"withskill\":{\"tests_present\":3,\"verify_command\":3,\"test_quality\":2,\"evidence\":3}}",
  "num_turns": 1,
  "session_id": "stub-grader-session",
  "total_cost_usd": 0.0
}
STUBEOF
}

run_grader_live() {
  local results_dir="$1"
  local rubric
  # Prefer a case-specific rubric if one exists, fall back to the generic one
  if [ -f "$CASE_DIR/rubric.md" ]; then
    rubric=$(cat "$CASE_DIR/rubric.md")
  else
    rubric=$(cat "$SCRIPT_DIR/graders/strategy-rubric.md")
  fi

  # Build the grader prompt with both arms' data
  local grader_prompt="$rubric

---

## Baseline arm

### File listing
$(if [ -f "$results_dir/baseline/out.json" ]; then jq -r '.result // "(no result)"' "$results_dir/baseline/out.json" 2>/dev/null || echo "(parse error)"; fi)

### Mechanical scorecard
$(cat "$results_dir/baseline/scorecard.json" 2>/dev/null || echo "(not available)")

---

## With-skill arm

### File listing
$(if [ -f "$results_dir/withskill/out.json" ]; then jq -r '.result // "(no result)"' "$results_dir/withskill/out.json" 2>/dev/null || echo "(parse error)"; fi)

### Mechanical scorecard
$(cat "$results_dir/withskill/scorecard.json" 2>/dev/null || echo "(not available)")"

  local BASE
  BASE=$(mktemp -d)
  local CFG="$BASE/config"
  local WS="$BASE/ws"
  mkdir -p "$CFG" "$WS"
  cp "$HOME/.claude/.credentials.json" "$CFG/.credentials.json"

  echo "  [live] Running grader"
  ( cd "$WS" && CLAUDE_CONFIG_DIR="$CFG" claude -p "$grader_prompt" \
      --output-format json \
      --strict-mcp-config \
      --permission-mode bypassPermissions \
      --model "$MODEL" \
      < /dev/null > "$results_dir/grader.json" 2> "$results_dir/grader-err.txt" ) || true
}

# ── Strategy-only mode (blind differential) ──────────────────────────────────
#
# Each arm produces a testing-strategy markdown document (strategy.md) and stops
# — no workspace, no implementation, no checks.sh. The grader is a blind A/B
# judge that never sees arm labels or scorecards (see blind_grade.py).

run_agent_arm_strategy() {
  local arm="$1"       # "baseline" or "withskill"
  local out_dir="$2"   # where to write strategy.md

  if [ "$AGENT_RUNNER" = "stub" ]; then
    run_agent_arm_strategy_stub "$arm" "$out_dir"
  else
    run_agent_arm_strategy_live "$arm" "$out_dir"
  fi
}

run_agent_arm_strategy_stub() {
  local arm="$1"
  local out_dir="$2"

  echo "  [stub] Writing canned strategy.md for $arm"

  # Two plausibly-different strategy docs so a "winner" is meaningful. The
  # with-skill arm is deliberately more calibrated (it right-sizes testing to a
  # low-criticality marketing page) than the baseline.
  if [ "$arm" = "withskill" ]; then
    cat > "$out_dir/strategy.md" <<'STRATEOF'
# Testing strategy: marketing landing page

## Risk read
This is a low-criticality, high-volatility marketing surface. The copy, layout,
and imagery will change weekly. Heavy test infrastructure here would rot faster
than it catches bugs, so the strategy is deliberately light and focused on the
few things that actually cost money if they break.

## What to test
- **Signup / CTA path** — one end-to-end smoke test that the primary call to
  action submits and the lead is captured. This is the only revenue-bearing flow.
- **Build + link check** — a static check that the page builds and has no broken
  internal links or missing assets.
- **Accessibility smoke** — an automated axe pass on the rendered page.

## What to deliberately NOT test
- Pixel-level layout and copy: these change constantly; assert them and the
  suite becomes a maintenance tax. Rely on a visual preview + review instead.
- Exhaustive cross-browser matrices: cover the top two browsers, no more.

## Verification
`npm run test:e2e` runs the single CTA smoke test; `npm run build` gates broken
links. Both run in CI on every PR.
STRATEOF
  else
    cat > "$out_dir/strategy.md" <<'STRATEOF'
# Testing plan for the landing page

## Approach
We will build a comprehensive automated test suite to guarantee quality across
the whole page.

## Coverage
- Unit tests for every React component (Hero, Nav, Feature cards, Footer, etc.).
- Snapshot tests for the full DOM of each section to catch any visual change.
- End-to-end tests for every link and button on the page.
- Cross-browser tests across Chrome, Firefox, Safari, and Edge.
- Property-based tests over the form validation logic.

## Tooling
Jest + React Testing Library for units, Playwright for e2e across all browsers,
and Percy for visual snapshots on every commit.

## Verification
Run `npm test` for the full suite; it must stay green before any merge.
STRATEOF
  fi
}

run_agent_arm_strategy_live() {
  local arm="$1"       # "baseline" or "withskill"
  local out_dir="$2"   # where to write strategy.md

  # Clean room must live OUTSIDE the repo tree: claude walks up from cwd and
  # re-discovers this repo's skills + CLAUDE.md if cwd is inside it (see
  # docs/headless-claude-cli-evals.md). $BASE is torn down at the end of this
  # function; every artifact we need is copied into $out_dir (the results dir)
  # first, and the intervening commands are individually guarded (|| true) so
  # nothing exits before teardown.
  local BASE
  BASE=$(mktemp -d)
  local CFG="$BASE/config"
  local WS="$BASE/ws"
  mkdir -p "$CFG" "$WS"

  # Copy credentials
  cp "$HOME/.claude/.credentials.json" "$CFG/.credentials.json"

  # With-skill arm: drop the compiled skill into the config dir. This single dir
  # is the ONLY difference between the two clean rooms (single-variable isolation).
  if [ "$arm" = "withskill" ]; then
    mkdir -p "$CFG/skills"
    cp -r "$SKILL_DIR" "$CFG/skills/assurance-strategist"
    echo "  [live] Skill installed at $CFG/skills/assurance-strategist/"
  fi

  echo "  [live] Running $arm arm (strategy) (workspace: $WS)"

  # Build the prompt from the scenario brief plus a strategy-only instruction:
  # produce a single markdown strategy doc and stop — no implementation.
  local prompt
  prompt="$(cat "$CASE_DIR/scenario.md")"$'\n\n'"Design a testing/assurance strategy for this project as a single markdown document. Do NOT implement anything — output only the strategy document. Then stop."

  # The with-skill arm is instructed to invoke the skill. This eval judges the
  # quality of the skill's guidance, not the model's organic routing to it — the
  # baseline arm has no such skill and proceeds with its default approach.
  if [ "$arm" = "withskill" ]; then
    prompt="$prompt"$'\n\n'"Before you begin, invoke the assurance-strategist skill (run /assurance-strategist) and follow its guidance throughout this task."
  fi

  ( cd "$WS" && CLAUDE_CONFIG_DIR="$CFG" claude -p "$prompt" \
      --output-format stream-json \
      --verbose \
      --strict-mcp-config \
      --permission-mode bypassPermissions \
      --model "$MODEL" \
      < /dev/null > "$out_dir/stream.jsonl" 2> "$out_dir/err.txt" ) || true

  # Extract the final result envelope (same shape as --output-format json)
  grep '"type":"result"' "$out_dir/stream.jsonl" | tail -1 > "$out_dir/out.json" 2>/dev/null || true

  # Write the strategy markdown straight from .result. No checks.sh, no scorecard.
  jq -r '.result // ""' "$out_dir/out.json" > "$out_dir/strategy.md" 2>/dev/null || true

  # Record the clean-room skills listing so isolation can be inspected out-of-band.
  ( ls -1 "$CFG/skills" 2>/dev/null || true ) > "$out_dir/cleanroom-skills.txt"

  # Teardown the out-of-repo clean room (artifacts already preserved in $out_dir).
  rm -rf "$BASE"

  echo "  [live] $arm arm complete (strategy.md: $out_dir/strategy.md)"
}

run_grader_blind() {
  local results_dir="$1"

  if [ "$AGENT_RUNNER" = "stub" ]; then
    run_grader_blind_stub "$results_dir"
  else
    run_grader_blind_live "$results_dir"
  fi
}

run_grader_blind_stub() {
  local results_dir="$1"

  echo "  [stub] Anonymising arms and writing canned blind judge verdict"

  # Blind the two arms: seeded A/B order + label-swap, mapping stored out-of-band.
  uv run --no-dev python "$SCRIPT_DIR/blind_grade.py" anonymise \
    --baseline "$results_dir/baseline/strategy.md" \
    --withskill "$results_dir/withskill/strategy.md" \
    --seed 42 \
    --out-input "$results_dir/judge_input.txt" \
    --out-mapping "$results_dir/mapping.json"

  # Canned judge verdict. The stub judge "prefers" the more-calibrated strategy,
  # which is the with-skill arm — resolve whichever blinded label it landed on so
  # the un-blinded winner is meaningful regardless of the seeded order.
  local skill_label
  skill_label=$(jq -r 'to_entries[] | select(.value=="withskill") | .key' "$results_dir/mapping.json")
  local other_label
  other_label=$(jq -r 'to_entries[] | select(.value=="baseline") | .key' "$results_dir/mapping.json")

  cat > "$results_dir/judge_raw.json" <<JUDGEEOF
{
  "winner": "$skill_label",
  "verdict": "Strategy $skill_label right-sizes the effort to a low-stakes, fast-changing marketing surface: it protects the one revenue-bearing flow and consciously refuses to test volatile copy and layout. Strategy $other_label over-invests — snapshotting the full DOM and property-testing form validation on a page that will be rewritten weekly buys little and creates a large maintenance tax.",
  "weaknesses_a": "placeholder",
  "weaknesses_b": "placeholder",
  "guess_skill": "$skill_label",
  "guess_confidence": "medium"
}
JUDGEEOF

  # Fill the label-keyed weakness prose so both labels are populated.
  local weak_skill="Could name a concrete rollback/monitoring signal for the CTA rather than leaving post-deploy detection implicit."
  local weak_other="Treats a throwaway marketing page like a safety-critical system: full-DOM snapshots and cross-browser matrices will rot faster than they catch real defects, and property-based tests over trivial form validation are misdirected effort."
  local wa wb
  if [ "$skill_label" = "A" ]; then wa="$weak_skill"; wb="$weak_other"; else wa="$weak_other"; wb="$weak_skill"; fi
  jq --arg wa "$wa" --arg wb "$wb" '.weaknesses_a=$wa | .weaknesses_b=$wb' \
    "$results_dir/judge_raw.json" > "$results_dir/judge_raw.json.tmp" \
    && mv "$results_dir/judge_raw.json.tmp" "$results_dir/judge_raw.json"

  # Un-blind: map the A/B verdict back to real arm names → grader.json.
  uv run --no-dev python "$SCRIPT_DIR/blind_grade.py" unblind \
    --judge "$results_dir/judge_raw.json" \
    --mapping "$results_dir/mapping.json" \
    --out "$results_dir/grader.json"
}

run_grader_blind_live() {
  local results_dir="$1"

  echo "  [live] Anonymising arms for the blind judge"
  # Blind the two arms: seeded A/B order + label-swap, mapping stored out-of-band.
  # Same seed as the stub path so a run is reproducible; blind_grade.py adds only
  # neutral "Strategy A"/"Strategy B" labels — no arm identity, no scorecards.
  uv run --no-dev python "$SCRIPT_DIR/blind_grade.py" anonymise \
    --baseline "$results_dir/baseline/strategy.md" \
    --withskill "$results_dir/withskill/strategy.md" \
    --seed 42 \
    --out-input "$results_dir/judge_input.txt" \
    --out-mapping "$results_dir/mapping.json"

  # Assemble the judge prompt: the holistic-judge preamble, the neutral project
  # brief (identical for both arms — safe to show), then the anonymised
  # Strategy A / Strategy B. Nothing here names an arm or embeds a scorecard.
  local judge_prompt
  judge_prompt="$(cat "$SCRIPT_DIR/graders/holistic-judge.md")

---

## Project brief

$(cat "$CASE_DIR/scenario.md")

---

$(cat "$results_dir/judge_input.txt")"

  # Skill-less clean room, OUTSIDE the repo tree: claude walks up from cwd and
  # would re-discover this repo's skills + CLAUDE.md if cwd were inside it (see
  # docs/headless-claude-cli-evals.md). The judge gets NO skills installed — in
  # particular not assurance-strategist, so it cannot recognise its own house
  # style. $BASE is torn down at the end of this function; the fallible claude
  # call is guarded with || true and unblind exits 0 even on a garbled verdict,
  # so a judge failure still reaches the teardown rather than aborting the run.
  local BASE
  BASE=$(mktemp -d)
  local CFG="$BASE/config"
  local WS="$BASE/ws"
  mkdir -p "$CFG" "$WS"
  cp "$HOME/.claude/.credentials.json" "$CFG/.credentials.json"

  echo "  [live] Running blind judge (skill-less clean room: $WS)"
  ( cd "$WS" && CLAUDE_CONFIG_DIR="$CFG" claude -p "$judge_prompt" \
      --output-format json \
      --strict-mcp-config \
      --permission-mode bypassPermissions \
      --model "$MODEL" \
      < /dev/null > "$results_dir/judge_envelope.json" 2> "$results_dir/judge-err.txt" ) || true

  # Record the clean-room skills listing so isolation can be inspected out-of-band.
  ( ls -1 "$CFG/skills" 2>/dev/null || true ) > "$results_dir/judge-cleanroom-skills.txt"

  # Unwrap the claude -p envelope to the judge's raw JSON text. Empty on any
  # failure — unblind then degrades to a "parse failed" row (reuses the defensive
  # extract_json_object path) rather than aborting the run.
  jq -r '.result // ""' "$results_dir/judge_envelope.json" > "$results_dir/judge_raw.json" 2>/dev/null || true

  # Un-blind: map the A/B verdict (winner + skill guess) back to real arm names.
  # unblind exits 0 even on garbled/missing judge JSON.
  uv run --no-dev python "$SCRIPT_DIR/blind_grade.py" unblind \
    --judge "$results_dir/judge_raw.json" \
    --mapping "$results_dir/mapping.json" \
    --out "$results_dir/grader.json"

  # Teardown the out-of-repo clean room (verdict already un-blinded into $results_dir).
  rm -rf "$BASE"
}

# ── Main flow ────────────────────────────────────────────────────────────────

if [ "$EVAL_MODE" = "strategy-only" ]; then
  # Strategy-only mode: each arm emits a strategy.md, the blind judge picks a
  # winner. No workspace, no mechanical checks.
  echo "── Baseline arm (strategy) ──"
  run_agent_arm_strategy "baseline" "$RESULTS_DIR/baseline"

  echo ""
  echo "── With-skill arm (strategy) ──"
  run_agent_arm_strategy "withskill" "$RESULTS_DIR/withskill"

  echo ""
  echo "── Grader (blind A/B) ──"
  run_grader_blind "$RESULTS_DIR"
  echo ""

  echo "── Report ──"
  export MODEL CASE
  (cd "$REPO_ROOT" && uv run --no-dev python "$SCRIPT_DIR/grade_report.py" "$RESULTS_DIR")

  echo ""
  echo "=== Done ==="
  echo "Report:     $RESULTS_DIR/report.md"
else
  # Run both arms
  echo "── Baseline arm ──"
  run_agent_arm "baseline" "$RESULTS_DIR/baseline"

  # In stub mode, run checks against the mock workspace
  if [ "$AGENT_RUNNER" = "stub" ] && [ -d "$RESULTS_DIR/baseline/workspace" ]; then
    bash "$CASE_DIR/checks.sh" "$RESULTS_DIR/baseline/workspace" > "$RESULTS_DIR/baseline/scorecard.json"
  fi
  extract_result_md "$RESULTS_DIR/baseline"
  check_skill_used "baseline" "$RESULTS_DIR/baseline"

  echo ""
  echo "── With-skill arm ──"
  run_agent_arm "withskill" "$RESULTS_DIR/withskill"

  # In stub mode, run checks against the mock workspace
  if [ "$AGENT_RUNNER" = "stub" ] && [ -d "$RESULTS_DIR/withskill/workspace" ]; then
    bash "$CASE_DIR/checks.sh" "$RESULTS_DIR/withskill/workspace" > "$RESULTS_DIR/withskill/scorecard.json"
  fi
  extract_result_md "$RESULTS_DIR/withskill"
  check_skill_used "withskill" "$RESULTS_DIR/withskill"

  echo ""

  # Run grader
  echo "── Grader ──"
  run_grader "$RESULTS_DIR"
  echo ""

  # Generate report
  echo "── Report ──"
  export MODEL CASE
  (cd "$REPO_ROOT" && uv run --no-dev python "$SCRIPT_DIR/grade_report.py" "$RESULTS_DIR")

  echo ""
  echo "=== Done ==="
  echo "Report:     $RESULTS_DIR/report.md"
  echo "Workspaces: $INSPECT_DIR/baseline/ws  $INSPECT_DIR/withskill/ws"
fi
