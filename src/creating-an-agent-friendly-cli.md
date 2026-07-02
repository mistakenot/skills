# Creating an Agent-Friendly CLI

Status: draft

This shared resource is a language-agnostic guide for designing command-line tools that agents can use reliably, inspectably, and safely. It applies both to new CLIs and to existing CLIs being adapted for agent use.

## Audience

- Engineers building or revising CLI tools.
- Skill authors documenting how agents should call those tools.
- Reviewers checking whether a CLI contract is practical for autonomous or semi-autonomous use.

## Agent-Friendly Means

An agent-friendly CLI should make it easy for an automated caller to:

- Discover available commands and options incrementally.
- Predict side effects before running a command.
- Run commands non-interactively.
- Parse outputs without brittle scraping.
- Detect success, partial success, and failure.
- Recover, retry, skip, or escalate safely.

## Core Principles

- Make command discovery hierarchical and predictable.
- Prefer explicit inputs over prompts.
- Use long, self-describing flags as the primary interface.
- Treat structured output as an API contract.
- Separate data on stdout from progress, warnings, and diagnostics on stderr.
- Make non-TTY execution safe by default.
- Provide dry-run or preview modes for side-effecting operations.
- Use documented, stable exit codes that guide control flow.
- Validate inputs strictly; assume agents may invent flags or values.
- Design operations to be safely repeatable.
- Make errors specific, structured, and actionable.
- Keep help text concise, example-led, and complete.
- Provide a `$tool quickstart` command for the happy-path main loop.
- Provide agent-facing docs and schema discovery inside the CLI.
- Make state-changing commands scoped, reviewable, and verifiable.
- Provide hermetic execution modes for CI and agent runs.
- Validate agent-friendliness with real or replayed agent workflows.

## Command Surface

Prefer a noun-verb command tree:

```bash
tool user create
tool user list
tool project deploy
tool invoice list
```

This lets an agent explore the CLI one layer at a time: `tool --help`, then `tool user --help`, then `tool user create --help`. Avoid flat command sets like `create-user`, `list-users`, and `deploy-project` once the CLI has enough surface area to need grouping.

Use consistent verbs across resource nouns:

- `list`
- `get`
- `create`
- `update`
- `delete`
- `ensure`
- `apply`
- `sync`

Avoid near-synonyms that split the command model, such as using both `update` and `upgrade` for the same kind of change. Avoid catch-all subcommands because they make future command growth harder to reason about. Avoid prefix abbreviations such as treating `tool u` as `tool user`; they create ambiguity as the command tree grows.

Expose schema or command introspection for larger CLIs:

```bash
tool schema --all
tool schema user create
```

The schema should be machine-readable and include command names, descriptions, flags, types, defaults, enums, required fields, and examples. This lets an agent query the contract it needs instead of carrying the whole CLI surface in prompt context.

Provide a first-class quickstart command:

```bash
$tool quickstart
```

`quickstart` should print concise markdown that works like the quickstart page for an open source library. It should show the happy-path main loop end to end: install or setup assumptions, authentication if required, the smallest useful command sequence, expected outputs, and the final verification command. Keep it practical and copy-pastable. It is not a full manual; it is the fastest route from zero context to one successful use of the tool. In generic docs, write this as `$tool quickstart`; in a concrete CLI, replace `$tool` with the executable name.

For larger tools, add an agent-facing docs surface:

```bash
$tool agent
$tool agent workflows
$tool agent workflow deploy
```

This should print compact markdown guidance organized around tasks an agent is likely to perform, not around implementation internals. Use it for workflow recipes, command sequencing, common recovery paths, and "when to use what" guidance. Keep `$tool quickstart` as the smallest happy path; use `$tool agent ...` for broader progressive disclosure.

## Flags

Every flag should have a long form. Short aliases are acceptable for humans, but long flags are the reliable agent-facing contract.

```bash
tool deploy --environment production --dry-run --format json
```

Flag guidance:

- Use lowercase words joined by hyphens, such as `--dry-run` and `--no-interactive`.
- Use `--no-` for boolean negation, such as `--color` and `--no-color`.
- Follow established names where they fit: `--help`, `--version`, `--verbose`, `--quiet`, `--output`, `--force`, `--recursive`, `--all`.
- Avoid relying on case-sensitive short flags for meaning.
- Never accept passwords directly in flags; prefer stdin, a file descriptor, or `--password-file`.
- Make value domains explicit for constrained flags, such as `--format json|table|csv|ndjson`.
- Provide `--quiet` for commands where agents need only a final identifier, path, URL, or status value.
- Provide `--cwd`, `--config`, `--no-config`, or `--profile` when ambient project state affects behavior.

