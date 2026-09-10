# Member: grok (Grok CLI)

Preference 5. xAI models via the Grok CLI.

## Read-only invocation

`scripts/council.py` runs, for either access mode:

```bash
grok --cwd "$CWD" --permission-mode plan --single "$PROMPT"
```

with `$CWD` the repo (repo) or an empty directory (none).

- `--single` (short form `-p`) takes the prompt as its immediate value and
  exits after one turn. Never put another flag between `--single` and the
  prompt.
- `--permission-mode plan` is the read-only mode. The review skills use
  `bypassPermissions --always-approve` because they need to edit docs; a
  council member never does, so plan mode is the right choice here.
- Headless mode ignores piped stdin, so no redirect is needed; `council.py`
  closes stdin anyway for uniformity.
- The answer is stdout.

## Auth

`~/.grok/auth.json` or `XAI_API_KEY`. An expired token does not fail fast:
headless mode falls into an interactive device-code login ("Waiting for
authorization...") and hangs until the timeout. `council.py` recognises
that text and reports status `auth` with the hint `grok login`.

## Notes

- `--permission-mode plan` is advertised in the help output of grok 0.2.60 and is
  in the agent CLI contract, but the PONG smoke in plan mode has not been
  run on this machine because grok was not authed at the time. Run
  `make test-agent-cli-live` after `grok login` to confirm.
- Grok discovers skills from `.agents/skills/`; irrelevant for a council
  member, which needs no skills.
