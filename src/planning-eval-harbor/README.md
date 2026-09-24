# planning-eval-harbor

Replays a planning-eval fixture — a real historical task, at its pre-planning
commit, with the operator's turns scripted — as a **Harbor** job instead of an
NTM-hosted terminal session. Same fixture file, same arm boundary, same result
shape as [`src/planning-eval/`](../planning-eval/README.md); a Docker sandbox
and Harbor's provenance instead of tmux scraping.

Built side by side with `planning-eval`, which is untouched and still works.
The research behind it — what Harbor actually provides, what it cost to fit,
and the recommendation — is
[`docs/research/harbor-vs-planning-eval.md`](../../docs/research/harbor-vs-planning-eval.md).

**Judgement is a human reading the outputs.** Every job runs with Harbor's
verifier disabled. There is no reward, no grader, no rubric; the one automated
check is whether a simulated operator sent its script verbatim, because that
failure would silently turn the run into a different experiment.

## Quickstart

```bash
# Compile the fixture into a Harbor task and validate the job — spends nothing.
make peval-harbor ARGS='run src/planning-eval-harbor/fixtures/008-commit-session-link-short.json --dry-run'

# The same, live. Bills real tokens (see Budget).
make peval-harbor ARGS='run src/planning-eval-harbor/fixtures/008-commit-session-link-short.json'

# What ran, and what it left.
make peval-harbor ARGS='list'
make peval-harbor ARGS='show <run>'
make peval-harbor ARGS='view'          # Harbor's own results viewer on runs/
```

`make peval-harbor` is
`uv run --project src/planning-eval-harbor --no-dev python src/planning-eval-harbor/run.py`.
The module has its own `pyproject.toml` and `uv.lock` because it depends on
`harbor` (>= 0.23); the tests do not, and run from the root environment with
the other suites (`make test`).

### Prerequisites

- **Docker** (rootless is fine — that is what this was verified on).
- **`~/.claude/.credentials.json`** — Claude Code's login. The sandbox
  authenticates from a copy of this file, exactly as `src/evals/` does; no
  API key is needed and none is read.
- The fixture's **target repo** checked out locally at a path the fixture names.
- Network access from containers: Harbor installs Claude Code into the
  sandbox at trial start.

## Concepts

| Term | Meaning |
|---|---|
| **Fixture** | The planning-eval fixture JSON: `fixture.target_repo`, an immutable `start_sha`, the opening `prompt`, `human_turns`, the `arm`, `limits`. Optional keys this harness reads: `limits.max_budget_usd` (hard spend cap, passed to Claude Code), `persona` (simulated operator only), and two source forms resolved by `sources.py` — `fixture.repo_url` in place of `target_repo` (any git URL; the start commit is fetched shallow into `~/.cache/planning-eval-harbor/repos/`) and `arm.skills_ref` in place of `arm.skills_dir` (below). See planning-eval's README for how to mine one. |
| **Arm** | `arm.skills_dir` — or `arm.skills_ref`, a commit of this repo whose compiled `skills/` tree is exported with `git archive` into `~/.cache/planning-eval-harbor/arms/<sha>/`. `run --skills-ref REF` swaps any fixture's arm for the skills at `REF` (labelled `skills-<sha12>` unless `--arm-id` says otherwise), so past versions replay without a checkout. Injected into the sandbox by Harbor (`agents[].skills`) and registered in the agent's `CLAUDE_CONFIG_DIR/skills`. The target repo's own `.claude/skills/` is stripped from the seed tree, so — as in planning-eval — two arms differ only by workflow. Harbor records every skill's content digest in `lock.json`. |
| **Operator** | Who sends the turns. `scripted` (default): one Harbor *step* per message, Claude Code resuming its native session between steps, so the message sent is the fixture's message byte for byte. `simulated`: a second Claude Code plays the operator over Harbor's ACP bridge and relays the script; what it actually sent is checked afterwards. |
| **Run** | One Harbor job: one fixture, one arm, `--trials N` attempts. `runs/<job>/` is Harbor's job directory with this harness's summaries written beside its files. |

## How a run flows

```
fixture.json ─► task.py ──► tasks/<fixture>-<arm>-<operator>/
                             environment/Dockerfile + repo.tar   (tree @ start_sha, minus .claude/skills)
                             steps/turn-NN/instruction.md        (scripted: one per message)
                             instruction.md + persona.md         (simulated: the script)
                             tests/test.sh                       (required by Harbor; never runs; fails loudly if it does)
            ─► job.py ───► job-config.json  → harbor run --config … --yes
                             agents[0]: peval_agents:ClaudeCodeReplay, skills=[arm], resume_trajectory
                             artifacts: /app (minus .git); verifier: disabled
            ─► Harbor ───► build image → start container → install claude → seed credentials + skills
                             → step 1: claude -p <msg> … → step N: claude -p --continue <msg>
                             → collect /app → runs/<job>/<trial>/…
            ─► results.py ► peval-result.json, transcript.txt, produced/, summary.json
```

## Run outputs

`runs/<job>/`:

