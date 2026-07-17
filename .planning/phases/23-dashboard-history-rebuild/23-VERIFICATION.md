---
phase: 23-dashboard-history-rebuild
verified: 2026-07-17T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 23: Dashboard & History Rebuild Verification Report

**Phase Goal:** Главная answers "what is the state of the business right now" at a glance, and История answers "what happened" narrowed to the operation type the operator cares about.
**Verified:** 2026-07-17
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Home page shows current date, weekday, time, active catalog number, and days remaining until close | ✓ VERIFIED | `app/services/dashboard.py::dashboard_now`/`catalog_status`; rendered in `app/templates/pages/home.html:9-19` and `app/templates/mobile_pages/home.html:24-33`. Empty/closed/open/number-only branches all present and tested (`tests/test_home.py`, `tests/test_mobile_home.py`). |
| 2 | Home page shows revenue/profit/expense for today/week/month, plus distinct product-code count and combined valuation | ✓ VERIFIED | `dashboard_metrics`/`stock_summary` in `app/services/dashboard.py`; rendered via `app/templates/partials/dashboard_tiles.html` (desktop) and inlined `.metric-grid` in `mobile_pages/home.html`. D-08 net-profit addition (never subtraction) and D-07 expense definition explicitly regression-tested in `tests/test_dashboard.py`. |
| 3 | Home page shows a recent-operations feed with columns adapted per operation type (type, code, name, expiry, quantity, cost, profit, customer) | ✓ VERIFIED | `recent_operations()` (6-type double-outerjoin, Sale/Customer stay outer) feeds a 10-column table in `pages/home.html:22-97` (Когда/Тип/Код/Товар/Срок/Кол-во/Себестоимость/Прибыль/Покупатель/Действие) and mobile's per-type `FEED_FIELDS`-gated cards. Per-type population verified by `tests/test_home.py`/`tests/test_mobile_home.py` (receipt vs sale field presence). |
| 4 | History page lets the operator select an operation type first, then shows only that type's relevant columns | ✓ VERIFIED | `app/routes/history.py` + `app/templates/partials/history_rows.html`: Тип select relocated to top filter-bar; `columns` (from `HISTORY_TYPE_COLUMNS`, `app/services/operations.py`) is `None` for no-filter/3 audit types (unchanged generic 10-column view) and a narrowed per-type tuple for the 6 stock-affecting types. Confirmed identical mechanism on mobile (`mobile_history.py` + `history_cards.html`). |
| 5 | History results filterable by product code, date range, customer, category; sortable; paginated | ✓ VERIFIED | `history_view()` (`app/services/operations.py`) accepts `product_id`, `start_iso`/`end_iso`, `customer` (sale/return-gated, D-05), `category` (Cyrillic-safe bounded resolution); `sort` unchanged; numbered `page_window`/`paginate` pagination on both desktop (`partials/pagination.html`) and mobile (new `mobile_partials/history_pagination.html`, retiring the legacy load-more control — `mobile_partials/history_load_more.html` confirmed deleted). |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/models.py::ActiveCatalog` | Singleton table (number, close_date) | ✓ VERIFIED | Present, migration `alembic/versions/0016_active_catalog.py` round-trips (tests pass). |
| `app/services/active_catalog.py` | get/set active catalog | ✓ VERIFIED | Exports `get_active_catalog`, `set_active_catalog`; used by `dashboard.py`. |
| `app/services/operations.py::HISTORY_TYPE_COLUMNS` + extended `history_view` | Per-type column map, customer/category/date filters, `columns`/`warehouse`/`customer` keys | ✓ VERIFIED | Constant present (line ~34); `history_view` signature carries all new kwargs (`customer`, `category`, `start_iso`, `end_iso`); row dict includes `warehouse` and `customer`. |
| `app/services/dashboard.py::dashboard_context` | Single composer for Главная | ✓ VERIFIED | Composes `dashboard_now`/`catalog_status`/`dashboard_metrics`/`stock_summary`/`recent_operations`; never raises without an `ActiveCatalog` row. |
| `app/routes/history.py`, `app/templates/partials/history_rows.html` | Desktop type-first History | ✓ VERIFIED | Filter-bar relocation, per-type `<thead>`/`<tbody>` narrowing, universal `period_filter.html` inclusion, pagination unchanged. |
| `app/routes/mobile_history.py`, `mobile_partials/history_cards.html`, `mobile_partials/history_pagination.html` | Mobile History parity | ✓ VERIFIED | Full filter set, numbered pagination via `page_window`, OOB pagination sibling (never nested in `#history-cards`), `history_load_more.html` deleted. |
| `app/routes/home.py`, `app/templates/pages/home.html`, `app/templates/partials/dashboard_tiles.html` | Desktop Главная rebuild | ✓ VERIFIED | Thin route calling `dashboard_context`; page renders date/catalog/tiles/feed per UI-SPEC. |
| `app/routes/mobile_home.py`, `app/templates/mobile_pages/home.html` | Mobile Главная rebuild | ✓ VERIFIED | Nav grid preserved verbatim first; dashboard content appended below (Pitfall-1 regression test present: nav-grid tile precedes «Показатели» heading). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `app/routes/catalogs.py` | `app/services/active_catalog.py` | `get_active_catalog`/`set_active_catalog` calls | ✓ WIRED | Confirmed in route + form partial (`hx-post="/catalogs/active"`). |
| `app/services/dashboard.py::dashboard_context` | `app/services/active_catalog.py::get_active_catalog` | direct call | ✓ WIRED | `dashboard_context` calls it before `catalog_status`. |
| `app/services/dashboard.py::period_metrics` | `reports.py::sales_profit_report` + `finance_reports.py::cash_expense_total` | direct calls, D-07/D-08 | ✓ WIRED | Addition-only net-profit regression test present and passing. |
| `app/services/dashboard.py::recent_operations` | `ledger.py::STOCK_AFFECTING_TYPES` | `.in_()` filter | ✓ WIRED | Confirmed; both Sale/Customer joins stay outer (source-inspection regression test in `tests/test_dashboard.py`). |
| `app/templates/partials/history_rows.html` | `GET /history` | `hx-get` + `hx-include` | ✓ WIRED | Filter-bar, period filter, and filter-row controls all `hx-target="#history-rows"`. |
| `app/routes/history.py` | `app/services/operations.py::history_view` | `customer=`/`category=`/`start_iso=`/`end_iso=` kwargs | ✓ WIRED | Confirmed passthrough in `history_page`. |
| `mobile_partials/history_cards.html` | `GET /m/history` | `hx-get` + `hx-include="#history-filters ..."` | ✓ WIRED | Confirmed in `mobile_pages/history.html`. |
| `app/routes/mobile_history.py` | `app/services/pagination.py::page_window` | direct call, replaces `has_next` | ✓ WIRED | Confirmed; `has_next` sentinel fully removed. |
| `app/routes/home.py` / `app/routes/mobile_home.py` | `app/services/dashboard.py::dashboard_context` | direct call | ✓ WIRED | Both routes call identically (`dashboard_context(session, settings.display_tz)`). |
| `app/templates/pages/home.html` / mobile feed cards | `/history` / `/m/history` | «Подробнее» links | ✓ WIRED | `/history?type={{ r.op.type }}&product={{ r.product.id }}` present on both surfaces. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full phase test suite passes (existence + behavior proof, not just import) | `uv run pytest -q` | 896 passed, 0 failed | ✓ PASS |
| Phase-specific suites (dashboard/home/history/mobile/active_catalog) | `uv run pytest tests/test_dashboard.py tests/test_home.py tests/test_mobile_home.py tests/test_history.py tests/test_mobile_history.py tests/test_active_catalog.py -q` | 66 passed | ✓ PASS |
| No debt markers (TBD/FIXME/XXX/TODO/HACK/PLACEHOLDER) in phase-touched files | `grep -rn -E "TBD\|FIXME\|XXX\|TODO\|HACK\|PLACEHOLDER..." <phase files>` | No matches | ✓ PASS |
| Legacy mobile load-more control retired, unrelated cash load-more untouched | `ls app/templates/mobile_partials/ \| grep -i load` | Only `cash_history_load_more.html` present | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` convention or PLAN/SUMMARY-declared probes found for this phase. Step 7c SKIPPED (no probes declared).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| DASH-01 | 23-03, 23-06, 23-07 | Home shows date/weekday/time | ✓ SATISFIED | `dashboard_now`, rendered on both surfaces, tested. |
| DASH-02 | 23-01, 23-03 | Home shows active catalog number + days remaining | ✓ SATISFIED | `ActiveCatalog` + `catalog_status`, tested. |
| DASH-03 | 23-03, 23-06, 23-07 | Home shows revenue/profit/expense for today/week/month | ✓ SATISFIED | `dashboard_metrics`, D-07/D-08 regression-tested. |
| DASH-04 | 23-03, 23-06, 23-07 | Home shows distinct product-code count + valuation | ✓ SATISFIED | `stock_summary` (single SQL count + `stock_valuation`), tested. |
| DASH-05 | 23-02, 23-03, 23-06, 23-07 | Recent-operations feed, per-type columns | ✓ SATISFIED | `recent_operations` + `HISTORY_TYPE_COLUMNS`-derived rendering, tested. |
| HIST-01 | 23-02, 23-04, 23-05 | Type-first column narrowing | ✓ SATISFIED | `HISTORY_TYPE_COLUMNS`, desktop + mobile narrowed thead/tbody/cards, tested. |
| HIST-02 | 23-02, 23-04, 23-05 | Filter by product/date/customer/category | ✓ SATISFIED | `history_view` extended kwargs, route wiring, tested (customer sale/return-gated per D-05). |
| HIST-03 | 23-02, 23-04, 23-05 | Sort by relevant columns | ✓ SATISFIED | Existing `sort`/`_SORT_MAP` mechanism unchanged, still exercised by tests. |
| HIST-04 | 23-04, 23-05 | Paginated results | ✓ SATISFIED | Desktop unchanged `page_window`/`paginate`; mobile migrated off `has_next` load-more onto the same mechanism, confirmed by dedicated pagination-bar tests. |

**Note (documentation gap, non-blocking):** `.planning/REQUIREMENTS.md`'s checkbox/Traceability table still marks DASH-01/03/04/05 and HIST-04 as unchecked/"Pending" even though ROADMAP.md marks Phase 23 complete and the code/tests above satisfy all of them. This is a stale tracking-document artifact, not a functional gap — recommend updating REQUIREMENTS.md's checkboxes and Traceability table to "Complete" as part of phase close-out.

### Anti-Patterns Found

None in the phase's modified/created files (`app/services/dashboard.py`, `app/services/active_catalog.py`, `app/routes/home.py`, `app/routes/mobile_home.py`, `app/routes/history.py`, `app/routes/mobile_history.py`, `app/services/operations.py`, and all phase templates). No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` markers, no empty-return stubs, no hardcoded-empty data flowing to rendering.

