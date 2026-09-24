# Iterate — change the skill, regenerate, compare, decide

One iteration tests **one hypothesis about one failure mode**:

change the skill → commit it → regenerate plans with both versions → review them
blind → label them → compare the counts → keep or revert.

Every iteration gets an entry in `src/plan-review/data/iterations.md`, which is the
decision log.

## 1. Pick the target

From `report` (baseline version, current taxonomy), pick one mode that is:

- **frequent**: present in a good share of labelled plans
- **costly**: the reviewer failed the plan over it, or would have to fix it by hand
  before execution
- **the skill's doing**: it appears across fixtures (`report --by fixture`), not in
  one repo

Confirm the pick with the reviewer.

## 2. Trace it to the skill source

Plans are written by `new-task-quick`, which reads shared stage and tab references.
Edit the **sources**, never `skills/`:

| The mode shows up in… | Look in `src/planning-workflow/` |
|---|---|
| Requirements tab, open questions, assumptions | `refs/stage-requirements.md`, `refs/tab-requirements.md` |
| Verification tab, acceptance-criteria checks | `refs/stage-solution.md`, `refs/tab-verification.md` |
| Solution tab, approach, file tree, `context.md` | `refs/stage-solution.md`, `refs/tab-solution.md`, `refs/template-context.md` |
| Plan tab, phases, steps | `refs/stage-plan.md`, `refs/tab-plan.md` |
| Stopping, questions, self-check | `skills/new-task-quick/SKILL.md` |

Read the plans that have the mode next to the instruction that produced them.
Write the hypothesis in one sentence: "Plans omit X because the tab reference asks
for Y and never mentions X". A change you can't tie to a hypothesis can't be judged
by the result.

## 3. Make one change and commit it

- Change **one thing**: the smallest edit that tests the hypothesis. Two changes in
  one iteration can't be told apart.
- These references are shared by `new-task`, `new-solution` and `new-plan` too.
  That is usually what you want, but say so in the iteration entry.
- `make compile`, then commit (a branch is fine). The commit sha **is** the candidate
  arm; uncommitted edits are invisible to `--skills-ref`.

Open the iteration entry now, before any results exist:

```markdown
## Iteration 3: <target mode id>
- baseline: <sha>   candidate: <sha>   batch: it3   taxonomy: v<N>
- hypothesis: <one sentence>
- change: <what was edited, where>
- expected: <target mode down>; watch for <modes the change could plausibly worsen>
```

## 4. Regenerate, both arms

Regenerate **both** the baseline and the candidate, with the same fixtures and the
same trial count (at least 2), in **one** `generate` call. The call stamps a single
batch id on every plan it produces:

```bash
make plan-review ARGS='generate --skills-ref <baseline-sha> --skills-ref <candidate-sha> --trials 2 --batch it3'
```

Record the batch id in the iteration entry. If the arms have to be generated
separately (for example, one crashed), pass the same `--batch` to both calls.

Regenerating the baseline in the same batch has two purposes:

- **Blindness.** The unreviewed plans are a mix of both versions, interleaved by
  content hash, so the reviewer can't tell which is which. A batch of candidate-only
  plans is unblinded by the fact that it is new.
- **Fairness.** Both arms are sampled at the same time, under the same model,
  harness and fixtures.

Use every fixture, not only those where the mode appeared, so that regressions
elsewhere show up. Confirm the cost first (see the generate reference).

## 5. Review the new batch

1. **Open coding** on the new plans. Run the same session as before, and don't
   mention the iteration. New notes can reveal modes the change introduced.
2. **Axial coding.** If new themes don't fit the taxonomy, add modes and bump the
   version (then re-label the older plans for those modes). Then label every new
   plan for every mode, the same way as the baseline.

## 6. Compare and decide

```bash
make plan-review ARGS='report --batch it3'
```

Compare the baseline column with the candidate column, **within the batch**.
Without `--batch`, the baseline's column also counts every earlier batch at that
sha (the report warns when more than one batch exists), which makes the
denominators unequal. Each generated plan counts once for its arm. If two trials
wrote byte-identical plans, the reviewer reads and labels that document once, and
the label counts for each of them.

- **Keep** if:
  - the target mode fell by more than noise (with 2 trials × N fixtures per arm,
    look for a drop of several plans, not one)
  - no other mode rose by as much
  - the verdict split did not get worse
- **Revert** if the target didn't move, or another mode rose to match it.
- **Unclear** (a small difference in either direction): add trials to both arms
  before deciding. Don't declare victory on noise.

Close the entry:

```markdown
- result: <mode>: baseline a/b → candidate c/d; <other notable deltas>; verdicts x → y
- decision: keep | revert | more trials | refine hypothesis
```

A kept change merges through the normal PR flow. After it merges, the candidate
becomes the next iteration's baseline.

## 7. Next iteration, and guarding against overfitting

- Next target: rerun `report`; the next most frequent and costly mode.
- **Rotate fixtures.** Every couple of iterations, add fresh fixtures, especially
  from new repos. A skill tuned against the same few plans learns those plans.
- Keep **one held-out fixture** you never read while designing changes, and look at
  its plans only when comparing. If held-out results diverge from the rest, you are
  overfitting.
- A mode that is stable and precisely defined is a candidate for an automated judge
  (a narrow pass/fail LLM prompt validated against these labels). That replaces
  labelling it by hand in later iterations; `labels.jsonl` is the judge's test set.
