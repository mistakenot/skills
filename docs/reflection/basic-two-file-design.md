---
hash: "b4ac6b83"
read_when: "designing or implementing the reflection playbook's observe, refine, or search stages"
summary: "Three-stage design for mining task observations, refining evergreen rules, and analyzing append-only rule-retrieval telemetry."
title: "Basic Reflection Playbook Design"
---

# Basic reflection playbook design

We still do not gather structured reflection from previous runs to inform future
tasks. This design introduces a deliberately small system for doing that. It is
inspired by <https://arxiv.org/abs/2510.04618>.

The system has three stages and three source-of-truth files:

```text
docs/playbooks/
├── observations.yaml  # immutable lessons mined from completed work
├── rules.yaml         # curated, evergreen guidance
└── retrievals.ndjson  # append-only rule-search telemetry
```

- `/playbook:observe` mines previous task runs for new observations.
- `/playbook:refine` turns noisy observations into a small evergreen rule set.
- `/playbook:search` retrieves rules relevant to the current task and records
  what it returned.

The files have deliberately different semantics:

- An **observation** is evidence from a particular task or session that may
  justify changing guidance.
- A **rule** is the current, deduplicated guidance distilled from observations.
- A **retrieval** is an operational event showing that search returned a rule.
  Retrieval proves selection, not that the caller applied the rule or that it
  helped.

## Observe (`/playbook:observe`)

A dedicated team of agents reviews previous task runs and records observations.
An observation is an ID-keyed instance of:

- `description`: a short sentence or two stating what was learned.
- `context`: the additional background needed to understand when it applies.
- `git_commit`: the repository commit checked out when it was observed.
- `files`: optional relevant repository paths.
- `session_ids`: the Claude/Codex sessions providing the raw process evidence.
- `task_id`: the task folder or other stable task identifier, when available.
- `sources`: the concrete transcript messages and feedback artifacts supporting
  the observation.

Observation IDs must be immutable and lexically time ordered. Use an ISO-like
UTC timestamp plus random suffix, for example
`20260623T123045Z-280bbc`. A date plus random suffix is insufficient because a
later observation created on the same day could sort before an earlier one.

### Sources of truth

Observe always uses both of the following when a task has them:

1. Session transcripts through `auto search`.
2. The task's `docs/tasks/*/feedback.md`.

Run `auto search index` before querying. If expected sessions are absent, run
`auto etl run` and rebuild the index. Scope session discovery to this repository
and the relevant task/time window, then inspect selected sessions with
`auto search session get <session-id>`.

The two inputs are complementary, not independent corroboration. Transcripts
contain raw process evidence, dead ends, failures, corrections, and sub-agent
work. `feedback.md` contains a curated retrospective. Evidence from both that
came from the same task still counts as one task-level instance when judging
whether a lesson recurs.

### Ingestion ledger

Do not use a single `lastProcessed` task name or timestamp as the observe cursor.
A task can have multiple parent and sub-agent sessions, feedback can be edited,
and follow-up work can arrive after newer tasks. Instead, `observations.yaml`
keeps a per-source ingestion ledger:

```yaml
# docs/playbooks/observations.yaml
cursors:
  sessions:
    processed:
      - 6c71f534-8a37-4157-9ae2-cabe1ab541c9
  feedback:
    docs/tasks/004-ac-progressive-disclosure/feedback.md:
      content_sha256: 41b3d8...
      processed_at: "2026-06-23T12:30:45Z"

observations:
  - id: 20260623T123045Z-280bbc
    description: >
      Prefer using JSDOM getValue() to read values instead of...
    context: >
      Writing a unit test that needs to read React prop state...
    git_commit: 23e7a7b...
    files:
      - src/components/example.test.tsx
    session_ids:
      - 6c71f534-8a37-4157-9ae2-cabe1ab541c9
    task_id: 004-ac-progressive-disclosure
    sources:
      - kind: session_message
        ref: 6c71f534-8a37-4157-9ae2-cabe1ab541c9-98
      - kind: feedback
        ref: docs/tasks/004-ac-progressive-disclosure/feedback.md
```

A session ID is processed once. A feedback file is processed again only when
its content hash changes. Observation records are immutable after insertion;
only the ingestion ledger is mutable during observe.

Observe writes `observations.yaml` only. It does not update rules or derive
retrieval counters.

## Refine (`/playbook:refine`)

