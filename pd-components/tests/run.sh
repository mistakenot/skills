#!/usr/bin/env bash
# Deterministic test runner for pd-components.
# Runs agent-browser eval assertions against each fixture.
# Usage: bash pd-components/tests/run.sh

set -euo pipefail

FIXTURES="$(cd "$(dirname "$0")/fixtures" && pwd)"
PASS=0
FAIL=0
ERRORS=()

assert() {
  local label="$1" expected="$2" actual="$3"
  if [[ "$actual" == "$expected" ]]; then
    PASS=$((PASS + 1))
    printf "  ✓ %s\n" "$label"
  else
    FAIL=$((FAIL + 1))
    ERRORS+=("$label: expected=$expected actual=$actual")
    printf "  ✗ %s (expected %s, got %s)\n" "$label" "$expected" "$actual"
  fi
}

run_playbook() {
  local name="$1"
  printf "\n── %s ──\n" "$name"
}

# Build first
echo "Building pd-components..."
(cd "$(dirname "$0")/.." && npm run build 2>&1 | tail -1)

# ── md-dedent ──────────────────────────────────────────────────
run_playbook "md-dedent"
agent-browser open "file://$FIXTURES/md-dedent.html" >/dev/null 2>&1
agent-browser wait 3000 >/dev/null 2>&1

assert "unordered list exists" "1" \
  "$(agent-browser eval "document.querySelectorAll('#indented-list md ul').length" 2>&1)"
assert "unordered list has 3 items" "3" \
  "$(agent-browser eval "document.querySelectorAll('#indented-list md ul li').length" 2>&1)"
assert "no pre blocks (dedent regression)" "0" \
  "$(agent-browser eval "document.querySelectorAll('#indented-list md pre').length" 2>&1)"
assert "ordered list exists" "1" \
  "$(agent-browser eval "document.querySelectorAll('#nested-deeper md ol').length" 2>&1)"
assert "ordered list has 3 items" "3" \
  "$(agent-browser eval "document.querySelectorAll('#nested-deeper md ol li').length" 2>&1)"
assert "mixed content heading" "1" \
  "$(agent-browser eval "document.querySelectorAll('#mixed-content md h2').length" 2>&1)"
assert "mixed content bold" "1" \
  "$(agent-browser eval "document.querySelectorAll('#mixed-content md strong').length" 2>&1)"
assert "mixed content code" "1" \
  "$(agent-browser eval "document.querySelectorAll('#mixed-content md code').length" 2>&1)"
assert "mixed content bullets" "2" \
  "$(agent-browser eval "document.querySelectorAll('#mixed-content md ul li').length" 2>&1)"

agent-browser close >/dev/null 2>&1

# ── md-script-wrapper ──────────────────────────────────────────
run_playbook "md-script-wrapper"
agent-browser open "file://$FIXTURES/md-script-wrapper.html" >/dev/null 2>&1
agent-browser wait 3000 >/dev/null 2>&1

assert "HTML tag names as code" "4" \
  "$(agent-browser eval "document.querySelectorAll('#html-tags md code').length" 2>&1)"
assert "four list items" "4" \
  "$(agent-browser eval "document.querySelectorAll('#html-tags md li').length" 2>&1)"
assert "no real textarea" "0" \
  "$(agent-browser eval "document.querySelectorAll('#html-tags textarea').length" 2>&1)"
assert "no real iframe" "0" \
  "$(agent-browser eval "document.querySelectorAll('#html-tags iframe').length" 2>&1)"
assert "Array<string> preserved" "true" \
  "$(agent-browser eval "document.querySelector('#angle-brackets md code').textContent.includes('Array<string>')" 2>&1)"
assert "Parser<T> preserved" "true" \
  "$(agent-browser eval "document.querySelector('#angle-brackets md pre code').textContent.includes('Parser<T>')" 2>&1)"
assert "sections not nested (DOM intact)" "3" \
  "$(agent-browser eval "document.querySelectorAll('pd-tab > pd-section').length" 2>&1)"
