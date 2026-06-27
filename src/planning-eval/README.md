# planning-eval (hacked v1)

A minimal harness to A/B our planning workflows (v2 vs v3) by **replaying real historical
tasks**: check a repo out at the state just before a task was planned, run a planning
workflow against it while a (currently hand-scripted) simulated human answers, and capture
the produced plan docs + velocity metrics.

This is a stand-in for `auto-stack`'s `auto-eval`, which is spec'd but unimplemented. It
borrows that spec's **build / config / isolation** skeleton and swaps the two parts that
don't fit our need (see `docs/research/v3-eval-spikes.md`):

- **Runner** — not `claude -p` one-shot, but a live **NTM-hosted** agent driven through a
  multi-turn conversation (`driver.py`), because planning is a dialogue.
- **Scoring** — velocity from autoetl (`auto search`) + plan-doc comparison, not just a PR diff.

## Status: thin spine working

Proven end-to-end (1 fixture · 1 arm · hand-scripted human):
build worktree → overlay arm skills → spawn agent → send prompt → replay scripted turns →
capture artifacts + per-turn metrics → tear down.

**Not yet built:** second arm comparison, auto-extracted intent corpus + simulator agent,
automated quality scoring, full `CLAUDE_CONFIG_DIR` isolation.

## Layout

| File | Role |
|------|------|
| `driver.py` | NTM conversation primitives: spawn (self-cleans on failure), send, race-free turn-wait, reply scrape, trust-gate auto-accept. The proven core. |
| `build.sh` | Compile one arm: `git worktree` at an immutable SHA, **fully swap** `.claude/skills/` for the arm's set (clean boundary), amend for clean history; target git hooks disabled. |
| `metrics.py` | Aggregate real velocity from autoetl/auto-search: tokens, messages, tool-time across the run's parent session **and its subagents** (fan-out cost included). |
| `run.py` | CLI: `run` / `list` / `clean`. Guaranteed teardown, transcript capture, metrics. |
| `fixtures/*.json` | A fixture (target repo, start SHA, opening prompt) + arm + hand-scripted `human_turns` + limits. |

## CLI

```bash
P=src/planning-eval/run.py
uv run --no-project python $P run   src/planning-eval/fixtures/<fixture>.json   # replay one arm
uv run --no-project python $P run   <fixture> --no-metrics                      # skip slow ingest
uv run --no-project python $P list                                             # table of runs
uv run --no-project python $P clean [--keep-runs]                              # kill sessions + rm worktrees
```

All arm work happens **outside this repo and out of git**, under a tmp workspace
(`$PLANNING_EVAL_WORKSPACE`, default `/tmp/planning-eval`):

- `…/ws/<session>/` — the agent's worktree (NTM's `projects_base` is pointed here via
  `NTM_PROJECTS_BASE`, so spawned agents land in the workspace, never in `/home/vscode/src`).
- `…/runs/<session>/` — `result.json` (metadata + per-turn timings + aggregated `velocity`),
  `transcript.txt` (full per-turn sent/reply/raw pane), `artifacts/` (only the run's git diff).

Worktrees are left in place for inspection; `clean` removes them. The driver auto-accepts
Claude Code's one-time "trust this folder?" gate for fresh worktree paths, and spawns with
`--no-recovery` (NTM's "continue where you left off" injection would otherwise hijack turn 1).

## Authoring a real fixture

1. Pick a historical task (e.g. an `auto-stack` `docs/tasks/NNN-*`).
2. Find the **session timestamp** when planning started via `auto search` — NOT the plan
   file's commit (plan docs are squashed in with the implementation; see spike S2).
3. Set `start_sha` to an immutable commit at/just before that time.
4. Set `prompt` to the operator's opening request; hand-author `human_turns` from the
   session's genuine human replies (filter out injected slash-command/skill boilerplate).

## Known rough edges (hacked v1)

- Reply scrape is heuristic (`●` TUI lines, diffed vs the pre-send pane). Good enough for
  metrics/transcripts; a judge should read `transcript.txt`, not trust the scrape.
- Turn completion is the scripted-turn count, not semantic "plan done" detection — the
  fixture's `human_turns` must drive the gated pipeline (`/new-solution`, `/new-plan`).
- No config-dir isolation: the agent uses the operator's auth; the **skill overlay** is the
  only arm boundary so far.
- Eval sessions ARE ingested by autoetl (that's how `velocity` is computed) — so they also
  land in the real session corpus. Push runs to an `eval/*` branch for exclusion (auto-eval
  §9) once that matters; not wired yet.
- Metrics filter sessions by exact worktree cwd; a subagent that records a slightly different
  cwd could be missed (undercount). Verify `velocity.session_count` looks right per run.