A single dedicated agent reads `observations.yaml` and curates `rules.yaml`. An
observation is a point-in-time record of something that happened; a rule is the
deduplicated, generalized, still-true instruction distilled from one or more
observations.

Inputs and outputs:

- Reads `docs/playbooks/observations.yaml`.
- Reads `docs/playbooks/rules.yaml`.
- Queries `docs/playbooks/retrievals.ndjson` for supporting analytics.
- Writes `docs/playbooks/rules.yaml` only.

Refine is manual initially. Its cursor stores the complete ID of the newest
processed observation. Because observation IDs are time ordered, refine selects
every observation whose ID sorts lexically after that value, processes them
oldest-first, and advances the cursor only after a successful write. Re-running
with no new observations is a no-op.

For each new observation, refine picks exactly one action:

- **ADD** — no existing rule covers the guidance, so author a new rule.
- **UPDATE** — the observation reinforces, sharpens, or partially contradicts
  an existing rule; update its `value`, `why`, or `read_when` and append the
  observation ID to `sources`.
- **MERGE** — several observations or rules describe the same lesson; fold them
  into one rule and widen `read_when` only enough to cover all valid triggers.
- **SPLIT** — a rule covers unrelated triggers; break it into narrower rules so
  each `read_when` remains specific.
- **REMOVE** — evidence shows a rule is wrong or obsolete, for example because
  the code it referenced no longer exists.
- **SKIP** — the observation is too one-off or low-signal to generalize; advance
  the cursor without changing a rule.

When the rule set becomes large, the agent can use `auto doc search`, `yq`, and
DuckDB queries to find neighboring rules, decide between ADD/UPDATE/MERGE, and
check for overlapping `read_when` triggers.

### Rule quality bar

- `read_when` is the load-bearing field: short enough that reading many of them
  does not bloat context, but specific enough to judge relevance without reading
  the full rule.
- `value` is evergreen and self-contained. It must not assume access to the
  originating session.
- `why` explains the failure mode or tradeoff behind the instruction.
- `sources` contains every observation ID supporting the rule, preserving the
  evidence trail required for later UPDATE, MERGE, SPLIT, or REMOVE decisions.
- `id` is stable and readable. When rules are merged or split, refine must retain
  enough lineage to interpret historical retrieval events that reference old
  IDs.

Example:

```yaml
# docs/playbooks/rules.yaml
cursors:
  rules:
    last_processed_observation: 20260623T123045Z-280bbc

rules:
  - id: prefer-get-value-in-react-prop-tests
    read_when: Writing a unit test that reads React props before rendering.
    value: Prefer using X...
    why: Using another method can cause...
    sources:
      - 20260623T123045Z-280bbc
    updated: "2026-06-23"
    previous_ids: []
```

### Rule decay and retrieval analytics

Refine uses retrieval analytics to nominate rules for inspection, not to remove
them automatically. A rarely retrieved rule may still protect a rare but severe
failure mode. Age or low retrieval count alone is not evidence that a rule is
wrong.

Useful signals include:

- rules frequently retrieved across distinct tasks;
- rules not retrieved over a long period, which may have an ineffective
  `read_when` or simply be intentionally niche;
- old rule revisions still being retrieved;
- rules contradicted by later observations;
- rules whose referenced files or APIs no longer exist.

Removal requires semantic evidence such as contradiction or obsolescence.
Retrieval data is supporting telemetry, not the source of truth for validity.

## Search (`/playbook:search`)

A planning or executing agent delegates to a search sub-agent at the start of a
task. The sub-agent returns only rules relevant to the current task so the
parent's context is never polluted by the full rule set.

Search proceeds in three steps:

1. Read only lightweight `(id, read_when, updated)` tuples. If `rules.yaml` is
   large, shard those tuples across sub-agents so no single matcher needs the
   full file.
2. Match `read_when` against the current task and return candidate IDs to the
   search coordinator.
3. Read `value` and `why` only for the selected IDs and return a compact list of
   `(id, value, why)` to the parent.

If nothing matches, return an explicit empty result so the parent can distinguish
"no relevant guidance" from search failure.

After final selection, search appends telemetry to
`docs/playbooks/retrievals.ndjson`. Candidate rules examined during sharding are
not retrievals. A `retrieval` event is written once for each rule actually
returned to the parent. A `no_match` event records searches returning no rules,
providing the denominator needed to measure search coverage.

