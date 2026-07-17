# Phase 23: Dashboard & History Rebuild - Context

**Gathered:** 2026-07-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Rebuild Главная (home page) from a Phase-1 walking-skeleton stub into an operational dashboard: current date/weekday/time, active catalog number + days until close, day/week/month revenue/profit/expense totals, total distinct product codes in stock + combined valuation, and a recent-operations feed with per-type-adapted columns including customer. Rebuild История from a single generic all-types table into a type-first flow: pick an operation type, see that type's relevant columns, filter by product code/date range/customer/category, sort, and paginate. Both desktop and mobile trees are rebuilt in this phase (mobile Главная and История are currently near-empty/legacy — see decisions below).

**Explicitly NOT in this phase:** No Настройки page (that's Phase 24, NAV-05/06) — the catalog close-date editing UI must fit into an existing page. No changes to the top-level nav structure or mobile nav tabs (NAV-08/MOB-01, Phase 24). No per-warehouse breakdown of stock valuation (DASH-04 reuses the existing whole-inventory `stock_valuation()`). No new "expense" concept beyond the existing cash-ledger definition — no COGS-based expense metric is introduced.

</domain>

<decisions>
## Implementation Decisions

### Active catalog + close date (DASH-02)

- **D-01: Fully manual — both the catalog number and the close date are separate operator-entered fields**, not derived from `scan_catalog_files()`'s PDF-filename scan. Operator explicitly chose this over the researched "hybrid" recommendation (auto-derive number from the newest scanned PDF, manual close date only) — direct control over both fields, no dependency on filename-derived state that could silently point at a superseded catalog if the operator drops a new PDF without updating the linked close date.
- **D-02: Editing lives on the existing `/catalogs` page** (`app/routes/catalogs.py`, `app/services/catalogs.py`), not a new dedicated route and not under Настройки (that page doesn't exist until Phase 24, NAV-05/06). Add the active-catalog-number + close-date fields to that existing page rather than inventing a new small settings page for a single-field edit.
- Empty state (no active catalog configured yet): the rest of the dashboard (DASH-01, 03, 04, 05) must still render independently — a missing catalog is a placeholder, not a blocking error.

### History type-first UX (HIST-01, HIST-02)

- **D-03: Single `/history` route/page — HTMX swaps both the row set AND the column set in place** when a type is selected, extending the existing `history_rows.html` swap-on-filter-change pattern (`app/routes/history.py`, `app/services/operations.py::history_view`). No new per-type routes (`/history/sale`, `/history/receipt`, ...), no client-side CSS/JS column hiding. Existing pagination (`page_window`/`paginate`, Phase 14) and the `/history` URL/query-param contract stay intact.
- **D-04: Before a type is explicitly picked, show today's existing generic view (10 fixed columns, all types combined)** — type selection is an additional refinement the operator can apply, not a mandatory first gate that blocks the page until a type is chosen.
- **D-05 (from the accepted research recommendation the operator did not object to): the customer filter appears only for types that carry `Sale.customer_id` (sale, return); the category filter appears only where `Product.category` is meaningful; the date-range filter stays visible for every type** (the one dimension common to all operation types). This governs how HIST-02's four filters combine with the type-first pivot.
- **D-06 (evidence-based, not separately re-asked): the type-first view and the recent-operations feed (DASH-05) cover the same 6 stock-affecting operation types** — `receipt, sale, writeoff, return, correction, transfer` (`STOCK_AFFECTING_TYPES` in `app/services/ledger.py`). The 3 audit-only types (`price_change`, `product_created`, `product_edited`) carry no `batch_id`/expiry/quantity/cost and are out of scope for type-first browsing — this mirrors STATE.md's note that DASH-05's and HIST-01's per-type column mappings are "the same mapping."

### Dashboard totals & feed (DASH-03, DASH-04, DASH-05)

- **D-07: "Expense" in the day/week/month totals uses the same definition as the Финансы page — cash-ledger withdrawals/returns (`cash_expense_total`)**, not cost-of-goods-sold. Same word, same meaning as the already-shipped Финансы dashboard (Phase 17) — no new "expense" vocabulary introduced.
- **D-08: The "profit" tile shows net profit — gross profit + cash expense — the identical `net_profit_cents = gross + expense` formula already used by `app/routes/finance.py::_metrics_context`** (addition, not subtraction, since `cash_expense_total` is already signed negative — same sign-convention gotcha documented there). Chosen over showing gross profit with expense as an independent, arithmetically-unlinked number, so the dashboard's numbers read consistently with what the operator already sees on Финансы.
- **D-09 (evidence-based, from the accepted research; not a separate open question): the day/week/month totals need a new service function generalizing `_metrics_context`'s single-period composition (`sales_profit_report` + `cash_expense_total` via `local_day_bounds_utc`) to 3 simultaneous periods.** The recent-operations feed reuses `recent_sales`'s Operation→Product join + Operation→Sale→Customer outerjoin shape, generalized from `type == "sale"` to all 6 `STOCK_AFFECTING_TYPES`, `limit=10` rows (mirroring `recent_sales`'s existing limit), each row linkable to `/history?type={op.type}&product={product.id}` using History's existing query-param contract — no new History-side plumbing needed for the link-through. DASH-04's stock valuation reuses `stock_valuation()` as-is (whole-inventory, no per-warehouse breakdown) alongside a new "distinct product codes with quantity > 0" count query (nothing existing computes this count today).

### Mobile scope (DASH/HIST on `/m/`)

- **D-10: Mobile Главная and История get full data parity with desktop — same service calls/data (date/time, catalog countdown, day/week/month totals, valuation, type-adapted feed; type-first filter set including date-range/customer/category; numbered `page_window`/`paginate` pagination) — rendered in mobile's own card/accordion layout, not a squeezed copy of desktop's tile grid/table.** Operator explicitly rejected both a literal 1:1 desktop copy and a cut-down mobile version (skipping week/month tiles or keeping the type-only filter). This follows the established Phase 12-22 pattern: same underlying data everywhere, mobile always gets its own simpler presentation shape, never a reduced data set. As a byproduct, this closes the known pagination generation-gap — mobile history currently still uses the legacy `history_load_more.html` "load more" button instead of the numbered pagination desktop migrated to in Phase 14.

### Claude's Discretion

- Exact Russian field labels/placeholder text for the catalog-number/close-date fields on `/catalogs`, and the exact empty-state wording when no active catalog is configured.
- Exact card/accordion layout for the mobile dashboard tiles and the mobile per-type History cards.
- Whether the recent-operations feed is its own new service function or a generalized variant of `recent_sales` — implementation detail, not operator-visible.
- Which sort options apply per operation type on the rebuilt History page (extending `history_view`'s existing sort allow-list per type) — as long as each type's sort options are sensible for its own columns.
- Whether the customer/category filter controls are hidden entirely or shown disabled/greyed for types where they don't apply (D-05) — as long as they never silently apply to a type they have no data for.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and scope
- `.planning/REQUIREMENTS.md` §Dashboard — DASH-01..05 (lines 21-27), §History — HIST-01..04 (lines 71-76).
- `.planning/ROADMAP.md` §"Phase 23: Dashboard & History Rebuild" — goal, 5 success criteria, depends-on note (Phase 18 for ДЦ/ПЦ-based stock valuation, Phase 22 for the customer-column join pattern).
- `.planning/PROJECT.md` §Current Milestone target features — dashboard/history bullets under "v2.0 UX Overhaul & Navigation Restructure."
- `.planning/STATE.md` §Decisions — "DASH-01..05 and HIST-01..04 combined into one phase (23)" note: both are read-only presentations over the existing ledger, and the per-operation-type column mapping is shared between the dashboard feed and History (D-06 above).

### Prior art this phase extends or replaces
- `app/routes/home.py`, `app/services/ledger.py::ledger_view`, `app/templates/pages/home.html` — the current Phase-1 walking-skeleton home page being fully replaced (shows only the oldest active product + last 50 raw operations, no dashboard content at all).
- `app/routes/history.py`, `app/services/operations.py::history_view`, `app/services/pagination.py` (`page_window`, `paginate`), `app/templates/pages/history.html` + `partials/history_rows.html` — existing join (`Operation→Product` inner, `Operation→Batch` outer) + Phase-14 pagination skeleton that D-03 extends with type-aware column/filter/sort logic, not replaces.
- `app/services/catalogs.py` (`scan_catalog_files`, `list_catalogs`, `get_catalog`, `catalogs_for_code`), `app/routes/catalogs.py`, existing `/catalogs` page — D-02's extension point for the new manual number/close-date fields; today this is 100% filename-derived with no stored metadata.
- `app/routes/mobile_home.py`, `app/templates/mobile_pages/home.html` (static 10-tile grid, zero data) and `app/routes/mobile_history.py`, `app/templates/mobile_pages/history.html` + `mobile_partials/history_cards.html` + `history_load_more.html` (type-filter-only, legacy load-more pagination) — the mobile trees D-10 rebuilds for full parity.

### Precedent patterns to follow
- `app/services/finance_reports.py::cash_expense_total`, `stock_valuation`; `app/routes/finance.py::_metrics_context` (`net_profit_cents = gross + expense`, sign convention documented inline) — the exact formula/definition source for D-07/D-08.
- `app/services/reports.py::sales_profit_report` — gross revenue/cost/profit source for the day/week/month totals.
- `app/core.py::local_day_bounds_utc` — the shared period-boundary helper (Phase 6/17/21 convention) to call 3x (today, current week, current month) for DASH-03.
- `app/services/sales.py::recent_sales` — the `Operation→Product` join + `Operation→Sale→Customer` OUTERJOIN pattern (both hops must stay outer — walk-in sales have NULL `sale_id`/`customer_id`) that D-09's feed query generalizes from `sale`-only to all 6 stock-affecting types.
- `app/models.py` `OPERATION_TYPES` / `OPERATION_TYPE_LABELS`, `app/services/ledger.py::STOCK_AFFECTING_TYPES` — the canonical 6-type set for both the feed and History's type-first menu.
- `app/templates/partials/history_rows.html` — the existing HTMX swap-on-filter-change pattern D-03 extends to also swap the column set.
- `app/routes/reports.py::_resolve_period` — an alternative existing period-preset convention (Monday-start week, calendar month) worth cross-checking against `local_day_bounds_utc`'s week/month boundaries for DASH-03 consistency.

### Money and ledger rules
- `CLAUDE.md` §"What NOT to Use" — integer minor units only; portable SQLAlchemy Core/ORM constructs only; no SQLite-specific SQL.
- `app/services/ledger.py::record_operation` — the single ledger write path; this phase is read-only over the existing ledger except for the new catalog number/close-date fields (D-01), which do not touch `Operation`/ledger tables at all.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/core.py::local_day_bounds_utc` — period-boundary helper, reusable unchanged for DASH-03's 3 simultaneous windows.
- `app/services/pagination.py::page_window`/`paginate` — Phase-14 pagination helper, already wired into desktop History; D-10 brings mobile History onto the same mechanism.
- `app/services/reports.py::sales_profit_report`, `app/services/finance_reports.py::cash_expense_total`/`stock_valuation` — period/point-in-time aggregation services to compose into the new dashboard service.
- `app/services/sales.py::recent_sales` — direct structural precedent for the feed query.
- `app/models.py` `OPERATION_TYPES`/`OPERATION_TYPE_LABELS` — canonical type set/labels already used by History's existing type dropdown.

### Established Patterns
- Server-rendered Jinja2 + HTMX 2.0.10 (vendored, offline). No SPA, no build step, no client-side column-visibility logic (ruled out for HIST-01, D-03).
- Desktop and mobile are fully separate route/template trees (`app/routes/mobile_*.py`, `app/templates/mobile_pages/`, `app/templates/mobile_partials/`) reusing the same underlying service functions — established since Phase 11, unbroken through Phase 22; D-10 follows this unchanged.
- Thin routes, all logic in `app/services/*.py`.
- Money as integer cents throughout; `cash_expense_total` is signed negative, so combining it with gross profit is addition (D-08), not subtraction — a documented gotcha, not a new one.

### Integration Points
- `app/models.py` + new Alembic migration — active-catalog-number/close-date fields or small table (D-01).
- `app/services/catalogs.py` / `app/routes/catalogs.py` / `/catalogs` page — new edit fields (D-02).
- `app/routes/home.py` + a new dashboard service (likely `app/services/dashboard.py` or extending `finance_reports.py`) — full rebuild (DASH-01..05).
- `app/routes/history.py` + `app/services/operations.py::history_view` — extended with type-aware column/filter/sort selection (D-03..D-06).
- `app/routes/mobile_home.py`, `app/routes/mobile_history.py` + their templates/partials — full rebuild for parity (D-10).

</code_context>

<specifics>
## Specific Ideas

- Operator explicitly chose fully-manual catalog number + close-date fields over the researched "hybrid" recommendation (auto-derive the number from the newest scanned PDF) — wants direct control over both fields rather than a value that could silently drift if a new PDF is dropped without an accompanying date update.
- Operator wants the dashboard's "прибыль" tile to read identically to the existing Финансы dashboard's net-profit figure — consistency of vocabulary and numbers across the app mattered more than a single self-consistent revenue−expense=profit tile in isolation.
- Mobile scope: operator explicitly rejected both extremes offered (a literal pixel-copy of desktop, and a deliberately cut-down mobile version) — wants full data parity in the project's established "same data, own simpler presentation" idiom, closing the known mobile-history pagination gap as a byproduct.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope across all 4 discussed areas (active catalog source, History type-first UX, dashboard totals/feed definition, mobile scope). No scope creep occurred.

</deferred>

---

*Phase: 23-Dashboard & History Rebuild*
*Context gathered: 2026-07-17*
