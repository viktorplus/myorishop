# Deferred Items — Phase 05

Out-of-scope discoveries logged during execution, per the executor's Scope Boundary rule
(fix only issues directly caused by the current task's changes).

## From 05-08 (CR-01 gap closure)

- **`tests/test_history.py` ruff I001 (import block un-sorted)** — pre-existing at HEAD
  before this plan touched the file (confirmed via `git show HEAD:tests/test_history.py`
  + `ruff check`). The file's two-group import layout (`from app.services.operations
  import history_view  # noqa: F401` isolated above the rest) is a deliberate repo-wide
  pattern shared by `tests/test_backup.py`, `tests/test_corrections.py`,
  `tests/test_customers.py`, `tests/test_sales.py`, and `tests/test_writeoffs.py` — all
  of which fail the same `I001` check under `uv run ruff check .`. Not caused by 05-08's
  diff (which only appended a new test function). Not fixed here — out of scope.
