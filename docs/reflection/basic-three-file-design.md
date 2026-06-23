---
hash: "3d381f6b"
id: "bee52e64"
read_when: "designing or implementing the reflection playbook's observe, refine, or search stages"
summary: "Three-stage design for mining task observations, refining evergreen rules, and analyzing append-only rule-retrieval telemetry."
title: "Basic Three-File Reflection Playbook Design"
---

# Basic three-file reflection playbook design

We still do not gather structured reflection from previous runs to inform future
tasks. This design introduces a deliberately small system for doing that. It is
inspired by <https://arxiv.org/abs/2510.04618>.

<!-- RESOLVED(P1): No relationship to existing learning/reflection stores
REVIEW: This repo already maintains two overlapping reflection pipelines with different schemas and quality bars: `learning-diary` → `docs/learnings.yaml` (git/PR/session mining, user-baseline filter) and `task-feedback-analyser` → `docs/rules.md` (3+ independent task examples, verbatim evidence). The `reflection` install module currently ships only `learning-diary` (`src/compile.py`). Separately, auto-stack already implements an observe → consolidate → retrieve loop via `auto reflect` (event-sourced JSONL under `.auto/reflect/`, Phase 1 complete per `auto-stack/docs/epics/001-reflect-playbook-loop.md`). This design introduces a third repo-local store (`docs/playbooks/*.yaml` + `retrievals.ndjson`) without stating whether it supersedes, feeds, or runs alongside those systems. Before implementation, the doc needs an explicit positioning section: migration path, deprecation plan, or deliberate multi-store boundaries.
AUTHOR: Added an explicit positioning and migration section defining the boundaries with `learning-diary`, the replacement path for `task-feedback-analyser`, the non-canonical role of `auto reflect`, and reflection-module installation.
-->

## Positioning and migration

This playbook owns reusable, task-facing instructions. It does not create a
third general-purpose learning diary:

- `learning-diary` and `docs/learnings.yaml` remain the home for novel
  techniques and personal learning. They continue mining git history, PRs, and
  sessions, and do not feed this rule set automatically.
- `task-feedback-analyser` and its proposed `docs/rules.md` are the predecessor
  of this workflow-rule system. The first Observe backfill consumes the same
  task feedback as migration input. Once Observe, Refine, and the workflow
  Search hooks reach parity, retire `task-feedback-analyser`; do not dual-write
  `docs/rules.md` and this playbook.
- `auto reflect` implements a similar event-sourced loop under `.auto/reflect/`.
  Its miner and stats may help discover candidates, but its events and folded
  snapshot are not canonical inputs to this design. This design deliberately
  keeps small, reviewable, repository-versioned artifacts under `docs/`.
  Adopting `auto reflect` as the storage backend later requires an explicit
  migration; do not silently mirror events between both stores.
- When implemented, the three playbook skills join `learning-diary` in the
  `reflection` install module. Sharing a module does not imply sharing schemas
  or lifecycle.

The first version intentionally mines only task session transcripts and
`feedback.md`. Git/PR mining remains the responsibility of `learning-diary`.
This narrower scope avoids duplicate mining while keeping task-specific process
evidence close to the rules that consume it.

The system has three stages and three source-of-truth files:

```text
docs/reflection/
├── observations.yaml  # immutable lessons mined from completed work
├── rules.yaml         # curated, evergreen guidance
└── retrievals.ndjson  # append-only rule-search telemetry
```

<!-- RESOLVED(P2): Filename says "two-file" but design defines three files
REVIEW: The document path is `basic-two-file-design.md`, but the architecture explicitly names three source-of-truth files (`observations.yaml`, `rules.yaml`, `retrievals.ndjson`). Either rename the file to match (e.g. `basic-three-file-design.md`) or explain which file is intentionally excluded from the "basic" scope (e.g. if `retrievals.ndjson` is deferred telemetry).
AUTHOR: Renamed the document to `basic-three-file-design.md` and updated its title.
-->