assert "plain md still works" "2" \
  "$(agent-browser eval "document.querySelectorAll('#plain-md md li').length" 2>&1)"

agent-browser close >/dev/null 2>&1

# ── md-list-rendering (with Tailwind) ─────────────────────────
run_playbook "md-list-rendering"
agent-browser open "file://$FIXTURES/md-list-rendering.html" >/dev/null 2>&1
agent-browser wait 4000 >/dev/null 2>&1

assert "ul has disc markers" '"disc"' \
  "$(agent-browser eval "getComputedStyle(document.querySelector('#basic-ul md ul')).listStyleType" 2>&1)"
assert "ul has non-zero padding" "true" \
  "$(agent-browser eval "parseInt(getComputedStyle(document.querySelector('#basic-ul md ul')).paddingLeft) > 0" 2>&1)"
assert "ul has 3 items" "3" \
  "$(agent-browser eval "document.querySelectorAll('#basic-ul md li').length" 2>&1)"
assert "ol has decimal markers" '"decimal"' \
  "$(agent-browser eval "getComputedStyle(document.querySelector('#basic-ol md ol')).listStyleType" 2>&1)"
assert "ol has 3 items" "3" \
  "$(agent-browser eval "document.querySelectorAll('#basic-ol md li').length" 2>&1)"
assert "nested ul uses circle markers" '"circle"' \
  "$(agent-browser eval "getComputedStyle(document.querySelector('#nested-lists md ul ul')).listStyleType" 2>&1)"
assert "nested section has 6 total items" "6" \
  "$(agent-browser eval "document.querySelectorAll('#nested-lists md li').length" 2>&1)"
assert "list-in-context has 2 paragraphs" "2" \
  "$(agent-browser eval "document.querySelectorAll('#list-in-context md p').length" 2>&1)"
assert "list-in-context has 3 items" "3" \
  "$(agent-browser eval "document.querySelectorAll('#list-in-context md li').length" 2>&1)"

agent-browser close >/dev/null 2>&1

# ── comment-workflow ───────────────────────────────────────────
run_playbook "comment-workflow"
agent-browser open "file://$FIXTURES/comment-workflow.html" >/dev/null 2>&1
agent-browser wait 2000 >/dev/null 2>&1

assert "export bar hidden initially" "true" \
  "$(agent-browser eval "document.querySelector('.pd-exportbar').hidden" 2>&1)"
assert "localStorage empty" "0" \
  "$(agent-browser eval "JSON.parse(localStorage.getItem('pd-pending:' + location.pathname) || '[]').length" 2>&1)"

# Add a comment: open composer, fill, queue
agent-browser eval "document.querySelector('.pd-btn-ghost[title*=\"Queue\"]').click()" >/dev/null 2>&1
agent-browser eval "(() => { const ta = document.querySelector('.pd-composer-input'); ta.value = 'Test comment for error handling.'; ta.dispatchEvent(new Event('input')); })()" >/dev/null 2>&1
agent-browser eval "document.querySelector('.pd-composer .pd-btn-primary').click()" >/dev/null 2>&1

assert "export bar visible after queue" "false" \
  "$(agent-browser eval "document.querySelector('.pd-exportbar').hidden" 2>&1)"
assert "pending count text" '"1 pending comment"' \
  "$(agent-browser eval "document.querySelector('.pd-exportbar span').textContent" 2>&1)"
assert "localStorage has 1 comment" "1" \
  "$(agent-browser eval "JSON.parse(localStorage.getItem('pd-pending:' + location.pathname) || '[]').length" 2>&1)"
assert "comment text stored" "true" \
  "$(agent-browser eval "JSON.parse(localStorage.getItem('pd-pending:' + location.pathname) || '[]')[0].text.includes('error handling')" 2>&1)"

# Copy for agent — clears queue (baf13ce)
agent-browser find text "Copy for agent" click >/dev/null 2>&1

assert "export bar hidden after copy" "true" \
  "$(agent-browser eval "document.querySelector('.pd-exportbar').hidden" 2>&1)"
