Invoke Grok in headless mode on the `review-task` skill:

```bash
LAST_MSG_FILE="/tmp/grok-$SLUG-review.txt"
LOG_FILE="/tmp/grok-$SLUG-review.log"

grok \
    --cwd "$CWD" \
    --permission-mode bypassPermissions \
    --always-approve \
    --single "/review-task $REVIEW_ARGS" \
    2>&1 | tee "$LOG_FILE" > "$LAST_MSG_FILE"
REVIEW_EXIT=${PIPESTATUS[0]}
echo "grok exit code: $REVIEW_EXIT"
```

**No `< /dev/null` redirect is needed.** Unlike `codex exec` and `claude -p`, Grok
headless mode does not read piped stdin into the prompt — it uses the `--single`
value directly and does not block on an inherited, never-closing stdin when
launched in the background.

`--permission-mode bypassPermissions` and `--always-approve` are both required for
unattended runs so Grok can read and edit files without prompting.

`--single` takes the prompt as its immediate value; it is not a boolean headless
flag. Do not place other flags between `--single` (or `-p`) and the prompt.
