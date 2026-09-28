---
name: request-council-review
description: "Runs a parallel Claude, Codex and Grok council review of task planning docs or any files, merges de-duplicated comments, then resolves them. Use when 'council review', 'review with all three'. Not for one reviewer (use request-codex-review)."
---

# Request Council Review

Run a **panel of three independent reviewers** — Claude Code, Codex, and Grok over a target in parallel: a task's planning docs (**task mode**, the usual case) or any files (**file mode**). Unlike the single-agent review skills, the reviewers **never touch the files**: each one reads the targets and codebase, gathers findings (with file + line/anchor), and hands them back to this coordinator. The coordinator de-duplicates across all three, appends one merged comment thread per real issue (inline in markdown/HTML, or a `<file>.review.md` sidecar for anything else — see [references/review-targets.md](references/review-targets.md)), then resolves them.

> Part of the task planning workflow. See [references/workflow-overview.md](references/workflow-overview.md) for the full pipeline.

## Input

- **Target** — a task ID (`042`) or task folder → task mode; or one or more file/directory paths → file mode
- **Focus** (optional, file mode) — what to look for, e.g. `"error handling"`
- The repository root path (absolute) -- use the current working directory if already at root

## Why reviewers don't edit

Three agents editing the same files in parallel would race and write duplicate, conflicting threads. Instead each reviewer is **read-only** and emits a findings block on stdout. The coordinator is the single writer, so de-duplication and placement happen once, deterministically.

## Process

### Step 1: Resolve the Targets

```bash
cd "<ABSOLUTE_REPO_ROOT>" || exit 1
CWD=$(pwd)
ARGS=(<TARGET> ...)   # a task ID / task folder, or file and directory paths
FOCUS=""              # optional file-mode focus, e.g. "error handling"
shopt -s nullglob

# Task mode: a single argument naming a task under docs/tasks/.
TASK_DIR=""
if [ "${#ARGS[@]}" -eq 1 ]; then
    A="${ARGS[0]%/}"
    if [[ "$A" =~ ^[0-9]+$ ]]; then
        TASK_DIR=$(find "$CWD/docs/tasks" -maxdepth 1 -type d -name "${A}-*" | head -1)
        [ -n "$TASK_DIR" ] || { echo "no task folder found for ID $A"; exit 1; }
    elif [ -d "$CWD/docs/tasks/$A" ]; then
        TASK_DIR="$CWD/docs/tasks/$A"
    elif [ -d "$A" ] && [ "$(realpath "$A/..")" = "$(realpath "$CWD/docs/tasks" 2>/dev/null)" ]; then
        TASK_DIR=$(realpath "$A")
    fi
fi

TARGETS=()
if [ -n "$TASK_DIR" ]; then
    MODE=task
    SLUG=$(basename "$TASK_DIR")
    REVIEW_ARGS="$SLUG"
    TARGETS=("$TASK_DIR"/*.md "$TASK_DIR"/*.html)
else
    MODE=files
    for A in "${ARGS[@]}"; do
        if [ -d "$A" ]; then
            while IFS= read -r F; do TARGETS+=("$F"); done < <(rg --files "$A" | grep -v '\.review\.md$' | sort)
        elif [ -f "$A" ]; then
            TARGETS+=("$A")
        else
            echo "target not found: $A"; exit 1
        fi
    done
    [ "${#TARGETS[@]}" -gt 0 ] || { echo "no files to review"; exit 1; }
    SLUG="files-$(basename "${TARGETS[0]}" | tr -c 'A-Za-z0-9._\n' '-')-$(printf '%s\n' "${TARGETS[@]}" | sha1sum | cut -c1-8)"
    REVIEW_ARGS="${ARGS[*]}${FOCUS:+ --focus \"$FOCUS\"}"
fi

# Comment sinks: markdown and HTML take threads inline; any other file gets a
# <file>.review.md sidecar (it may not exist until the reviewer writes it).
SINKS=()
for F in "${TARGETS[@]}"; do
    case "$F" in
        *.md|*.markdown|*.html|*.htm) SINKS+=("$F") ;;
        *) SINKS+=("$F.review.md") ;;
    esac
done
SCOPE_FILE="/tmp/review-scope-$SLUG.txt"
printf '%s\n' "${SINKS[@]}" > "$SCOPE_FILE"
echo "mode=$MODE slug=$SLUG targets=${#TARGETS[@]} scope=$SCOPE_FILE"
echo "review args: $REVIEW_ARGS"
```