## Inputs

Inputs should be explicit, validated, and deterministic.

Define precedence when the same input can come from several sources:

1. Command-line flags.
2. Environment variables.
3. Config files.
4. Defaults.

Document that precedence in help text or reference docs. If a command needs input that was not provided and there is no usable TTY, fail with a clear error instead of waiting for a prompt.

Document environment variables in a dedicated help section. Prefix tool-specific variables with the tool name, such as `MYTOOL_PROFILE`, `MYTOOL_TOKEN`, or `MYTOOL_CONFIG`, so agents can distinguish them from unrelated process state.

Validate aggressively:

- Reject unknown flags instead of ignoring them.
- Use enums for constrained values.
- Validate URLs and reject unsafe protocols or embedded credentials where inappropriate.
- Validate file paths and avoid traversal into sensitive locations.
- Validate domains and identifiers before using them in shell commands, network calls, or file paths.
- Echo the invalid input in the error when safe so the caller can correct it.

Support composable inputs for batch and pipeline use:

- Accept stdin for natural data flows, using `-` where file paths are accepted.
- Provide selectors or filters for batch operations instead of requiring agents to fetch everything and filter locally.
- Define stable ordering for list outputs so repeated runs are comparable.
- Keep startup overhead low for commands agents may call many times in a loop.

## Hermetic Execution

Agents and CI systems need a way to run commands without hidden local state changing the result.

Provide a documented hermetic mode for commands affected by config, plugins, hooks, cache, credentials, working directory, or auto-discovery. Depending on the tool, this can be one flag or a small set of flags:

```bash
$tool run --no-config --cwd /workspace/project --profile ci
```

Hermetic guidance:

- Make the working directory explicit with `--cwd` when relative paths matter.
- Provide `--no-config` or `--config <path>` to control config loading.
- Provide `--profile <name>` for named environments.
- Disable user hooks, plugins, aliases, auto-updaters, and local memory unless explicitly enabled.
- Show the effective config in structured output or through `$tool status --format json`.
- Keep cache use explicit when cached data can affect correctness.

## Outputs

Treat machine-readable output as a versioned API.

Output guidance:

- Support `--format json` for every command that returns data.
- Prefer JSON by default when stdout is not a TTY.
- Support `ndjson` for streaming or large result sets.
- Support `table` for humans and `csv` where tabular export is natural.
- Keep stdout for data only.
- Send progress, warnings, logs, and prompts to stderr.
- Never mix ANSI color, spinners, progress bars, or prose into structured stdout.
- Keep JSON field names and types stable.
- Adding optional fields is usually compatible; removing or renaming fields is breaking.
- Prefer shallow, consistent structures over deeply nested bespoke shapes.
- Provide pagination or streaming for large collections.

For errors in non-TTY or structured-output mode, write a structured error object to stderr.

Expose output and error schemas through `$tool schema`. Include schema versions in structured output when the command is consumed by automation:

```json
{
  "schema_version": "1.0",
  "status": "ok",
  "result": {}
}
```

Support response-shaping where large outputs are common:

- `--verbosity concise|normal|detailed`
- `--fields name,status,url`
- `--limit 50`
- `--page-token <token>`

Prefer high-signal fields by default. Use meaningful names, URLs, paths, statuses, and short summaries before opaque IDs. Include opaque IDs when they are needed for follow-up commands.

## Errors and Exit Codes

Exit codes are an agent's first control-flow signal. Define and document stable meanings beyond generic success and failure.

Suggested baseline:

| Code | Meaning | Typical Agent Response |
| --- | --- | --- |
| 0 | Success | Continue |
| 1 | General error | Read stderr and decide |
| 2 | Usage or invalid argument error | Fix arguments and retry |
| 3 | Resource not found | Skip, create, or ask |
| 4 | Permission denied | Escalate for authorization |
| 5 | Conflict or already exists | Skip, update, or reconcile |
| 10 | Dry-run succeeded | Safe to consider applying |

Distinguish transient failures from permanent failures. Network timeouts, rate limits, and temporary service failures should be recognizable as retryable. Invalid arguments, permission failures, and missing required inputs should not look retryable.

Actionable error output should include:

