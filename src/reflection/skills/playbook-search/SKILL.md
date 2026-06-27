---
name: playbook-search
description: "Retrieves task-relevant rules from docs/reflection/rules.yaml via a search sub-agent and logs each return to retrievals.ndjson. Use when 'search rules', 'playbook search', 'relevant rules for this task', or at the start of a planning/execution phase. Not for distilling rules (use playbook-refine) or mining observations (use playbook-observe)."
---

# Playbook: Search

A planning or executing agent delegates to a search **sub-agent** at the start of
a task or phase. The sub-agent returns only rules relevant to the current task,
so the parent's context is never polluted by the full rule set. Search appends to
`retrievals.ndjson` and reads `rules.yaml`; it never edits the other two files.

{{ ref:reflection-overview.md }}

## Workflow hooks

The planning workflow invokes Search at these boundaries. After migration, Search
**replaces** direct reads of `docs/rules.md` (the `task-feedback-analyser`
pipeline) — callers must not query both rule stores.

| Caller | Phase | Intent sent to Search |
|---|---|---|
| `{{ skill:new-task }}` | `requirements` | user request plus repository context |
| `{{ skill:new-solution }}` | `solution` | approved requirements plus discovered constraints |
| `{{ skill:new-plan }}` | `planning` | approved solution and proposed file/phase structure |
| `{{ skill:execute-task }}` | `execution` | task plan, then each phase objective before dispatch |
| `{{ skill:review-task }}` / `{{ skill:code-review }}` | `review` | review target, acceptance criteria, changed surface |

`{{ skill:complete-task }}` keeps producing `feedback.md`; a later
`{{ skill:playbook-observe }}` run mines it.

## Procedure (three steps, no context bloat)

Capture a `search_id` for this invocation:

```bash
python3 "$CLAUDE_SKILL_DIR/scripts/reflect.py" gen-id   # -> search_id
```

1. **Read lightweight tuples only.** From `rules.yaml`, read just
   `(id, read_when, updated, lifecycle)` for each rule — never the full bodies
   (these tuples are ~20× smaller; see "operating at scale" above):
   `yq -r '.rules[] | [.id, .read_when, .updated, .lifecycle] | @tsv' docs/reflection/rules.yaml`
   If the file is large, shard those tuples across matcher sub-agents so no single
   matcher needs the whole file. Skip `retired` rules; skip `draft` rules unless
   the caller explicitly asked for provisional guidance.
2. **Match `read_when` against the current task.** Each matcher returns candidate
   rule IDs to the coordinator. Candidate rules examined during sharding are
   **not** retrievals.
3. **Fetch selected rules.** Read `value` and `why` only for the finally selected
   IDs and return a compact `(id, value, why)` list to the parent:
   `yq '.rules[] | select(.id == "<id>") | {"id": .id, "value": .value, "why": .why}' docs/reflection/rules.yaml`
   Use explicit `"key": .field` pairs. The bare-shorthand `{value, why}` is jq
   syntax and **fails** on mikefarah yq (`lexer: invalid input text`); the comma
   form `.value, .why` is also wrong — `,` is a top-level union, so `.why`
   evaluates against the document root and silently returns `null`.

If nothing matches, return an **explicit empty result** so the parent can
distinguish "no relevant guidance" from search failure.

## Telemetry — single serialized writer

Sharded matchers **never** write telemetry. The single coordinator for a
`search_id` collects results, builds all complete events, and appends them in one
locked call via the shared helper (advisory `flock`, complete lines, fsync):

- Write one `retrieval` event per rule **actually returned** to the parent.
- Write one `no_match` event when the search returned no rules — this is the
  denominator for measuring search coverage.

```bash
# Build events (one JSON object per line) and append atomically. event_id and
# occurred_at are stamped by the helper if omitted.
cat <<'NDJSON' | python3 "$CLAUDE_SKILL_DIR/scripts/reflect.py" \
    append --file docs/reflection/retrievals.ndjson
{"event_type":"retrieval","search_id":"<search_id>","rule_id":"prefer-get-value-in-react-prop-tests","rule_updated":"2026-06-01","task_id":"004-ac-progressive-disclosure","session_id":"abc123","phase":"planning"}
NDJSON
```

A `no_match` event sets `rule_id` and `rule_updated` to `null`.

### Event fields

- `event_id` — immutable, time-ordered (stamped by the helper).
- `event_type` — `retrieval` or `no_match`.
- `occurred_at` — UTC timestamp (stamped by the helper).
- `search_id` — groups every event from one search invocation.
- `rule_id` — stable rule ID, or `null` for `no_match`.
- `rule_updated` — revision date of the rule content returned.
- `task_id` — stable task identifier when available.
- `session_id` — the parent session that requested the search.
- `phase` — `requirements`, `solution`, `planning`, `execution`, or `review`.

Use `retrieval` / `retrieval_count` / `last_retrieved` terminology only. A
retrieval does **not** claim the rule was applied or helpful. If those states
later become reliably observable, add **new** event types rather than redefining
retrieval.

## Rules

- Append to `retrievals.ndjson` only (via `reflect.py append`). Never edit
  `rules.yaml` or `observations.yaml`.
- Only the coordinator writes; matchers return candidates, never log.
- One `retrieval` event per rule returned to the parent; one `no_match` per empty
  search. Never log candidates that weren't returned.
- Return an explicit empty result on no match — never silently return nothing.
