# Context: Task 001

Codebase findings for [001-default-subcommand](plan.html). Covers key files, patterns, and conventions relevant to adding `default?: string` to `CommandDef`.

## Key Files

- `src/types.ts:99-107` — `CommandDef<T>` interface: `meta`, `args`, `subCommands`, `plugins`, `setup`, `cleanup`, `run`. The `default` field goes here, after `subCommands`.
- `src/command.ts:51-65` — `runCommand` subcommand dispatch: resolves `subCommands`, finds `subCommandName` via `findSubCommandIndex`, throws `E_NO_COMMAND` when name missing and no `run`. The new `cmd.default` branch sits in this else-chain.
- `src/command.ts:108-124` — `resolveSubCommand`: used by `runMain` to resolve the right command for `--help`. Needs a `cmd.default` fallback so `--help` with no args shows the default sub-command.
- `src/command.ts:128-147` — `_findSubCommand`: resolves by direct key or `meta.alias`. Re-used by the default branch — no changes needed.
- `src/command.ts:149-162` — `findSubCommandIndex`: finds the positional index of the subcommand token, skipping flags. Returns `-1` when no token found. Already handles the "no subcommand given" case.
- `test/main.test.ts:108-143` — `describe('sub command')`: reference pattern for testing `runCommand` with subcommands — mocks `setup`, `run`, `cleanup` as `vi.fn()`, asserts call count and argument.
- `src/_utils.ts` — `CLIError(message, code)`: existing error codes include `E_NO_COMMAND` and `E_UNKNOWN_COMMAND`. Use `E_UNKNOWN_COMMAND` for an unresolved default name.

## Patterns

- Subcommand dispatch always resolves lazily via `resolveValue(cmd.subCommands)` — the new default path must also go through `_findSubCommand` (handles lazy + alias).
- `runCommand` calls `cmd.run` unconditionally after the subcommand block; the current guard is `typeof cmd.run === "function"`. When a default subcommand fires, `cmd.run` must be skipped — introduce a flag (`ranDefault`) before the try block.
- `resolveSubCommand` is called in `runMain` for both `--help` and error paths; its fallback must mirror `runCommand`'s logic.

## Related Tasks

- None (first task in this repo).
