---
hash: "61709c72"
id: "b86e61ee"
read_when: "actually running an eval — setting one up, authoring a scenario, reading a result, iterating on a skill against it, or working out why a run failed"
summary: "Task-oriented user guide for the src/evals/ harness: your first run, the three jobs it does, writing a scenario, reading a result in the right order, the edit-run-read loop, budgeting, troubleshooting the real failure modes, and how learnings get back into the skills."
title: "evals — user guide"
---

# evals — user guide

This is the **how-do-I** guide. For what each piece *is*, see
[`src/evals/README.md`](../src/evals/README.md) (the reference). For whether to
use this harness at all, see [evals-harness.md](evals-harness.md) (orientation
and limitations).

The mental model in one line: **a run executes one task against one or more
*arms*, each in its own clean room, and leaves you two things to read.** An arm
is a version of a skill, or no skill at all.

---

## 1. Your first run

Start with the stub lane. It exercises the entire harness — arm resolution,
clean room, canaries, run directory, report — with a canned transcript instead
of a billed agent. It costs nothing and takes about a second.

```bash
make evals ARGS='run --skill rich-doc --arm none --arm WORKTREE \
    --prompt "what is 2+2?" --runner stub'
```

You should see each arm resolve, run, and report, ending with a path to
`REPORT.md`. Open it. This is the artifact you will spend all your time in.

Then look at what it left behind:

```bash
make evals ARGS='list'
make evals ARGS='show <run-id>'
```

Once the stub run works, the live lane is the same command minus `--runner
stub`. **It bills.** Budget below.

`make evals` is just `PYTHONPATH=src uv run --no-dev python -m evals` — run that
directly if you prefer. A live run needs `~/.claude/.credentials.json`; the stub
needs nothing.

---

## 2. The three jobs

All three are the same mechanism. Only the arms change.

### With vs without a skill

*"Does this skill do anything at all?"*

```bash
make evals ARGS='run --skill rich-doc --arm none --arm WORKTREE \
    --scenario datasette-parquet-renderer --invoke organic'
```

