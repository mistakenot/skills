---
name: request-council-review
description: "Runs a parallel council review of task planning docs via Claude, Codex, and Grok, merges de-duplicated comments into the docs, then resolves them. Use when 'council review', 'request council review', 'review with all three', or when multiple independent reviewers are wanted before execution. Not for a single-agent review (use request-claude-review / request-codex-review / request-grok-review)."
---

# Request Council Review

Run a **panel of three independent reviewers** — Claude Code, Codex, and Grok — over the task planning docs in parallel. Unlike the single-agent review skills, the reviewers **never touch the docs**: each one reads the docs and codebase, gathers findings (with file + line/anchor), and hands them back to this coordinator. The coordinator de-duplicates across all three, appends one merged comment thread per real issue (markdown **and** HTML supported), then resolves them.

> Part of the task planning workflow. See [references/workflow-overview.md](references/workflow-overview.md) for the full pipeline. For the underlying headless-CLI handoff details, see [references/delegating-to-agents.md](references/delegating-to-agents.md).

## Input

- **Task ID** (numeric, e.g. `042`)
- The repository root path (absolute) -- use the current working directory if already at root

## Why reviewers don't edit

Three agents editing the same files in parallel would race and produce duplicate, conflicting threads anchored to the same content. Instead each reviewer is **read-only** and emits a structured findings block on stdout. The coordinator is the single writer, so de-duplication and placement happen once, deterministically.

## Process

### Step 1: Resolve the Task Folder

```bash
CWD="<ABSOLUTE_REPO_ROOT>"
TASK_ID="<TASK_ID>"
TASK_DIR=$(find "$CWD/docs/tasks" -maxdepth 1 -type d -name "${TASK_ID}-*" | head -1)
if [ -z "$TASK_DIR" ]; then
    echo "no task folder found for ID $TASK_ID"
    exit 1
fi
TASK_NAME=$(basename "$TASK_DIR")
echo "reviewing $TASK_NAME"
```

### Step 2: Launch the Three Reviewers in Parallel

All three run the **same read-only review prompt** and write their findings block to a per-agent file. They are launched as concurrent background jobs and waited on together, so wall-clock time is the slowest single reviewer, not the sum.

The shared prompt forbids edits and pins the exact output contract:

```bash
read -r -d '' REVIEW_PROMPT <<EOF
You are one of three independent reviewers of the planning documents for task
$TASK_NAME, located in docs/tasks/$TASK_NAME/.

Read EVERY planning doc present (markdown: requirements.md, solution.md,
context.md, plan.md — or HTML: plan.html / epic.html) and verify each claim
against the ACTUAL codebase using your read tools (grep, glob, read).

Review for: untestable or ambiguous acceptance criteria; missing or wrong file
paths, types, and signatures; security / tenant-isolation gaps; test coverage
that does not cover every AC; inaccurate context snippets or line numbers; a
broken execution sequence or wrong commands; and cross-document inconsistencies.

CRITICAL: You are READ-ONLY. Do NOT edit, create, move, or delete ANY file.
Your entire job is to OUTPUT findings. Do not insert comments into the docs.

Output ONLY the findings block below and nothing after it. For each real issue,
emit one object. Use the codebase as evidence — back every finding with a fact.

===COUNCIL-FINDINGS-START===
[
  {
    "file": "<repo-relative path, e.g. solution.md or plan.html>",
    "location": "<for .md: the line number the issue sits on, as a string; for .html: the id/anchor attribute of the element it discusses>",
    "priority": "P1|P2|P3",
    "title": "<short issue title>",
    "detail": "<the concern with concrete evidence>"
  }
]
===COUNCIL-FINDINGS-END===

If you find no issues, output an empty array [] between the two sentinels.
EOF

CLAUDE_OUT="/tmp/council-$TASK_ID-claude.txt"; CLAUDE_LOG="/tmp/council-$TASK_ID-claude.log"
CODEX_OUT="/tmp/council-$TASK_ID-codex.txt";   CODEX_LOG="/tmp/council-$TASK_ID-codex.log"
GROK_OUT="/tmp/council-$TASK_ID-grok.txt";     GROK_LOG="/tmp/council-$TASK_ID-grok.log"

# Claude Code — read-only review. `< /dev/null` gives immediate EOF so print
# mode doesn't stall on inherited stdin.
claude \
    --add-dir "$CWD" \
    -p \
    --permission-mode plan \
    "$REVIEW_PROMPT" \
    < /dev/null \
    > "$CLAUDE_OUT" 2> "$CLAUDE_LOG" &
CLAUDE_PID=$!

# Codex — read-only sandbox genuinely prevents edits. `< /dev/null` stops codex
# blocking on "Reading additional input from stdin...".
codex exec \
    --cd "$CWD" \
    --sandbox read-only \
    -o "$CODEX_OUT" \
    "$REVIEW_PROMPT" \
    < /dev/null \
    > "$CODEX_LOG" 2>&1 &
CODEX_PID=$!

# Grok — headless mode ignores piped stdin, so no redirect is needed. The prompt
# enforces read-only; bypassPermissions only avoids interactive prompts.
grok \
    --cwd "$CWD" \
    --permission-mode bypassPermissions \
    --always-approve \
    --single "$REVIEW_PROMPT" \
    > "$GROK_OUT" 2> "$GROK_LOG" &
GROK_PID=$!

wait $CLAUDE_PID; CLAUDE_EXIT=$?
wait $CODEX_PID;  CODEX_EXIT=$?
wait $GROK_PID;   GROK_EXIT=$?
echo "exits: claude=$CLAUDE_EXIT codex=$CODEX_EXIT grok=$GROK_EXIT"
```

