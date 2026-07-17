# Deferred Items — Phase 21

Out-of-scope issues discovered during execution, logged per the executor's
SCOPE BOUNDARY rule (only auto-fix issues directly caused by the current
task's changes).

## Found during 21-03 (Task 3 verification: `uv run ruff check` / `ruff format --check`, whole repo)

Both whole-repo commands were run per Task 3's verify block. All findings
below are in files this plan never touched (`app/services/customers.py` and
`tests/test_customers.py` are clean and already-formatted) — pre-existing
drift, not caused by 21-03.

**`uv run ruff check` (9 errors, unrelated files):**
- `app/routes/dictionary.py:73` — E501 line too long (106 > 100)
- `app/routes/products.py:133` — E501 line too long (106 > 100)
- `scripts/import_master_pricelist.py:3,111,118` — E501 line too long (3 occurrences)
- `tests/test_catalog.py:1175` — E501 line too long (101 > 100)
- `tests/test_catalogs_feature.py:122` — E501 line too long (102 > 100)
- `tests/test_export.py:243` — E501 line too long (102 > 100)
- `tests/test_mobile_receipts.py:16` — F401 unused import `app.services.dictionary.add_entry`

**`uv run ruff format --check` (51 files would be reformatted, unrelated files):**
Widespread formatting drift across `tests/test_dictionary.py`,
`tests/test_export.py`, `tests/test_finance.py`, `tests/test_finance_reports.py`,
`tests/test_history.py`, `tests/test_ledger.py`, `tests/test_mobile_receipts.py`,
`tests/test_mobile_reports.py`, `tests/test_mobile_returns.py`,
`tests/test_mobile_sales.py`, `tests/test_mobile_transfers.py`,
`tests/test_mobile_writeoff.py`, `tests/test_receipts.py`, `tests/test_reports.py`,
`tests/test_returns.py`, `tests/test_sales.py`, `tests/test_sales_search.py`,
`tests/test_warehouses.py`, `tests/test_writeoffs.py`, and others (51 total).

**Action:** none taken — out of scope for 21-03. Revisit in a dedicated
lint/format cleanup pass, or the next time any of these specific files is
touched for its own reasons.
