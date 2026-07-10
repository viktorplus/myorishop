---
phase: 06-reports-data-export
verified: 2026-07-10T18:15:00Z
status: passed
human_verification_resolved: "2026-07-10T16:26:31Z (see 06-UAT.md — CSV Excel open check: pass)"
score: 5/5 must-haves verified
overrides_applied: 0
notes:
  - "ROADMAP.md tags this phase 'Mode: mvp' but the phase goal text ('Operator can see sales, profit, and stock health for any period, and get all data out as CSV') does not match the User Story format required by MVP-mode verification (gsd-tools query user-story.validate returns valid=false: missing 'As a ...', ', I want to ...', ', so that ...', trailing period). All 6 plans use the standard must_haves (truths/artifacts/key_links) frontmatter shape, not an MVP user-story shape, and 06-CONTEXT/06-UI-SPEC/06-RESEARCH were produced as standard-phase artifacts. Treating this as a stale/mismatched ROADMAP tag rather than refusing verification outright — standard goal-backward verification below is complete and evidence-based. Recommend the human either strip 'Mode: mvp' from ROADMAP.md Phase 6 or run `/gsd mvp-phase 6` to reconcile, as a housekeeping item; this does not block the phase.
human_verification:
  - test: "Download each of the three CSVs from /export (products.csv, sales.csv, customers.csv) and double-click to open in Excel on the target Windows machine"
    expected: "Each file opens with columns correctly split (semicolon delimiter) and Cyrillic text renders correctly (no mojibake), per D-07/D-06"
    why_human: "Automated tests (test_products_csv_roundtrip, test_sales_csv_roundtrip, test_customers_csv_roundtrip) verify the byte-level contract (single BOM, ';' delimiter, header, row count, formula-injection escaping) by parsing the bytes back with Python's csv module — they cannot verify that Excel's actual double-click-to-open behavior renders the file correctly, which depends on Excel's own locale/encoding detection. Phase's own 06-04-SUMMARY.md explicitly flags this as pending manual UAT (RESEARCH A3)."
---

# Phase 6: Reports & Data Export Verification Report

