---
name: playbook-refine
description: "Distils immutable observations into a small evergreen rule set in docs/reflection/rules.yaml, choosing ADD/UPDATE/MERGE/SPLIT/REMOVE/SKIP per observation. Use when 'refine rules', 'refine playbook', 'curate rules', 'distil observations', or after playbook-observe. Not for mining observations (use playbook-observe) or matching rules to a task (use playbook-search)."
---

# Playbook: Refine

A single dedicated agent reads `observations.yaml` and curates `rules.yaml`. An
observation is a point-in-time record; a rule is the deduplicated, generalized,
still-true instruction distilled from one or more observations. Refine writes
`rules.yaml` only.

{{ ref:reflection-overview.md }}

## Inputs and outputs

- Reads `docs/reflection/observations.yaml`.
- Reads `docs/reflection/rules.yaml`.
- Queries `docs/reflection/retrievals.ndjson` (via DuckDB) for supporting
  analytics — never as the source of truth for rule validity.
- Writes `docs/reflection/rules.yaml` only.

Refine is **manually triggered**. Its cursor stores the complete ID of the
newest processed observation:

```yaml
# docs/reflection/rules.yaml
cursors:
  rules:
    last_processed_observation: 20260623T123045.123456Z-0001
rules:
  - id: prefer-get-value-in-react-prop-tests
    lifecycle: confirmed          # draft | confirmed | retired
    read_when: Writing a unit test that reads React props before rendering.
    value: Read prop state with getValue(); assert on the prop API, not innerHTML.
    why: innerHTML reflects rendered DOM, not the live prop, so it lags a tick.
    sources: [20260623T123045.123456Z-0001]
    updated: "2026-06-23"
    predecessor_ids: []            # transitive retired ancestors that roll up here
    successor_ids: []              # on a retired rule: what replaced it
```

Because observation IDs are time-ordered, select every observation whose ID
sorts lexically **after** `last_processed_observation`, process oldest-first,
and advance the cursor only after a successful write. No new observations is a
no-op. At scale, fetch just the new slice with
`yq '.observations[] | select(.id > "<cursor>")'` rather than loading the whole
file, and read existing rules as `(id, read_when, lifecycle)` tuples (see
"operating at scale" above) to decide ADD vs UPDATE/MERGE.

## Deriving a rule from an observation's diagnostic chain

Each observation carries a diagnostic chain. Map it straight onto the rule
fields — do not re-derive guidance from scratch:

| Observation field | Rule field |
|---|---|
| `context` | `read_when` (the recognisable trigger) |
| `correct_approach` + `key_insight` | `value` (evergreen, self-contained action) |
| `root_cause` | `why` (the failure mode / tradeoff) |

The `key_insight` is the generalised principle; the `correct_approach` is the
concrete action. A good `value` states the action and carries the principle so
it transfers beyond the originating incident.

**Keep `value` terse — one action, not a tutorial.** Map the chain into a single
imperative sentence (two at most): the primary action, with the principle folded
in as a short clause. Do not enumerate every step, flag, or alternative the
observation happened to mention — those belong in the originating session, not an
evergreen rule. If a `value` needs a bulleted procedure or more than ~3 lines,
the observation is really several lessons (SPLIT) or one over-specific incident
(SKIP). A rule an engineer can skim in one glance beats a complete one they
won't read.

**SKIP one-off, project-bound incidents.** A diagnostic chain alone does not make
a rule worth keeping — the lesson must plausibly recur *for a reader of this
playbook*. SKIP an observation when its `read_when` is bound to a specific app,
stack, or environment that won't be seen again here (e.g. a frontend-app build
quirk in a skills/playbook repo), or when the trigger is so narrow it would
essentially never fire again. Generalise it to a portable principle if one
exists; otherwise leave it in the immutable backlog rather than padding the rule
set. Each rule costs skim time on every search — fewer, more general rules raise
the floor; niche war stories lower it.

### Worked example (ADD)

Observation:

```yaml
- id: 20260623T140210.001122Z-0007
  context: Running a Python script or Makefile target in this repo's dev environment.
  what_happened: >
    `python src/compile.py` failed with `python: command not found` (exit 127);
    `python3` succeeded.
  root_cause: Assumed a `python` shim exists; only `python3` is installed here.
  correct_approach: Invoke `python3` (or `uv run`) for every script and target.
  key_insight: Don't assume a `python` alias exists in an environment you don't control.
```

No existing rule covers it → **ADD**:

```yaml
- id: use-python3-not-python
  lifecycle: draft
  read_when: Running a Python script or Makefile target in this repo's dev environment.
  value: Use `python3` (or the repo's `make`/`uv` target), never a bare `python`.
  why: Bare `python` is not installed (exit 127); the assumption it exists fails outright.
  sources: [20260623T140210.001122Z-0007]
  updated: "2026-06-23"
  predecessor_ids: []
  successor_ids: []
```

`read_when` ← `context`, `value` ← `correct_approach` + `key_insight`, `why` ←
`root_cause`. The rule is `draft` until a second distinct session reinforces it.

