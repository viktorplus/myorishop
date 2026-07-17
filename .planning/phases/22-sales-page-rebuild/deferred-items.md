# Deferred Items — Phase 22 (Sales Page Rebuild)

Out-of-scope discoveries logged during plan execution, per the executor's
Scope Boundary rule (only auto-fix issues directly caused by the current
task's changes).

## 22-01: Repo-wide `ruff check .` / `ruff format --check .` pre-existing debt

**Found during:** Task 3 verification (`uv run ruff check . && uv run ruff format --check .`).

**Scope:** `tests/test_sales.py` (this plan's only `files_modified` entry) is
clean — `uv run ruff check tests/test_sales.py` and
`uv run ruff format --check tests/test_sales.py` both pass after this plan's
changes (confirmed via `uv run ruff format tests/test_sales.py`, which
reformatted 3 pre-existing multi-line `record_operation(...)` calls plus one
line from this plan's own new code, then re-verified clean).

**Out of scope, not fixed:**
- `uv run ruff check .` (whole repo): 9 pre-existing errors (E501 line-too-long
  in `app/routes/dictionary.py`, `app/routes/products.py`,
  `scripts/import_master_pricelist.py` x3, `tests/test_catalog.py`,
  `tests/test_catalogs_feature.py`, `tests/test_export.py`; plus one F401
  unused-import in `tests/test_mobile_receipts.py`) — none in any file this
  plan touched.
- `uv run ruff format --check .` (whole repo): 50 files would be reformatted
  — none is `tests/test_sales.py`. Files affected include
  `app/services/sales.py`, `app/services/stock.py`, `app/services/transfers.py`,
  `app/services/warehouses.py`, `scripts/import_master_pricelist.py`, and 25
  test files across the suite.

**Recommendation:** A dedicated repo-wide formatting/lint pass (not scoped to
any single Phase 22 plan) would close this cleanly. Do not let it block
Phase 22 — every plan in this phase only touches its own declared
`files_modified`, and each plan's own file(s) should be verified clean
individually rather than gated on the whole repo's pre-existing debt.

## 22-02: Repo-wide ruff debt (pre-existing, not introduced by 22-02)

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

## 22-04: Repo-wide ruff debt (pre-existing, not introduced by 22-04)

`uv run ruff check .` reports the same 9 pre-existing findings noted under 22-01/22-02
(E501 line-too-long in `app/routes/dictionary.py`, `app/routes/products.py`,
`scripts/import_master_pricelist.py` x3, `tests/test_catalog.py`,
`tests/test_catalogs_feature.py`, `tests/test_export.py`; plus one F401 unused-import in
`tests/test_mobile_receipts.py`) — none in any file this plan's `files_modified` declares.

This plan's only Python file, `tests/test_sales_total.py`, passes both `uv run ruff check
tests/test_sales_total.py` and `uv run ruff format --check tests/test_sales_total.py`
cleanly (verified individually after removing the six xfail markers and the now-unused
`import pytest`). `app/static/sale-total.js` and the three `.html` templates touched this
plan are not Python and are outside ruff's scope.

Full suite: `uv run pytest -q` → 834 passed, 15 xfailed, 0 failed (≥808 required).

Not fixed here (out of scope for 22-04). Revisit with a dedicated formatting/lint pass if
this debt starts blocking CI.

## 22-05: Repo-wide ruff debt (pre-existing, not introduced by 22-05)

Same accumulated debt as 22-01/22-02, reconfirmed during 22-05's Task 3 verification:

- `uv run ruff check .`: 9 pre-existing errors (E501 line-too-long across several
  `app/`/`scripts/`/`tests/` files, plus one F401 unused import in
  `tests/test_mobile_receipts.py`) — none in `app/routes/sales.py`,
  `app/templates/partials/sale_customer.html`, or `tests/test_sales.py` (this plan's
  entire `files_modified`).
- `uv run ruff format --check .`: 47 pre-existing files would be reformatted — none
  is a file this plan touched.

This plan's own 3 files pass `ruff check` and `ruff format --check` cleanly, verified
individually. Not fixed here — out of scope per the plan's `<files>` frontmatter.
