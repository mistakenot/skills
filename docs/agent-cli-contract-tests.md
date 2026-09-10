---
hash: "d7c34c30"
id: "d45ac9d9"
read_when: "a delegate/review/council skill stalls or errors on a claude/codex/gemini/opencode/grok/herdr flag, after upgrading one of those CLIs, or when adding a new agent flag to a skill — how the contract tests work, how to run them, and how to update the contract"
summary: "Contract-driven pytest suite that checks every claude/codex/gemini/opencode/grok/herdr flag the delegate, review and council skills pass against the installed CLIs' --help, verifies the skill sources use only contracted flags, and optionally smoke-runs the canonical headless invocations."
title: "Agent CLI Contract Tests"
---

# Agent CLI Contract Tests

The delegate, review and council skills shell out to `claude`, `codex`,
`gemini`, `opencode`, `grok` and `herdr` with hardcoded flags: permission bypasses, sandbox modes, headless
print mode, pane and worktree control. Those CLIs ship weekly. When one renames
or drops a flag, the skill text keeps reading fine while a background worker
silently stalls on a permission prompt nobody can answer.

This suite makes that drift a test failure instead of a mystery.

## Where it lives

```
src/planning-workflow/tests/
  agent-cli-contract.toml       # the flags we depend on, per agent + command path
  agent_cli_contract.py         # contract loader, --help parser, source scanner
  test_agent_cli_contract.py    # the tests
```

Run with `make test` (part of the default suite) or directly:

```bash
uv run pytest src/planning-workflow/tests/            # static checks, < 1s
make test-agent-cli-live                              # live PONG smoke, bills tokens
```

All four CLIs must be on `PATH`. A missing CLI is a failure, not a skip: the
premise is that the latest release is installed and the skills are verified
against it.

## What is checked

**Layer 0: installed and current.** Each CLI resolves on `PATH`, and its
`--version` is not older than the contract's `verified_version`. A green run
against an old build proves nothing, so the test refuses it.

**Layer 1: `--help` advertises the contract.** For every command path in the
contract (`claude`, `codex exec`, `herdr agent start`, …) the test runs
`<cmd> --help`, parses the option list (commander style for Claude Code, clap
style for the rest), and asserts every contracted flag is present. Where the
contract pins enum values (`--permission-mode bypassPermissions`,
`--sandbox read-only`, `--kind claude`, `--until working`) those must appear in
the advertised choices too. No auth, no tokens.

**Layer 2: the sources agree with the contract, both ways.** A scanner walks
`src/planning-workflow/`, `src/consult-the-council/` and
`src/assurance/evals/run.sh`, finds every `claude|codex|gemini|opencode|grok|herdr …`
invocation (joining backslash continuations, following
`herdr agent start --kind X -- …` into the nested agent's argv), and extracts
the flags. Two assertions:

- every flag a source uses is in the contract for that command path;
- every flag in the contract is used by at least one source.

The evals harness's `build_argv` in `src/evals/runners.py` is imported and
checked the same way, since its argv is Python, not shell. The
consult-the-council script's argv is checked by that module's own tests
(`src/consult-the-council/tests/`), which load the same contract file.

**Layer 3: live smoke (opt-in).** With `AGENT_CLI_LIVE=1` the canonical
unattended invocation of each agent (`claude -p --dangerously-skip-permissions`,
`codex exec --sandbox read-only`, `grok --permission-mode bypassPermissions
--always-approve --single`) is run under closed stdin and must print PONG. This
overlaps with `test-background-review-stdin.sh`, which additionally proves the
stdin-hang negative control.

## When it fails

| Failure | Meaning | Fix |
| ------- | ------- | --- |
| `test_help_exposes_contract_flags[claude]` lists `--foo` | The installed CLI dropped or renamed `--foo` | Find the replacement in `--help`, update the refs under `src/planning-workflow/refs/` and the skill bodies, update the contract, `make compile` |
| `test_help_exposes_contract_values[...]` | An enum value (permission mode, sandbox, agent kind) went away | Same as above |
| `test_sources_use_only_contract_flags` names a file:line | A skill started passing a flag nobody verified | Confirm it in `--help`, add it to the contract |
| `test_contract_flags_are_used_somewhere` | Contract lists a flag no source uses | Remove it, or the scanner missed an invocation (see below) |
| `test_installed_version_not_older_than_verified` | The CLI on this machine is older than the contract was verified against | Update the CLI |

After a green run on a newer CLI release, bump that agent's `verified_version`
in the contract so the floor moves forward.

## A false positive to recognise

If layer 1 reports many flags missing at once and the advertised list stops
partway through the alphabet, suspect truncated help output before suspecting
the CLI. Claude Code 2.1.267 exits before draining stdout when it is a pipe
and delivers 16KB of a 21KB help text; `run_help` therefore captures to a
temp file, never a pipe. A genuine removal is one or two flags, with the
rest of the list intact.

## Adding a flag or an agent

1. Use the flag in the skill source.
2. Run the scanner to see what it extracted:
   `uv run --no-dev python src/planning-workflow/tests/agent_cli_contract.py`
3. Add the flag under the matching `[[agent.<name>.command]]` entry (keyed by
   `path`, the subcommand words after the agent name, `""` for top level).
   Pin enum values under `[agent.<name>.command.values]` when the skill depends
   on a specific one.
4. Run the tests.

A new agent gets an `[agent.<name>]` table with `verified_version` and,
optionally, `live_smoke` + `live_expect` for the opt-in PONG check. Add its
name to `AGENTS` in `agent_cli_contract.py` so the scanner recognises it.

## Scanner limits

- Invocations behind a shell alias (`H="herdr --session x"; $H agent start …`)
  are invisible to it. The delegation test doc uses this pattern; its flags are
  covered because the same commands appear unaliased in the herdr refs.
- Prose that mentions a flag without an agent name in front of it is not an
  invocation and is not checked.
- Short flags are contracted as written (`-p`, `-o`); the help parser records
  both short and long forms, so either spelling passes layer 1.