**Phase Goal:** Operator can see sales, profit, and stock health for any period, and get all data out as CSV
**Verified:** 2026-07-10T18:15:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Operator can view sales and profit reports for a day, week, month, or custom period, with correct local-day boundaries | VERIFIED | `app/core.py::local_day_bounds_utc` (half-open `[start,end)` UTC range via `ZoneInfo`), `app/services/reports.py::sales_profit_report` (NULL-cost-safe), `GET /reports/sales` wired through `_resolve_period` shared helper; 24 tests in `tests/test_core.py`/`tests/test_reports.py` cover the exact evening-sale-near-midnight boundary and the NULL-cost Pitfall 2 scenario; full suite green |
| 2 | Operator can view current stock levels including a low-stock items list | VERIFIED | `app/services/stock.py::effective_low_stock_threshold` (explicit `is not None`, not bare `or`), `low_stock_products`, `all_active_products`; `GET /reports/stock` renders both; explicit-zero-threshold Pitfall 3 test passes |
| 3 | Operator can view write-off reports for a chosen period | VERIFIED | `app/services/reports.py::writeoff_report` groups by `WRITEOFF_REASONS`' declared key order, excludes zero-count reasons, no `deleted_at` filter (historical); `GET /reports/writeoffs` reuses `_resolve_period` verbatim |
| 4 | Operator can view top-selling products and products with no sales for a long time | VERIFIED | `top_selling_products` (SQL-side `func.sum`/`.group_by()`/`.order_by()`/`.limit()`), `stale_products` (LEFT OUTER JOIN, never-sold products included, explicit `stale_days=0` respected via `_effective_stale_days`, soft-deleted excluded); `GET /reports/products` renders both halves independently (stale half unconditional, not gated on period validity) |
| 5 | Operator can export products, sales, and customers to CSV files | VERIFIED | `app/services/export.py`: `stream_products_csv`/`stream_sales_csv`/`stream_customers_csv`, BOM-once (`_encode_once`), `;` delimiter, `_csv_safe` formula-injection guard applied to **every** free-text cell across all three exports (including `consultant_number`, fixed post-review via CR-01); `GET /export` with three plain `<a href>` (non-htmx) download links; zero client-supplied filename/path params |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `alembic/versions/0005_product_thresholds.py` | nullable `low_stock_threshold`/`stale_days` columns | VERIFIED | `revision = "0005"`, `down_revision = "0004"`; `alembic heads` confirms `0005 (head)` |
| `app/models.py` (`Product.low_stock_threshold`/`stale_days`) | `Mapped[int \| None]` columns | VERIFIED | Both present, lines 102-103 |
| `app/config.py` (`Settings.low_stock_threshold=5`/`stale_days=90`) | global fallback defaults | VERIFIED | Both present, lines 25-26 |
| `app/core.py::local_day_bounds_utc` | half-open UTC boundary helper | VERIFIED | Present, correct docstring, tested |
| `app/services/reports.py` | `sales_profit_report`, `writeoff_report`, `top_selling_products`, `stale_products`, `_effective_stale_days` | VERIFIED | All present, read-only, no writes |
| `app/services/stock.py` | `effective_low_stock_threshold`, `low_stock_products`, `all_active_products` | VERIFIED | All present; `is not None` fallback confirmed by reading function body |
| `app/services/export.py` | 3 CSV streaming generators + `_csv_safe`/`_csv_rows`/`_encode_once` | VERIFIED | All present; `utf-8-sig`, `delimiter=";"` confirmed by grep and by reading the code |
| `app/routes/reports.py` | `GET /reports`, `/reports/sales`, `/reports/stock`, `/reports/writeoffs`, `/reports/products`, shared `_resolve_period` | VERIFIED | All 5 routes present, single `_resolve_period` definition reused by all period-based routes |
| `app/routes/export.py` | `GET /export`, `/export/products.csv`, `/export/sales.csv`, `/export/customers.csv` | VERIFIED | All present; zero client params on any route |
| Templates (`reports_landing.html`, `reports_sales.html`, `reports_stock.html`, `reports_writeoffs.html`, `reports_products.html`, `export.html`, partials) | real Jinja markup, no placeholders | VERIFIED | Read all; real tables, real empty-states, no TBD/TODO/placeholder text |
| `app/main.py` router registration | `include_router(reports.router)`, `include_router(export.router)` | VERIFIED | Both present |
| `app/templates/base.html` nav | `href="/reports"`, `href="/export"` | VERIFIED | Both present with active-state checks |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `app/templates/pages/product_form.html` | `app/routes/products.py` | form fields `low_stock_threshold`/`stale_days` | WIRED | Both `Form("")` params present in `product_create`/`product_update` |
| `app/routes/products.py` | `app/services/catalog.py` | `*_raw` kwargs into `create_product`/`update_product` | WIRED | Confirmed |
| `app/routes/reports.py` | `app/core.py` | `local_day_bounds_utc(...)` calls | WIRED | Used in `/reports/sales`, `/reports/writeoffs`, `/reports/products` |
| `app/templates/base.html` | `app/routes/reports.py` / `export.py` | nav `href="/reports"` / `href="/export"` | WIRED | Confirmed |
| `app/main.py` | `app/routes/reports.py` / `export.py` | `include_router(...)` | WIRED | Confirmed |
| `app/routes/reports.py` | `app/services/stock.py` | `GET /reports/stock` calls `low_stock_products`/`all_active_products` | WIRED | Confirmed |
| `app/templates/pages/reports_landing.html` | all 4 report routes | `href="/reports/{sales,stock,writeoffs,products}"` | WIRED | All 4 hrefs present in one `<p>` |
| `app/templates/pages/export.html` | `app/routes/export.py` | plain `<a href>` (no `hx-get`) | WIRED | Confirmed no `hx-get="/export` occurrences |
| `app/templates/partials/writeoffs_report_rows.html` | `app/models.py::WRITEOFF_REASONS` | RU label via `entry.label` (resolved server-side in `writeoff_report`) | WIRED | Confirmed |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full project test suite passes | `uv run pytest -q` | `222 passed, 2 warnings` | PASS |
| Reports/export/core/catalog test subset passes | `uv run pytest tests/test_reports.py tests/test_export.py tests/test_core.py tests/test_catalog.py -q` | `91 passed` | PASS |
| Migration 0005 is head | `uv run alembic heads` | `0005 (head)` | PASS |
| Ruff clean on phase-touched files | `uv run ruff check .` | 4 errors, all in `tests/test_sales.py`/`tests/test_writeoffs.py` (pre-existing, Phase 5 files, documented in `deferred-items.md` as out-of-scope) | PASS (no regressions introduced by this phase) |
| No debt markers in phase files | `grep TBD\|FIXME\|XXX` across all phase-touched `.py` files | none found | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| RPT-01 | 06-02 | Sales/profit reports for day/week/month/custom period | SATISFIED | `local_day_bounds_utc`, `sales_profit_report`, `/reports/sales`, 24 tests |
| RPT-02 | 06-01, 06-03 | Current stock levels + low-stock list | SATISFIED | threshold fields + `stock.py` + `/reports/stock` |
| RPT-03 | 06-05 | Write-off reports for a period | SATISFIED | `writeoff_report` + `/reports/writeoffs` |
| RPT-04 | 06-01, 06-06 | Top-selling + stale products | SATISFIED | `top_selling_products`/`stale_products` + `/reports/products` |
| BCK-02 | 06-04 | Export products/sales/customers to CSV | SATISFIED | `export.py` + `/export`, CR-01 formula-injection gap fixed post-review |

