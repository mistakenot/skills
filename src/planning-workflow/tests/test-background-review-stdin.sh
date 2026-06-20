#!/usr/bin/env bash
#
# Rerunnable test for request-codex-review and request-claude-review.
#
# Guards the bug where `codex exec` (and, more mildly, `claude -p`) block on an
# inherited, never-closing stdin when launched in the background — the CLI sits
# at "Reading additional input from stdin..." instead of running the review.
# The skills fix this with a `< /dev/null` redirect; this test proves both that
# the redirect works and that the skill files still carry it.
#
# Usage:  bash src/planning-workflow/tests/test-background-review-stdin.sh
#         SKIP_NEG=1 bash .../test-background-review-stdin.sh   # skip the slow negative control
#
# Exit 0 = all checks pass. Exit 1 = a check failed. Exit 2 = preconditions missing.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CODEX_SKILL="$REPO_ROOT/skills/request-codex-review/SKILL.md"
CLAUDE_SKILL="$REPO_ROOT/skills/request-claude-review/SKILL.md"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"; jobs -p | xargs -r kill 2>/dev/null' EXIT

PASS=0 FAIL=0
ok()   { echo "  PASS: $1"; PASS=$((PASS+1)); }
bad()  { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }
note() { echo "  ---- $1"; }

# Run $1 (a command string) with stdin attached to an open pipe that never sends
# EOF — the exact condition a background launch creates. Times out after $2s.
# Returns the command's exit code (124 = timed out = hung on stdin).
run_with_open_stdin() {
    local cmd="$1" secs="$2" fifo="$TMP/fifo.$RANDOM"
    mkfifo "$fifo"
    # Hold the write end open for longer than the timeout, but never write -> no EOF.
    sleep "$((secs + 10))" > "$fifo" &
    local holder=$!
    timeout "$secs" bash -c "$cmd" < "$fifo" > "$TMP/out.log" 2>&1
    local rc=$?
    kill "$holder" 2>/dev/null
    rm -f "$fifo"
    return $rc
}

echo "== Preconditions =="
command -v codex  >/dev/null || { echo "codex not on PATH";  exit 2; }
command -v claude >/dev/null || { echo "claude not on PATH"; exit 2; }
codex login status >/dev/null 2>&1 || { echo "codex not logged in (run: codex login)"; exit 2; }
[ -f "$CODEX_SKILL" ]  || { echo "missing $CODEX_SKILL (run: make compile)";  exit 2; }
[ -f "$CLAUDE_SKILL" ] || { echo "missing $CLAUDE_SKILL (run: make compile)"; exit 2; }
ok "codex + claude present and authed; compiled skills exist"

echo
echo "== Static guard: skills carry the stdin redirect =="
grep -q '< /dev/null' "$CODEX_SKILL"  && ok "request-codex-review keeps '< /dev/null'"  || bad "request-codex-review LOST '< /dev/null' — codex will hang on background launch"
grep -q '< /dev/null' "$CLAUDE_SKILL" && ok "request-claude-review keeps '< /dev/null'" || bad "request-claude-review LOST '< /dev/null'"

echo
echo "== Negative control: codex hangs WITHOUT the redirect =="
if [ "${SKIP_NEG:-0}" = "1" ]; then
    note "skipped (SKIP_NEG=1)"
else
    note "expect a ~10s hang then timeout — this proves the redirect is still necessary"
    run_with_open_stdin 'codex exec --sandbox read-only "reply with exactly: PONG"' 10
    rc=$?
    [ "$rc" -eq 124 ] && ok "codex without '< /dev/null' hangs on open stdin (rc=124, as expected)" \
                       || bad "codex did NOT hang without redirect (rc=$rc) — codex behaviour may have changed; revisit the skill"
fi

echo
echo "== Positive: codex runs WITH the redirect under background stdin =="
run_with_open_stdin 'codex exec --sandbox read-only "reply with exactly: PONG" < /dev/null' 60
rc=$?
if [ "$rc" -eq 124 ]; then
    bad "codex STILL hung even with '< /dev/null' (rc=124)"; tail -5 "$TMP/out.log" | sed 's/^/      /'
elif grep -q "PONG" "$TMP/out.log"; then
    ok "codex completed and produced output (rc=$rc)"
else
    bad "codex finished (rc=$rc) but produced no expected output"; tail -5 "$TMP/out.log" | sed 's/^/      /'
fi

echo
echo "== Positive: claude -p runs under background stdin =="
run_with_open_stdin 'claude -p --dangerously-skip-permissions "reply with exactly: PONG" < /dev/null' 60
rc=$?
if [ "$rc" -eq 124 ]; then
    bad "claude -p hung even with '< /dev/null' (rc=124)"; tail -5 "$TMP/out.log" | sed 's/^/      /'
elif grep -q "PONG" "$TMP/out.log"; then
    ok "claude -p completed and produced output (rc=$rc)"
else
    bad "claude -p finished (rc=$rc) but produced no expected output"; tail -5 "$TMP/out.log" | sed 's/^/      /'
fi

echo
echo "== Summary: $PASS passed, $FAIL failed =="
[ "$FAIL" -eq 0 ]
