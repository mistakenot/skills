# Member: gemini (Gemini CLI)

Preference 3. Google models via the Gemini CLI.

## Read-only invocation

`scripts/council.py` runs, for either access mode:

```bash
gemini -p "$PROMPT" --approval-mode plan < /dev/null
```

from `$CWD` (repo) or an empty directory (none); the CLI uses its working
directory as the workspace.

- `-p` is headless mode. The CLI appends stdin to the prompt if any is
  present, so stdin is closed to keep the prompt file the only input.
- `--approval-mode plan` is the read-only mode. Do not use `--yolo` or
  `auto_edit`.
- The answer is stdout.

## Auth

Either `GEMINI_API_KEY` in the environment or OAuth. Which one is used is
`security.auth.selectedType` in `~/.gemini/settings.json`; when it says
`gemini-api-key` and the variable is unset, the CLI exits 41 with "you must
specify the GEMINI_API_KEY environment variable". `council.py` reports that
as status `auth` with the hint to export the key or switch the setting to
OAuth (run `gemini` interactively and use `/auth`).

## Notes

- Verified against Gemini CLI 0.34.0 for flags only; the read-only PONG
  smoke could not be run on this machine because gemini was not authed at
  the time. Run `make test-agent-cli-live` after logging in to confirm.
- Flags are pinned in the agent CLI contract.