**Handoff notes** (full detail in [references/delegating-to-agents.md](references/delegating-to-agents.md)):
- **Claude**: `--permission-mode plan` keeps it read-only (planner cannot write). `< /dev/null` is required or print mode stalls ~3s waiting for stdin.
- **Codex**: `--sandbox read-only` blocks all writes. `-o` writes the final message to the findings file. `< /dev/null` is required or `codex exec` blocks reading stdin forever in a background launch.
- **Grok**: no stdin redirect needed. `--single` takes the prompt as its immediate value — never place other flags between `--single` and the prompt.

A reviewer that errors or produces no findings block does not abort the council — the coordinator proceeds with whoever succeeded and notes the gap. A degraded run (1–2 reviewers) is still useful; a 0-reviewer run is a failure (Step 6).

### Step 3: Collect the Findings

Extract the JSON array from each reviewer's output (the text between the sentinels). Some agents wrap output in prose or fences; slice on the sentinels and parse the array inside.

```bash
for AGENT in claude codex grok; do
    OUT="/tmp/council-$TASK_ID-$AGENT.txt"
    echo "=== $AGENT ==="
    sed -n '/===COUNCIL-FINDINGS-START===/,/===COUNCIL-FINDINGS-END===/p' "$OUT" 2>/dev/null \
        | sed '1d;$d'
done
```

Read each agent's array. If an agent's file is missing the sentinels, open its `.log` to see whether it failed or just answered in a different shape, and recover the findings by reading the file directly. Tag every finding you parse with the agent it came from (`claude` / `codex` / `grok`).

### Step 4: De-duplicate and Merge

Pool all findings from all three reviewers. Two findings are **the same issue** when they target the same `file` and the same (or adjacent) `location` AND describe the same underlying concern — even if the wording differs. Merge each cluster into ONE thread:

- **priority**: take the highest any reviewer assigned (P1 > P2 > P3).
- **title**: the clearest of the titles.
- **detail**: the strongest single explanation, plus any distinct evidence a second reviewer added.
- **attribution**: prefix the REVIEW text with `[council: <agents>]` listing the reviewers that raised it, e.g. `[council: claude, codex]`. Consensus across reviewers is a strong signal — a 3/3 issue is almost always real; a 1/3 issue may be noise, so only keep it if its evidence holds up.

Drop findings whose evidence you can disprove against the codebase. You are the editor of record — a reviewer being wrong is expected.

### Step 5: Append Merged Threads to the Docs

