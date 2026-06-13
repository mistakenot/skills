#!/usr/bin/env bash
# Pre-commit checks: run auto doc and auto skill validation steps.
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

# 1. Compile skills from src/ and stage output
step "compile skills"
if python3 src/compile.py 2>&1; then
  git add skills/ install.sh
  pass
else
  fail
fi

# 2. Lint skills
step "auto skill lint"
if auto skill lint --text 2>&1; then
  pass
else
  fail
fi

# 3. Check for stale doc hashes
step "auto doc stale"
stale_output=$(auto doc stale --json 2>&1)
if [ "$stale_output" = "[]" ] || [ -z "$stale_output" ]; then
  pass
else
  echo "$stale_output"
  fail
fi

# 4. Rebuild search index (non-blocking)
step "auto doc search reindex"
if auto doc search reindex 2>&1; then
  pass
else
  fail
fi

# 5. Sync skills into agent configs and stage generated files
step "auto skill sync"
if auto skill sync 2>&1; then
  # Stage all files that sync may have generated/updated
  for path in .agents/ .claude/skills/ AGENTS.md CLAUDE.md; do
    if [ -e "$path" ]; then
      git add -N "$path" 2>/dev/null || true
      changed=$(git diff --name-only "$path" 2>/dev/null || true)
      if [ -n "$changed" ]; then
        git add "$path"
      fi
    fi
  done
  pass
else
  fail
fi

if [ "$errors" -gt 0 ]; then
  printf "\n${RED}%d check(s) failed. Fix issues before committing.${NC}\n" "$errors"
  exit 1
fi

printf "\n${GREEN}All checks passed.${NC}\n"