## Per-observation action (pick exactly one)

- **ADD** — no existing rule covers it and the evidence threshold is met; author
  a new rule.
- **UPDATE** — it reinforces/sharpens/partially contradicts an existing rule;
  edit `value`/`why`/`read_when` and append the observation ID to `sources`.
- **MERGE** — several observations/rules describe one lesson; fold into one rule,
  widening `read_when` only enough to cover all valid triggers.
- **SPLIT** — a rule covers unrelated triggers; break into narrower rules so each
  `read_when` stays specific.
- **REMOVE** — evidence shows a rule is wrong/obsolete (e.g. the code it
  referenced is gone); retire it (do not delete) so historical retrievals stay
  interpretable.
- **SKIP** — too one-off / low-signal / project-bound to generalize (see "SKIP
  one-off, project-bound incidents" above); advance the cursor without changing a
  rule. The observation stays in the immutable backlog for later clustering.

## Evidence threshold (separates early capture from trusted guidance)

- A normal ADD requires observations from **≥2 distinct sessions** and creates a
  `draft` rule.
- A single directly-evidenced **high-severity incident or explicit user
  correction** may create a `draft`, but it stays provisional.
- A rule becomes `confirmed` only with supporting observations from **≥3 distinct
  task IDs** (retains the predecessor `task-feedback-analyser` bar).
- A normal single observation that cannot UPDATE an existing rule is SKIPped for
  rule creation but remains in the backlog.

`{{ skill:playbook-search }}` returns `confirmed` rules by default; `draft` rules
are flagged and returned only on explicit request for provisional guidance.

## Rule quality bar

- `read_when` is load-bearing: short enough that reading many doesn't bloat
  context, specific enough to judge relevance without reading the full rule.
- `value` is evergreen and self-contained — must not assume access to the
  originating session.
- `why` explains the failure mode or tradeoff.
- `sources` lists **every** observation ID supporting the rule.
- `id` is immutable and readable. Records are **never deleted** from `rules.yaml`.
- `lifecycle` is `draft`, `confirmed`, or `retired`; search ignores `retired`.
- `predecessor_ids` on an active rule lists every transitive retired ancestor
  whose retrievals should roll up to it. `successor_ids` on a retired rule names
  the active/intermediate rules that replaced it (MERGE → one successor; SPLIT →
  several).

## Decay and analytics — nominate, never auto-remove

A rarely-retrieved rule may still guard a rare but severe failure mode. Age or
low retrieval count alone is **not** evidence a rule is wrong; removal requires
semantic evidence (contradiction or obsolescence). Use analytics only to
*nominate* rules for inspection.

Expose the rule array as JSON without loading it into context, then run DuckDB
over the NDJSON log:

```bash
yq -o=json '.rules' docs/reflection/rules.yaml > /tmp/reflection-rules.json
```

Per-rule retrieval totals and recency:

```sql
SELECT rule_id, count(*) AS retrieval_count,
       count(DISTINCT task_id) AS distinct_tasks,
       max(occurred_at) AS last_retrieved
FROM read_ndjson_auto('docs/reflection/retrievals.ndjson')
WHERE event_type = 'retrieval'
GROUP BY rule_id ORDER BY retrieval_count DESC;
```

Roll historical (merged/split) IDs into their active successors via
`predecessor_ids`:

DuckDB infers `JSON[]` for `predecessor_ids` when every rule's list is still
empty, which breaks `unnest`; cast to `VARCHAR[]` and guard the unnest so the
query is robust both before and after any MERGE/SPLIT lineage exists:

```sql
WITH active_rules AS (
  SELECT id, CAST(predecessor_ids AS VARCHAR[]) AS predecessor_ids
  FROM read_json_auto('/tmp/reflection-rules.json')
  WHERE lifecycle IN ('draft','confirmed')
), aliases AS (
  SELECT id AS active_rule_id, id AS historical_rule_id FROM active_rules
  UNION ALL
  SELECT id, unnest(predecessor_ids) FROM active_rules WHERE length(predecessor_ids) > 0
), retrievals AS (
  SELECT * FROM read_ndjson_auto('docs/reflection/retrievals.ndjson')
  WHERE event_type = 'retrieval'
)
SELECT coalesce(aliases.active_rule_id, retrievals.rule_id) AS active_rule_id,
       count(*) AS retrieval_count, max(retrievals.occurred_at) AS last_retrieved
FROM retrievals LEFT JOIN aliases
  ON aliases.historical_rule_id = retrievals.rule_id
GROUP BY 1 ORDER BY retrieval_count DESC;
```

DuckDB is an analytics layer, not the semantic matcher.

## Rules

- Write `rules.yaml` only. Never touch `observations.yaml` or `retrievals.ndjson`.
- One action per observation; advance the cursor only after a successful write.
- Never delete a rule record — retire it with `successor_ids` set.
- Confirmed needs ≥3 distinct task IDs; draft needs ≥2 distinct sessions (or one
  high-severity incident / user correction).
