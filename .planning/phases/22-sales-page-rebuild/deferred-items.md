# Deferred Items — Phase 22

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
