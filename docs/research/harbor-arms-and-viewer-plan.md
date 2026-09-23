---
hash: "9131f576"
id: "e7ad2dac"
read_when: "implementing the follow-up to the Harbor planning-eval harness — adding `--arm` (git refs, WORKTREE, merge-base baseline, baseline-run reuse), multi-arm Harbor jobs, or the export into the evals viewer; or wanting the intended branch-based A/B workflow for skill edits"
summary: "Pickup-ready design for the two missing pieces of src/planning-eval-harbor/: git-ref arms (`--arm main --arm HEAD`, baseline defaulting to the merge-base, baseline runs reusable) run as one multi-agent Harbor job, and an export of a Harbor run into the src/evals/ viewer layout so a human can read the produced docs rendered side by side, see the skill diff next to the output diff, and copy comments back as instructions for the next iteration. Lists the exact files to lift from, the mapping table, the tests, and the decisions already taken."
title: "Plan: branch-vs-baseline arms and a rendered viewer for planning-eval-harbor"
---

# Plan: branch-vs-baseline arms and a rendered viewer for planning-eval-harbor

**Status.** Design only, not built. Written 2026-09-23 at the end of the
session that produced `src/planning-eval-harbor/` (PR #8), so the next agent
can pick it up cold. Read `docs/research/harbor-vs-planning-eval.md` first for
what the harness is and the evidence behind it, and
`src/planning-eval-harbor/README.md` for how it runs today.

## The workflow this enables

The operator's intended loop, in their words: lean into the ordinary PR and
worktree workflow. Check out a branch, edit the skill source, re-render, rerun
the eval, and have the viewer A/B the branch's version against the commit it
forked from.

```bash
git checkout -b skill/new-task-quick-tighter
# edit src/planning-workflow/new-task-quick/…, then
uv run --no-dev python src/compile.py && git commit -am "…"

make peval-harbor ARGS='run src/planning-eval-harbor/fixtures/008-commit-session-link-short.json --arm HEAD'
#   → baseline arm = merge-base(main, HEAD) is added automatically
#   → both arms run as one Harbor job, one image build
make peval-harbor ARGS='view'
#   → both plans rendered side by side, skill diff beside output diff, comments
```

Before committing, `--arm WORKTREE` is the uncommitted edit (compiled first),
exactly as in `src/evals/`.

## What exists today (do not rebuild)

| Piece | Where | Reuse |
|---|---|---|
| Arm resolution: `none` / `WORKTREE` (compile then copy) / any git ref (`git archive`, never checkout), safe dir names, per-arm `manifest.json` with sha/head/dirty | `src/evals/arms.py` (`resolve`, `resolve_all`, `write_manifest`, `dir_name`, `compile_skills`, `head_sha`, `is_dirty`, `resolve_ref`) | Lift as is; the only change is archiving the whole `skills/` tree instead of `skills/<name>` (see D1) |
| Run manifest, written before the first token and rewritten at the end | `src/evals/manifest.py` | Reuse for the exported run |
| Viewer: rendered HTML per cell in sandboxed iframes, skill-tree diff between arms, output diff, transcript tool list, comments sidebar with Copy | `src/evals/viewer/server.py` + `static/` | Untouched; feed it an exported run directory with `--runs-dir` |
| Invocation check (`invocation.json`, "did the skill fire") | `src/evals/invocation.py` | Reuse `write` on the concatenated transcript |
| Fixture → Harbor task, job config, `harbor run`, result reading | `src/planning-eval-harbor/{task,job,run,results}.py` | Extend |

The evals cell layout the viewer expects (`src/evals/tests/helpers.py`
`CELL_ENTRIES`): `runs/<run-id>/<arm-dir>/<trial>/{out.md, stream.jsonl,
err.txt, ws/, skill/}` plus `<arm-dir>/manifest.json`, `<arm-dir>/invocation.json`
and `runs/<run-id>/manifest.json`. `describe_cell` in the viewer reads the
`result` envelope from `stream.jsonl` for cost and exit code, and
`report.workspace_outputs` lists files in `ws/` that are new or changed against
the run's `seed` directory.

## Part 1 — arms

### CLI

```
run <fixture> [--arm REF]... [--baseline-run RUN_ID] [--no-baseline]
```

- No `--arm`: today's behaviour, the fixture's `arm.skills_dir`, unchanged.
- `--arm X` (repeatable): each arm is resolved exactly as `src/evals/arms.py`
  does — `WORKTREE` compiles `src/` and uses `skills/`; anything else is
  `git archive <sha> -- skills` into a temp dir. `none` is meaningless here
  (a planning workflow with no skills is not an arm) and is rejected.
- **Baseline default.** When exactly one arm is given and it is `HEAD` or
  `WORKTREE`, add a baseline arm `git merge-base main HEAD` unless
  `--no-baseline` or `--baseline-run` is passed. The merge-base, not `main`:
  if main moved during the iteration, `main` carries unrelated skill changes
  and the comparison stops being about the branch.
- **`--baseline-run <run>`.** Reuse an existing run of the same fixture as the
  baseline instead of spending on it again; the export (Part 2) pairs the two.
  Validate: same `fixture_id`, same operator, same model, and the baseline
  run's arm sha is recorded (from its `peval.json`). Refuse otherwise.

### One job, several agents

Harbor's `JobConfig.agents` is a list; every trial is one (task, agent,
attempt) combination. Each arm becomes one agent entry:

