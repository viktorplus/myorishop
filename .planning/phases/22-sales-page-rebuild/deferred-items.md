# Deferred Items — Phase 22 (Sales Page Rebuild)

Out-of-scope discoveries found while executing plan 22-02, logged per the executor's
Scope Boundary rule (only auto-fix issues directly caused by the current task's changes).

## Repo-wide ruff debt (pre-existing, not introduced by 22-02)

`uv run ruff check .` / `uv run ruff format --check .` report pre-existing findings in files
untouched by plan 22-02:

- `ruff check .`: 9 errors, including `F401 app.services.dictionary.add_entry imported but
  unused` in `tests/test_mobile_receipts.py:16` and several long-line issues.
- `ruff format --check .`: 49 files would be reformatted (all pre-existing test files this
  plan did not touch — `test_corrections.py`, `test_dictionary.py`, `test_export.py`,
  `test_finance.py`, `test_finance_reports.py`, `test_history.py`, `test_ledger.py`,
  `test_mobile_receipts.py`, `test_mobile_reports.py`, `test_mobile_returns.py`,
  `test_mobile_transfers.py`, `test_mobile_writeoff.py`, `test_receipts.py`,
  `test_reports.py`, `test_returns.py`, `test_sales.py`, `test_sales_search.py`,
  `test_warehouses.py`, `test_writeoffs.py`).

Verified via `git show <22-02 worktree base commit>:pyproject.toml` that the ruff config
(line-length 100, select E/F/I/UP/B) predates this plan, so this is accumulated debt, not a
regression from 22-02. This plan's own 3 files
(`tests/test_sales_total.py`, `tests/test_mobile_sales.py`, `tests/test_core.py`) pass both
`ruff check` and `ruff format --check` cleanly — verified individually.

Not fixed here (out of scope for 22-02, whose `<files>` frontmatter is scoped to those 3
files). Revisit with a dedicated formatting/lint pass if this debt starts blocking CI.