<!-- RESOLVED(P2): `docs/playbooks/` path collides with assurance-strategist convention
REVIEW: `docs/assurance-strategist-research-diary.md` already documents `docs/playbooks/*.md` as the home for agent-run semantic E2E playbooks. Reusing `docs/playbooks/` for YAML reflection stores (`observations.yaml`, `rules.yaml`) will mix unrelated artifact types in one directory. Consider a distinct path (e.g. `docs/reflection/` or `docs/playbook-rules/`) or an explicit subdirectory split (`docs/playbooks/reflection/` vs `docs/playbooks/e2e/`).
AUTHOR: Moved all three reflection stores to `docs/reflection/`, leaving `docs/playbooks/` available for semantic E2E playbooks.
-->

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
UTC timestamp with microseconds plus a monotonic per-process counter, for example
`20260623T123045.123456Z-0001`. A date or second-resolution timestamp plus a
random suffix is insufficient because a later observation could sort before an
earlier one.

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

<!-- RESOLVED(P2): Observe candidate discovery is unspecified
REVIEW: The ingestion ledger records which sessions and feedback files are already processed, but Observe never describes how to enumerate *candidates*. An implementer needs a concrete procedure — e.g. `auto search session list --cwd <repo> --since <window>` filtered against `cursors.sessions.processed`, plus a glob over `docs/tasks/*/feedback.md` compared to `cursors.feedback` keys. Without this, idempotency is defined but the scan boundary is not.
AUTHOR: Added a deterministic candidate-discovery procedure with a scan watermark, overlap window, pagination, processed-session filtering, and feedback content-hash comparison.
-->

<!-- RESOLVED(P2): Git/PR mining is out of scope but not stated
REVIEW: The shipped `learning-diary` skill mines git history and merged PRs as first-class sources (Steps 1–3), not just session transcripts and `feedback.md`. If Observe intentionally narrows to those two inputs, say so explicitly under scope/out-of-scope so implementers do not silently drop a proven source or duplicate `learning-diary` with a smaller surface.
AUTHOR: The positioning section now states that Git/PR mining stays with `learning-diary`; this playbook intentionally limits Observe to task transcripts and feedback.
-->

### Candidate discovery

At the beginning of a run, capture `scan_started_at`. On the first run, paginate
through every session returned by:

```bash
auto search session list --cwd <repo-root> --limit 50 --offset <offset>
```

On later runs, add `--after <previous-scan-start-minus-24-hours>`. The overlap
allows late ETL arrivals to reappear safely. Continue increasing `--offset`
until a page is empty, then discard IDs already present in
`cursors.sessions.processed`. Process parent and sub-agent sessions oldest-first.

Separately, enumerate `docs/tasks/*/feedback.md` in lexical order, hash every
file, and select files whose path is absent from `cursors.feedback` or whose
hash changed. Advance `last_scan_started_at` to this run's `scan_started_at`
only after every selected session and feedback file has been processed.

### Ingestion ledger

Do not use a single `lastProcessed` task name or timestamp as the observe cursor.
A task can have multiple parent and sub-agent sessions, feedback can be edited,
and follow-up work can arrive after newer tasks. Instead, `observations.yaml`
keeps a per-source ingestion ledger:

