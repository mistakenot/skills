# Context: Task 001

Codebase grounding for the `fix-insert-pk-indexerror` task. See [plan.html](plan.html).

## Key Files

- `sqlite_utils/db.py:4385-4400` — Post-insert block that sets `self.last_pk` for single-row inserts. The bug is at line 4390: `if (hash_id or pk) and self.last_rowid:`. The `self.last_rowid` guard was written assuming SQLite returns `lastrowid=0` for an INSERT OR IGNORE no-op, but modern SQLite returns the last connection-wide rowid, which may belong to a different table.
- `sqlite_utils/db.py:4389` — `self.last_rowid = result.lastrowid` — set from the cursor returned by `insert_chunk`. When INSERT OR IGNORE ignores a row, `lastrowid` reflects the last insert from any table in the session.
- `sqlite_utils/db.py:4368` — `result = self.insert_chunk(...)` — the cursor whose `.lastrowid` and `.rowcount` are relevant.
- `sqlite_utils/db.py:2072` — `last_rowid: Optional[int] = None` — class-level attribute on the `Table` dataclass.
- `sqlite_utils/db.py:4309` — `self.last_rowid = None` — reset at the start of each insert/upsert call.
- `sqlite_utils/db.py:3881-3883` — Extract inserts inside `build_insert_queries_and_params` also advance `lastrowid` (same root cause, covered by the same fix).
- `tests/test_create.py:944-953` — `test_insert_ignore`: existing test for pk+ignore, does not assert `last_pk` and does not test cross-table rowid scenario.

## Patterns

- All insert/upsert logic funnels through `insert_all` → `insert_chunk`. The post-chunk `last_pk` assignment block at line 4385 is the only place to fix.
- `cursor.rowcount` is the standard CPython sqlite3 mechanism to detect whether an INSERT OR IGNORE actually wrote a row: 0 = ignored, 1 = inserted.
- Existing tests use `pytest` with `fresh_db` fixture (in-memory `Database`); new tests should follow the same pattern.

## Related Tasks

- None (first task in this repository's task history).
