# Context: 065 skill-add-comma-filter

## Key Files

- `auto-skill/internal/cli/add.go:122` — `--skill` flag: `StringArrayVar`, description "exact-match skill filter (repeatable; '*' for all)"
- `auto-skill/internal/cli/add.go:40-41` — `--as` guard: `len(skills) > 1` (correctly fires with `StringSliceVar` after cobra splits `a,b` → `["a","b"]`)
- `auto-skill/internal/add/add.go:539` — `applySelection` function entry
- `auto-skill/internal/add/add.go:557-559` — normalises each skill name: `strings.ToLower(strings.TrimSpace(s))` — safe for post-split entries
- `auto-skill/internal/add/add.go:571-583` — not-found branch: builds `available` and `missing` lists, returns `AddError{Code: CodeSkillNotFound, Message: "skill(s) not found: X; available: Y"}`
- `auto-skill/internal/cli/cli_integration_test.go:1128-1141` — `TestAddSkillNotFound`: checks exit non-zero and `stderr` contains "alpha"
- `auto-skill/internal/cli/cli_integration_test.go:1112-1126` — `TestAddAsConflictFlagValidation`: uses `--skill a --skill b` (two flags)
- `auto-skill/internal/cli/init.go:142` — `--target` uses `StringSliceVar` — **existing precedent within auto-skill**

## Existing Precedents for StringSliceVar

- `auto-skill/internal/cli/init.go:142`: `StringSliceVar` for `--target` (in the same binary)
- `auto-etl/cmd/run.go:140`: `StringSliceVar` for `--only` (consistent across tools)
- No manual `strings.Split` on flag values anywhere in the codebase

## Normalisation is Already Correct

`applySelection` calls `strings.ToLower(strings.TrimSpace(s))` on each element of `opts.Skills`. After cobra's CSV split, each element is already a clean name (no embedded commas). TrimSpace handles trailing spaces from `--skill "a, b"`.

## --as Guard Remains Correct

```go
if as != "" && (len(skills) > 1 || (len(skills) == 1 && skills[0] == "*")) {
```
With `StringSliceVar`, `--skill a,b` → `["a","b"]`, `len == 2`, guard fires correctly when `--as` is also given.

## Test Helper Signatures

- `makeAddFixture(t *testing.T, skills map[string]string) string` — creates a temp git repo, returns path
- `addSkillMD(name, desc string) string` — minimal SKILL.md content
- `runCLI(t, ...args) (stdout, stderr string, code int)`
- Verifying installed skills: pass `--text` and check `stdout` contains "Added <name>"

## Impact Analysis

| File | Change | Risk |
|------|--------|------|
| `cli/add.go` | `StringArrayVar` → `StringSliceVar` for `--skill` | Low — cobra handles split; all existing callers pass one or two explicit flags |
| `add/add.go` | Append hint line to not-found error message | Very low — string formatting only |
| `cli_integration_test.go` | Add 2 new tests, update 1 assertion | Zero — test-only |

## Related Tasks

No prior tasks directly modified `--skill` flag type. Task 063 (auto-mail parent handle) is the last merge, unrelated.
