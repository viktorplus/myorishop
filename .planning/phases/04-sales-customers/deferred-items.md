# Deferred Items — Phase 04 (sales-customers)

Out-of-scope discoveries logged during execution (SCOPE BOUNDARY rule — not
fixed here; left for a dedicated cleanup task if the team wants it).

## From Plan 04-01

- **`ruff check tests/test_backup.py`** — 2 pre-existing `I001` (unsorted
  import block) findings, unrelated to Plan 04-01 (file belongs to Phase
  03-03, never touched by this plan). Confirmed pre-existing by running
  `ruff check` on the file in isolation before any 04-01 edits.
- **`ruff format --check .`** — 7 pre-existing files would be reformatted:
  `alembic/versions/0001_initial_schema.py`, `app/models.py`,
  `app/services/catalog.py`, `app/services/ledger.py`,
  `tests/test_catalog.py`, `tests/test_ledger.py`, `tests/test_receipts.py`.
  Confirmed via `ruff format --diff` that every reported hunk in
  `app/models.py` and `app/services/ledger.py` sits on pre-existing lines
  untouched by 04-01 (e.g. the `Operation.product_id` column, the
  `ledger_view` query chaining) — none of the new Customer/Sale/`sale_id`
  code this plan added triggers a reformat. The repository was apparently
  never run through `ruff format` end-to-end; a dedicated formatting pass
  is out of scope for a feature plan.
