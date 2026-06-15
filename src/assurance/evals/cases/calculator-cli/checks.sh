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

# ── Emit JSON ────────────────────────────────────────────────────────────────

cat <<EOJSON
{"t1_testing_doc":$t1_testing_doc,"t1_verify_entry":$t1_verify_entry,"t1_tests_dir":$t1_tests_dir,"t2_command":"$t2_command","t2_status":"$t2_status","t2_exit":$t2_exit}
EOJSON

exit 0