- A stable machine-readable error code.
- A short human-readable message.
- The failing input when safe to show.
- Whether the failure is retryable.
- A concrete recovery suggestion.
- A command to run next when there is an obvious fix.

## Interactivity

Agents usually run CLIs without an interactive terminal. TTY-aware behavior should make that mode safe automatically.

In non-TTY mode:

- Default to structured output.
- Disable colors.
- Disable interactive prompts.
- Disable pagers.
- Disable spinners and progress animations.
- Fail explicitly if required input is missing.

Provide explicit overrides:

- `--no-interactive` to fail instead of prompting.
- `--yes` to accept all confirmations for a command.
- `--no-color` to suppress ANSI output.
- `--format json` to force structured output.

Respect common environment conventions such as `NO_COLOR` and `TERM=dumb`. If `--yes` exists, make it comprehensive; partial confirmation bypasses are difficult for agents to reason about.

Interactive wizards are acceptable for humans, but they must be a fallback over the same command contract. Any value a wizard asks for should also be available as a flag, stdin input, config value, or environment variable. If some values are supplied and a TTY is present, prefill the wizard. If the same command runs without a TTY and required values are missing, fail with a usage error listing the exact missing inputs.

## State and Side Effects

Every command that creates, modifies, deletes, deploys, migrates, charges, sends, or otherwise changes state should support a preview path.

Dry-run guidance:

- Use `--dry-run` consistently.
- Make dry-run output structured, not just a sentence saying no changes were made.
- Show what would be created, modified, deleted, sent, or charged.
- Show the explicit scope: files, resources, account, workspace, project, environment, region, or user-visible destination.
- Show validations already performed and validations deferred until apply time.
- Show warnings, skipped work, permissions required, and expected external side effects.
- Show target identifiers, reversibility, risk, and required permissions when applicable.
- Use a distinct documented exit code for dry-run success if callers need to distinguish preview from execution.

For destructive commands, require either confirmation in TTY mode or explicit flags such as `--force --yes` in non-TTY mode. Make dangerous operations hard to trigger accidentally but straightforward to trigger deliberately.

Make review artifacts first-class for high-risk operations:

```bash
$tool deploy plan --environment production --output plan.json
$tool deploy apply --plan plan.json --yes
```

A review artifact should capture intent, scope, planned operations, expected side effects, validation results, warnings, and the exact inputs needed to apply the plan later. Prefer signed, timestamped, or checksum-protected plan files when the operation is sensitive.

Design state-changing operations to be repeatable:

- Prefer declarative commands such as `ensure`, `apply`, or `sync` where possible.
- Support `--if-exists` and `--if-not-exists` for delete and create flows.
- Return a conflict exit code when creation finds an existing resource.
- Support idempotency keys for operations that cannot be naturally idempotent, such as sending messages or taking payments.
- Make ambiguous outcomes inspectable with `get`, `status`, or operation IDs.

Document the post-action verification command for every mutating command:

```bash
$tool deploy apply --plan plan.json --yes
$tool deploy status --operation-id op_123 --format json
```

Verification commands should be read-only, structured-output friendly, and specific enough that an agent can tell whether the intended change actually happened.

## Long-Running Commands

Commands that stream, watch, poll, deploy, migrate, or otherwise run for a long time need explicit lifecycle behavior.

Provide:

- Structured progress events, preferably on stderr or as NDJSON when progress is the data.
- A final structured summary.
- Timeouts or documented timeout behavior.
- Cancellation behavior for interrupts.
- Resumability or operation IDs when work may continue server-side.
- Log locations for detailed diagnostics.
- A way to query current status separately from starting the operation.

Avoid commands that only show an animated progress UI. Agents need durable state transitions and final outcomes.

## Security

Agent-friendly CLIs should also be hard to misuse.

Security guidance:

- Never print secrets unless explicitly requested through a purpose-built command.
- Redact tokens, passwords, private keys, and session cookies in logs and errors.
- Avoid accepting secrets through flags because they can appear in process lists and shell history.
- Prefer stdin, file descriptors, secure files, or platform credential stores for secret input.
- Validate any value used in shell commands, paths, URLs, or remote execution.
- Avoid shell interpolation when structured process APIs are available.
- Make authentication scopes visible in errors and status commands.
- Use least-privilege defaults for generated credentials and tokens.

## Help Text

Help text is part of the agent interface. Agents often discover and choose commands from `--help`, so the content needs to be concise and operational.

Each command's help should include:

