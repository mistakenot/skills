# evals — a contained A/B harness for skill versions

Runs one task against one or more **arms** — an arm being a specific version of a
skill, or no skill at all — each in its own isolated clean room, and leaves a run
directory a human can read side by side.

**Judgement is a human reading the outputs.** There are no graders, no LLM
judges, no rubrics: those are downstream of knowing what "good" looks like, and
for the cases this was built for we do not yet know. The single automated check
is whether the skill actually fired, because that failure is the one that lies to
you (see [The one automated check](#the-one-automated-check)).

Named plural deliberately: `eval` is a shell builtin, so a bare `eval` on PATH
would be shadowed.

## Getting started

**New here? The task-oriented walkthrough is
[docs/evals-user-guide.md](../../docs/evals-user-guide.md)** — first run, the
three jobs, writing a scenario, reading a result, budget, and what to do when
something breaks. This section is the short version; the rest of this file is
reference.

### 1. Run the stub lane first

It exercises the whole harness — arm resolution, clean room, canaries, run
directory, report — with a canned transcript instead of a billed agent. Free,
about a second, and it catches every boring failure before you spend anything.

```bash
make evals ARGS='run --skill rich-doc --arm none --arm WORKTREE \
    --prompt "what is 2+2?" --runner stub'
```

Open the `REPORT.md` it prints a path to. That artifact is where you will spend
all your time.

### 2. Pick your arms

The arms *are* the experiment; everything else is held constant.

| Question | Arms |
|---|---|
| Does this skill do anything? | `--arm none --arm WORKTREE` |
| Is my edit better than what is committed? | `--arm HEAD --arm WORKTREE` |
| What does this idea even do? | `--arm WORKTREE` alone |

`WORKTREE` is your **uncommitted** working tree, which is the point: you can
evaluate a change before committing it, rather than committing in order to test.

### 3. Go live

Same command without `--runner stub`. Two arms on a real repo is roughly
**$1–2 and 7–8 minutes**.

```bash
make evals ARGS='run --skill rich-doc --arm none --arm WORKTREE \
    --scenario datasette-parquet-renderer'
```

### 4. Read it

```bash
make evals ARGS='list'
make evals ARGS='show 20260904-124538-3ea2ee7'
make evals ARGS='clean --keep 5 --yes'
```

In `REPORT.md`, read in this order — **did the skill fire** (if not, stop; it is
not a comparison), then the side-by-side table, then the excerpts, then the
output files if you need to judge quality. The counts are observations, not
scores: the harness never tells you which arm is better.

`make evals` is `PYTHONPATH=src uv run --no-dev python -m evals`; run that
directly if you prefer. A live run needs `~/.claude/.credentials.json` (Claude
Code auth) — the clean room authenticates by copying that file into a relocated
config dir. The stub needs nothing.

## Arms

An arm is a parameter, which is what makes "with vs without a skill" and
"version A vs version B" the same mechanism. `--arm` is repeatable; one arm is a
legal run (a single-arm exploration, away from this repo's ~38 skills and
`CLAUDE.md`, rather than a degenerate A/B).

| `--arm` | What gets installed |
|---|---|
| `none` | Nothing. The baseline: same prompt, same model, same clean room, minus the skill. No `skills/` directory is created at all — an empty one is a different condition. |
| `WORKTREE` | `src/compile.py` is run, then `skills/<name>` is copied off disk. This is **not** a git operation and must not become one: `git archive` only sees committed content, and evaluating a change before committing it is the entire author loop. |
| anything else | A git ref, materialised with `git archive <ref> -- skills/<name>`. Extracted, never checked out — a checkout would move the tree the `WORKTREE` arm reads from. |

`none` and `WORKTREE` are therefore reserved names: a branch called either one
cannot be addressed as an arm. Every arm is resolved before the first token is
spent, so a typo in the third arm's ref surfaces before the first arm is billed.
Each arm writes a `manifest.json` recording its resolved sha (or, for
`WORKTREE`, the head it sat on and whether the tree was dirty).

## Scenarios

The task is either `--prompt "..."` (inline, for throwaways) or `--scenario
<name-or-dir>` (a directory that also prepares the workspace). Bundled scenarios
live in `scenarios/`; their rules — pinning, relocatability, the clone cache —
are in [`scenarios/README.md`](scenarios/README.md).

## The run directory

```
runs/<run-id>/
    manifest.json         what this run compared: skill, arms, prompt, model, invoke mode, trials
    REPORT.md             the human-facing summary
    <arm>/
        manifest.json     provenance: kind, resolved sha, head, dirty
        invocation.json   did the skill fire, what did it read
        <trial>/
            out.md        the final assistant message
            stream.jsonl  the full stream-json transcript
            err.txt       stderr
            ws/           the workspace as the agent left it
            skill/        exactly what was installed (absent on the `none` arm)
```

Nothing is ever cleared automatically, which is what keeps "what exactly was in
that arm?" answerable a day later. `evals clean` is the management for that, and
is dry by default — it prints what it would remove and removes nothing until
`--yes`.

The run manifest is written *before* the first token is spent and rewritten at
the end, so a run killed halfway still lists and is visibly `status:
incomplete`.

## The one automated check

If the skill never loaded, both arms are the same run — and you will sit
comparing two outputs, inventing explanations for what is sampling noise. Every
other failure here announces itself; this one does not.

`invocation.py` parses `stream.jsonl` for `tool_use` blocks and records, per arm:
whether a `Skill` call named *this* skill **and came back without an error**,
every `Read` path that resolved inside the skill, and every `Bash` command.
Ground truth from the transcript, never a self-report. An arm counts as invoked
only if **every** trial invoked.

A miss puts `SKILL NOT INVOKED` above everything else in `REPORT.md` — but only
a miss that means something. An arm that installed nothing (`none`) was never
going to invoke, so its silence is stated in the comparison table
(`no — expected (nothing installed)`) rather than alarmed on; the banner is for
an arm that *had* the skill and did not run it, or for a run where no arm ran it
at all. The arm's `kind` (from its own `manifest.json`) is what decides which,
and an arm whose manifest cannot be read is assumed installed so an unknown run
alarms rather than passing quietly. Firing on every healthy with/without run
would be the same failure as never firing, with the sign flipped: both teach the
reader to skip the line.

A `Skill` tool_use is a *request*, not an outcome: when the skill is not
installed the CLI emits the call anyway and the result comes back
`<tool_use_error>Unknown skill: …</tool_use_error>`. Each call is paired with its
`tool_result` by `tool_use_id`, and `registered` (membership in `init.skills`)
corroborates in one direction — an init event that does not list the skill vetoes
any claim that it loaded. The `Skill` tool also opens `SKILL.md` without emitting
a `Read`, so the load itself is counted in `reads`; `skill_bash` carries the other
real evidence, the `Bash` lines that name a path inside the skill.

`--invoke` decides what the run is measuring:

- **`instructed`** (default) appends "Invoke the `<skill>` skill before you
  begin." Routing is removed from the experiment, so the run measures the
  skill's *content*. Right for version-vs-version.
- **`organic`** appends nothing, so the description has to earn the invocation.
  Here "did it fire" is itself the result, not a precondition — nothing escalates
  a miss.

## Isolation canaries

Four filesystem checks (`canaries.py`) run on every cell, before the agent is
spawned, in both the live and stub lanes. They raise rather than warn, because
isolation failing is silent — a leaked repo tree produces a plausible result that
measures the wrong thing.

1. `CLAUDE_CONFIG_DIR` resolves outside the repo tree.
2. No git repo above the workspace. Claude Code walks *up* from cwd and
   re-discovers a parent repo's project skills and `CLAUDE.md` regardless of
   `CLAUDE_CONFIG_DIR`.
3. The config dir's skill set is exactly what we installed.
4. No `CLAUDE.md` or `.claude/` in any strict ancestor of the workspace.

The isolation recipe itself is documented and version-stamped in
[`docs/headless-claude-cli-evals.md`](../../docs/headless-claude-cli-evals.md).
One rule from it is load-bearing and easy to undo by accident: **never pass
`--setting-sources ''`.** It isolates, but it also suppresses discovery of the
skill under test, so the with-skill arm quietly becomes a second baseline.

## Limitations

Read these before you trust a result. Each names a specific thing that breaks.

### 1. Claude-only

`stream.jsonl` parsing is specific to Claude Code's `--output-format
stream-json`. The invocation check reads `system/init`'s `skills` array and
`assistant` events' `tool_use` blocks by name (`Skill`, `Read`, `Bash`). Point
this at Codex or Grok and the parser silently finds no tool calls — every arm
reports NOT INVOKED regardless of what happened. Adding a second host means
replacing transcript parsing with a self-reported trailer protocol; Compound
Engineering's `FILES_READ:` trailer
([`docs/compound-engineering-evals.md`](../../docs/compound-engineering-evals.md))
is the migration path.

### 2. With/without under `instructed` carries a prompt confound

You cannot tell an arm to invoke a skill it does not have. Under `--invoke
instructed` (the default) the with-skill arm's prompt gains "Invoke the `<skill>`
skill before you begin." and the `none` arm's does not — so the arms differ by a
sentence of prompt *as well as* by the skill, and a difference in the outputs
cannot be attributed to the skill alone. `src/assurance/evals/run.sh:194-196`
acknowledges exactly the same thing for its own harness. Prefer `--invoke
organic` for with/without comparisons wherever the skill routes reliably; keep
`instructed` for version-vs-version, where both arms get the same sentence and
the confound cancels.

### 3. N=1 by default

One pair of outputs can mislead — the same arm run twice differs, and the spread
can exceed the effect you are looking for (the planning-eval baseline measured
~1.5–1.8×). The tool will not stop you running a single pair and drawing a
conclusion from it. What it does do is state the trial count on its own line in
`REPORT.md`, so it is always obvious which you are holding. `--n` repeats each
arm into `<arm>/<trial>/` and does **no statistics**: no aggregation, no medians,
no bests. The trials are for looking at.

### 4. Component-library confound, for `rich-doc` specifically

`rich-doc`'s SKILL.md curls `llms.txt` from a CDN tag that `src/compile.py`
expands from `pd-components/package.json` at compile time. A `WORKTREE` arm
therefore pins the version in the current `package.json`, while a ref arm pins
whatever was baked in at that commit — so the two arms can differ by component
library version as well as by SKILL.md, and any difference in the output is
un-attributable. Pin both arms to the same `pd-version` before comparing, or the
result is uninterpretable. The same trap applies to any skill that fetches
versioned content at run time.

### 5. Not a sandbox

Cells run `claude -p --permission-mode bypassPermissions` with a copy of your
real credentials, in a `mktemp -d` workspace. The agent can do anything you can
do — including reaching the network and writing outside the workspace. Scenario
fixtures must be disposable, and a scenario prompt is as trusted as a command you
typed yourself.

### 6. Never in CI

A live run bills real tokens and takes minutes. `make evals` is a human-driven
command. Only the stub lane (`--runner stub`) and `pytest src/evals/tests/` are
safe to automate; both are offline and free.

## Findings that shaped the design

These were measured, not assumed. They are the reason several things here look
more paranoid than they need to.

**The CLI's project-root walk-up is name-based; ours is content-based, and they
deliberately disagree.** Canary 2 asks whether a directory is a *real* git repo
(`.git/HEAD` present, or `.git` as a gitlink file), because this machine has an
empty `/tmp/.git` that git itself rejects — treating it as a repo would fail
every clean-room run. The CLI does not make that distinction: measured on
2.1.260, a workspace seven levels below `/tmp` resolved its project root to
`/tmp` on the strength of that same empty `.git`, and a `CLAUDE.md` planted
there was loaded into the clean room as project instructions. Canary 4 exists
because canary 2 stays green through exactly that leak. `mktemp -d` under `/tmp`
is *usable, not self-evidently safe* — `/tmp` is world-writable, and canary 4 is
what converts that assumption into a pre-flight failure.

**Never assert against the built-in skill floor.** The skills that ship with the
`claude` binary cannot be removed by relocating the config dir, so they appear in
both arms — and the set drifts by CLI version *and* by environment (14 on
2.1.175, 13 on 2.1.260, with membership changes). Worse, `init.skills` and the
model's own account of its skills are both real but have different inclusion
rules, and disagreed by 4–5 entries on the same binary in the same process. A
hard-coded floor is a time bomb: assert on config-dir contents you control, and
if you need the visible list, compare arms *within* a run. See "The irreducible
floor" in [`docs/headless-claude-cli-evals.md`](../../docs/headless-claude-cli-evals.md).
The stub's `STUB_BUILTIN_SKILLS` exists only so its init event looks real;
a test rewrites that list and requires a stub run to be unaffected.

**The stub was too kind — and a negative control is only as good as the world it
runs against.** The invocation check shipped with a false positive in exactly the
case it exists to catch: under `--invoke instructed` the `none` arm reported
`invoked: true`, because the detector read the `Skill` tool_use and never its
`tool_result`. It had a negative control, and the control passed — in stub mode.
The stub modelled "skill absent" as *no `Skill` call at all* and never emitted a
failed tool call of any kind, so the control was run against the world the
implementer imagined rather than against the CLI, where the agent calls `Skill`
and is refused. Two lessons, both general:

- A negative control that only ever runs against your own mock proves your mock
  agrees with your parser. Anchor it to recorded output from the real system —
  `tests/fixtures/live-none-instructed-stream.jsonl` is that run, committed.
- Mocks are lenient in the direction of the author's assumptions. The failure
  modes a stub declines to model are precisely the ones nothing will catch, so
  make the stub emit the ugly shapes: errors, refusals, partial results.

A detector that is trusted and wrong is worse than no detector, which is the
thing the check was built to prevent — so `test_failed_skill_call.py` asserts the
failed call is *present* in the transcript before asserting the verdict, and
reverting the fix fails eight tests.

**Cache reuse cannot be proven by a marker file alone.** The scenario cache
publishes atomically: a second fetch is assembled in a staging directory and
discarded on `rename` if another one won, so the marker survives and a
marker-only assertion passes against a cache that re-fetched every time. The test
counts `setup.sh` executions instead, and a companion test proves the counter
would catch a missing cache.

**Scenario `setup.sh` runs in a cache staging directory, not in the cell.** It
runs once per scenario and the prepared tree is copied into each cell, so the
directory it runs in is not the directory the agent sees: it must produce a
*relocatable* tree with no absolute paths baked into anything it generates. It
must also not make `ws/` a git repo, or canary 2 rejects every cell. That is why
the datasette fixture fetches a tarball rather than cloning.

**Fixtures must be pinned to a literal 40-character sha,** enforced at load time
by `check_pins`. A floating ref drifts between runs, so two runs a week apart are
not comparable — and for a "plan how to add X" task, an upstream X merged since
the scenario was written would be handed to the agent as the answer, and the eval
would measure nothing.

## Tests

```bash
uv run pytest src/evals/tests/ -q     # offline, no credentials needed
```

`make test` runs these alongside the assurance tests. The stub runner's canned
transcript is checked for shape against `tests/fixtures/live-stream.jsonl`, a
real recorded run, so the offline lane cannot drift into a simplified shape the
invocation parser would never meet in production.

## Related

- [`docs/evals-user-guide.md`](../../docs/evals-user-guide.md) — the user guide: first run, the three jobs, authoring a scenario, reading a result, budget, troubleshooting.
- [`docs/evals-harness.md`](../../docs/evals-harness.md) — orientation: when to reach for this harness rather than another.
- [`docs/headless-claude-cli-evals.md`](../../docs/headless-claude-cli-evals.md) — the isolation recipe, the CLI flags, the JSON envelope, the floor.
- [`src/assurance/evals/`](../assurance/evals/) — the two-arm harness this cell was lifted from; adds mechanical checks and an LLM judge.
- [`src/planning-eval/`](../planning-eval/) — the conversational, multi-turn harness. Use that when the skill needs turns; use this when one prompt determines the output.
- `eval-engineer` skill — how to choose between them, and how to validate an eval before trusting it.
