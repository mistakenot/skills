---
name: handoff
description: "Store and retrieve short handoff notes through a machine-local JSONL-backed LIFO stack. Use when the user asks to hand off context between sessions or agents, save text for later, or run /handoff push, /handoff pull, or /handoff pop."
---

# Handoff

Persist short text notes on the local machine and retrieve them later in last-in,
first-out order. The default store is `$HOME/.handoff.jsonl`; each line is one
JSON object with `created_at` and `text` fields.

## Commands

Always use the bundled script for stack operations:

```bash
uv run "$CLAUDE_SKILL_DIR/scripts/handoff.py" push "text to hand off"
uv run "$CLAUDE_SKILL_DIR/scripts/handoff.py" pull
```

For Codex or another agent runtime, substitute the directory containing this
`SKILL.md` for `$CLAUDE_SKILL_DIR`.

### push

Append one item to the stack.

```bash
uv run "$CLAUDE_SKILL_DIR/scripts/handoff.py" push "investigate flaky test in auth"
printf '%s\n' "$LONG_NOTE" | uv run "$CLAUDE_SKILL_DIR/scripts/handoff.py" push
```

Use command arguments for short one-line notes. Use stdin for multiline or
generated text.

### pull / pop

Read and remove the most recently pushed item:

```bash
uv run "$CLAUDE_SKILL_DIR/scripts/handoff.py" pull
uv run "$CLAUDE_SKILL_DIR/scripts/handoff.py" pop
```

`pop` is an alias for `pull`. Both commands print the stored text to stdout and
exit non-zero when the stack is empty.

## Options

- `--file PATH`: use a different JSONL stack file for tests or a scoped handoff.
  Place this before the subcommand: `handoff.py --file /tmp/handoff.jsonl push
  "note"`.
- `HANDOFF_FILE=/path/to/file.jsonl`: override the default store path.
- `pull --json`: print the complete JSON object instead of only `text`.

Use the script rather than editing `$HOME/.handoff.jsonl` by hand, so push and
pull operations stay serialized under a file lock.