```yaml
# docs/reflection/observations.yaml
cursors:
  sessions:
    last_scan_started_at: "2026-06-23T12:30:45Z"
    processed:
      - 6c71f534-8a37-4157-9ae2-cabe1ab541c9
  feedback:
    docs/tasks/004-ac-progressive-disclosure/feedback.md:
      content_sha256: 41b3d8...
      processed_at: "2026-06-23T12:30:45Z"

observations:
  - id: 20260623T123045.123456Z-0001
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

- Reads `docs/reflection/observations.yaml`.
- Reads `docs/reflection/rules.yaml`.
- Queries `docs/reflection/retrievals.ndjson` for supporting analytics.
- Writes `docs/reflection/rules.yaml` only.

Refine is manual initially. Its cursor stores the complete ID of the newest
processed observation. Because observation IDs are time ordered, refine selects
every observation whose ID sorts lexically after that value, processes them
oldest-first, and advances the cursor only after a successful write. Re-running
with no new observations is a no-op.

For each new observation, refine picks exactly one action:

- **ADD** — no existing rule covers the guidance and the evidence threshold
  below is met, so author a new rule.
- **UPDATE** — the observation reinforces, sharpens, or partially contradicts
  an existing rule; update its `value`, `why`, or `read_when` and append the
  observation ID to `sources`.
- **MERGE** — several observations or rules describe the same lesson; fold them
  into one rule and widen `read_when` only enough to cover all valid triggers.
- **SPLIT** — a rule covers unrelated triggers; break it into narrower rules so
  each `read_when` remains specific.
- **REMOVE** — evidence shows a rule is wrong or obsolete, for example because
  the code it referenced no longer exists; retain it as a retired record so
  historical retrievals remain interpretable.
- **SKIP** — the observation is too one-off or low-signal to generalize; advance
  the cursor without changing a rule.

<!-- RESOLVED(P1): No evidence threshold for ADD contradicts existing rule-extraction policy
REVIEW: ADD can create a new rule from a single observation with no recurrence requirement. Elsewhere this repo enforces stricter bars: `task-feedback-analyser` requires 3+ independent task examples before drafting a rule (`src/planning-workflow/skills/task-feedback-analyser/SKILL.md`), and auto-stack's reflect loop requires ≥2 distinct sessions before consolidation promotes to a rule (`auto-stack/docs/epics/001-reflect-playbook-loop.md`). The design should state the minimum evidence for ADD (e.g. 1 vs 2 vs 3 sessions/tasks) and how SKIP vs ADD is decided, or explicitly justify why a lower bar is safe here.
AUTHOR: Added explicit draft and confirmed thresholds. Normal rules require two independent sessions to become drafts and three independent tasks to become confirmed; a high-severity incident can create only a provisional draft from one observation.
-->

### Evidence threshold

Refine separates early capture from trusted guidance:

- A normal ADD requires observations from at least two distinct sessions and
  creates a `draft` rule.
- A single directly evidenced, high-severity incident or explicit user
  correction may create a `draft`, but the rule remains provisional.
- A rule becomes `confirmed` only with supporting observations from at least
  three distinct task IDs. This retains the predecessor
  `task-feedback-analyser` quality bar.
- A normal single observation that cannot UPDATE an existing rule is SKIPped for
  rule creation but remains in the immutable observation backlog for later
  clustering.

Search returns confirmed rules by default. Draft rules are clearly flagged and
are returned only when the caller explicitly requests provisional guidance.

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
- `id` is immutable and readable. Records are never deleted from `rules.yaml`.
- `lifecycle` is `draft`, `confirmed`, or `retired`; Search ignores retired
  rules.
- `predecessor_ids` on an active rule contains every transitive retired ancestor
  whose retrievals should roll up to it.
- `successor_ids` on a retired rule names the active or intermediate rules that
  replaced it. MERGE produces one successor; SPLIT may produce several.

<!-- RESOLVED(P2): MERGE/SPLIT lineage schema is underspecified for retrieval analytics
REVIEW: `previous_ids` is shown as an empty array in the example, and the quality bar says refine must "retain enough lineage" after MERGE/SPLIT, but there is no normative schema for mapping retired IDs to successors. Retrieval events log `rule_id` at return time; after a MERGE, historical counts for the old ID will stall unless analytics join through `previous_ids` (or a dedicated `supersedes`/`merged_into` field). Specify the required fields and the DuckDB join pattern so refine does not break the per-rule retrieval queries in this doc.
AUTHOR: Defined immutable rule records with lifecycle, transitive `predecessor_ids`, and `successor_ids`, and added a DuckDB alias join that rolls historical retrievals into active rules.
-->

Example:

```yaml
# docs/reflection/rules.yaml
cursors:
  rules:
    last_processed_observation: 20260623T123045.123456Z-0001

rules:
  - id: prefer-get-value-in-react-prop-tests
    lifecycle: confirmed
    read_when: Writing a unit test that reads React props before rendering.
    value: Prefer using X...
    why: Using another method can cause...
    sources:
      - 20260623T123045.123456Z-0001
    updated: "2026-06-23"
    predecessor_ids: []
    successor_ids: []
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

<!-- RESOLVED(P2): Workflow integration points are missing
REVIEW: Search is described as running "at the start of a task" with a `phase` field (`requirements`, `solution`, `planning`, `execution`, `review`), but the doc does not name which existing skills invoke it. The portable workflow already ends tasks with `feedback.md` (`complete-task`) and extracts rules separately (`task-feedback-analyser`). Specify the hook points — e.g. `/new-task`, `/new-solution`, `/execute-task` — and whether search replaces reading `docs/rules.md` or complements it.
AUTHOR: Added normative workflow hook points and clarified that this playbook replaces, rather than complements, the predecessor `docs/rules.md` pipeline after migration.
-->

### Workflow hooks

The planning workflow invokes Search at these boundaries:

