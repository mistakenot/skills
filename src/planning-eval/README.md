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
| `driver.py` | NTM conversation primitives: spawn, send, race-free turn-wait, reply scrape. The proven core. |
| `build.sh` | Compile one arm: `git worktree` at an immutable SHA, overlay the arm's skills into `.claude/skills/`, amend for clean history. |
| `run.py` | Orchestrate one arm end to end; writes `runs/<id>/result.json` + `artifacts/`. |
| `fixtures/*.json` | A fixture (target repo, start SHA, opening prompt) + arm + hand-scripted `human_turns` + limits. |
| `runs/` | Per-run output (gitignored-worthy): metrics + captured task docs. |

## Run

```bash
uv run --no-project python src/planning-eval/run.py src/planning-eval/fixtures/<fixture>.json
```

The worktree is created at `/home/vscode/src/<session>` (NTM derives an agent's cwd from
`projects_base/<session_name>`) and left in place for inspection after the run.

## Authoring a real fixture

1. Pick a historical task (e.g. an `auto-stack` `docs/tasks/NNN-*`).
2. Find the **session timestamp** when planning started via `auto search` — NOT the plan
   file's commit (plan docs are squashed in with the implementation; see spike S2).
3. Set `start_sha` to an immutable commit at/just before that time.
4. Set `prompt` to the operator's opening request; hand-author `human_turns` from the
   session's genuine human replies (filter out injected slash-command/skill boilerplate).

## Known rough edges (hacked v1)

- Reply scrape is heuristic (`●` TUI lines, diffed vs the pre-send pane). Hardening deferred.
- Turn completion is the scripted-turn count, not semantic "plan done" detection.
- No config-dir isolation: the agent uses the operator's auth; the **skill overlay** is the
  only arm boundary so far.
- Eval runs should later push to an `eval/*` branch so autoetl excludes them from the real
  session corpus (auto-eval §9); not wired yet.
