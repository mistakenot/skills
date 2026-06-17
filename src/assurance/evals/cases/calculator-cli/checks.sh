#!/usr/bin/env bash
# Mechanical checks for a calculator-cli workspace.
# Usage: checks.sh <workspace-dir>
# Emits a single JSON object with T1 (file probes) and T2 (test run) fields.
# ALWAYS exits 0 and emits well-formed JSON — it reports on the project,
# it does not adopt the project's exit code.
set -uo pipefail

WS="${1:?Usage: checks.sh <workspace-dir>}"

# ── T1: probe for harness files ──────────────────────────────────────────────

# t1_testing_doc: check for testing documentation
t1_testing_doc="false"
for f in TESTING.md testing.md tests/README.md test/README.md docs/testing.md; do
  if [ -f "$WS/$f" ]; then
    t1_testing_doc="true"
    break
  fi
done

# t1_verify_entry: check for a verify/test entry point
t1_verify_entry="false"
if [ -f "$WS/Makefile" ] && grep -qE '^(verify|test)\s*:' "$WS/Makefile" 2>/dev/null; then
  t1_verify_entry="true"
elif [ -f "$WS/package.json" ] && grep -q '"test"' "$WS/package.json" 2>/dev/null; then
  t1_verify_entry="true"
elif [ -f "$WS/pyproject.toml" ] && grep -qE '\[tool\.(pytest|tox)\]' "$WS/pyproject.toml" 2>/dev/null; then
  t1_verify_entry="true"
fi

# t1_tests_dir: check for test files/directories
t1_tests_dir="false"
if [ -d "$WS/tests" ] || [ -d "$WS/test" ] || [ -d "$WS/__tests__" ]; then
  t1_tests_dir="true"
else
  # Check for test file patterns
  if find "$WS" -maxdepth 3 \( -name '*_test.*' -o -name 'test_*.*' -o -name '*.test.*' -o -name '*.spec.*' \) -print -quit 2>/dev/null | grep -q .; then
    t1_tests_dir="true"
  fi
fi

# ── T2: probe and run the project's test command ─────────────────────────────

t2_command="none"
t2_status="absent"
t2_exit="null"

if [ -f "$WS/Makefile" ] && grep -qE '^verify\s*:' "$WS/Makefile" 2>/dev/null; then
  t2_command="make verify"
elif [ -f "$WS/Makefile" ] && grep -qE '^test\s*:' "$WS/Makefile" 2>/dev/null; then
  t2_command="make test"
elif [ -f "$WS/package.json" ] && grep -q '"test"' "$WS/package.json" 2>/dev/null; then
  t2_command="npm test"
elif command -v pytest &>/dev/null && [ -d "$WS/tests" -o -d "$WS/test" ]; then
  t2_command="pytest"
fi

if [ "$t2_command" != "none" ]; then
  t2_status="ran"
  # Run the test command from the workspace directory, capture exit code
  ( cd "$WS" && eval "$t2_command" ) >/dev/null 2>&1
  t2_exit=$?
fi

# ── G: gotcha probes (language-agnostic, token-based) ────────────────────────
# See graders/gotchas.md for the rationale behind each probe. These are
# deterministic file inspections so rerun variance reflects the agent, not an
# LLM grader.

# Known generator-based PBT framework tokens (a real PBT library is present).
PBT_LIB_RE='hypothesis|fast-check|fast_check|proptest|quickcheck|jqwik|gopter|hedgehog|scalacheck|fscheck|cscheck'
# Property-vocabulary tokens (the output claims property/invariant testing).
PBT_VOCAB_RE='propert|invariant|commutativ|idempoten|round-?trip|for[ _]?all'
# Seed/determinism management tokens.
SEED_RE='seed|derandomize|deterministic|random_state'

# Vendor/generated dirs to exclude from token searches — these contain library
# source that can match our token patterns as false positives.
EXCLUDE_DIRS="--exclude-dir=.venv --exclude-dir=node_modules --exclude-dir=__pycache__ --exclude-dir=.pytest_cache --exclude-dir=.git --exclude-dir=vendor --exclude-dir=.cargo"

# g_pbt_library: any real PBT framework referenced in project source
# (manifests, lock files, or imports — not vendor/generated code)
g_pbt_library="false"
if grep -rqiE $EXCLUDE_DIRS "$PBT_LIB_RE" "$WS" 2>/dev/null; then
  g_pbt_library="true"
fi

# g_pbt_claimed: property vocabulary appears in any test file
g_pbt_claimed="false"
while IFS= read -r f; do
  # Skip vendor/generated paths
  case "$f" in */.venv/*|*/node_modules/*|*/__pycache__/*|*/.pytest_cache/*) continue ;; esac
  if grep -qiE "$PBT_VOCAB_RE" "$f" 2>/dev/null; then
    g_pbt_claimed="true"
    break
  fi
done < <(find "$WS" -maxdepth 4 \( -name '*_test.*' -o -name 'test_*.*' -o -name '*.test.*' -o -name '*.spec.*' \) 2>/dev/null)

# G1 g_fake_pbt: claims properties but ships no generator-based library
g_fake_pbt="false"
if [ "$g_pbt_claimed" = "true" ] && [ "$g_pbt_library" = "false" ]; then
  g_fake_pbt="true"
fi

# G2 g_separate_pbt_layer: a dedicated property layer was carved out
g_separate_pbt_layer="false"
if find "$WS" -maxdepth 4 -type d \( -iname 'properties' -o -iname 'property' \) -print -quit 2>/dev/null | grep -q .; then
  g_separate_pbt_layer="true"
elif [ -f "$WS/Makefile" ] && grep -qE '^verify-properties\s*:' "$WS/Makefile" 2>/dev/null; then
  g_separate_pbt_layer="true"
fi

# G3 g_nondeterminism_unmanaged: real PBT present but no seed/determinism story.
# Reported as null (n/a) when no PBT library is present.
g_nondeterminism_unmanaged="null"
if [ "$g_pbt_library" = "true" ]; then
  if grep -rqiE $EXCLUDE_DIRS "$SEED_RE" "$WS" 2>/dev/null; then
    g_nondeterminism_unmanaged="false"
  else
    g_nondeterminism_unmanaged="true"
  fi
fi

# ── Emit JSON ────────────────────────────────────────────────────────────────

cat <<EOJSON
{"t1_testing_doc":$t1_testing_doc,"t1_verify_entry":$t1_verify_entry,"t1_tests_dir":$t1_tests_dir,"t2_command":"$t2_command","t2_status":"$t2_status","t2_exit":$t2_exit,"g_pbt_library":$g_pbt_library,"g_pbt_claimed":$g_pbt_claimed,"g_fake_pbt":$g_fake_pbt,"g_separate_pbt_layer":$g_separate_pbt_layer,"g_nondeterminism_unmanaged":$g_nondeterminism_unmanaged}
EOJSON

exit 0