| Caller | Phase | Intent sent to Search |
|---|---|---|
| `new-task` | `requirements` | user request plus repository context |
| `new-solution` | `solution` | approved requirements plus discovered constraints |
| `new-plan` | `planning` | approved solution and proposed file/phase structure |
| `execute-task` | `execution` | task plan initially, then each phase objective before dispatch |
| `review-task` and `code-review` | `review` | review target, acceptance criteria, and changed surface |

`complete-task` continues producing `feedback.md`; a later Observe run mines it.
During migration, existing `docs/rules.md` guidance may be imported as sourced
observations, but callers must not query both rule stores. Once these hooks are
enabled, Search replaces direct reads of `docs/rules.md` and
`task-feedback-analyser` is retired.

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
`docs/reflection/retrievals.ndjson`. Candidate rules examined during sharding are
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

<!-- RESOLVED(P3): Concurrent append safety not addressed
REVIEW: Search is the sole writer of `retrievals.ndjson`, but multiple parent sessions (or sharded sub-agents finishing together) could append concurrently. NDJSON tolerates torn writes only if each line is atomically flushed. Consider specifying single-writer coordination (file lock, append-via-CLI) or documenting that search runs through one coordinator process per `search_id`.
AUTHOR: Required sharded matchers to return candidates without writing and required the Search coordinator to serialize complete-line appends under an advisory file lock.
-->

Sharded matchers never write telemetry. The single Search coordinator for a
`search_id` collects their results, builds all complete NDJSON lines, acquires an
advisory lock for `retrievals.ndjson`, appends each line with one write, flushes,
and releases the lock. Concurrent parent sessions use the same lock. The
implementation should expose this as one append helper rather than open-coding
shell redirection in each skill.

Example events:

```json
{"event_id":"20260623T123045.123456Z-0001","event_type":"retrieval","occurred_at":"2026-06-23T12:30:45.123456Z","search_id":"20260623T123044.990000Z-0001","rule_id":"prefer-get-value-in-react-prop-tests","rule_updated":"2026-06-01","task_id":"004-ac-progressive-disclosure","session_id":"abc123","phase":"planning"}
{"event_id":"20260623T123045.123457Z-0002","event_type":"retrieval","occurred_at":"2026-06-23T12:30:45.123457Z","search_id":"20260623T123044.990000Z-0001","rule_id":"run-browser-regression-suite","rule_updated":"2026-05-18","task_id":"004-ac-progressive-disclosure","session_id":"abc123","phase":"planning"}
{"event_id":"20260623T131102.441020Z-0001","event_type":"no_match","occurred_at":"2026-06-23T13:11:02.441020Z","search_id":"20260623T131101.880000Z-0001","rule_id":null,"rule_updated":null,"task_id":"005-unrelated-task","session_id":"def456","phase":"execution"}
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
FROM read_ndjson_auto('docs/reflection/retrievals.ndjson')
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
    FROM read_ndjson_auto('docs/reflection/retrievals.ndjson')
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
FROM read_ndjson_auto('docs/reflection/retrievals.ndjson')
WHERE event_type = 'retrieval'
GROUP BY rule_id, rule_updated
ORDER BY rule_id, rule_updated;
```

To roll historical IDs into active successors, first expose the YAML rule array
as JSON without loading it into agent context:

```bash
yq -o=json '.rules' docs/reflection/rules.yaml > /tmp/reflection-rules.json
```

Because each active rule carries all transitive `predecessor_ids`, DuckDB can
build a direct alias map:

```sql
WITH active_rules AS (
    SELECT *
    FROM read_json_auto('/tmp/reflection-rules.json')
    WHERE lifecycle IN ('draft', 'confirmed')
), aliases AS (
    SELECT id AS active_rule_id, id AS historical_rule_id
    FROM active_rules
    UNION ALL
    SELECT id AS active_rule_id, unnest(predecessor_ids) AS historical_rule_id
    FROM active_rules
), retrievals AS (
    SELECT *
    FROM read_ndjson_auto('docs/reflection/retrievals.ndjson')
    WHERE event_type = 'retrieval'
)
SELECT
    coalesce(aliases.active_rule_id, retrievals.rule_id) AS active_rule_id,
    count(*) AS retrieval_count,
    max(retrievals.occurred_at) AS last_retrieved
FROM retrievals
LEFT JOIN aliases
    ON aliases.historical_rule_id = retrievals.rule_id
GROUP BY coalesce(aliases.active_rule_id, retrievals.rule_id)
ORDER BY retrieval_count DESC;
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