assert "localStorage cleared after copy" "0" \
  "$(agent-browser eval "JSON.parse(localStorage.getItem('pd-pending:' + location.pathname) || '[]').length" 2>&1)"

# Thread expand
agent-browser find text "show history" click >/dev/null 2>&1
assert "resolved thread expanded" "true" \
  "$(agent-browser eval "document.querySelector('pd-thread[title=\"Resolved blocker\"] pd-comment:last-child').textContent.includes('migration step')" 2>&1)"

# Tab switching
agent-browser find role tab click --name "Solution" >/dev/null 2>&1
assert "Solution tab visible" '""' \
  "$(agent-browser eval "document.querySelector('pd-tab[name=\"Solution\"]').style.display" 2>&1)"
assert "Overview tab hidden" '"none"' \
  "$(agent-browser eval "document.querySelector('pd-tab[name=\"Overview\"]').style.display" 2>&1)"
assert "Overview badge shows 1 open thread" '"1"' \
  "$(agent-browser eval "document.querySelector('.pd-tabbtn[data-name=\"Overview\"] .pd-tabbadge')?.textContent" 2>&1)"

agent-browser close >/dev/null 2>&1

# ── decision ───────────────────────────────────────────────────
run_playbook "decision"
agent-browser open "file://$FIXTURES/decision.html" >/dev/null 2>&1
agent-browser wait 3000 >/dev/null 2>&1

assert "two decision records render" "2" \
  "$(agent-browser eval "document.querySelectorAll('pd-decision .pd-decision-head').length" 2>&1)"
assert "D-1 status badge" '"accepted"' \
  "$(agent-browser eval "document.querySelector('#D-1 .pd-badge').textContent" 2>&1)"
assert "D-1 by-line" '"by agent"' \
  "$(agent-browser eval "document.querySelector('#D-1 .pd-decision-meta').textContent" 2>&1)"
assert "D-1 body wraps children" "true" \
  "$(agent-browser eval "!!document.querySelector('#D-1 .pd-decision-body md')" 2>&1)"
assert "D-2 proposed status" '"proposed"' \
  "$(agent-browser eval "document.querySelector('#D-2 .pd-badge').textContent" 2>&1)"
assert "decisions log aggregates decisions + closed threads" "3" \
  "$(agent-browser eval "document.querySelectorAll('pd-decisions .pd-decision-list li').length" 2>&1)"
assert "log entries in source order" '"Token bucket over sliding window|Defer multi-region replication|Why not a queue?"' \
  "$(agent-browser eval "[...document.querySelectorAll('pd-decisions .pd-decision-list li a')].map(a=>a.textContent).join('|')" 2>&1)"
assert "log links to source element" '"#D-1"' \
  "$(agent-browser eval "document.querySelector('pd-decisions .pd-decision-list li a').getAttribute('href')" 2>&1)"
assert "decision outcome uses summary" '"Token bucket: simpler, bursts within SLA."' \
  "$(agent-browser eval "document.querySelector('pd-decisions .pd-decision-list li .pd-decision-outcome').textContent" 2>&1)"
assert "thread outcome uses last comment" '"Adds latency; the bucket is sufficient."' \
  "$(agent-browser eval "[...document.querySelectorAll('pd-decisions .pd-decision-list li')].find(li=>li.textContent.includes('Why not a queue?')).querySelector('.pd-decision-outcome').textContent" 2>&1)"

agent-browser close >/dev/null 2>&1

# ── Summary ────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════"
printf "PASS: %d  FAIL: %d\n" "$PASS" "$FAIL"
if [[ ${#ERRORS[@]} -gt 0 ]]; then
  echo ""
  echo "Failures:"
  for e in "${ERRORS[@]}"; do
    printf "  ✗ %s\n" "$e"
  done
  echo "════════════════════════════════════════"
  exit 1
else
  echo "ALL PASS ✓"
  echo "════════════════════════════════════════"
fi
