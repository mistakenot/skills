# Context: Task 001

Codebase context for per-model compaction settings. See [plan.html](plan.html).

## Key Files

- `packages/coding-agent/src/core/settings-manager.ts:13-17` — `CompactionSettings` interface (user-facing, all fields optional): `enabled?`, `reserveTokens?`, `keepRecentTokens?`
- `packages/coding-agent/src/core/settings-manager.ts:100` — `Settings.modelThinkingLevels?: Record<string, ThinkingLevel>` — the established per-model override pattern keyed by `"provider/modelId"`, used as the design reference
- `packages/coding-agent/src/core/settings-manager.ts:794` — `getModelThinkingLevel(provider, modelId)` — reference implementation: `this.settings.modelThinkingLevels?.[`${provider}/${modelId}`]`
- `packages/coding-agent/src/core/settings-manager.ts:830-857` — compaction getter methods: `getCompactionEnabled()`, `getCompactionReserveTokens()`, `getCompactionKeepRecentTokens()`, `getCompactionSettings()`
- `packages/coding-agent/src/core/settings-manager.ts:408` — settings parse path: raw `JSON.parse` → cast to `Settings`; no field-level validation, so `profiles` will round-trip correctly without further parser changes
- `packages/coding-agent/src/core/agent-session.ts:540` — `_compactBeforeNextAssistantResponse`: calls `getCompactionSettings()`, has `this.model` available
- `packages/coding-agent/src/core/agent-session.ts:1981` — `compact()` manual path: calls `getCompactionSettings()`, has `this.model` available
- `packages/coding-agent/src/core/agent-session.ts:2154` — `_checkCompaction`: calls `getCompactionSettings()`, has `this.model` available via `this.model?.contextWindow`
- `packages/coding-agent/src/core/agent-session.ts:2270` — `_runAutoCompaction`: calls `getCompactionSettings()`, has `this.model` available
- `packages/coding-agent/src/core/agent-session.ts:906` — `get model(): Model<any> | undefined` — model has `.provider: ProviderId` and `.id: string`
- `packages/coding-agent/src/core/compaction/compaction.ts:235` — coding-agent's `shouldCompact(contextTokens, contextWindow, settings)` — consumes resolved `CompactionSettings`, no change needed
- `packages/agent/src/harness/compaction/compaction.ts:147-161` — harness-internal `CompactionSettings` (all fields required) + `DEFAULT_COMPACTION_SETTINGS` — NOT modified (out of scope)
- `packages/agent/src/harness/runtime/drive/structural.ts:1123-1145` — harness threshold check using `checkpoint.settings.compaction` — NOT modified (out of scope)
- `packages/coding-agent/docs/settings.md:114-130` — compaction settings table and JSON example to be updated
- `packages/coding-agent/docs/compaction.md:43` — compaction docs to be updated

## Patterns

- Per-model overrides follow `modelThinkingLevels` pattern exactly: key is `"${provider}/${modelId}"`, both as index when writing and as lookup when reading.
- `SettingsManager.inMemory(settings?)` factory in tests: pass `Partial<Settings>` directly, no file I/O.
- Nested settings getters: `this.settings.compaction?.field ?? defaultValue` — profiles follow the same nullable chain.
- Settings are deep-merged (global + project) via `deepMergeSettings`; `profiles` as a plain object will merge correctly at the object level (project profile keys override global keys).
- Test pattern: `SettingsManager.inMemory({ compaction: { profiles: { "anthropic/claude-opus": { reserveTokens: 400000 } } } }).getCompactionSettings("anthropic", "claude-opus")` → `toEqual({ enabled: true, reserveTokens: 400000, keepRecentTokens: 20000 })`.
