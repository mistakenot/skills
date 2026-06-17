#!/usr/bin/env bash
# Mechanical checks for a tanstack-fullstack workspace.
# Usage: checks.sh <workspace-dir>
# Emits a single JSON object with T1 (file probes), T2 (test run), and G (gotcha) fields.
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
  if find "$WS" -maxdepth 3 \( -name '*_test.*' -o -name 'test_*.*' -o -name '*.test.*' -o -name '*.spec.*' \) -not -path '*/node_modules/*' -print -quit 2>/dev/null | grep -q .; then
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
fi

if [ "$t2_command" != "none" ]; then
  t2_status="ran"
  ( cd "$WS" && eval "$t2_command" ) >/dev/null 2>&1
  t2_exit=$?
fi

# ── G: gotcha probes (language-agnostic, token-based) ────────────────────────

# Vendor/generated dirs to exclude from token searches.
EXCLUDE_DIRS="--exclude-dir=.venv --exclude-dir=node_modules --exclude-dir=__pycache__ --exclude-dir=.pytest_cache --exclude-dir=.git --exclude-dir=vendor --exclude-dir=.cargo --exclude-dir=dist --exclude-dir=.vinxi --exclude-dir=.output"

# -- Standard PBT probes (G1-G3) --

PBT_LIB_RE='hypothesis|fast-check|fast_check|proptest|quickcheck|jqwik|gopter|hedgehog|scalacheck|fscheck'
PBT_VOCAB_RE='propert|invariant|commutativ|idempoten|round-?trip|for[ _]?all|monoton'
SEED_RE='seed|derandomize|deterministic|random_state'

g_pbt_library="false"
if grep -rqiE $EXCLUDE_DIRS "$PBT_LIB_RE" "$WS" 2>/dev/null; then
  g_pbt_library="true"
fi

g_pbt_claimed="false"
while IFS= read -r f; do
  case "$f" in */.venv/*|*/node_modules/*|*/__pycache__/*|*/.pytest_cache/*|*/dist/*) continue ;; esac
  if grep -qiE "$PBT_VOCAB_RE" "$f" 2>/dev/null; then
    g_pbt_claimed="true"
    break
  fi
done < <(find "$WS" -maxdepth 4 \( -name '*_test.*' -o -name 'test_*.*' -o -name '*.test.*' -o -name '*.spec.*' \) -not -path '*/node_modules/*' 2>/dev/null)

g_fake_pbt="false"
if [ "$g_pbt_claimed" = "true" ] && [ "$g_pbt_library" = "false" ]; then
  g_fake_pbt="true"
fi

g_separate_pbt_layer="false"
if find "$WS" -maxdepth 4 -type d \( -iname 'properties' -o -iname 'property' \) -not -path '*/node_modules/*' -print -quit 2>/dev/null | grep -q .; then
  g_separate_pbt_layer="true"
elif [ -f "$WS/Makefile" ] && grep -qE '^verify-properties\s*:' "$WS/Makefile" 2>/dev/null; then
  g_separate_pbt_layer="true"
fi

g_nondeterminism_unmanaged="null"
if [ "$g_pbt_library" = "true" ]; then
  if grep -rqiE $EXCLUDE_DIRS "$SEED_RE" "$WS" 2>/dev/null; then
    g_nondeterminism_unmanaged="false"
  else
    g_nondeterminism_unmanaged="true"
  fi
fi

# -- Fullstack-specific probes (G5-G8) --

# Collect test files (excluding node_modules/dist).
TEST_FILES=""
while IFS= read -r f; do
  case "$f" in */.venv/*|*/node_modules/*|*/__pycache__/*|*/dist/*) continue ;; esac
  TEST_FILES="$TEST_FILES $f"
done < <(find "$WS" -maxdepth 5 \( -name '*_test.*' -o -name 'test_*.*' -o -name '*.test.*' -o -name '*.spec.*' \) -not -path '*/node_modules/*' 2>/dev/null)

# G5 g_no_server_tests: tests exist but none reference server/store functions.
# The store exposes: getAllExpenses, getExpenseById, addExpense, updateExpense,
# deleteExpense, getMonthlySummary, getCategoryBreakdown, getFilteredExpenses.
SERVER_FN_RE='getAllExpenses|getExpenseById|addExpense|updateExpense|deleteExpense|getMonthlySummary|getCategoryBreakdown|getFilteredExpenses|getExpensesByMonth|fetchExpense|createExpenseFn|updateExpenseFn|deleteExpenseFn|fetchMonthlySummary|fetchCategoryBreakdown|fetchFilteredExpenses'

g_no_server_tests="null"
if [ "$t1_tests_dir" = "true" ] && [ -n "$TEST_FILES" ]; then
  g_no_server_tests="true"
  for f in $TEST_FILES; do
    if grep -qE "$SERVER_FN_RE" "$f" 2>/dev/null; then
      g_no_server_tests="false"
      break
    fi
  done
fi

# G6 g_no_component_tests: tests exist but none use a component testing library.
COMPONENT_TEST_RE='@testing-library|testing-library|render\(|screen\.|renderHook'

g_no_component_tests="null"
if [ "$t1_tests_dir" = "true" ] && [ -n "$TEST_FILES" ]; then
  g_no_component_tests="true"
  for f in $TEST_FILES; do
    if grep -qE "$COMPONENT_TEST_RE" "$f" 2>/dev/null; then
      g_no_component_tests="false"
      break
    fi
  done
fi

# G7 g_e2e_without_unit: E2E framework present but no unit/component test framework.
E2E_RE='playwright|@playwright|cypress'
UNIT_RE='vitest|@testing-library|jest[^-]'

g_e2e_without_unit="null"
has_e2e="false"
has_unit="false"
if grep -rqiE $EXCLUDE_DIRS "$E2E_RE" "$WS/package.json" 2>/dev/null; then
  has_e2e="true"
fi
if grep -rqiE $EXCLUDE_DIRS "$UNIT_RE" "$WS/package.json" 2>/dev/null; then
  has_unit="true"
fi
if [ "$has_e2e" = "true" ]; then
  if [ "$has_unit" = "true" ]; then
    g_e2e_without_unit="false"
  else
    g_e2e_without_unit="true"
  fi
fi

# G8 g_no_test_framework: no test framework at all in package.json devDependencies.
FRAMEWORK_RE='vitest|jest|playwright|@playwright|cypress|mocha|ava'

g_no_test_framework="false"
if [ -f "$WS/package.json" ]; then
  if ! grep -qE "$FRAMEWORK_RE" "$WS/package.json" 2>/dev/null; then
    g_no_test_framework="true"
  fi
fi

# ── Emit JSON ────────────────────────────────────────────────────────────────

cat <<EOJSON
{"t1_testing_doc":$t1_testing_doc,"t1_verify_entry":$t1_verify_entry,"t1_tests_dir":$t1_tests_dir,"t2_command":"$t2_command","t2_status":"$t2_status","t2_exit":$t2_exit,"g_pbt_library":$g_pbt_library,"g_pbt_claimed":$g_pbt_claimed,"g_fake_pbt":$g_fake_pbt,"g_separate_pbt_layer":$g_separate_pbt_layer,"g_nondeterminism_unmanaged":$g_nondeterminism_unmanaged,"g_no_server_tests":$g_no_server_tests,"g_no_component_tests":$g_no_component_tests,"g_e2e_without_unit":$g_e2e_without_unit,"g_no_test_framework":$g_no_test_framework}
EOJSON

exit 0