```json
{"import_path": "peval_agents:ClaudeCodeReplay", "model_name": "…",
 "skills": ["<resolved arm skills dir>"], "resume_trajectory": true, "kwargs": {…}}
```

Consequences to handle:

- **Trial → arm mapping.** Harbor names trials `<task>__<7 chars>`
  (`harbor/models/trial/config.py` `generate_trial_name`), with no agent in
  the name. Read `<trial>/config.json` → `agent.skills[0]` and match it to
  the arm's resolved skills dir. Record the mapping in `peval.json`
  (`arms: [{name, dir_name, sha, head, dirty, skills_dir, trials: […]}]`).
- **`n_concurrent_trials`.** Default stays 1; `--concurrent 2` runs both arms
  at once (two containers, two agents billing at once — say so in the help).
- **Lock file.** Harbor records each agent's skill digests separately in
  `lock.json`; nothing to add, but `results.summarize_job` should surface the
  per-arm digest list so "what was in that arm" stays answerable.
- **Arm dir names** in the run: reuse `arms.dir_name` (`origin/main` → `origin-main`).

### Results

`results.summarize_job` groups trials by arm; `summary.json` gains
`arms: [{name, sha, trials: […]}]`; `list` shows `arms` as `main→HEAD` style;
`show` prints per arm. `peval-result.json` gains `arm: {name, sha, head, dirty}`.

## Part 2 — export into the evals viewer

A new `export` command (and `run` calls it at the end) writes
`src/planning-eval-harbor/runs-view/<run-id>/` in the evals layout. The viewer
is then `make evals ARGS='view --runs-dir src/planning-eval-harbor/runs-view'`,
which `make peval-harbor ARGS='view'` should wrap (replacing today's
`harbor view`, which previews HTML as source — keep it reachable as
`view --harbor`).

Mapping, per arm and trial:

