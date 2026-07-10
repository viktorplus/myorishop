# Deferred Items — Phase 06 (reports-data-export)

Items discovered during execution that are out of scope for the current plan
(pre-existing, unrelated to the files this plan touches) and were left
unfixed per the executor's scope-boundary rule.

## Plan 06-06

- **Pre-existing `ruff check .` import-sort errors (I001)** in `tests/test_backup.py`
  (also one `SIM108` at line 173), `tests/test_corrections.py`, `tests/test_customers.py`,
  `tests/test_sales.py`, `tests/test_writeoffs.py`. Confirmed via `git log` that these
  files were last modified in a Phase 05 commit (`337ad94`), not by this plan. Not fixed
  here — out of scope (plan 06-06 only touches `app/services/reports.py`,
  `app/routes/reports.py`, templates, and `tests/test_reports.py`, all of which pass
  `ruff check` cleanly).
