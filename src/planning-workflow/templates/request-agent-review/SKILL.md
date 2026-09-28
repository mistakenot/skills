---
name: request-{{ var:agent }}-review
description: "Runs a {{ var:product }} review of task planning docs or any files (code, markdown, config), then resolves its comments. Use when 'request {{ var:agent }} review', '{{ var:agent }} review task 042', 'have {{ var:agent }} review <file>'."
---

# Request {{ var:Agent }} Review

Have {{ var:product }} review a target in a fresh headless session, then resolve the comment threads it leaves.

> Part of the task planning workflow. See [references/workflow-overview.md](references/workflow-overview.md) for the full pipeline.

## Input

- **Target** — one of:
  - a **task ID** (`042`) or task folder (`042-add-team-settings`, `docs/tasks/042-…`) → **task mode**, the usual case: the task's planning docs, reviewed as a set.
  - one or more **file or directory paths** (code, markdown, HTML, config) → **file mode**. Directories expand to their non-ignored files.
- **Focus** (optional, file mode) — what to look for, e.g. `"error handling"`.
- The repository root path (absolute) -- use the current working directory if already at root.

Threads land inline in markdown and HTML, and in a `<file>.review.md` sidecar next to any other file — see [references/review-targets.md](references/review-targets.md).

## Process

### Step 1: Resolve the Targets

{{ ref:review-scope.md }}

### Step 2: Run {{ var:Agent }} Review

{{ var:invoke }}

### Step 3: Check for Comments

Count the threads {{ var:Agent }} left across every sink (inline docs and sidecars):

```bash
mapfile -t SINKS < "$SCOPE_FILE"
MD_COUNT=$(rg -o "<!-- (UNRESOLVED|RESOLVED|REJECTED)\(P[123]\):" "${SINKS[@]}" 2>/dev/null | wc -l)
HTML_COUNT=$(rg -o "<pd-thread " "${SINKS[@]}" 2>/dev/null | wc -l)
COMMENT_COUNT=$((MD_COUNT + HTML_COUNT))
echo "review comment count: $COMMENT_COUNT (md=$MD_COUNT html=$HTML_COUNT)"
```

### Step 4: Handle Failure

If {{ var:Agent }} exited non-zero or left no comments, inspect the log to diagnose:

```bash
if [ "$REVIEW_EXIT" -ne 0 ] || [ "$COMMENT_COUNT" -eq 0 ]; then
    echo "{{ var:agent }} failed or no comments found; inspect log output"
    tail -n 200 "$LOG_FILE"
fi
```

If the log contains `unexpected argument` (or `unknown option`), the installed `{{ var:agent }}` has renamed or
dropped a flag this skill passes (it has happened before: codex's `--full-auto` became
`--sandbox workspace-write`). Check `--help` for the current spelling, and if this is a
vendored copy of the skill, run `auto skill update` first — the upstream copy may already
carry the fix.

Stop and report the failure to the user. Do not proceed to resolution.

### Step 5: Resolve Comments

**Mandatory**, in both modes. After a successful review with comments, invoke `resolve-comments` in the current agent context on the same target:

```
/resolve-comments $REVIEW_ARGS
```

In file mode this edits the target files themselves — that is the point: sidecar threads are fixed in the code they point at.

Do NOT resolve feedback by manually editing or deleting comment threads. Comment handling is append-only per the review format conventions.

### Step 6: Verify Resolution

Confirm that `resolve-comments` ran by checking for author replies across every sink:

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

### Step 7: Strip Closed Threads from Regular Docs

Plan files keep every thread as their decision log. A regular doc (a README, guide, or plain HTML page) should not carry review history, so once resolution is verified, remove its RESOLVED and REJECTED threads:

```bash
bash <skill-dir>/scripts/strip-closed-threads.sh "$SCOPE_FILE"
```

The script skips plan files (anything under `docs/tasks/`, and pd-* HTML docs) and `.review.md` sidecars, and always keeps UNRESOLVED threads — they still need an answer. Run it only after Step 6, which counts the replies it removes.

### Step 8: Report

Summarize:
- Whether the {{ var:Agent }} review succeeded, and the mode (task / files)
- Comment count by priority (P1/P2/P3)
- How many threads were resolved, rejected, or left unresolved
- Which files were changed, which regular docs had closed threads stripped, and any `.review.md` sidecars created (the user decides whether to keep or delete them)
- Any threads needing user input

## Comment Format

- **Which file gets the thread**: [references/review-targets.md](references/review-targets.md)
- **Markdown syntax** (`.md`, plain HTML, sidecars): [references/review-format.md](references/review-format.md)
- **`<pd-thread>` syntax** (pd-* HTML docs): [references/review-format-html.md](references/review-format-html.md)