The independent code review (`23-REVIEW.md`, `status: issues_found`, 0 critical) found 3 non-blocking warnings, none of which fail a phase must-have:
- WR-01: `history_view` echoes an unvalidated `type_filter` value (`?type=bogus` renders no dropdown option `selected` and leaks into `extra_qs`) — cosmetic UI-desync, not a data-integrity or goal-blocking issue.
- WR-02: `active_catalog`'s singleton get-or-create has a theoretical double-POST race (irrelevant for a single-operator app, and explicitly documented as an accepted convention elsewhere in the codebase).
- WR-03: `close_date` accepts non-canonical ISO-8601 basic-format strings (e.g. `20260831`) without normalizing before storage, which could render blank in the HTML5 date input on reload.

These are legitimate follow-up items but do not block the DASH/HIST goal — recommend tracking as a small follow-up plan/PR rather than reopening Phase 23.

### Human Verification Required

None. All must-haves are verifiable via code, template inspection, and the automated test suite; no visual/real-time/external-service behavior in this phase's scope that grep/tests cannot confirm (server-rendered HTML, no new client-side JS, established codebase conventions for money rendering and Jinja autoescaping already spot-checked).

### Gaps Summary

No gaps. All 5 ROADMAP success criteria hold in the codebase, all 9 requirement IDs (DASH-01..05, HIST-01..04) have concrete, tested implementations, all key links are wired, the full test suite (896 tests) passes, and no debt markers or stub patterns were found in phase-touched files. The only follow-up items are the 3 non-blocking code-review warnings (WR-01/02/03) and the stale REQUIREMENTS.md checkbox state — both informational, not blockers.

---

_Verified: 2026-07-17_
_Verifier: Claude (gsd-verifier)_