You are now the single writer. For each merged issue, insert ONE comment thread into the doc it targets, anchored by the finding's `location`. Threads are **append-only**: never edit or delete existing content or existing threads.

Match the syntax to the file's extension — see the **Comment Format** section below.

- **Markdown** (`.md`): insert below the line at `location`, with a blank line above and below:

  ```markdown
  <!-- UNRESOLVED(P1): Title of issue
  REVIEW: [council: claude, codex] Description of the concern with evidence.
  -->
  ```

- **HTML** (`.html`): insert a `<pd-thread>` directly after the element whose `id` equals `location`, inside the relevant tab:

  ```html
  <pd-thread anchor="section-id" status="unresolved" priority="p1" title="Title of issue">
    <pd-comment by="review">[council: claude, codex] Description of the concern with evidence.</pd-comment>
  </pd-thread>
  ```

If the merged set is empty (all three reviewers came back clean), insert a single clean-review thread so the run is distinguishable from a failure — markdown at the top of `plan.md`, or after the first `<pd-section>` for HTML:

```markdown
<!-- RESOLVED(P3): Council review complete — no issues found
REVIEW: [council: claude, codex, grok] All planning documents reviewed against the codebase by three independent reviewers. No problems detected.
-->
```

Then verify the threads landed:

```bash
MD_COUNT=$(rg -cn "<!-- (UNRESOLVED|RESOLVED|REJECTED)\(P[123]\):" "$TASK_DIR"/*.md 2>/dev/null | awk -F: '{s+=$2}END{print s+0}')
HTML_COUNT=$(rg -cn "<pd-thread " "$TASK_DIR"/*.html 2>/dev/null | awk -F: '{s+=$2}END{print s+0}')
echo "threads in docs: md=$MD_COUNT html=$HTML_COUNT"
```

### Step 6: Handle Failure

If **all three** reviewers exited non-zero or produced no parseable findings, the council failed — inspect the logs and stop without writing placeholder threads:

```bash
if [ "$CLAUDE_EXIT" -ne 0 ] && [ "$CODEX_EXIT" -ne 0 ] && [ "$GROK_EXIT" -ne 0 ]; then
    echo "all reviewers failed; inspecting logs"
    tail -n 80 "$CLAUDE_LOG" "$CODEX_LOG" "$GROK_LOG"
fi
```

Report the failure to the user. Do not proceed to resolution.

### Step 7: Resolve Comments

**Mandatory** after appending. Invoke `resolve-comments` in the current agent context to work through every thread the council raised:

```
/resolve-comments $TASK_ID
```

Do NOT resolve feedback by manually editing or deleting threads — comment handling is append-only per the review-format conventions.

### Step 8: Verify Resolution

Confirm `resolve-comments` ran by checking for author replies (both formats):

```bash
MD_REPLIES=$(rg -cn "AUTHOR:" "$TASK_DIR"/*.md 2>/dev/null | awk -F: '{s+=$2}END{print s+0}')
HTML_REPLIES=$(rg -cn 'by="author"' "$TASK_DIR"/*.html 2>/dev/null | awk -F: '{s+=$2}END{print s+0}')
AUTHOR_REPLY_COUNT=$((MD_REPLIES + HTML_REPLIES))
echo "author reply count: $AUTHOR_REPLY_COUNT"
if [ "$AUTHOR_REPLY_COUNT" -eq 0 ]; then
    echo "resolve-comments was not applied; run /resolve-comments $TASK_ID"
fi
```

### Step 9: Report

Summarize:
- Which reviewers succeeded (claude / codex / grok) and which, if any, failed
- Raw finding counts per reviewer, and the merged count after de-duplication
- Consensus breakdown — how many issues were raised by 3/3, 2/3, 1/3 reviewers
- Merged comment count by priority (P1/P2/P3)
- How many threads were resolved, rejected, or left unresolved
- Any threads needing user input

## Comment Format

Determine the format from the file extension:
- **Markdown files** (`.md`): See [references/review-format.md](references/review-format.md)
- **HTML files** (`.html`): See [references/review-format-html.md](references/review-format-html.md)