Search is the only writer of `retrievals.ndjson`. It never edits
`observations.yaml` or `rules.yaml`.

## Retrieval event log

`retrievals.ndjson` is a single append-only newline-delimited JSON file. NDJSON
is used instead of a YAML sequence because each event is independently
appendable and DuckDB can query it directly. The file remains the source of
truth; any DuckDB database built from it is a disposable, ignored cache.

Example events:

```json
{"event_id":"20260623T123045Z-a31f","event_type":"retrieval","occurred_at":"2026-06-23T12:30:45Z","search_id":"20260623T123044Z-872c","rule_id":"prefer-get-value-in-react-prop-tests","rule_updated":"2026-06-01","task_id":"004-ac-progressive-disclosure","session_id":"abc123","phase":"planning"}
{"event_id":"20260623T123046Z-b83d","event_type":"retrieval","occurred_at":"2026-06-23T12:30:46Z","search_id":"20260623T123044Z-872c","rule_id":"run-browser-regression-suite","rule_updated":"2026-05-18","task_id":"004-ac-progressive-disclosure","session_id":"abc123","phase":"planning"}
{"event_id":"20260623T131102Z-d912","event_type":"no_match","occurred_at":"2026-06-23T13:11:02Z","search_id":"20260623T131101Z-f19a","rule_id":null,"rule_updated":null,"task_id":"005-unrelated-task","session_id":"def456","phase":"execution"}
```

Fields:

- `event_id`: immutable, time-ordered event identifier.
- `event_type`: `retrieval` or `no_match`.
- `occurred_at`: UTC timestamp.
- `search_id`: groups every event produced by one search invocation.
- `rule_id`: stable rule ID, or `null` for `no_match`.
- `rule_updated`: revision date of the rule content that was returned.
- `task_id`: stable task identifier when available.
- `session_id`: the parent session that requested the search.
- `phase`: task stage such as `requirements`, `solution`, `planning`,
  `execution`, or `review`.

Use `retrieval`, `retrieval_count`, and `last_retrieved` terminology. The log
does not claim a rule was applied or helpful. If those states later become
reliably observable, add separate event types rather than redefining retrieval.

### DuckDB analytics

DuckDB's JSON reader handles NDJSON directly, allowing agents to compute compact
analytics without loading the event log into model context.

Per-rule retrieval totals and recency:

```sql
SELECT
    rule_id,
    count(*) AS retrieval_count,
    count(DISTINCT task_id) AS distinct_tasks,
    max(occurred_at) AS last_retrieved
FROM read_ndjson_auto('docs/playbooks/retrievals.ndjson')
WHERE event_type = 'retrieval'
GROUP BY rule_id
ORDER BY retrieval_count DESC;
```

Overall search coverage:

```sql
WITH searches AS (
    SELECT
        search_id,
        max(CASE WHEN event_type = 'retrieval' THEN 1 ELSE 0 END) AS matched
    FROM read_ndjson_auto('docs/playbooks/retrievals.ndjson')
    GROUP BY search_id
)
SELECT
    count(*) AS searches,
    sum(matched) AS searches_with_matches,
    count(*) - sum(matched) AS searches_without_matches
FROM searches;
```

Retrievals by rule revision:

```sql
SELECT
    rule_id,
    rule_updated,
    count(*) AS retrieval_count,
    max(occurred_at) AS last_retrieved
FROM read_ndjson_auto('docs/playbooks/retrievals.ndjson')
WHERE event_type = 'retrieval'
GROUP BY rule_id, rule_updated
ORDER BY rule_id, rule_updated;
```

These queries produce small result sets for refine and later reporting. DuckDB
is an analytics layer, not the semantic rule matcher: relevance still depends on
the search agents understanding the current task and each rule's `read_when`.

## Operational summary

| Stage | Reads | Writes |
|---|---|---|
| Observe | `auto search` transcripts, task `feedback.md`, `observations.yaml` | `observations.yaml` |
| Refine | `observations.yaml`, `rules.yaml`, DuckDB analytics over `retrievals.ndjson` | `rules.yaml` |
| Search | `rules.yaml` | append-only `retrievals.ndjson` |

Refine is manually triggered for the initial version. Observe and refine are
idempotent through their ingestion ledgers and cursors; retrieval logging is
append-only and each event has a unique ID.
