Invoke Claude Code in print mode on the `review-task` skill:

```bash
LAST_MSG_FILE="/tmp/claude-$SLUG-review.txt"
LOG_FILE="/tmp/claude-$SLUG-review.log"

claude \
    --add-dir "$CWD" \
    -p \
    --dangerously-skip-permissions \
    "/review-task $REVIEW_ARGS" \
    < /dev/null \
    2>&1 | tee "$LOG_FILE" > "$LAST_MSG_FILE"
REVIEW_EXIT=${PIPESTATUS[0]}
echo "claude exit code: $REVIEW_EXIT"
```

**`< /dev/null` is required.** In print mode (`-p`) with an inherited, open stdin
(as in a background launch) Claude waits several seconds for stdin data before
proceeding (`no stdin data received in 3s, proceeding without it`). Redirecting
from `/dev/null` gives an immediate EOF so the review starts without the stall.
