# Context: Task 004

Code context for `ts-alias-reexport-resolution`. See [plan.html](plan.html).

## Key Files

- `auto-graph/internal/scanner/typescript.go:72-81` — `patterns` slice: 7 ast-grep patterns including 3 re-export patterns. Missing: `export * as $_ from "$_"` (namespace re-export).
- `auto-graph/internal/scanner/typescript.go:191-228` — `extractImportPath`: extracts import specifier from ast-grep match text using `reFromClause` (`from\s+['"]([^'"]+)['"]`) — handles both quote styles.
- `auto-graph/internal/resolver/typescript.go:62-112` — `NewTypeScriptResolver` + `loadTSConfig`: reads `tsconfig.json`, parses `compilerOptions.baseUrl` and `compilerOptions.paths`, builds `[]pathMapping` sorted longest-prefix-first.
- `auto-graph/internal/resolver/typescript.go:126-150` — `Resolve`: dispatches to `resolveAlias` (aliases), `resolveRelative` (relative), or external (bare specifiers).
- `auto-graph/internal/resolver/typescript.go:168-201` — `resolveAlias`: substitutes alias prefix, joins with `baseDir = filepath.Join(projectRoot, baseURL)`, then calls `probeFile`.
- `auto-graph/internal/cli/code_graph.go:227-317` — `buildGraph`: calls `res.Resolve(m.ImportPath, m.SourceFile, projectRoot)` for each scanner match; creates edges for resolved non-external paths.
- `auto-graph/internal/cli/code_graph_test.go:200-219` — `runGoGraphFixture`: pattern to replicate for TypeScript.
- `auto-graph/internal/scanner/typescript_test.go:69-127` — `TestAllImportStyles`: checks 6 import kinds; needs 4 more re-export entries.
- `auto-graph/internal/scanner/typescript_test.go:179-207` — `TestReexport`: focused re-export check.
- `auto-graph/internal/resolver/typescript_test.go:36-53` — `TestAliasResolve`: passes with `path-aliases` fixture (`@/*` → `src/*`, `baseUrl: "."`).

## Patterns

- Go integration tests for scanner use `exec.LookPath("ast-grep")` skip guard (see `typescript_test.go:18-23`).
- Go CLI integration tests use `runGoGraphFixture(t, fixtureName)` returning `*graph.Graph` (see `code_graph_test.go:200-219`).
- The TypeScript resolver accepts absolute `sourceFile` path (from ast-grep) and uses `filepath.Dir(sourceFile)` for relative resolution — this is correct because ast-grep returns absolute paths.
- `probeExtensions` tries exact path, then `.ts`, `.tsx`, `.js`, `.jsx`, `/index.ts`, `/index.tsx`, `/index.js`, `/index.jsx` (see `resolver/typescript.go:26-36`).
- ast-grep patterns use `--globs !node_modules --globs !dist --globs !build` exclusions.

## Test Fixtures

- `auto-graph/testdata/fixtures/all-import-styles/reexport_source.ts` — currently only has `export { something } from "./reexport_target";` (one line, double-quoted named re-export).
- `auto-graph/testdata/fixtures/all-import-styles/` — has: `dynamic_target.ts`, `main.ts`, `reexport_source.ts`, `reexport_target.ts`, `require_target.ts`, `side_effect.ts`, `static_target.ts`, `type_target.ts`, `tsconfig.json` (`{}`).
- `auto-graph/testdata/fixtures/path-aliases/tsconfig.json` — `{"compilerOptions":{"baseUrl":".","paths":{"@/*":["src/*"]}}}`.
- `auto-graph/e2e/testdata/sample-project/tsconfig.json` — `baseUrl: "./src"`, paths: `@/*`, `@components/*`, `@utils/*`.
- `auto-graph/e2e/testdata/golden/sample-project.json` — 15 edges; includes alias-resolved edges and re-export edges, confirming end-to-end pipeline works for the sample project.

## Related Tasks

- Task 001: `ts-import-graph` — original TypeScript import graph implementation; established scanner/resolver architecture and added partial re-export support.
- Task 003: `go-import-graph` — Go import graph; `runGoGraphFixture` pattern to replicate for TypeScript.