Later blocks use `CWD`, `MODE`, `SLUG`, `REVIEW_ARGS` and `SCOPE_FILE` from this
block. If your shell does not keep state between calls, set them from its output.

### Step 2: Launch the Three Reviewers in Parallel

All three run the **same read-only review prompt** and write their findings block to a per-agent file. They are launched as concurrent background jobs and waited on together, so wall-clock time is the slowest single reviewer, not the sum.

The shared prompt forbids edits and pins the exact output contract. Only the subject and checklist differ by mode:

```bash
if [ "$MODE" = task ]; then
read -r -d '' SUBJECT <<EOF
the planning documents for task $SLUG, located in docs/tasks/$SLUG/.

Read EVERY planning doc present (markdown: requirements.md, solution.md,
context.md, plan.md — or HTML: plan.html / epic.html) and verify each claim
against the ACTUAL codebase using your read tools (grep, glob, read).

Review for: untestable or ambiguous acceptance criteria; missing or wrong file
paths, types, and signatures; security / tenant-isolation gaps; test coverage
that does not cover every AC; inaccurate context snippets or line numbers; a
broken execution sequence or wrong commands; and cross-document inconsistencies.
EOF
else
read -r -d '' SUBJECT <<EOF
these files: ${ARGS[*]} (a directory means every non-ignored file in it).

Read every target in full, plus the code that calls, tests, or is described by
them, and verify each target against the ACTUAL codebase using your read tools.

Review for: incorrect behaviour and unhandled edge cases or errors; security
gaps; tests that do not prove what they claim; docs whose paths, commands,
names or signatures do not match the code; stale or contradictory content; and
inconsistencies between the targets.${FOCUS:+ Focus above all on: $FOCUS.}
EOF
fi

read -r -d '' REVIEW_PROMPT <<EOF
You are one of three independent reviewers of $SUBJECT

CRITICAL: You are READ-ONLY. Do NOT edit, create, move, or delete ANY file.
Your entire job is to OUTPUT findings. Do not insert comments into the docs.

Output ONLY the findings block below and nothing after it. For each real issue,
emit one object. Use the codebase as evidence — back every finding with a fact.

The "file" field MUST be the path relative to the REPOSITORY ROOT, with the full
directory prefix — e.g. "docs/tasks/042-x/solution.md" or "src/api/client.py",
never just "solution.md". Use this same form for every finding so the coordinator can match
files across reviewers without guessing.

===COUNCIL-FINDINGS-START===
[
  {
    "file": "<path relative to the repository root, with full directory prefix>",
    "location": "<for .md: the line number, as a string; for pd-* .html: the id/anchor of the element; for any other file: line number plus enclosing symbol, e.g. '42 def fetch'>",
    "priority": "P1|P2|P3",
    "title": "<short issue title>",
    "detail": "<the concern with concrete evidence>"
  }
]
===COUNCIL-FINDINGS-END===

If you find no issues, output an empty array [] between the two sentinels.
EOF

CLAUDE_OUT="/tmp/council-$SLUG-claude.txt"; CLAUDE_LOG="/tmp/council-$SLUG-claude.log"
CODEX_OUT="/tmp/council-$SLUG-codex.txt";   CODEX_LOG="/tmp/council-$SLUG-codex.log"
GROK_OUT="/tmp/council-$SLUG-grok.txt";     GROK_LOG="/tmp/council-$SLUG-grok.log"

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

**Handoff notes** — the inline comments above carry each CLI's read-only and stdin rule; full detail in [references/headless-delegation.md](references/headless-delegation.md). For Grok, never place other flags between `--single` and the prompt.

A reviewer that errors or produces no findings block does not abort the council — the coordinator proceeds with whoever succeeded and notes the gap. A degraded run (1–2 reviewers) is still useful; a 0-reviewer run is a failure (Step 6).

### Step 3: Collect the Findings

Extract the JSON array from each reviewer's output (the text between the sentinels). Some agents wrap output in prose or fences; slice on the sentinels and parse the array inside.

```bash
for AGENT in claude codex grok; do
    OUT="/tmp/council-$SLUG-$AGENT.txt"
    echo "=== $AGENT ==="
    sed -n '/===COUNCIL-FINDINGS-START===/,/===COUNCIL-FINDINGS-END===/p' "$OUT" 2>/dev/null \
        | sed '1d;$d'
