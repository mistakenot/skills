# Harness patterns by skill type

Match the skill's interaction shape to a harness. Each has a working reference in this repo —
copy and adapt rather than building plumbing from scratch.

## Universal requirements (every harness)

- **Clean arm isolation** — install *exactly* the skill version under test into the run
  environment, **fully replacing** any existing copy (don't overlay — a mix means the arms
  differ by more than the variable). Keep shared project context (CLAUDE.md/AGENTS.md) the
  same across arms.
- **Out-of-repo, out-of-git workspace** — run in a tmp workspace; never let arm work touch the
  source tree or pollute git.
- **Guaranteed teardown** — kill agents/sessions and (optionally) remove worktrees in a
  `finally`, so a crash mid-run never orphans resources.
- **Full capture** — transcript, produced artifacts (the run's git diff, not the whole tree),
  and metrics, per run, so results are auditable.
- **Velocity metrics** — aggregate from the session corpus, summing the parent run **and its
  subagents** (fan-out is real cost). Filter by the run's unique workspace path.

## 1. Conversational / multi-turn → NTM-driven replay A/B

For skills that are a *dialogue* (planning workflows, interrogation, anything multi-turn): you
need a live agent you can send messages to and read replies from across turns. Headless
one-shot `claude -p` cannot do this.

**Reference implementation: `src/planning-eval/`** (driver + build + metrics + CLI, fully
documented in its README).

Mechanics:
- **Host** the agent with NTM (`ntm`, Named Tmux Manager): spawn one agent in the worktree
  with `--no-user --no-cass-context --no-hooks --no-recovery` (the recovery injection will
  otherwise hijack the first turn). Point `NTM_PROJECTS_BASE` at the tmp workspace so the
  agent lands there.
- **Drive** turn by turn via the `--robot-*` API: `--robot-send` → wait for the turn (confirm
  the agent left `WAITING`/started, *then* `--robot-wait --wait-until=idle`, so a fast turn
  isn't mistaken for done) → `--robot-tail` and scrape the reply (assistant lines marked `●`,
  diffed against the pre-send pane).
- **Gotchas** (all handled in the reference impl): auto-accept Claude Code's one-time "trust
  this folder?" gate for fresh worktree paths; forbid interactive `AskUserQuestion` menus via
  a preamble (they stall the text channel) and force the autonomous path equally for both
  arms; disable the target repo's git hooks during checkout (`core.hooksPath=/dev/null`).

## 2. Single-shot transform / generation → headless two-arm

For skills that take one prompt and produce one output (format a doc, extract data, generate
a file): run the agent headless in an isolated clean room, once per arm, and diff the outputs.

**References: `docs/headless-claude-cli-evals.md`** (the isolation recipe: relocated config
dir, auth, skill scoping, the `claude -p` flags and JSON output shape) and
**`src/assurance/evals/`** + **`docs/assurance-eval-system.md`** (a working two-arm
with-skill/without-skill differential harness with mechanical checks and an LLM-as-judge).

Mechanics: a clean `CLAUDE_CONFIG_DIR` per arm so the operator's config can't leak; scope which
skills each arm sees; capture the structured JSON envelope (`total_tokens`, etc.); score with
mechanical checks first (cheap, deterministic) then an isolated judge for the subjective part.

## 3. Skill *triggering* / description quality → trigger evals

For "does the right skill fire for the right query?": a labelled set of should-trigger /
should-not-trigger queries, run against the description. The skill-creator plugin's
description optimizer (`run_loop.py`) automates this — generate ~20 realistic queries (the
valuable ones are near-misses that share keywords but shouldn't trigger), split train/held-out,
and let it propose description improvements scored on the held-out set. Use this *after* the
skill's behaviour is good; it tunes routing, not capability.

## Choosing between 1 and 2

If the skill hard-stops and waits for human input partway through, or its quality depends on a
back-and-forth, it's conversational → harness 1. If a single well-specified prompt fully
determines the output, it's single-shot → harness 2 (much cheaper to run). When unsure, start
with the cheaper headless harness and move to NTM only if the skill genuinely needs turns.
