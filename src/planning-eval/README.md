# planning-eval

A harness to **measure and compare planning workflows** by replaying real historical tasks.
It checks a repo out at the state just before a task was planned, runs a planning workflow
against it while a hand-scripted "human" answers, and captures the produced plan docs plus
real velocity metrics (wall-clock, tokens, tool-time — fan-out included).

The point: answer *"is workflow v3 actually faster/better than v2?"* with evidence from our
own tasks, not intuition. Run the same fixture through two arms (e.g. `v2` vs `v3` skills)
and compare the captured plans and metrics side by side.

---

## Table of contents

- [Concepts](#concepts) · [How a run flows](#how-a-run-flows) · [Prerequisites](#prerequisites)
- [Quickstart](#quickstart) · [CLI reference](#cli-reference) · [Authoring a fixture](#authoring-a-fixture)
- [Run outputs](#run-outputs) · [Comparing arms](#comparing-arms) · [How it works](#how-it-works-internals)
- [Troubleshooting](#troubleshooting) · [Limitations](#limitations--deferred) · [Background](#background)

---

## Concepts

| Term | Meaning |
|------|---------|
| **Fixture** | One historical task to replay: a target repo, an immutable **start SHA** (the state before planning began), an opening **prompt**, the **human_turns** the simulated operator will send, and run **limits**. A JSON file in `fixtures/`. |
| **Arm** | The thing under test — which planning workflow the agent runs. Selected by `arm.skills_dir`: the harness installs exactly those skills into the worktree, so two arms differ *only* by workflow. |
| **Run** | One replay of one arm of one fixture. Produces a `runs/<session>/` directory. |
| **Simulated human** | For now, a hand-authored `human_turns` list (sent in order). Later this becomes an agent answering from an extracted intent corpus. |
| **Velocity** | The cost/speed axis: wall-clock, tokens, messages, tool-time — summed across the run's parent session and all its subagents. |

This is a deliberately **hacked stand-in** for `auto-stack`'s `auto-eval` (which is spec'd
but unimplemented). It borrows that spec's build/config/isolation skeleton and swaps in an
**NTM-driven multi-turn conversation** (planning is a dialogue, not a one-shot `claude -p`)
and **autoetl-based scoring**. See [Background](#background).

---

## How a run flows

```
fixture.json
    │
    ▼  build.sh
┌─────────────────────────────────────────────────────────────┐
│ git worktree @ start_sha   (hooks disabled)                  │
│   └─ .claude/skills/  ← FULLY REPLACED with the arm's skills  │  ← clean arm boundary
│   └─ amend onto start commit  → agent sees clean `git log`    │
└─────────────────────────────────────────────────────────────┘
    │
    ▼  driver.Session.spawn  (NTM hosts a live Claude agent in the worktree)
    │     • --no-recovery, --no-cass-context, --no-hooks
    │     • auto-accepts the "trust this folder?" gate
    ▼  for each message (opening prompt, then each human_turn):
    │     send → wait for turn (confirm GENERATING, then idle) → scrape reply
    ▼  capture
        • artifacts/   ← only the run's git diff (the produced plan docs)
        • transcript.txt ← full sent/reply/raw-pane per turn
        • result.json  ← metadata + per-turn timings + aggregated velocity
    │
    ▼  teardown (always — even on error): kill the agent
    │
    ▼  metrics.collect → auto etl run + auto search → sum parent+subagent tokens/time
```

Everything lives **outside this repo and out of git**, under
`$PLANNING_EVAL_WORKSPACE` (default `/tmp/planning-eval`):
`ws/<session>/` worktrees, `runs/<session>/` outputs.

---

## Prerequisites

- **`ntm`** (Named Tmux Manager) — hosts/drives the agent. `ntm deps` should show Claude + tmux.
- **`auto`** with `etl` + `search` subcommands (autoetl) — for velocity metrics.
- **`claude`** (Claude Code) — authenticated; the agent runs under the operator's auth.
- **`uv`** — to run the Python (`uv run --no-project python …`).
- A **target repo** checked out locally with intact history (e.g. `~/src/auto-stack`).

---

## Quickstart

```bash
P="uv run --no-project python src/planning-eval/run.py"

# Replay the worked example (task 008, v2 arm) against the historical auto-stack checkout.
$P run src/planning-eval/fixtures/008-commit-session-link.json

# See what ran.
$P list

# Inspect a result.
cat /tmp/planning-eval/runs/<session>/result.json | python3 -m json.tool
less /tmp/planning-eval/runs/<session>/transcript.txt

# Reset (kill sessions, remove worktrees + run outputs).
$P clean
```

A full v2 planning replay takes ~10–15 min and a few million tokens (it runs the real
`/new-task → /new-solution → /new-plan` pipeline with subagent fan-out). Use small,
self-contained tasks for fixtures and watch the cost.

---

## CLI reference

```bash
run.py run <fixture.json> [--no-metrics]
```
Replay one arm end to end. `--no-metrics` skips the slow `auto etl run` ingest and reports
only whatever autoetl has already indexed (faster; velocity may be unavailable).

```bash
run.py list
```
Table of all captured runs: completion, wall-clock, turn count, total tokens, artifact count.

```bash
run.py clean [--keep-runs]
```
Kill every live `peval-*` NTM session and remove every worktree under `ws/`. Also deletes
`runs/` unless `--keep-runs`. **Destructive** — it wipes all captured runs by default.

Environment:
- `PLANNING_EVAL_WORKSPACE` — workspace root (default `/tmp/planning-eval`).
- `NTM_PROJECTS_BASE` — set automatically by `run.py` so NTM spawns agents in the workspace.

---

## Authoring a fixture

A fixture is JSON. Full annotated schema:

```jsonc
{
  "id": "008-commit-session-link",        // used in the run/session name
  "_provenance": { ... },                  // optional free-form notes (sessions mined, etc.)

  "fixture": {
    "target_repo": "/home/vscode/src/auto-stack",
    "start_sha": "0ea36adc…",              // IMMUTABLE sha (not HEAD/main); pre-planning state
    "prompt": "/new-task we want to …"      // the operator's opening message; lead with the
                                            // slash command if the workflow is invoked that way
  },

  "arm": {
    "id": "v2",                             // label for this arm
    "skills_dir": "skills"                  // path (relative to repo root) whose contents fully
                                            // replace the worktree's .claude/skills/
  },

  "human_turns": [                          // sent in order, one per turn, AFTER the prompt
    "Add to the requirements: …",           // substantive steering pulled from the real session
    "/new-solution",                        // drive the GATED pipeline yourself — the workflow
    "…clarifying answer…",                  //   hard-stops between stages and waits for these
    "/new-plan",
    "Looks good — that completes planning."
  ],

  "limits": {
    "max_turns": 14,                        // hard cap on messages sent
    "wall_clock_s": 2400,                   // overall budget
    "per_turn_timeout_s": 900               // max wait for a single agent turn
  }
}
```

### Finding the inputs for a real task

1. **Pick a task** from the target repo's `docs/tasks/NNN-*`. Prefer ones with a *separate*
   `docs(tasks): add task NNN` commit — those have planning docs isolated from implementation.
   (`fixtures/CANDIDATES.md` has a vetted auto-stack shortlist.)
2. **start_sha** = the parent of that docs/feature commit:
   `git -C <repo> rev-parse <feat_commit>^`. Confirm it predates the implementation
   (`git -C <repo> ls-tree <sha> | grep <feature>` → empty).
3. **Find the planning session** with `auto search`: search for the task slug + `new-task`,
   then `auto search session get <id>` and confirm it contains the `/new-task`→`/new-solution`
   →`/new-plan` flow with genuine human turns. Beware: the top content hit is often the
   *execution* session, not planning; and a task may be planned across several sessions.
4. **prompt + human_turns** = the genuine human messages from that thread, with the injected
   boilerplate filtered out (`<local-command…>`, `<command-name>…`, "Base directory for this
   skill", `<teammate-message>` blocks). Keep the substantive asks and answers.

### Two authoring methods

Pinpointing a task's planning thread is the genuinely hard, manual part — and it's
*inconsistent*: some threads are clean (008), others are fragmented across sessions,
buried under execution/review sessions that mention the task more, or were abandoned and
converted to research docs. Two methods, pick by what the task offers:

- **Session-mined** (higher fidelity): reconstruct prompt + turns from the real planning
  session, as above. Use when the thread is findable. Example: `008-commit-session-link.json`.
- **Requirements-derived** (faster, reliable): when the thread is fragmented, author the
  prompt + the load-bearing `human_turns` from the task's own `requirements.md`/`solution.md`
  in the target repo — those *are* the planning ground truth. Pull the real steering
  decisions (e.g. an explicit "this supersedes the duckdb plan"). Example:
  `010-autosearch-co-change.json`. Caveat: hindsight bias — you're authoring from the
  outcome — but the same fixture drives both arms, so the comparison stays fair.

> The harness prepends a fixed preamble to the opening prompt telling the agent it's driven
> by an automation and must not use interactive `AskUserQuestion` menus (those stall the
> text channel). It's applied to every arm equally, so comparisons stay fair.

---

## Run outputs

`runs/<session>/`:

| File | Contents |
|------|----------|
| `result.json` | Everything machine-readable (schema below). |
| `transcript.txt` | Per turn: the message sent, the scraped agent reply, and the full raw pane tail. **Read this to see what actually happened** — the scrape is heuristic. |
| `artifacts/` | Only the files the run produced (the worktree's git diff vs the start commit) — i.e. the generated plan docs. |

### `result.json` schema

```jsonc
{
  "session": "peval-008-…-v2-<ts>",   // == run dir name == NTM session == worktree dir name
  "fixture_id": "008-commit-session-link",
  "arm_id": "v2",
  "target_repo": "/home/vscode/src/auto-stack",
  "start_sha": "0ea36adc…",
  "worktree": "/tmp/planning-eval/ws/peval-008-…",
  "completion": "ok",                  // "ok" | "capped" | "error: <type>: <msg>"
  "total_wall_ms": 787633,             // harness-measured wall-clock of the conversation
  "turn_count": 6,
  "artifacts": ["docs/tasks/008-…/plan.html", "docs/tasks/008-…/context.md"],
  "turns": [
    { "i": 0, "sent": "…", "reply": "…", "wall_ms": 154462, "state_at_end": "WAITING" }
  ],
  "velocity": {                        // aggregated from autoetl across parent + subagents
    "available": true,
    "session_count": 3, "parent_count": 1, "subagent_count": 2,
    "total_tokens": 17340919,
    "total_messages": 332,
    "total_tool_duration_ms": 198007,
    "wall_span_ms": 780776,
    "total_errors": 0,
    "per_session": [ { "session_id": "…", "is_subagent": false, "tokens": 15102799, … } ]
  }
}
```

If `velocity.available` is `false`, `reason` says why (e.g. not indexed yet) — re-run
`auto etl run && auto search index` and recompute, or it was run with `--no-metrics`.

---

## Comparing arms

Run the same fixture twice with different `arm.skills_dir` (e.g. a `v2` and a `v3` fixture),
then compare two axes:

- **Velocity** — `total_wall_ms`, `velocity.total_tokens`, `total_messages`, `turn_count`.
  v2's 008 baseline: **787s wall, 17.3M tokens, 6 turns, 3 sessions**.
- **Quality** — read each `artifacts/…/plan.html`; lint it
  (`node .claude/skills/planning-doc/scripts/pd-lint.mjs <plan.html>`); eyeball completeness
  (tabs, `pd-ac` coverage, phase DAG). Automated judging is a deferred next step.

Run **multiple trials per arm** — planning is non-deterministic, so single runs are noisy.

---

## How it works (internals)

- **`build.sh`** — `git worktree add --detach` at `start_sha` with `core.hooksPath=/dev/null`
  (the target's `post-checkout`/`pre-commit` hooks would fail at a historical commit). It
  **removes** the worktree's `.claude/skills/` and copies in the arm's set, then
  `git commit --amend` so the agent's `git log` shows no eval scaffolding.
- **`driver.py`** — wraps NTM's `--robot-*` API. `Session.send()` does race-free turn
  detection: after sending, it first confirms the agent left `WAITING` (started the turn),
  *then* waits for `idle`, so a fast turn isn't mistaken for "already done". Replies are
  scraped from the TUI pane (lines marked `●`), diffed against the pre-send snapshot so each
  turn returns only its new output. `spawn()` self-cleans if the agent never becomes ready.
- **`metrics.py`** — a run's worktree path is unique, so every session autoetl recorded
  against that cwd belongs to the run. It sums tokens/messages/tool-time across the parent
  planning session **and its subagents** (context gatherers, option explorers) — the true
  cost of the workflow's fan-out.
- **`run.py`** — orchestrates the above with guaranteed teardown (the agent is killed in a
  `finally`, so a crash mid-conversation never orphans a tmux session).

---

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| Agent stuck, `_await_ready` raises | Usually the "trust this folder?" gate (auto-handled) or a slow first spawn. Check `ntm --robot-tail=<session>`. |
| Agent answers a "continue where you left off" prompt | NTM recovery injection — ensure `--no-recovery` is in `driver.spawn` (it is). |
| Run stalls on a menu (`1. … / Enter to select`) | The agent used `AskUserQuestion`. The harness preamble forbids it; if a fixture's prompt overrides that tone, restore the instruction. |
| `build.sh` aborts right after "Preparing worktree" | A target git hook fired — confirm `core.hooksPath=/dev/null` is on the worktree `add`. |
| `velocity.available: false` | autoetl hasn't ingested the session. Run `auto etl run && auto search index`, or the run used `--no-metrics`. |
| `velocity.session_count` looks low | A subagent recorded a slightly different cwd and was missed. Inspect `auto search session list --cwd /tmp/planning-eval`. |
| Worktrees / sessions piling up | `run.py clean` (kills sessions, removes worktrees). |
| `dcg`/permission guard blocks a manual `rm -rf` under `/home` | Use `git worktree remove` or `run.py clean`; never `rm -rf` a home path. |

---

## Limitations / deferred

- **Hand-scripted human only.** The intent-corpus extractor + simulator agent is future work;
  for now `human_turns` is authored by reading the original session.
- **No automated quality scoring.** Quality is read/linted by a human today.
- **No config-dir isolation.** The agent uses the operator's auth; the **skill overlay** is
  the only arm boundary. Different operator configs would not be controlled.
- **Eval sessions are ingested by autoetl** (that's how velocity is computed) — so they also
  land in the real session corpus. Push runs to an `eval/*` branch for exclusion when it matters.
- **Turn completion is the scripted-turn count**, not semantic "plan done" detection — the
  fixture must drive the gated pipeline itself.

---

## Background

- Feasibility was established by spikes S0–S6 — see `docs/research/v3-eval-spikes.md`. Proven
  primitives: NTM agent-driving, `auto search` session retrieval, autoetl velocity metrics,
  clean git checkout. `auto-eval` itself is docs-only, so this harness builds the plumbing.
- The v2-vs-v3 workflow design being measured lives in `docs/research/planning-workflow-v3.md`
  and task `docs/tasks/005-v3-new-task/`.
- Candidate replay fixtures from auto-stack: `fixtures/CANDIDATES.md`.