- A one-line purpose statement.
- Two or three realistic examples near the top.
- Required and optional flags clearly marked.
- Value domains for constrained flags.
- Default values where defaults matter.
- Side effects and confirmation requirements.
- Output formats.
- Exit codes relevant to the command.
- Subcommands with one-line descriptions for command groups.

Aim for short help per command. If the full contract is large, provide a schema command or docs link rather than burying the useful examples in a long wall of text.

Provide `$tool quickstart` as a separate markdown-oriented entry point for the happy path. Agents should be able to run it before using an unfamiliar tool and get a compact, end-to-end recipe without scanning all command help.

Provide `$tool agent` or an equivalent command for broader agent-facing workflow docs. It should explain common task loops, safe mutation patterns, recovery commands, and verification commands in concise markdown.

Respond to common help forms:

```bash
tool --help
tool -h
tool help user create
tool user create --help
```

## Agent-Facing Evals

Do not rely only on human inspection to decide whether a CLI is agent-friendly. Run realistic agent workflows against the CLI and inspect the transcripts.

Useful eval signals:

- Task completion rate.
- Number of commands needed to finish the task.
- Repeated or redundant command calls.
- Invalid flags or malformed inputs the agent attempts.
- Error recovery success.
- Whether the agent uses dry-run, plan, and verification commands correctly.
- Token volume from command help, outputs, and errors.
- Time spent in long-running commands.

Eval tasks should be grounded in realistic workflows, not only toy examples. Include at least one happy path, one missing-input recovery path, one non-TTY run, one destructive dry-run/apply flow, and one ambiguous or partial-success case.

## Testing Checklist

- `--help` is complete, concise, and current.
- `$tool quickstart` prints a concise markdown happy-path guide.
- `$tool agent` or equivalent exposes concise workflow docs for agents.
- `$tool schema` exposes command, output, and error contracts where the CLI is large enough to need it.
- Command discovery works layer by layer from the root command.
- Every flag has a long form.
- `--quiet` returns only the final value when a command naturally has one.
- Unknown flags fail fast.
- Commands work without an interactive TTY.
- Non-TTY mode disables colors, prompts, pagers, and spinners.
- Non-TTY missing-input failures list the exact flags or inputs needed.
- Hermetic mode controls config, cwd, profile, hooks, plugins, and cache behavior where relevant.
- Structured output is valid and stable.
- Structured output includes a schema version when consumed by automation.
- stdout contains data only when structured output is requested.
- stderr contains progress, warnings, logs, and structured errors.
- Exit codes distinguish common failure classes.
- Destructive commands have preview or dry-run support.
- Dry-run output says exactly what would change and where.
- High-risk operations can emit a reviewable plan artifact.
- State-changing commands are idempotent or accept idempotency keys.
- Mutating commands document and support read-only verification commands.
- Error messages include actionable recovery guidance.
- Secrets are not exposed in flags, logs, or errors.
- Agent workflow evals cover happy path, recovery, non-TTY, destructive, and partial-success cases.

## Examples To Add Later

TODO: Add language-agnostic examples of good and bad CLI contracts.

Useful example categories:

- Small single-resource CRUD CLI.
- Deployment CLI with plan/apply.
- Streaming export command.
- Authenticated API wrapper.
- Dangerous destructive command.

## Sources

- Johnixr, "Agent CLI Design Guide": https://raw.githubusercontent.com/Johnixr/agent-cli-guide/refs/heads/main/GUIDE.md
- Anthropic, "Writing effective tools for AI agents": https://www.anthropic.com/engineering/writing-tools-for-agents
- clig.dev, "Command Line Interface Guidelines": https://clig.dev/
- InfoQ, "Keep the Terminal Relevant: Patterns for AI Agent Driven CLIs": https://www.infoq.com/articles/ai-agent-cli/
- OpenStatus, "Building a CLI That Works for Humans and Machines": https://www.openstatus.dev/blog/building-cli-for-human-and-agents
- Propel Code, "Agent-First CLI Design: Make Coding Agents Reviewable": https://www.propelcode.ai/blog/agent-first-cli-design-coding-agents
- Speakeasy, "Making your CLI agent-friendly": https://www.speakeasy.com/blog/engineering-agent-friendly-cli
- Steve Kinney, "Structured CLI Output as Pipeline Glue": https://stevekinney.com/courses/self-testing-ai-agents/structured-cli-output-as-pipeline-glue

## Open Questions

TODO: Track unresolved design choices as more guidance is folded in.
