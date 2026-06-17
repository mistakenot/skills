#!/usr/bin/env bash
# Two-arm eval harness for the assurance-strategist skill.
#
# Runs a baseline arm (no skill) and a withskill arm (assurance-strategist),
# then grades the difference. Produces results/<run-id>/report.md.
#
# Environment variables:
#   MODEL          - model to pin (default: claude-sonnet-4-20250514)
#   AGENT_RUNNER   - "stub" for deterministic/offline mode (default: live)
#   CASE           - case directory name (default: calculator-cli)
#
# Usage:
#   make eval-assurance                       # live mode
#   make eval-assurance AGENT_RUNNER=stub     # stub mode (no API calls)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
MODEL="${MODEL:-claude-sonnet-4-6}"
AGENT_RUNNER="${AGENT_RUNNER:-live}"
CASE="${CASE:-calculator-cli}"
RUN_ID="run-$(date +%Y%m%d-%H%M%S)"
RESULTS_DIR="$SCRIPT_DIR/results/$RUN_ID"
CASE_DIR="$SCRIPT_DIR/cases/$CASE"
SKILL_DIR="$REPO_ROOT/skills/assurance-strategist"

# ── Preflight ────────────────────────────────────────────────────────────────

if [ ! -d "$CASE_DIR" ]; then
  echo "Error: case directory not found: $CASE_DIR" >&2
  exit 1
fi

if [ ! -f "$CASE_DIR/prompt.md" ]; then
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

  if [ "$arm" = "withskill" ]; then
    cat > "$out_dir/out.json" <<'STUBEOF'
{
  "result": "I've built a calculator CLI with tests.\n\nCreated files:\n- calculator.py - main CLI\n- tests/test_calculator.py - unit tests\n- Makefile - with test target\n- TESTING.md - testing documentation\n\nRan `make test` and all 3 tests pass.",
  "num_turns": 5,
  "session_id": "stub-withskill-session",
  "total_cost_usd": 0.0
}
STUBEOF
    # Create a mock workspace with test artifacts for checks.sh
    local ws_dir="$out_dir/workspace"
    mkdir -p "$ws_dir/tests"
    echo '#!/usr/bin/env python3\nimport sys\nprint(int(sys.argv[1]) + int(sys.argv[2]))' > "$ws_dir/calculator.py"
    echo 'def test_add(): assert 1 + 2 == 3' > "$ws_dir/tests/test_calculator.py"
    cat > "$ws_dir/Makefile" <<'MKEOF'
test:
	echo "tests pass"
MKEOF
    echo '# Testing' > "$ws_dir/TESTING.md"
  else
    cat > "$out_dir/out.json" <<'STUBEOF'
{
  "result": "I've built a calculator CLI.\n\nCreated files:\n- calculator.py - main CLI that adds two numbers\n\nYou can run it with: python calculator.py 2 3",
  "num_turns": 3,
  "session_id": "stub-baseline-session",
  "total_cost_usd": 0.0
}
STUBEOF
    # Create a mock workspace without test artifacts
    local ws_dir="$out_dir/workspace"
    mkdir -p "$ws_dir"
    echo '#!/usr/bin/env python3\nimport sys\nprint(int(sys.argv[1]) + int(sys.argv[2]))' > "$ws_dir/calculator.py"
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

  echo "  [live] Running $arm arm (workspace: $WS)"

  # Run the agent
  local prompt
  prompt=$(cat "$CASE_DIR/prompt.md")

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

# ── Main flow ────────────────────────────────────────────────────────────────

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
