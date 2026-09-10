# Member: opencode

Preference 4. OpenCode is a harness, not a model: it runs whichever
provider/model its config selects. On this machine the default is
`z-ai/glm-5.3`, which is a model family none of the other members use, so
it earns its seat on diversity. If it were pointed at an Anthropic or
OpenAI model it would add a vote without adding a view; check with
`opencode models` or the banner line it prints (`> plan · provider/model`).

## Read-only invocation

`scripts/council.py` runs, for either access mode:

```bash
opencode run --dir "$CWD" --agent plan --format json "$PROMPT" < /dev/null
```

with `$CWD` the repo (repo) or an empty directory (none).

- `--agent plan` selects the built-in read-only agent. The default `build`
  agent has write permission on everything and must not be used here.
- `--dir` sets the project root. The process working directory is not
  enough: without `--dir`, opencode treated the parent's cwd as the project
  and auto-rejected every read of the repo as an "external directory".
- `--format json` is required, not cosmetic. With the default format the
  answer text is dropped whenever stdout is not a terminal (verified: a
  piped PONG printed only the `> plan · model` banner). The JSON stream
  carries the answer as `text` events; `council.py` concatenates them.

## Auth

`opencode auth login` (alias of `opencode providers`). Missing credentials
surface as a provider error on stdout; `council.py` reports status `auth`.

## Notes

- Verified live on opencode 1.15.13: `--agent plan --format json` answered
  a PONG in about 20 seconds, and with `--dir` read the repo's Makefile.
- The model choice is an OpenCode config decision, not a council one. To
  change it, edit `~/.config/opencode/opencode.jsonc`.
- Flags are pinned in the agent CLI contract.
