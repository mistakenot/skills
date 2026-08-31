# Headless CLI delegation

How to delegate to Claude Code, Codex, or Grok **without a pane** — invoking
the CLI in print/headless mode directly from bash, capturing its output, and
exiting. Nothing here depends on a pane or a multiplexer: this is plain
process invocation, so it applies the same way whether or not `herdr` is
involved.

Used by the `request-claude-review`, `request-codex-review`,
`request-grok-review`, and `request-council-review` skills — each invokes its
CLI in print/headless mode with `/review-task`, then hands off to
`resolve-comments`.

When you need a second agent to review task docs without an interactive
pane, invoke the matching CLI headlessly from bash. All three follow the
same shape: set cwd, send `/review-task <folder>`, capture output, count
comments, then run `/resolve-comments` in the coordinator.

| Agent | Headless command | Stdin gotcha | Auto-approve flags |
| ----- | ---------------- | ------------ | ------------------- |
| **Claude Code** | `claude -p --add-dir "$CWD" --dangerously-skip-permissions "/review-task …"` | **Requires** `< /dev/null` — inherited open stdin stalls ~3s or blocks in background | `--dangerously-skip-permissions` |
| **Codex** | `codex exec --cd "$CWD" --sandbox workspace-write "…"` | **Requires** `< /dev/null` — blocks on open stdin with "Reading additional input from stdin…" | `--sandbox workspace-write` (writes task docs) |
| **Grok** | `grok --cwd "$CWD" --permission-mode bypassPermissions --always-approve --single "/review-task …"` | **No redirect needed** — headless mode ignores piped stdin | `--permission-mode bypassPermissions --always-approve` |

Grok discovers skills from `.agents/skills/` (the same tree `auto skill
sync` renders for Codex). Ensure `review-task` is installed before
delegating. `--single` (short form `-p`) takes the prompt as its immediate
value; never put other flags between it and the prompt.

Auth: Claude uses `~/.claude/.credentials.json`; Codex uses `codex login`;
Grok uses `~/.grok/auth.json` or `XAI_API_KEY`.

**Read-only variants.** A reviewer that must not touch the docs (e.g. the
parallel reviewers in `request-council-review`) swaps the auto-approve/write
flags above for read-only equivalents: `--permission-mode plan` for Claude
Code, `--sandbox read-only` for Codex. Grok's `bypassPermissions` only avoids
interactive prompts — read-only-ness there comes from the prompt itself
forbidding edits.
