#!/usr/bin/env bash
# Validate the strategy-only blind-differential instrument before trusting it.
#
# Repeats the FULL blind A/B run (both arms + judge) on one scenario N times and
# measures the eval's noise floor and blinding leakage:
#
#   - Winner stability  — did the same arm win every run? A verdict that flips
#                         run-to-run is noise, not signal.
#   - Cost spread       — min/max/range of the per-run total cost (baseline +
#                         withskill + judge). An A/B cost difference smaller than
#                         this spread is noise, not signal.
#   - Leakage accuracy  — how often the blind judge correctly guessed which arm
#                         was the skill (AC-6). A reliably-correct guess means
#                         house-style leaked (ADR-0001's accepted risk) and is
#                         the trigger to escalate anonymisation (follow-up, D-4).
#
# This is a THIN wrapper (D-5): it drives the existing run.sh once per iteration
# with a different anonymisation SEED (so the A/B order varies and leakage
# accuracy isn't a fixed-order artifact) and aggregates the per-run artifacts.
# It re-implements no arm or grading logic.
#
# Environment variables:
#   N / RUNS   - number of full A/B runs (default 3)
#   CASE       - case directory name (default strategy/marketing-landing-page)
#   MODEL      - model to pin (passed through to run.sh)
#   AGENT_RUNNER - "live" (default) or "stub" for an offline pipeline smoke test
#
# Usage:
#   bash validate-instrument.sh                       # 3 live runs, default case
#   N=5 CASE=strategy/admin-bulk-delete-cli bash validate-instrument.sh
#   AGENT_RUNNER=stub bash validate-instrument.sh     # offline plumbing check
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
N="${N:-${RUNS:-3}}"
CASE="${CASE:-strategy/marketing-landing-page}"
AGENT_RUNNER="${AGENT_RUNNER:-live}"
export MODEL="${MODEL:-claude-sonnet-4-6}"

echo "=== Validate Instrument (noise floor + leakage) ==="
echo "Runs:    $N"
echo "Case:    $CASE"
echo "Model:   $MODEL"
echo "Mode:    $AGENT_RUNNER"
echo ""

# Per-run collected values, one entry per run.
winners=()
costs=()
guesses=()   # "correct" | "incorrect" | "unscored"
orders=()    # A/B mapping so order variation across seeds is visible
run_dirs=()

for i in $(seq 1 "$N"); do
  # A distinct anonymisation seed per iteration so the blind A/B order varies
  # across the series (leakage accuracy must not be an artifact of fixed order).
  seed=$((41 + i))
  echo "── Run $i/$N (seed $seed) ──────────────────────────────────────────────"

  log="$(mktemp)"
  # Drive the existing single-run harness. run.sh prints "Results: <dir>".
  SEED="$seed" CASE="$CASE" EVAL_MODE="strategy-only" AGENT_RUNNER="$AGENT_RUNNER" \
    bash "$SCRIPT_DIR/run.sh" 2>&1 | tee "$log"

  rdir="$(sed -n 's/^Results:[[:space:]]*//p' "$log" | head -1)"
  rm -f "$log"
  if [ -z "$rdir" ] || [ ! -d "$rdir" ]; then
    echo "  [error] could not locate results dir for run $i — aborting" >&2
    exit 1
  fi
  run_dirs+=("$rdir")

  local_grader="$rdir/grader.json"
  winner="$(jq -r '.winner // "none"' "$local_grader" 2>/dev/null || echo "none")"
  gc="$(jq -r '.guess_correct' "$local_grader" 2>/dev/null || echo "null")"
  order="$(jq -r '"A=" + (.mapping.A // "?") + " B=" + (.mapping.B // "?")' "$local_grader" 2>/dev/null || echo "?")"

  case "$gc" in
    true)  guess="correct" ;;
    false) guess="incorrect" ;;
    *)     guess="unscored" ;;
  esac

  # Total run cost = both arms + judge. Absent/stub costs read as 0.
  b_cost="$(jq -r '.total_cost_usd // 0' "$rdir/baseline/out.json" 2>/dev/null || echo 0)"
  w_cost="$(jq -r '.total_cost_usd // 0' "$rdir/withskill/out.json" 2>/dev/null || echo 0)"
  j_cost="$(jq -r '.total_cost_usd // 0' "$rdir/judge_envelope.json" 2>/dev/null || echo 0)"
  total_cost="$(awk -v b="$b_cost" -v w="$w_cost" -v j="$j_cost" 'BEGIN{printf "%.6f", b+w+j}')"

  winners+=("$winner")
  costs+=("$total_cost")
  guesses+=("$guess")
  orders+=("$order")

  echo ""
  echo "  run $i → winner=$winner  guess=$guess  cost=\$$total_cost  order[$order]"
  echo ""
done

# ── Aggregate ────────────────────────────────────────────────────────────────

# Winner stability: same arm every run, or a split.
declare -A win_counts=()
for w in "${winners[@]}"; do win_counts["$w"]=$(( ${win_counts["$w"]:-0} + 1 )); done
stability_detail=""
top_winner=""
top_count=0
for w in "${!win_counts[@]}"; do
  stability_detail+="${w} ${win_counts[$w]}/${N}; "
  if [ "${win_counts[$w]}" -gt "$top_count" ]; then top_count=${win_counts[$w]}; top_winner=$w; fi
done
if [ "$top_count" -eq "$N" ]; then
  stability="STABLE — $top_winner won $N/$N"
else
  stability="SPLIT — ${stability_detail%; }"
fi

# Cost spread: min / max / range across runs.
read -r cost_min cost_max cost_range < <(printf '%s\n' "${costs[@]}" | awk '
  NR==1{min=$1;max=$1}
  {if($1<min)min=$1; if($1>max)max=$1}
  END{printf "%.6f %.6f %.6f\n", min, max, max-min}')

# Leakage accuracy: correct guesses / N.
correct=0
for g in "${guesses[@]}"; do [ "$g" = "correct" ] && correct=$((correct+1)); done

echo "════════════════════════════════════════════════════════════════════════"
echo "SUMMARY ($N runs, case $CASE, model $MODEL)"
echo "════════════════════════════════════════════════════════════════════════"
echo ""
echo "Per-run:"
for i in $(seq 1 "$N"); do
  idx=$((i-1))
  printf '  run %d: winner=%-9s guess=%-9s cost=$%s  order[%s]\n' \
    "$i" "${winners[$idx]}" "${guesses[$idx]}" "${costs[$idx]}" "${orders[$idx]}"
done
echo ""
echo "Winner stability : $stability"
echo "Cost spread      : min=\$$cost_min  max=\$$cost_max  range=\$$cost_range"
echo "Leakage accuracy : $correct/$N judge skill-arm guesses correct"
echo ""
echo "Noise-floor threshold: a verdict that flips run-to-run, or an A/B cost"
echo "difference smaller than the observed \$$cost_range spread, is noise not"
echo "signal. High leakage accuracy (judge reliably identifies the skill arm)"
echo "is the trigger to escalate anonymisation (follow-up per D-4) — not a blocker."
echo ""
echo "Run dirs:"
for d in "${run_dirs[@]}"; do echo "  $d"; done