| Evals layout | From the Harbor trial |
|---|---|
| `<arm-dir>/manifest.json` | `arms.write_manifest` with the resolved `Arm`; `skill` = `"<all>"` or the fixture's workflow entry skill (D2) |
| `<arm-dir>/invocation.json` | `invocation.write` over the concatenated stream; the skill name to check is the fixture's entry skill, i.e. the slash command in message 1 (`/new-task` → `new-task`) (D2) |
| `<trial>/stream.jsonl` | `steps/turn-NN/agent/claude-code.txt` concatenated in step order (scripted). Simulated: the target's native session jsonl is *not* stream-json; write the user agent's `claude-code.txt` and note the difference in `manifest.json` (`runner: "harbor-simulated"`) |
| `<trial>/out.md` | `transcript.txt` |
| `<trial>/err.txt` | `trial.log`, or empty |
| `<trial>/ws/` | the final collected `/app` (`results._artifact_app_dir`), copied without `.git` |
| `<trial>/skill/` | the arm's resolved skills tree (all 39), so the viewer's skill-diff tab shows the branch edit between arms |
| `runs/<run-id>/manifest.json` | `manifest.write(...)` with `runner: "harbor"`, `skill`, `scenario: <fixture id>`, `seed: <extracted repo.tar>`, arm names, trials, model, `started_at`/`finished_at` from `peval.json` |
| `runs/<run-id>/seed/` | `environment/repo.tar` extracted once, so `workspace_outputs` lists only what the run produced (same content-hash idea as `results.produced_files`) |

Pairing with `--baseline-run`: export writes one viewer run containing the
fresh arm and the baseline run's arm, with the baseline's `manifest.json`
noting `reused_from: <run-id>`.

Comments (`comments.json`) live in the exported run dir; `Copy` in the viewer
already formats them for pasting into the next session. Nothing to build.

## Tests (offline, root environment, no harbor import)

- `test_arms_integration.py`: `--arm HEAD` on a synthetic repo with a
  committed `skills/` resolves to an archive; `WORKTREE` compiles; `none`
  rejected; baseline defaults to merge-base and is suppressed by
  `--no-baseline`; two arms map to two agent entries with distinct skills.
- `test_export.py`: export a fixture-shaped Harbor run (extend
  `tests/fixtures/scripted-trial/` with a `config.json` naming the skills
  dir) and assert the evals `CELL_ENTRIES` shape, that `stream.jsonl` holds
  every step's events in order, that `ws/` lacks `.git`, and that the evals
  viewer's `describe_run` (importable from `src/evals`) reads it without
  error and lists the produced plan as an output.
- `test_baseline_run.py`: refusal on mismatched fixture/operator/model; the
  paired export carries `reused_from`.

## Decisions already taken

| # | Decision | Why |
|---|---|---|
| D1 | Arms are the **whole** compiled `skills/` tree at a ref, not one skill | A planning replay exercises several skills (`new-task` loads `rich-doc`); companions come for free and the only difference between arms is the branch's edits |
| D2 | The "skill under test" for the invocation check is the **entry skill**: the slash command of message 1 | It is the one whose absence would silently turn the run into a different experiment; the rest are companions |
| D3 | Baseline = merge-base, opt-out with `--no-baseline` | A moving `main` confounds the comparison |
| D4 | Baseline reuse is explicit (`--baseline-run`), never automatic | Planning runs are non-deterministic (1.5–1.8× spread); silently pairing with a stale run would invite reading noise as effect |
| D5 | Export into the evals viewer rather than extending `harbor view` or writing a third viewer | The evals viewer already renders HTML side by side, diffs skills and outputs, and carries comments; it is the repo's reading room |
| D6 | The evals viewer is not modified | Its tests and its contract (`CELL_ENTRIES`) are the spec the export is held to |

## Open questions for the implementer

1. Whether `invocation.write` needs the `Skill` tool_use to name the entry
   skill exactly, given `/new-task` arrives as a slash command rather than a
   `Skill` call in the first step. If the detector misses, the fallback is
   the `system/init` `skills` list plus the step's `skill_calls`; do not weaken
   the detector to make it pass.
2. `--trials N` with two arms and `--concurrent 1` is `2N` sequential
   containers; whether to warn on the estimated cost before starting.

## Effort

Roughly: arms and multi-agent job ~150 lines lifted from `src/evals/arms.py`
plus config changes; export ~150 lines; results/list/show updates ~60 lines;
tests ~200 lines. One live verification run of `--arm HEAD` with the default
baseline on the short 008 fixture: about $2.30 and 12 minutes.
