#!/usr/bin/env bash
# Pre-commit checks: run autodoc and autoskill validation steps.
# Can be run standalone or via the git pre-commit hook.
set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

errors=0

step() { printf "${YELLOW}=> %s${NC}\n" "$1"; }
pass() { printf "${GREEN}   OK${NC}\n"; }
fail() { printf "${RED}   FAIL${NC}\n"; errors=$((errors + 1)); }

# 1. Lint skills
step "autoskill lint"
if autoskill lint --text 2>&1; then
  pass
else
  fail
fi

# 2. Check for stale doc hashes
step "autodoc stale"
stale_output=$(autodoc stale --json 2>&1)
if [ "$stale_output" = "[]" ] || [ -z "$stale_output" ]; then
  pass
else
  echo "$stale_output"
  fail
fi

# 3. Rebuild search index (non-blocking)
step "autodoc search reindex"
if autodoc search reindex 2>&1; then
  pass
else
  fail
fi

# 4. Sync skills into agent configs and stage generated files
step "autoskill sync"
if autoskill sync 2>&1; then
  # Stage any files sync may have generated/updated
  git add -N .agents/ 2>/dev/null || true
  changed=$(git diff --name-only .agents/ 2>/dev/null || true)
  if [ -n "$changed" ]; then
    git add .agents/
    printf "   Staged updated agent configs\n"
  fi
  pass
else
  fail
fi

if [ "$errors" -gt 0 ]; then
  printf "\n${RED}%d check(s) failed. Fix issues before committing.${NC}\n" "$errors"
  exit 1
fi

printf "\n${GREEN}All checks passed.${NC}\n"