| File | Written by | Contents |
|---|---|---|
| `config.json`, `lock.json`, `result.json`, `job.log` | Harbor | Resolved job config; **provenance** (task digest, each injected skill's sha256, harbor version); job result; log. |
| `peval.json` | this harness | What was replayed: fixture path, arm, operator, model, the messages, the compiled task and seed tarball. |
| `summary.json` | this harness | Per-trial completion, wall, tokens, cost, produced-file count. |
| `<trial>/steps/turn-NN/agent/claude-code.txt` | Harbor | The **full stream-json transcript** of that turn — the same format `src/evals/` parses. |
| `<trial>/steps/turn-NN/agent/trajectory.json` | Harbor | The turn as an ATIF trajectory (what `harbor view` renders). |
| `<trial>/steps/turn-NN/agent/sessions/` | Harbor | Claude Code's config dir after the turn: native session `.jsonl` (parent + subagents), the registered skills. |
| `<trial>/steps/turn-NN/artifacts/app/` | Harbor | The workspace **after each turn**. |
| `<trial>/peval-result.json` | this harness | planning-eval's schema: `completion`, `turns[]` (sent / reply / wall / cost / tokens / skill calls / files produced so far), `velocity`, `artifacts`. |
| `<trial>/transcript.txt` | this harness | Per turn: what was sent, everything the agent said. |
| `<trial>/produced/` | this harness | Only the files the run created or changed, diffed against the seed tarball by content hash. |

Nothing is ever cleared automatically. `clean` is dry by default and prints
what it would remove; `--yes` removes runs and compiled tasks. Docker images
Harbor built are left for `docker image prune`.

## The one automated check: adherence (simulated operator only)

With `--operator simulated`, an LLM is following the script. `results.adherence`
reads the **target's own session file** — every message it actually received —
and compares it to the script, turn by turn, seeing through Claude Code's
slash-command rewriting and shell escapes. A paraphrased, skipped or extra
message marks the trial `diverged` and prints the mismatch in the transcript.
In the verification runs the operator was verbatim three of three times; treat
that as encouraging, not as a guarantee.

The scripted operator needs no such check: the instruction file *is* the message.

## Comparing arms

Run the same fixture twice with different `arm.skills_dir` (as planning-eval
does), then read the two runs' `transcript.txt` and `produced/` side by side.
`harbor view` renders every step's trajectory with its cost and timing, but
previews an HTML artifact as source, not rendered. To judge a produced
`plan.html` open `produced/…/plan.html` in a browser (it is a self-contained
pd-components document), or see the research doc's §8a for the planned export
into the `src/evals/` viewer, which renders HTML side by side and carries
comments.

Planning is non-deterministic: planning-eval measured a 1.5–1.8× spread between
identical runs (`docs/research/planning-eval-validation.md`). `--trials 3`
gives three attempts to look at; nothing here averages them.

## Budget

Measured on this harness (Claude Code 2.1.273 in the sandbox, `claude-sonnet-4-6`):

| What | Wall | Cost |
|---|---|---|
| Image build (first time; cached after) | ~40 s | – |
| Container start + Claude Code install, per trial | ~20–30 s | – |
| 3-turn smoke replay, scripted | 59 s total | $0.09 |
| 3-message smoke replay, simulated operator | ~55 s total | $0.04 operator + target |
| `008-commit-session-link-short` (real `/new-task` + one steering turn, 39 skills) | 349 s (20 s of it Docker + install) | $1.15, 1.9 M tokens |

A full 6-turn planning replay is the same order as planning-eval's (minutes to
tens of minutes, millions of tokens). Set `limits.max_budget_usd` in the fixture.

## Limitations

1. **Claude Code only.** `peval_agents.py` subclasses Harbor's `claude-code`
   integration; the transcript reader parses its stream-json.
2. **History-free seed.** The sandbox gets the tree at `start_sha` as one
   commit, not the repo's history (deliberately — see `task.py`). A workflow
   that mines `git log` sees less than it would under planning-eval.
3. **Turn boundary = process exit.** A scripted turn ends when `claude -p`
   returns; there is no "agent asked a question mid-turn" detection, and an
   `AskUserQuestion` cannot be answered (the same preamble planning-eval uses
   forbids it).
4. **Simulated operator fidelity is measured, not guaranteed** — see adherence.
   Under the ACP bridge the target also uses ACP-provided file tools rather
   than native ones, so its tool surface differs from a terminal session.
5. **Velocity comes from Claude Code's own accounting** (per-turn `result`
   events, cross-checked against the native session files), not autoetl. In
   simulated mode Harbor's cost figure covers the *operator* only; the target's
   tokens are recovered from its session file, without a dollar figure.
6. **Not a sandbox against the network.** Containers run with public egress by
   default (Harbor supports allowlists; not wired here).
7. **Never in CI.** A live run bills real tokens; `--dry-run` and
   `pytest src/planning-eval-harbor/tests/` are the free lanes.

## Tests

```bash
uv run pytest src/planning-eval-harbor/tests/ -q     # offline; no harbor, no docker, no credentials
```

`tests/fixtures/` holds two real Harbor 0.23.0 trial directories from the
verification runs, trimmed to what the reader consumes, so the parser is held
to recorded output rather than an imagined shape.
