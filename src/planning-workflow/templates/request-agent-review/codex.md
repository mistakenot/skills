Invoke Codex headlessly on the `review-task` skill:

```bash
LAST_MSG_FILE="/tmp/codex-$SLUG-review.txt"
LOG_FILE="/tmp/codex-$SLUG-review.log"

codex exec \
    --cd "$CWD" \
    --sandbox workspace-write \
    -o "$LAST_MSG_FILE" \
    "\$review-task $REVIEW_ARGS" \
    < /dev/null \
    2>&1 | tee "$LOG_FILE" >/dev/null
REVIEW_EXIT=${PIPESTATUS[0]}
echo "codex exit code: $REVIEW_EXIT"
```

**`< /dev/null` is required.** `codex exec` reads its prompt from stdin whenever
stdin is a pipe — even when a prompt argument is supplied, it appends piped stdin
as a `<stdin>` block and blocks reading until EOF (you'll see `Reading additional
input from stdin...`). In a background launch stdin is an inherited, never-closing
pipe, so codex hangs forever instead of running the review. Redirecting from
`/dev/null` gives an immediate EOF so the prompt argument is used directly.