`none` installs nothing: same prompt, same model, same clean room, minus the
skill. Prefer `--invoke organic` here — see [§6](#6-instructed-vs-organic).

### Version A vs version B

*"Is my change better than what's committed?"*

```bash
make evals ARGS='run --skill rich-doc --arm HEAD --arm WORKTREE \
    --scenario datasette-parquet-renderer'
```

This is the loop you will use most. `HEAD` is committed; `WORKTREE` is your
uncommitted edit. **This is why `WORKTREE` exists** — `git archive` only sees
committed content, so without it you would have to commit in order to test,
which inverts the whole workflow. Edit, run, read, edit again; commit only once
it is actually better.

Any git ref works as an arm, so `--arm v0.3.0 --arm HEAD` compares releases.

### Single-arm exploration

*"What does this new skill idea even do on a hard problem?"*

```bash
make evals ARGS='run --skill my-new-idea --arm WORKTREE --scenario <s>'
```

One arm is a legal run, not a degenerate A/B. Its value is **isolation**: your
idea runs without this repo's ~38 other skills, its `CLAUDE.md`, and its hooks
all shaping the result. You cannot get that by testing in the repo.

The caveat: with one arm you cannot tell *"the skill did this"* from *"the model
would have done this anyway."* The moment you want to claim value, add `--arm
none`. One flag turns a look into an experiment.

---

## 3. Writing a scenario

Use `--prompt` for throwaways. Promote to a scenario as soon as you will run it
twice, or as soon as the task needs a prepared workspace.

```
src/evals/scenarios/<name>/
    prompt.md    required   handed to every arm verbatim
    setup.sh     optional   prepares the workspace; cwd is the workspace
    fixture/     optional   static files copied in
```

There is no registry. The catalog is `ls src/evals/scenarios/`.

Four rules, all **enforced** rather than left to review — the full rationale is
in [`src/evals/scenarios/README.md`](../src/evals/scenarios/README.md):

1. **Pin every ref to a literal 40-character SHA.** `check_pins` fails a
   `setup.sh` naming a branch — at load, before a token is spent. A floating
   fixture drifts between runs; worse, on a *"plan how to add X"* task, an
   upstream X merged since you wrote the scenario gets handed to the agent as
   the answer.
2. **Fetch a tarball, not a clone.** `https://codeload.github.com/<owner>/<repo>/tar.gz/<sha>`
   gets the tree without the history. Much faster, and no history for an agent
   to mine.
3. **Never make the workspace root a git repo.** Extract into a subdirectory, or
   canary 2 rejects every cell.
4. **`setup.sh` must produce a relocatable tree.** It runs once in a cache
   directory and the result is copied per cell, so the directory it runs in is
   not the one the agent sees. No absolute paths baked in.

The bundled `datasette-parquet-renderer` scenario is the worked example, and its
`setup.sh` is commented with why each rule is there.

**Choosing a task matters more than the mechanics.** A good scenario has a
*discriminating* path — something a weaker skill version gets wrong — and the
task should be absent from the fixture at that SHA, or the agent is just reading
you the answer.

---

## 4. Reading a result

Open `REPORT.md` and read it in this order. The order matters: each step can
invalidate everything below it.

**1. Did the skill actually fire?** If the arm that has the skill did not invoke
it, stop — nothing below is a comparison, and any difference you see is sampling
noise. This is the one automated check the harness makes, because it is the
failure that lies to you.

> ⚠️ **Currently unreliable in one direction** (`skills-7k7.15`, open): the
> banner also fires on *healthy* with/without runs, because a `none` arm not
> invoking the skill is expected. Read the `skill invoked` row of the table
> rather than the banner until that is fixed.

**2. The side-by-side table.** Type, size, line counts, structural counts,
custom elements. Note the footnote about structural rows not being comparable
across arms when the file types differ — `headings: 31 | 0` does not mean the
second arm has no structure.

**3. The excerpts.** The first lines of each arm's output, inline. Usually
enough to see the shape of the difference without opening anything.

**4. The output files themselves**, if you need to judge quality. Paths are in
the Files section.

Counts in the report are **observations, not scores**. Nothing in the artifact
tells you which arm is better — that judgement is yours, deliberately.

---

## 5. Is the difference real?

**The honest answer: we have not measured the noise floor for this harness yet.**

Agent runs are non-deterministic. Two runs of the *same* arm on the *same*
scenario will differ. Until you know how much they differ, you cannot tell a
skill effect from weather. For `src/planning-eval/` that spread was measured at
**~1.5–1.8×**, driven by variable subagent fan-out — enough that single-run
comparisons there are worthless.

To measure it here, run the same arm three times and look at the spread:

```bash
make evals ARGS='run --skill rich-doc --arm WORKTREE --scenario <s> --n 3'
```

`--n` deliberately does **no statistics** — no medians, no aggregation. It gives
you three results to eyeball, and `REPORT.md` always states the trial count so
you never forget which you are reading.

Until the noise floor is known, treat a single pair as a *hypothesis*, not a
finding. A difference you can describe in one sentence ("markdown vs a
pd-components document") is safe. A difference of degree ("this one is a bit
better organised") is not, at N=1.

---

## 6. `instructed` vs `organic`

`--invoke` controls whether the prompt tells the agent to use the skill.

| Mode | What gets appended | What it measures |
|---|---|---|
| `instructed` (default) | "invoke skill X before you begin" | The skill's **content** — its guidance, given that it loaded |
| `organic` | nothing | The **description's routing** — whether the skill fires on its own |

For **version A/B**, use `instructed`: both arms get the identical prompt, so
the only variable is the skill.

For **with/without**, prefer `organic`. Under `instructed` you cannot tell an
arm to invoke a skill it does not have, so the arms differ by a sentence as well
as by a skill — a confound you cannot remove. Use `instructed` for with/without
only when you specifically need the skill guaranteed to fire, and note the
confound when you report the result.

Under `organic`, "did it fire?" is itself a result rather than a precondition —
a skill that never routes is telling you something about its description.

---

## 7. Budget

Real numbers from runs on this harness:

| What | Time | Cost |
|---|---|---|
| Stub run, any arms | ~1–3s | free |
| `pytest src/evals/tests/` | ~3s | free |
| Live, trivial prompt, 1 arm | ~7s | ~$0.06 |
| Live, 2 arms, real repo, design-doc task | ~7–8 min | ~$1–2 |

Fixture fetches are negligible and cached: the datasette tarball is ~1 MB / 329
files, 0.4s to fetch, and is fetched **once per scenario** — not per arm, not
per trial.

Rules of thumb: stub first, always — it catches every boring failure for free.
Then price the live run as *arms × trials*. A validated A/B at N≥3 on two arms
is six live cells, so budget accordingly before starting.

---

## 8. When something goes wrong

**`SKILL NOT INVOKED` on a run you think is fine.** Check the table's `skill
invoked` row per arm. A `none` arm not invoking is correct and expected — see
the caveat in §4. If an arm *with* the skill installed did not invoke it, that
is real: check that arm's `skill/` snapshot exists and contains `SKILL.md`, and
that you are not using `--invoke organic` with a skill whose description does not
route for this prompt.

**A canary fails before anything runs.** That is the harness refusing to produce
a contaminated result, and it costs nothing. The four canaries check: the config
dir is outside the repo; no *real* git repo above the workspace; the installed
skill set is exactly what was placed; and no `CLAUDE.md`/`.claude` in any
ancestor. The last one exists because Claude Code's project-root walk-up is
**name-based** — a `CLAUDE.md` in `/tmp` reaches an agent seven levels below it.
`/tmp` is world-writable, so this is a live hazard, not a theoretical one; if
canary 4 trips, something dropped project context into a parent directory.

**`setup.sh` fails the pin check.** Your scenario names a branch somewhere — a
`git checkout`, a `--branch` flag, or an archive URL. Replace it with a literal
40-character SHA. `SHA=...` used as `"$SHA"` is expanded and accepted.

**A `WORKTREE` arm evaluates the wrong thing.** `skills/` is compiled output.
Arm resolution runs `src/compile.py` first for exactly this reason, but if you
edited a skill and did not see your change, confirm you edited the **source**
under `src/<module>/`, not the compiled copy under `skills/`.

**Two arms differ in more than the skill.** The classic is `rich-doc`, which
fetches `llms.txt` from a CDN tag baked in at compile time — so two arms can
differ by component-library version as well as by `SKILL.md`. Pin both arms to
the same version, or the result is uninterpretable.

**`src/assurance/tests/` has two failures.** Pre-existing and unrelated
(`skills-xfw`): `compile.py` requires `pd-components/package.json`, which the
synthetic repos those tests build do not have. Not caused by anything here.

---

## 9. Feeding learnings back

The mechanical loop works today: edit the skill source, re-run with `--arm HEAD
--arm WORKTREE`, read, repeat, commit when it is better.

**What does not exist yet is a way to capture what you learned.** A run leaves
`REPORT.md`, `manifest.json`, `invocation.json` and the outputs — and nothing
consumes them. The knowledge lives in your head between runs.

Until that is wired, do this by hand and it costs almost nothing:

- **Write a short note in the run directory after you read it.** What you
  expected, what you saw, what you changed as a result. Three sentences. It is
  what makes a run from two months ago legible, and it is the raw material any
  future automation would mine.
- **Promote anything durable into the repo's existing machinery** —
  `learning-diary` (`docs/learnings.yaml`) for techniques and breakthroughs,
  `playbook-observe` → `playbook-refine` (`docs/reflection/rules.yaml`) for
  rules that should shape future work.
- **File what you find.** Two of the most valuable findings about this harness —
  that the invocation detector counted a *failed* skill call as a success, and
  that the report's alarm fires on every healthy run — came out of running it
  and reading the result carefully, not out of building it.

---

## Related

- [`src/evals/README.md`](../src/evals/README.md) — the reference: arms, run
  directory, the invocation check, canaries, limitations, design findings.
- [evals-harness.md](evals-harness.md) — orientation: when to reach for this
  rather than `planning-eval` or the assurance harness.
- [`src/evals/scenarios/README.md`](../src/evals/scenarios/README.md) — scenario
  authoring rules in full.
- [headless-claude-cli-evals.md](headless-claude-cli-evals.md) — the clean-room
  isolation recipe the cell implements.
- The `eval-engineer` skill — building and validating an eval before trusting
  it, including the noise-floor method referenced in §5.
