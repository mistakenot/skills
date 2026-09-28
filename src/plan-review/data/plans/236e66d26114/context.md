# Context: Task 001 — improve-time-flags

Codebase context gathered for plan.html in this folder.

## Key Files

- `internal/filter/filter.go:48-56` — `ParseSince`: delegates directly to `time.ParseDuration`; rejects `d` and `w` because those are not Go duration units.
- `internal/filter/filter.go:66-87` — `NewTimeFilterAbsolute`: calls `time.Parse(time.RFC3339, ...)` only; rejects plain dates like `"2026-03-13"`.
- `cmd/root.go:111-123` — `buildTimeFilter`: early-returns when `sinceFlag != ""`; any `--before` value is silently discarded in that branch.
- `cmd/root.go:93-101` — Cobra flag registrations; `--since` description currently says only `10m, 2h, 60s`.
- `internal/filter/filter_test.go:33-57` — `TestParseSince`: tests for `10m`, `2h`, `60s`, `abc`; no `d`/`w` cases.
- `internal/filter/filter_test.go:114-158` — `TestNewTimeFilterAbsolute`: tests for RFC 3339 only; no plain-date cases.
- `README.md:193-195` — Time filtering section states "Supported units: `s`, `m`, `h`" — needs updating.
- `README.md:170-179` — Flags table; `--since`, `--after`, `--before` descriptions to update.

## Patterns

- `time.DateOnly` constant (`"2006-01-02"`) is available in Go 1.20+ (this project uses Go 1.25, see README) — safe to use.
- All filter functions are pure (no I/O), making them straightforward to unit-test with table-driven tests.
- `buildTimeFilter` reads package-level cobra flag vars (`sinceFlag`, `afterFlag`, `beforeFlag`); its logic lives entirely in `cmd/root.go`. Cannot be unit-tested without cobra setup, so coverage via e2e binary invocation is the pragmatic choice.
- Existing `TestParseSince` and `TestNewTimeFilterAbsolute` are table-driven — extend the tables rather than adding new test functions.

## Related Tasks

None (this is the first task in docs/tasks/).
