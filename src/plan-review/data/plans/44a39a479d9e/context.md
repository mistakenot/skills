# Context: Task 045

Codebase context for etl-project-registry. See [plan.html](plan.html).

## Key Files

- `auto-etl/cmd/run.go:376` — `runGitETL`: currently calls `git.DiscoverRepos(remotes, explicitPaths)` where `remotes` is the workspace→remote cache built from all session workspaces
- `auto-etl/cmd/run.go:230` — `runGitHubSync`: currently calls `ghclient.DiscoverRepos(remotes)` from the same remotes cache
- `auto-etl/cmd/run.go:325` — `loadRemotesCache` / `saveRemotesCache`: reads/writes `~/.auto/etl/settings.json`; the `remotes` map is keyed by workspace path (e.g. `/home/user/.claude/projects/-repo-name`)
- `auto-etl/internal/git/discover.go:19` — `DiscoverRepos(remotes map[string]string, explicitPaths []string) []RepoInfo`: current git discovery from remotes cache
- `auto-etl/internal/github/repo.go:31` — `DiscoverRepos(remotes map[string]string) []RepoRef`: current github discovery from remotes cache
- `auto-shared/config/projects.go:34` — `ProjectsConfig` / `ProjectRef`: the canonical project registry struct; `ProjectRef` has `ID`, `Path`, `Remote`, `Name`, `Tools`, `RegisteredAt`
- `auto-shared/config/projects.go:103` — `EnsureProjects()`: loads or creates `~/.auto/projects.json`; returns `(path, cfg, created, err)`
- `auto-shared/config/projects.go:176` — `UpsertProject`: inserts/updates a project by path
- `auto-cli/cmd/auto/initcmd.go:21` — `newInitCmd`: `auto init --project` handler that registers the current git repo into the shared registry
- `auto-etl/cmd/run.go:46` — `newRunCmd`: defines `--repo-path` flag (explicit git paths); this supplements discovery, not replaces it

## Patterns

- The `explicitOnly` boolean in `runGitHubSync:86` controls whether an empty repo list is a fatal error or a silent skip — same pattern should apply for empty registry.
- All auto tools import `sharedconfig "github.com/mistakenot/auto-shared/config"` to access the registry.
- The `internal/github/repo_test.go` and `internal/git/discover.go` files show the test pattern: table-driven Go tests, no external dependencies.
- `auto-etl/go.mod` must already import `auto-shared`; confirm before adding new import paths.

## Related Tasks

- Task 017 (`017-unify-binaries-into-auto`): Created the unified `auto` binary and `auto init --project` surface that writes to `~/.auto/projects.json`.
- Task 032 (`032-skill-project-schemas`): Established `ProjectRef` as the shared schema for project registration across auto tools.
