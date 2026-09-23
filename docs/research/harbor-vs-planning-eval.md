---
hash: "d3237147"
id: "736983b0"
read_when: "deciding whether planning replays should run on Harbor or on planning-eval's NTM harness, or picking up src/planning-eval-harbor/ and needing the evidence and the known gaps behind it (auth stripping, skills not reaching the ACP target, Docker iteration cost)"
summary: "Research finding on replacing src/planning-eval/ (NTM-driven multi-turn planning replay) with the Harbor agent-eval framework: what Harbor 0.23 actually provides (verified by running it), the three patches its simulated-user path needed for a claude-code target on subscription auth, what a migration costs and loses, the side-by-side implementation in src/planning-eval-harbor/, live evidence with costs, and a recommendation. Decisions taken without asking are listed at the end."
title: "Harbor vs planning-eval — can the agent-eval framework replace the NTM harness?"
---

# Harbor vs planning-eval

**Question.** `src/planning-eval/` replays a historical planning task by hosting a
Claude Code TUI in tmux via `ntm`, sending the operator's turns one by one and
scraping replies off the pane. It is the fragile harness. Harbor
(<https://docs.harborframework.com>) advertises a first-class simulated-user
trial (`--user-agent … --bridge acp`) and first-class skill injection
(`--skill`, digest-recorded). Can it replace planning-eval without being
fought — a "run the arms, give me readable outputs" tool with no grader — and
is the Docker-per-trial cost acceptable?

**Answer.** Yes, with a qualified recommendation. Harbor can drive a scripted
multi-turn planning replay in a Docker sandbox with no verifier, and the
result is *more* evidence than planning-eval captures (full stream-json per
turn, native session files, ATIF trajectories, the workspace after every turn,
skill digests in a lock file), for a similar token cost and a ~1 minute
per-trial overhead. But Harbor's headline feature, the LLM simulated user, was
**not** usable as shipped for this repo's setup: three gaps had to be patched
in a 60-line agent subclass, and the deterministic scripted operator turned
out to be the better replacement for what planning-eval does today. The
working implementation is `src/planning-eval-harbor/`; `src/planning-eval/`
is untouched.

Everything below was verified by running it, on 2026-09-16, with Harbor
0.23.0, Claude Code 2.1.273 inside the sandbox, rootless Docker 29.4.3,
`claude-sonnet-4-6`.

## 1. What Harbor actually provides

A Harbor **task** is a directory: `instruction.md` + `environment/Dockerfile`
+ `tests/test.sh` + `task.toml`. A **trial** builds the image, starts a
container, installs the agent CLI into it (Harbor's own integration curls
Claude Code's bootstrap installer), uploads any `--skill` directories, runs the
agent on the instruction, collects declared **artifacts** and the agent's logs
to the host, then runs the verifier. A **job** is a set of trials.

What matters for a planning replay, with the evidence:

| Capability | Verified? | Evidence |
|---|---|---|
| Run with **no verifier** (`verifier.disable: true`) | yes | every run below; `tests/test.sh` must still exist, so the harness ships one that exits 1 if ever executed |
| **Skill injection**, local path, content digest in `lock.json` | yes | `lock.json` records `{"name": "peval-marker", "source": …, "digest": "sha256:377a37…"}`; the agent's `system/init` event listed the skill and it invoked it |
| Skill root = a directory of skills (the compiled `skills/`, 39 entries) | yes | the live replay's init event registered 54 skills = 39 arm + 15 built-ins |
| **Multi-turn, scripted**: multi-step task + `--resume-trajectory` | yes | one session id across three steps; turn 3 recalled a word given in turn 1; each step is `claude -p --continue` |
| **Multi-turn, simulated user** (`--user-agent claude-code --bridge acp`) | yes, after patching (§3) | operator sent the 3-message script verbatim; target answered; artifact collected |
| **Full transcripts**: stream-json per step (`agent/claude-code.txt`), ATIF `trajectory.json`, native session `.jsonl` | yes | the same stream-json shape `src/evals/invocation.py` already parses |
| **Artifacts**: collect `/app` (excluding `.git`) after each step | yes | multi-step collects run-level artifacts *per step* under `steps/<name>/artifacts/`, which gives the workspace after every turn for free |
| Per-step **cost and token** accounting | yes | `step_results[].agent_result` has cost/tokens per step, from the stream `result` event |
| **Viewer** (`harbor view <jobs-dir>`) | yes, with a gap | lists jobs and trials, renders the trajectory with per-step cost and timing, shows config, lock and an artifact file tree — but serves an HTML artifact as `text/plain` (verified 2026-09-23), so a pd-components plan is shown as source, not rendered; no arm-vs-arm diff and no comments |
| **Subscription (OAuth) auth** via `CLAUDE_CODE_OAUTH_TOKEN` | yes for a headless target; **no** for the ACP target | §3.1 |
| `harbor run --dry-run` validates config, task, credentials without a container | yes | used by `run.py --dry-run` |

What it is *not*: Harbor is reward-centric by design (task → verifier →
`reward.json` → aggregate), the docs and `harbor view` foreground reward, and
the verifier is the only post-agent hook inside the sandbox. None of that has
to be used. `verifier.disable` is a first-class switch, artifacts are
collected regardless, and "what did the run produce" is answered on the host
by diffing the collected tree against the seed tarball. The one place the
reward model leaks is cosmetic: every job prints `Mean: 0.000`.

## 2. The two operator shapes, and which one replaces planning-eval

planning-eval's operator is a **hand-scripted list of turns**. Its README
calls an LLM simulator "future work". Harbor offers both shapes:

**Scripted (multi-step + resume).** One Harbor step per fixture message,
Claude Code resuming its native session between steps. The message sent is
the fixture's message, byte for byte. Deterministic on the operator side, one
agent per trial, no bridge. Each turn ends when `claude -p` exits — which is
also, in effect, how planning-eval's "wait for idle" ends a turn, minus the
scraping heuristics. This is the direct replacement and the default.

**Simulated (user agent + ACP bridge).** Harbor gives the *user agent* the
instruction (persona + bridge instructions + `instruction.md`), and the target
starts blind; the user relays messages with `acpx prompt`. To replay a script
you write the script into `instruction.md` and a replay persona. The operator
is an LLM following orders, so the harness reads the target's own session file
afterwards and checks, turn by turn, that the script was sent verbatim
(`results.adherence`). In three verification runs it was. This is the upgrade
path to planning-eval's "simulator agent answering from an intent corpus", not
the replacement for what it does now.

Two fidelity notes on the simulated path: the target runs through Zed's
`claude-code-acp` adapter and the Claude Agent SDK, so its file tools are
ACP-provided (`mcp__acp__*`) rather than native, and Harbor's cost accounting
for the trial covers the *user agent only* — the target's spend has to be
recovered from its session file (the harness does; tokens only, no dollars).

## 3. What had to be patched (and why the simulated user failed as shipped)

All three live in `src/planning-eval-harbor/peval_agents.py`, a subclass of
Harbor's `claude-code` integration selected with `agents[].import_path`. No
Harbor source is modified.

### 3.1 Auth: Claude Code's Bash tool strips the OAuth token

Harbor forwards `CLAUDE_CODE_OAUTH_TOKEN` into the sandbox as an environment
variable. For a headless target that works (smoke run 1). In a simulated-user
trial the target is spawned by `acpx`, which the *user agent* runs from its
Bash tool — and Claude Code strips that variable from child processes.
Measured directly: a `claude -p` given `CLAUDE_CODE_OAUTH_TOKEN` and a control
variable `PEVAL_PROBE=1`, asked to print its Bash environment, printed the
control and not the token. The ACP target therefore failed `session/new` with
*"Could not resolve authentication method"* while the same adapter, driven by
hand with the same token, answered `PONG`.

Fix: seed `~/.claude/.credentials.json` into each role's `CLAUDE_CONFIG_DIR`
(the recipe `docs/headless-claude-cli-evals.md` verified), and export no token
at all. This also lets the CLI refresh an access token that would otherwise
expire mid-run (access tokens live for hours, not days).

Whether an `ANTHROPIC_API_KEY` survives the same shell hop was **not** tested —
none exists here. Harbor's own simulated-user examples use API keys, so it is
possible the upstream path only works with a key.

### 3.2 Skills never reach the ACP target

Harbor registers `--skill` directories in `ClaudeCode.run()`, and in a
simulated-user trial `run()` executes for the **user agent**. The target's
config dir only ever receives a `settings.json`. Smoke run 2: the operator
relayed the script perfectly, and the target reported *"peval-marker is not a
skill in its list"*. Fix: copy `skills_dir` into the target's config dir in
`acp_install`. Smoke run 3 confirmed the target then registered and invoked it.

This is an upstream gap worth reporting: with skills it silently measures an
arm that was never installed — exactly the failure `src/evals/` built its one
automated check to catch.

### 3.3 Nothing for the scripted path

Only the credentials seeding, so no token env is needed in either mode.

## 4. Migration cost

| Cost | Assessment |
|---|---|
| **Docker per trial** | Image build ~40 s the first time and cached after (Docker's layer cache is content-addressed, so a new task dir for the same start SHA reuses layers). Per trial: container start + Claude Code install + skill upload ≈ 20–30 s. On a 10–15 min planning replay this is noise; on a 1-minute smoke it is half the wall clock. The iteration loop is: edit fixture → `--dry-run` (seconds, free) → live. |
| **A dependency with a surface** | `harbor` pulls ~94 packages into the module's own uv environment. Its CLI moves fast (0.18 was installed locally; simulated users arrived in 0.22, the flags this harness uses in 0.23). The module pins `>=0.23,<0.24`. |
| **A subclass of an internal** | `peval_agents.py` overrides two methods of `harbor.agents.installed.claude_code.ClaudeCode`. Both are documented extension points (custom agents), but the internals they touch (`environment_logs_dir / "sessions"`) are conventions, not API. |
| **History-free seed** | The sandbox gets the tree at `start_sha` as a single commit (a tarball, per `src/evals/scenarios/README.md`), not planning-eval's full worktree history. A workflow that mines `git log` sees less. Bundling history is a small change if it turns out to matter. |
| **No autoetl velocity** | Velocity comes from Claude Code's own per-turn accounting (cost, tokens, duration) cross-checked against the native session files, not from `auto etl` + `auto search`. Simpler and self-contained, but a different meter than planning-eval's — do not compare the two harnesses' token totals as if they were one instrument. |
| **Tooling to learn** | `harbor view`, `lock.json`, the trial directory layout. Documented in the module README. |

## 5. What we lose

- **Watching it live in a terminal.** planning-eval's agent is a real TUI in
  tmux you can attach to. Harbor's is a headless `claude -p` in a container;
  the stream-json file grows on the host (`/logs` is a bind mount), and
  `harbor run` streams a progress table, but there is no pane to look at.
- **Mid-turn interaction.** With NTM one could, in principle, answer an
  `AskUserQuestion` menu. Neither harness does today (the shared preamble
  forbids the tool), so nothing actually used is lost.
- **autoetl-based velocity** (see above) and, with it, the eval sessions
  landing in the real session corpus — which planning-eval's README lists as a
  limitation, not a feature.
- **Full git history** in the workspace, unless bundled.

## 6. What we gain

- **Evidence.** Per turn: the full stream-json transcript (no pane scraping —
  planning-eval's README marks its reply scrape "heuristic, to be hardened"),
  an ATIF trajectory, the native session files including subagents, cost and
  tokens, and the **workspace after every turn**. planning-eval captures the
  final diff and the scraped text.
- **Provenance.** `lock.json` records the task digest and every injected
  skill's sha256; `config.json` the resolved job. "What exactly did that arm
  contain?" is answerable a month later without the tree.
- **Isolation.** A container per trial instead of a worktree beside the real
  repo, with `CLAUDE_CONFIG_DIR` relocated by Harbor itself. Two of the four
  canaries `src/evals/` needs (repo walk-up, stray `CLAUDE.md` in an ancestor)
  cannot happen: `/app` in a fresh container has no ancestors of ours.
- **Trials.** `--trials N` is one flag (`n_attempts`); concurrency is another.
- **A path to the simulated operator** that planning-eval only planned.
- **Less code to own.** The NTM driver — spawn, trust-gate auto-accept,
  race-free "confirm GENERATING then wait idle", pane diffing — is gone.
  What remains is fixture → task compilation and reading results back.

## 7. Live evidence

Smoke runs (all under `scratchpad`, not committed except as trimmed test fixtures):

| Run | Shape | Result | Wall | Cost |
|---|---|---|---|---|
| 1 | single agent, `--skill` marker | skill registered + invoked; artifact collected; ATIF + stream-json written | 58 s incl. first image build | $0.068 |
| 2 | simulated user, stock `claude-code` target | **failed**: target `session/new` "Could not resolve authentication method"; operator burned turns diagnosing (§3.1) | killed | ~$0.10 |
| 2′ | simulated user, credentials seeded | operator verbatim 3/3; target answered; **skill absent** from target (§3.2) | ~55 s | $0.037 operator |
| 3 | simulated user, credentials + skills seeded | operator verbatim 3/3; target registered + invoked the skill | ~55 s | $0.037 operator |
| steps | 3-step scripted, `--resume-trajectory` | one session across steps; word from turn 1 recalled in turn 3; per-step cost | 59 s | $0.092 |

Local ACP auth matrix (adapter driven by hand, outside Harbor): OAuth token
in env → PONG; copied credentials file, no env → PONG; `ANTHROPIC_AUTH_TOKEN`
= OAuth token → PONG. So the adapter is fine; the shell hop is the problem.

The real replay, through the module (`make peval-harbor ARGS='run
src/planning-eval-harbor/fixtures/008-commit-session-link-short.json'`):
planning-eval's worked example (auto-stack task 008 at its pre-planning
commit, the v2 planning skills) truncated to the `/new-task` prompt plus the
first steering turn:

| | |
|---|---|
| Completion | `ok` — both turns ran, one native session, no exceptions |
| Wall clock | 349 s total: image build cached, 8.7 s environment start, 11.9 s Claude Code install + skill upload, 305 s agent (turn 1: 203 s, turn 2: 103 s) |
| Cost | **$1.15** (turn 1: $0.79, turn 2: $0.36), from Claude Code's own `result` events |
| Tokens | 1.93 M total, of which 1.85 M cache reads and 12.9 k output |
| Skills | 54 registered (39 arm + 15 built-ins); turn 1 invoked `new-task` then `rich-doc` |
| Produced | exactly one file: `docs/tasks/008-session-id-from-commit/plan.html` — a Requirements tab with 9 `pd-ac` criteria, a mermaid diagram, and one `pd-question`, which turn 2 answered (`status="answered"`) as the steering turn asked |
| Provenance | `lock.json`: task digest, 39 skill digests, `peval_agents:ClaudeCodeReplay`, model, `resume_trajectory: true` |
| Evidence kept | `docs/research/harbor-vs-planning-eval-evidence/` — the transcript, `peval-result.json`, `summary.json`, `lock.json`, and the produced `plan.html` |

For scale: planning-eval's full six-turn v2 baseline for the same task was
787 s and 17.3 M tokens (its README). Two of those six turns here cost 349 s
and 1.9 M tokens on a cheaper model, with ~20 s of that being Docker overhead.
The numbers are not comparable as an A/B — different model, different turn
count, different token meter — but they say the Docker cost is not the story.

## 8. Recommendation

1. **Keep `src/planning-eval/` as is for now; use `src/planning-eval-harbor/`
   for new replays.** Same fixture files, so nothing is stranded. Retire
   planning-eval once a full 6-turn fixture has been replayed on both and the
   outputs compared (a good next task: cost is one planning replay each).
2. **Default to the scripted operator.** It is the faithful replacement; the
   simulated operator is available (`--operator simulated`) for the intent-
   corpus future, with adherence checked.
3. **Report the two upstream gaps** (token stripped on the ACP hop; skills not
   reaching the ACP target) to Harbor with the reproductions above. If they
   land, `peval_agents.py` shrinks to the credentials seeding.
4. **Do not adopt Harbor's verifier/reward path.** Nothing in this repo's eval
   stance changed: judgement stays human, and the harness never emits a score.
   `harbor view` is useful for the trajectory and the artifact tree, not for
   judging a rendered document: it previews HTML as source. For human
   judgement of the produced docs, side-by-side arms, and comments that feed
   the next iteration, the `src/evals/` viewer already does all three — an
   exporter from the Harbor run layout into the evals run layout is the
   cheapest route (see §8a).

8a. **Arms and a reading room are the next two pieces.** `run.py` takes one
   arm per run today (the fixture's `skills_dir`); comparing an edit to a
   skill against its committed version means two runs and a hand-made
   snapshot. Lifting `src/evals/arms.py` (`--arm HEAD --arm WORKTREE`, any
   ref via `git archive`) and putting each arm into one Harbor job as its own
   `agents[]` entry gives both arms in one job, one image build, and per-arm
   skill digests in the lock file.
5. **Bundle git history into the seed if a replay needs it.** Cheap to add
   (`git bundle`), not needed for the evidence run.

## 9. Decisions taken without asking

| Question | Choice | Why |
|---|---|---|
| Installed Harbor is 0.18.0 (no simulated user) | Left the user's tool install alone; the module carries its own `uv` environment pinned to `>=0.23,<0.24` | Repo convention (per-module `pyproject` + `uv.lock`), and no state change to the machine |
| No `ANTHROPIC_API_KEY` on this machine | Authenticate from a copy of `~/.claude/.credentials.json` seeded into the sandbox | The recipe `src/evals/` already relies on; also survives token expiry |
| Scripted vs simulated as the default | Scripted (multi-step + resume) | Matches what planning-eval does today; deterministic; one agent per trial |
| Fixture schema | planning-eval's, unchanged, plus optional `limits.max_budget_usd` and `persona` | One file drives both harnesses |
| Seed tree | `git archive` at the SHA, `.claude/skills/` excluded, one commit in the image | Small, reproducible, consistent with `src/evals` scenario rules; same arm boundary as `build.sh` |
| Where the arm's skills go | Harbor `--skill` injection (`CLAUDE_CONFIG_DIR/skills`), not baked into the image | Digest-recorded provenance in `lock.json`; the image stays a function of the SHA alone |
| Model | `anthropic/claude-sonnet-4-6` (evals' default), overridable | Same model as the sibling harness; cheaper than opus for evidence runs |
| "What did the run produce" | Collect `/app` minus `.git`; diff against the seed tarball on the host | Avoids using the verifier as a post-run hook |
| Evidence run size | 008 truncated to two turns, `max_budget_usd: 8` | The brief asked for a small real replay with the cost reported |
| Harbor telemetry | Off (`HARBOR_TELEMETRY=off`) for every run | Nothing about this repo's runs should leave the machine |

## Related

- `src/planning-eval-harbor/README.md` — the module reference.
- `src/planning-eval/README.md` — the harness being compared.
- `src/evals/README.md`, `docs/evals-user-guide.md` — the single-shot sibling whose conventions this follows.
- `docs/headless-claude-cli-evals.md` — the credentials-file isolation recipe.
- `docs/research/planning-eval-validation.md` — the noise floor any A/B on either harness has to respect.
