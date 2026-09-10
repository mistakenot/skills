# Member: claude (Claude Code)

Preference 1. Anthropic models via the Claude Code CLI.

## Read-only invocation

`scripts/council.py` runs, for `--access repo`:

```bash
claude --add-dir "$CWD" --tools "Read,Grep,Glob" -p "$PROMPT" < /dev/null
```

and for `--access none`, from an empty directory, with no tools at all:

```bash
claude --tools "" -p "$PROMPT" < /dev/null
```

- Read-only comes from the tool allowlist, not from `--permission-mode
  plan`. Plan mode was tried first: it made claude behave like a planning
  session (it wrote a plan file under `~/.claude/plans/` and opened its
  answer with remarks about missing planning tools) and took about 110s
  for an answer the allowlist form gave in 5s. An allowlist is also the
  stronger guarantee: there is no Bash, Edit or Write to misuse.
- `--add-dir` and `--tools` both take lists, so the prompt must not follow
  either directly: `--tools "Read,Grep,Glob" "$PROMPT"` parses the prompt
  as a tool name and print mode then fails with "Input must be provided".
  The boolean `-p` sits between them and the prompt.
- `-p` is print mode: answer on stdout, exit. The answer is the whole of
  stdout.
- `< /dev/null` matters: with inherited open stdin, print mode waits a few
  seconds for input before proceeding, and blocks in a background launch.

## Auth

`~/.claude/.credentials.json`. Not logged in shows as an auth error on
stdout; `council.py` reports status `auth` with the hint `claude login`.

## Notes

- If the parent is itself Claude Code, this member is the same family as
  the parent. Its answer still counts, but watch for it clustering with the
  parent's own prior; that is the correlation the other members exist to
  break.
- Flags are pinned in the agent CLI contract
  (`src/planning-workflow/tests/agent-cli-contract.toml`).
