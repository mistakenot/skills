# Axial coding — from notes to named failure modes, then labels

Open coding produced free-text notes. Axial coding groups them into a small set of
**failure modes** (`data/taxonomy.json`). Then it records, for every reviewed plan,
whether each mode is present (`data/labels.jsonl`). The labels turn "the plans feel
better" into "mode X: 4/6 plans before, 1/6 after".

**The reviewer decides; you draft.** You propose groupings and labels, and they
confirm, rename, merge, split or override them. A taxonomy the agent wrote alone is
the agent's opinion of the plans, not the reviewer's.

## 1. Draft the taxonomy

1. Read every note and verdict (`notes.fold()`, or `data/notes.jsonl` directly) and
   `data/open-coding-log.jsonl`.
2. Cluster the notes by the *problem they describe*, not by which tab they're on.
   Aim for **4–8 modes**. Fewer merges distinct problems; more means you are
   restating the notes.
3. For each proposed mode, show the reviewer:
   - a kebab-case id
   - a name
   - a one-sentence definition
   - **include / exclude** rules for the borderline cases the notes actually contain
   - the note ids and quotes it covers

   List notes that fit nowhere separately, so they aren't forced into a mode.
4. Iterate in chat until the reviewer is happy, then write:

```json
{
  "version": 1,
  "modes": [
    {
      "id": "untestable-acceptance-criteria",
      "name": "Untestable acceptance criteria",
      "definition": "An acceptance criterion has no concrete check that would fail if it were unmet.",
      "include": "ACs verified only by 'manual review' or restating the requirement.",
      "exclude": "A check exists but is weak; that is thin-verification."
    }
  ]
}
```

A good mode is **binary and observable**: two people reading the same plan would
agree whether it is present. "Plan quality is low" is not a mode;
"no rollback step for a data migration" is.

## 2. Label every reviewed plan

For each plan with a verdict, and each mode:

1. Propose present/absent from that plan's notes, plus your own reading of the plan
   where the notes are silent. Show the reviewer one table per plan (mode, proposed
   value, evidence note ids, one-line reason). Batch it; don't ask per cell.
2. They accept or override. Then record each cell:

```bash
make plan-review ARGS='label <plan_id> <mode> present --evidence <note_id> --reason "..."'
make plan-review ARGS='label <plan_id> <mode> absent --reason "..."'
```

- Label **every** mode for every reviewed plan. `report` counts a plan toward a mode
  only once it has a label for it: unlabelled is not "absent".
- Never write `labels.jsonl` by hand; `label` validates the plan, mode and version.
- A later label for the same plan and mode wins; history is kept.

## 3. Changing the taxonomy

Bump `version` whenever you add a mode, remove one, or change a definition or its
include/exclude rules. Labels carry the version they were made under, and `report`
counts only the current version. So after a bump, **re-label all reviewed plans**
for any mode that is new or whose definition changed. You can re-record unchanged
modes under the new version as they stand.

Expect a bump in most iterations: new plans surface new modes (see the open-coding
reference, "Later rounds").

## 4. Read the report

```bash
make plan-review ARGS='report'              # per skills version
make plan-review ARGS='report --by fixture' # is a mode one repo's quirk?
```

Each mode cell is `plans with it / plans labelled for it`. The report **unblinds**,
so run it only after labelling is finished.

Before choosing what to fix, check `--by fixture`. A mode that appears in only one
fixture is more likely about that repo than the skill.