done
```

Read each agent's array. If an agent's file is missing the sentinels, open its `.log` to see whether it failed or just answered in a different shape, and recover the findings by reading the file directly. Tag every finding you parse with the agent it came from (`claude` / `codex` / `grok`).

### Step 4: De-duplicate and Merge

Pool all findings from all three reviewers. Every reviewer reports `file` as a repository-root-relative path, so identical files match directly — if one comes back as a bare basename, treat it as the same file once you confirm the path. Two findings are **the same issue** when they target the same `file` and the same (or adjacent) `location` AND describe the same underlying concern — even if the wording differs. Merge each cluster into ONE thread:

- **priority**: take the highest any reviewer assigned (P1 > P2 > P3).
- **title**: the clearest of the titles.
- **detail**: the strongest single explanation, plus any distinct evidence a second reviewer added.
- **attribution**: prefix the REVIEW text with `[council: <agents>]` listing the reviewers that raised it, e.g. `[council: claude, codex]`. Consensus across reviewers is a strong signal — a 3/3 issue is almost always real; a 1/3 issue may be noise, so only keep it if its evidence holds up.

Drop findings whose evidence you can disprove against the codebase. You are the editor of record — a reviewer being wrong is expected.

### Step 5: Append Merged Threads to the Docs

You are now the single writer. For each merged issue, write ONE comment thread into the sink [references/review-targets.md](references/review-targets.md) assigns to the finding's `file`, anchored by its `location`. Threads are **append-only**: never edit or delete existing content or existing threads.

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

- **Any other file** (code, config, data): append to its `<file>.review.md` sidecar — the markdown form above plus a `LOCATION: <path>:<line> <symbol>` line. Never write threads into the code itself.

If the merged set is empty (all three reviewers came back clean), insert a single clean-review thread so the run is distinguishable from a failure, placed as review-targets.md describes for the mode:

```markdown
<!-- RESOLVED(P3): Council review complete — no issues found
REVIEW: [council: claude, codex, grok] All targets reviewed against the codebase by three independent reviewers. No problems detected.
-->
```

Then verify the threads landed:

```bash
mapfile -t SINKS < "$SCOPE_FILE"
MD_COUNT=$(rg -o "<!-- (UNRESOLVED|RESOLVED|REJECTED)\(P[123]\):" "${SINKS[@]}" 2>/dev/null | wc -l)
HTML_COUNT=$(rg -o "<pd-thread " "${SINKS[@]}" 2>/dev/null | wc -l)
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

**Mandatory** after appending, in both modes. Invoke `resolve-comments` in the current agent context on the same target — in file mode this fixes the target files themselves:

```
/resolve-comments $REVIEW_ARGS
```

Do NOT resolve feedback by manually editing or deleting threads — comment handling is append-only per the review-format conventions.

### Step 8: Verify Resolution

Confirm `resolve-comments` ran by checking for author replies across every sink:

```bash
mapfile -t SINKS < "$SCOPE_FILE"
MD_REPLIES=$(rg -o "AUTHOR:" "${SINKS[@]}" 2>/dev/null | wc -l)
HTML_REPLIES=$(rg -o 'by="author"' "${SINKS[@]}" 2>/dev/null | wc -l)
AUTHOR_REPLY_COUNT=$((MD_REPLIES + HTML_REPLIES))
echo "author reply count: $AUTHOR_REPLY_COUNT"
if [ "$AUTHOR_REPLY_COUNT" -eq 0 ]; then
    echo "resolve-comments was not applied; run /resolve-comments $REVIEW_ARGS"
fi
```

### Step 9: Strip Closed Threads from Regular Docs

Remove closed threads from regular docs; plan files, sidecars and UNRESOLVED threads are kept (see review-targets.md):

```bash
bash <skill-dir>/scripts/strip-closed-threads.sh "$SCOPE_FILE"
```

### Step 10: Report

Summarize:
- Which reviewers succeeded (claude / codex / grok) and which, if any, failed
- Raw finding counts per reviewer, and the merged count after de-duplication
- Consensus breakdown — how many issues were raised by 3/3, 2/3, 1/3 reviewers
- Merged comment count by priority (P1/P2/P3)
- How many threads were resolved, rejected, or left unresolved
- Which files were changed, which regular docs were stripped, and any `.review.md` sidecars created (the user decides whether to keep them)
- Any threads needing user input

## Comment Format

- **Which file gets the thread**: [references/review-targets.md](references/review-targets.md)
- **Markdown syntax** (`.md`, plain HTML, sidecars): [references/review-format.md](references/review-format.md)
- **`<pd-thread>` syntax** (pd-* HTML docs): [references/review-format-html.md](references/review-format-html.md)