**Orphaned requirements check:** `.planning/REQUIREMENTS.md` traceability table maps exactly these 5 IDs to Phase 6 — none additional, none missing. No orphans.

**Note (non-blocking housekeeping):** `.planning/REQUIREMENTS.md`'s checkboxes for RPT-01 (`[ ]`), RPT-03 (`[ ]`), and BCK-02 (`[ ]`) and its traceability table (`Pending`) are stale — they were not updated to reflect Phase 6 completion, even though the code evidence above confirms all three are implemented and tested. RPT-02/RPT-04 were already marked `[x]`/`Complete` (likely updated by an earlier partial pass). Recommend updating `.planning/REQUIREMENTS.md` checkboxes/table for RPT-01, RPT-03, BCK-02 as part of phase close-out — this is a documentation-sync task, not a code gap.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `app/templates/partials/sales_report_results.html` | 39 | `{{ row.product.code }}` with no `or ""` guard (renders literal "None" if code is ever NULL) | Info | Currently unreachable — `create_product` requires non-empty code — but inconsistent with sibling templates in the same phase that do guard it (`reports_stock.html`, `reports_products.html`). Documented as IN-01 in `06-REVIEW.md`, left unfixed (Info findings excluded from review-fix scope) |
| `app/templates/partials/top_selling_rows.html` | 25 | same unguarded `row.product.code` pattern | Info | Same as above (IN-01) |
| `app/services/reports.py` | `writeoff_report` | builds a `"lines"` payload that is never rendered by any template | Info | Documented as IN-03 in `06-REVIEW.md` — wasted memory load, not a correctness bug, intentionally left as-is (reserved for a future drill-down view per review note) |

No blocker-level anti-patterns found. All 4 review findings that were classified critical/warning (CR-01, WR-01, WR-02, WR-03, WR-04) were fixed and verified in `06-REVIEW-FIX.md`, confirmed present in the current code (`_csv_safe(customer.consultant_number or "")`, "Удалён" column, int32 bound check, negative-price rejection — all read directly from the current file contents above).

### Human Verification Required

### 1. CSV files open correctly in Excel

**Test:** Download `products.csv`, `sales.csv`, and `customers.csv` from `/export` and double-click each to open in Excel on the target Windows machine.
**Expected:** Columns split correctly (semicolon-delimited), Cyrillic text is readable (no mojibake), and money values with comma decimals (e.g. "12,50") remain in a single cell.
**Why human:** Automated tests decode the CSV bytes programmatically and confirm the byte-level contract (single BOM, `;` delimiter, header/row shapes, formula-injection escaping) — this is real evidence the format is correct, but it cannot substitute for Excel's own file-open/encoding-detection behavior on an actual double-click. The phase's own `06-04-SUMMARY.md` explicitly flags this as the one item needing manual UAT (RESEARCH A3), and it was never marked done in any summary.

### Gaps Summary

No code-level gaps found. All 5 phase success criteria are backed by working, tested code: threshold configuration (06-01), sales/profit reporting with correct local-day math (06-02), stock/low-stock reporting (06-03), CSV export (06-04, post-review-fix), write-off reporting (06-05), and top-selling/stale-products reporting (06-06). The full test suite (222 tests) passes, migration 0005 is head, and all critical/warning code-review findings were fixed and are confirmed present in the current codebase.

Two non-blocking items remain:
1. **Human verification needed:** an actual Excel double-click-open check for the three CSV exports (byte-level contract is proven; real-world Excel rendering is not).
2. **Housekeeping:** `.planning/REQUIREMENTS.md` checkboxes/traceability table are stale for RPT-01/RPT-03/BCK-02 despite the code being complete — should be updated at phase close-out.

A separate, unrelated process discrepancy was also noted: ROADMAP.md tags this phase `Mode: mvp`, but the phase goal text is not in User Story format (confirmed via `gsd-tools query user-story.validate`), and none of the 6 plans used the MVP user-story planning shape. This looks like a stale ROADMAP tag rather than an intentional MVP-mode phase; flagged for human awareness but did not block this verification, since standard goal-backward verification found complete, working evidence for every success criterion.

---

_Verified: 2026-07-10T18:15:00Z_
_Verifier: Claude (gsd-verifier)_
