I need a small internal command-line tool for our ops team. Nothing fancy —
it's just a helper script a couple of engineers will run from their laptops, so
it doesn't need a UI or anything.

The tool:
- Takes a filter (by account status, signup date range, or a plaintext list of
  account IDs) and finds the matching customer accounts in our production
  database.
- Prints how many accounts matched, then permanently deletes them and all their
  associated records — orders, invoices, uploaded files, audit history — in one
  pass. This is a hard delete, not a soft flag; the rows are gone and there is no
  undo.
- Supports a `--dry-run` flag that lists what would be deleted without touching
  anything.

We mostly use it to clear out spam signups and to honour account-deletion
requests, so it runs against the live production database with a service account
that has full delete permissions. It's only ever run by hand, a few times a
week.

Keep it simple — it's an internal script, not a customer-facing product. Before
writing any code, design a solid testing strategy for this project. Then we'll
implement the tool and its tests according to that strategy.
