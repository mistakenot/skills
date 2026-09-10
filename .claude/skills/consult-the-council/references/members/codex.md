# Member: codex (OpenAI Codex CLI)

Preference 2. OpenAI models via `codex exec`.

## Read-only invocation

`scripts/council.py` runs, for `--access repo`:

```bash
codex exec --cd "$CWD" --sandbox read-only -o "$ANSWER_FILE" "$PROMPT" < /dev/null
```

and for `--access none`, from an empty directory:

```bash
codex exec --cd "$EMPTY" --sandbox read-only -o "$ANSWER_FILE" --skip-git-repo-check "$PROMPT" < /dev/null
```

`--skip-git-repo-check` is needed because codex refuses to run outside a git
repository and the empty directory is not one.

- `--sandbox read-only` is enforced by the sandbox, not by the prompt: the
  agent genuinely cannot write.
- `-o FILE` writes the final message to a file. stdout carries session and
  tool noise, so `council.py` takes the answer from the file and keeps
  stdout in the `.log`.
- `< /dev/null` is required: with a piped stdin codex reads it as extra
  prompt input and blocks at "Reading additional input from stdin..." until
  EOF, which in a background launch never comes.

## Auth

`codex login`; `codex login status` reports it. `council.py` reports status
`auth` with that hint.

## Notes

- More than one `codex` build can be on PATH (an nvm-managed one and one in
  `~/.local/bin`); `which codex` decides which answers.
- Flags are pinned in the agent CLI contract.
