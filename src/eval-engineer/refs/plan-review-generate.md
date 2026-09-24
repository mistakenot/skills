# Generate — build or extend the corpus

Plans are produced by replaying fixtures through planning-eval-harbor: Docker, the
target repo at a fixed commit, the skills at a fixed commit, one turn, stopping at
`new-task-quick`'s first gate. The output is one `plan.html` per trial, ingested into
the corpus.

## Commands

```bash
make plan-review ARGS='generate --dry-run'                          # every fixture; free, validates
make plan-review ARGS='generate --skills-ref <REF> --trials 2'      # all fixtures at REF; bills
make plan-review ARGS='generate f1.json f2.json --skills-ref <REF>' # a subset
make plan-review ARGS='generate --skills-ref <REF> --model <id>'    # override the pinned model
make plan-review ARGS='ingest --all'                                # pick up existing Harbor runs
```

`REF` is any commit-ish of this repo (`HEAD`, `main`, a sha). The arm is the
**committed** `skills/` tree at that commit. Uncommitted edits are not in it, so run
`make compile` and commit before generating from a change.

## Cost: always confirm before spending

In the first batch (sonnet-4-6) one plan cost $0.88–$2.32 and took 5–11 minutes;
each fixture caps a run at $15 (`limits.max_budget_usd`). Before a live run, state
the count (fixtures × trials × versions), the expected cost, and the cap. Wait for a
yes. Runs are independent: launch them as separate background commands, one per
fixture, so they run in parallel.

## How many plans

- **Discovering failure modes (open coding):** breadth beats repeats. One trial of
  many varied fixtures surfaces more modes than many trials of a few.
- **Comparing versions (the loop):** at least **2 trials per fixture per version**.
  Identical runs vary 1.5–1.8× (`docs/research/planning-eval-validation.md`), so
  one plan per fixture cannot tell a change from noise. Both versions get the same
  fixtures and the same trial count.
- **Model:** the corpus should use the model the operator actually plans with. If
  that differs from planning-eval-harbor's pinned default, pass `--model`, and use
  the same model for every version in a comparison.

## Fixtures

Fixtures live in `src/plan-review/fixtures/`. Copy an existing one. The rules:

- `limits.max_turns = 1`. The prompt starts `/new-task-quick ` and **ends with the
  stop line**: `Stop after Stage 4 (self-check); do not run the Codex review.`
  (`corpus.STOP_SUFFIX`). Without it, a run with no open questions goes straight on
  into a Codex review.
- `start_sha` is a literal 40-character sha, from before the work existed.
- `arm` is `{"id": "head", "skills_ref": "HEAD"}`; `generate --skills-ref` overrides it.
- Record the source in `_provenance`. There are three sources:
  - **historic:** the operator's real opening message (find it with `auto search`),
    at the parent of the commit that first added the task's docs.
  - **authored:** written in the operator's voice (look at a few real prompts with
    `auto search search "new-task" --role user --text` first), and grounded in
    something real at the start commit.
  - **oss:** a real closed issue, verbatim, with `repo_url` in place of
    `target_repo`, at the parent of the commit that fixed it. Prefer issues fixed by
    one commit; that commit is a reference answer for later.
- Vary the repos (Go, TypeScript, Python), the task sizes and the task shapes
  (feature, refactor, bug, CLI ergonomics). Failure modes that only show up in one
  repo are about that repo, not the skill.

## After generating

Ingest prints one line per plan with cheap checks. Treat these as defects of the
*run*, not findings about the plan:

- `CODEX RAN`: the stop line was ignored.
- `lint: <codes>`: pd-lint issues other than `open-question`.
- `no plan.html produced`: the run failed. Read its `transcript.txt`.

Re-run the affected fixture rather than reviewing a broken plan.
