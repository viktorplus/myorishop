# Milestones

## v1.3 Финансы / Касса (Shipped: 2026-07-15)

**Delivered:** A cash ledger (`cash_movements`, append-only) that auto-credits on every sale and auto-debits symmetrically on every return, with the live balance shown in a new «Финансы» section (desktop + mobile); manual withdrawal (mandatory category + comment) and deposit entry with a warn-but-allow negative-balance gate; a paginated/filterable movement history; a period cash-flow report broken down by income vs. expense category; CSV export of period movements; and a Финансы dashboard showing gross profit, net profit, and stock valuation (at cost and at sale price).

**Phases completed:** 3 phases (15-17), 13 plans
**Timeline:** 2026-07-14 → 2026-07-15 (2 days)
**Git range:** `fb60988` (feat(15-01)) → `d34fe1b` (docs(17)) — 142 files changed, +11,114/-10,521 lines, 102 commits
**Known deferred items at close:** 1 carried forward from v1.1 (2 advisory code-review warnings in transfers.py/writeoffs.py, unrelated to v1.3 scope) + 1 new advisory (desktop `/finance` history renders literal `None` for an empty comment; mobile unaffected) + no `17-SECURITY.md` threat-verification pass or `/gsd-audit-milestone` run before close (both skipped by operator decision at completion time)

**Key accomplishments:**

- `CashMovement` model + append-only `cash_movements` ledger (migration 0013) mirroring the existing `Operation` ledger's sync-ready shape (UUID PK, device_id/seq, DB-level no-update/no-delete triggers) but with no cached balance column — balance is always a live `SUM(amount_cents)`.
- `app/services/finance.py` as the single sanctioned cash write path (`record_cash_movement`, `compute_balance`), wired into `register_sale`/`register_return` at the service layer so both desktop and mobile callers credit/debit for free, with the return debit always recomputed from the return's own qty × the origin sale's frozen unit price.
- New «Финансы» section (desktop nav + mobile hub tile) showing the live «Баланс кассы».
- Manual cash movements: `record_manual_movement` with server-applied sign, a mandatory-category gate on withdrawal, and a warn-but-allow negative-balance check matching the existing oversell/min-price pattern; shared `finance_base`-parameterised form partials reused verbatim across desktop `/finance` and mobile `/m/finance`.
- Paginated/filterable cash history: desktop numbered pagination (mirrors Phase 14's `pagination.html`), mobile cards + «Показать ещё» load-more — both filterable by a coarse `CASH_BUCKETS` category grouping.
- `app/services/finance_reports.py`: `cash_expense_total`, `stock_valuation`, and `cash_flow_report` — read-only aggregation services reusing `sales_profit_report` and the existing period-filter/local-day-boundary helpers; net profit computed as `gross_profit + cash_expense_total` (rows already signed negative).
- Финансы dashboard tiles (gross profit, net profit, stock valuation at cost and at sale price) on both `/finance` and `/m/finance`, plus a period cash-flow report page and CSV export (`/finance/report`, `/finance/report.csv`) reusing the existing BOM/semicolon/formula-escape export convention.
- Gap-closure plan 17-05 added missing navigation entry points to the new report pages (desktop top-nav item, mobile home tile, dashboard buttons), found by UAT Test 2.

---

## v1.2 Catalog Pricing UX & List Ergonomics (Shipped: 2026-07-14)

**Delivered:** Formalized catalog/consultant-price and name autofill by product code across the product-add form, goods receipt (desktop + mobile), and sales page (name↔code cross-autofill); closed mobile wizard context/navigation gaps (visible code/name/warehouse, uniform Назад, basket step indicator, search quick actions); added pagination, filtering, and sorting to every list page plus stock-guarded quick-delete for warehouses and products.

**Phases completed:** 3 phases (12-14), 17 plans, 41 tasks
**Timeline:** 2026-07-13 → 2026-07-14 (2 days)
**Git range:** `a058bac` (feat(12-01)) → `537316c` (chore(catalogs)) — 186 files changed, +12,808/-882 lines, 142 commits
**Known deferred items at close:** 1 carried forward from v1.0 (Phase 1 offline run.bat human-verification, still not executed) + 2 advisory (non-blocking) code-review warnings in transfers.py/writeoffs.py from v1.1 (batch-ownership leak, unstripped qty echo) — unrelated to v1.2 scope

**Key accomplishments:**

- Extended receipt lookup to combine Dictionary name and CatalogPrice cost/catalog for codes unknown to Product, wired into the desktop OOB-fill route/template, and formalized the already-shipped product-add autofill (PRICE-02/PRICE-03) with traceability comments.
- Mobile goods-receipt step 2 now resolves cost/sale/catalog via a single `lookup_prefill()` call and forwards them as hidden fields that pre-fill step 3, plus step 3 always shows a visible bolded product code (and name when known).
- Debounced name-fragment search on the sales page rendering a click-to-select, mark-highlighted dropdown of matching code+name rows, wired as a shared partial so it survives both the initial basket-row render and every subsequent code-triggered /sales/lookup OOB swap.
- Mobile sale and transfer wizards now show the product name alongside its code on every step from the batch step onward, using only data each handler already fetches — zero new SQL lookups.
- Corrections wizard's Партия/Режим/Значение steps now show visible code/name/warehouse context via a new shared `_wizard_header.html` partial, and all 4 steps' "Назад" buttons target their own immediate predecessor via hx-get/hx-post + fragment swap instead of a plain link that reset to step 1.
- Write-off wizard migrated from its old full-page-per-step architecture (per-step `{% extends %}` templates, `history.back()` for "Назад") to the persistent-shell + htmx-fragment-swap architecture every other mobile wizard uses, gaining visible code/name/warehouse context on all 3 intermediate steps along the way.
- Receipts wizard's step 2 "Назад" converted from a plain full-page link to the same hx-get + fragment pattern used everywhere else in the phase, GET /m/receipts now accepts a ?code= pre-fill and serves both a full page and a bare fragment, and step 2 now shows the same visible code/name/warehouse header as every other fixed wizard's Партия step.
- Converted transfers wizard step 2's plain `<a>` "Назад" link to an explicit `hx-get="/m/transfers"` + `hx-vals` request, and extended `GET /m/transfers` to accept an optional `?code=` query param served as both a full page and a bare HX-Request fragment.
- Adds a "Корзина" step-indicator to the mobile sale wizard's basket screen and unconditional Продать/Принять quick-action links (with `?code=` pre-fill) from the mobile search product-detail screen
- Sale wizard now shows a `Склад:` (warehouse) line at every step -- per-card on the multi-warehouse batch-pick step, and a single line on qty-price/basket -- closing the last remaining Phase 13 Success Criterion #1 gap (UI-02).
- Shared `app/services/pagination.py` (LIST_PAGE_SIZE=20, ellipsis-aware `page_window()`, clamping `paginate()`), a copy-paste-ready `partials/pagination.html` bar with 4 new structural CSS rules, and `Dictionary.name_lc` (migration 0012, Python-backfilled Cyrillic-safe) for Wave 2's six list pages to build on.
- Migrated `/history`'s offset+has_next "Показать ещё" pagination onto the shared total-count page-number pagination bar, moved its type/product filters from a standalone `.filter-bar` into a header-row filter shape, and added a "Сортировать по" newest/oldest sort dropdown — all inside one swappable `#history-rows` block.
- `list_entries()` rewritten as an SQL LIMIT/OFFSET + COUNT query with Cyrillic-safe name filtering and allow-listed sort, plus header-row code/name filters and a sort dropdown wired into `/dictionary` via the shared `pagination.html` partial.
- New `list_products_view()`/`quick_delete_product()` catalog service functions power a filterable, sortable, paginated `/products` list with a one-click stock-guarded quick-delete, while the existing search/mobile/sales code paths stay byte-for-byte unchanged.
- `/warehouses` gains header-row name/address/status filters, a sort dropdown, numbered pagination, and a per-warehouse stock quick-delete guard that runs before the existing last-active-warehouse guard — quick-deleted warehouses now disappear from the default view and are reachable only via `status=Удалённые`.
- New `list_customers_view()` gives `/customers` independent per-column filters (name/surname/consultant number), an allow-listed sort dropdown, and page-number pagination — while `search_customers`/`customer_search_view` stay byte-for-byte unchanged for the sale-form customer picker, and the now-redundant `/customers/search` route is retired.
- `/catalogs` gained year filtering, newest/oldest sorting, and page-number pagination by pre-slicing the flat catalog list inside `list_catalogs()` before the existing per-year `<table>` grouping loop (now extracted into `partials/catalog_rows.html`) ever sees it — so a 20-row page boundary falling mid-year never leaves an unclosed `</table>`.

---

## v1.0 MVP (Shipped: 2026-07-10)

**Delivered:** A local-first warehouse inventory app — catalog, goods receipts, sales with customer linking, write-offs/returns/corrections, full operation history, period reports, and CSV export — all backed by an append-only, sync-ready ledger.

**Phases completed:** 6 phases, 31 plans, 72 tasks
**Timeline:** 2026-07-08 → 2026-07-10 (3 days)
**Git range:** `93c910e` (feat(01-02)) → `f0d35fb` (docs(phase-06)) — 263 files changed, ~35,500 insertions, ~9,000 LOC Python
**Known deferred items at close:** 1 (see STATE.md Deferred Items — Phase 1 offline run.bat human-verification not yet executed)

**Key accomplishments:**

- uv project on Python 3.13.13 with hash-pinned FastAPI/SQLAlchemy/Alembic stack, vendored htmx 2.0.10, and a 4-file RED pytest suite locking the FND-01/02/03 ledger contract for Plans 01-02/01-03
- Sync-ready SQLite schema live: SQLAlchemy 2.0 models with UUID4 TEXT PKs / integer cents / UTC ISO text, per-connection WAL+FK PRAGMAs, and Alembic migration 0001 installing DB-level append-only triggers plus a seeded demo product
- Walking skeleton complete: record_operation as the sole ledger write path, HTMX-driven GET / + POST /ops UI showing who/when and recomputed stock, and run.bat migrate-serve-open launcher — full suite GREEN, ruff clean
- Product cards with code/name/category/three-price fields creatable at /products/new and listed at /products, backed by migration 0002, a Cyrillic-safe name_lc shadow column, an atomic product_created ledger op, and the IN-01 deleted-product guard in the single write path
- Product cards editable at /products/{id}/edit with every price change preserved as an immutable price_change ledger op rendered as «История цен» (when/who/field/old → new), plus hx-confirm soft delete and one-click restore via HX-Redirect
- Ranked instant search on /products: Cyrillic case-insensitive matching via the Python-lowered name_lc shadow column, exact-code > code-prefix > name-substring ordering, LIKE-wildcard-safe, capped at 20 rows, with debounced HTMX partial updates and autoescaped `<mark>` highlighting
- Code→name reference dictionary at /dictionary with inline add/edit, plus debounced HTMX autofill that fills an empty product-form name from a known code via the 200-fragment/204 contract
- Save-and-next goods receipt entry at /receipts/new: one immutable ledger receipt op per save, product auto-creation for unknown codes in the same transaction, and a last-10 receipts list refreshed out-of-band
- Typing a code on /receipts/new auto-fills the name (dictionary) or name + empty price fields (existing card) via a 204-contract lookup, and saving a receipt for an existing product updates the card prices through price_change ops in the same transaction
- VACUUM INTO backups on every app start (gated, pruned to 30) plus a one-click /backup page and restore.bat with -wal/-shm cleanup, proven by an automated backup→restore roundtrip test that also confirms append-only triggers survive
- Customer + Sale models, Operation.sale_id link column, record_operation(sale_id=) kwarg, migration 0004, and the phase-wide RED test contract for the sales/customers vertical slice.
- Multi-line walk-in sale basket (service + routes + templates): entered price and frozen cost snapshot per line, one-transaction commit, «Продажи» nav wiring, and an oob-refreshed recent-sales list.
- Aggregate oversell check in register_sale (sums duplicate lines before comparing to stock) with a warn-then-confirm HTMX flow that writes zero sale ops until the operator explicitly confirms.
- Full customer CRUD at `/customers` with Cyrillic-safe instant search (Python-folded `search_lc` shadow) and a customer detail page showing frozen-price purchase history via an Operation→Sale→Product join.
- Sale-form customer header (Cyrillic autocomplete search + inline quick-create + selected chip with hidden customer_id) backed by two thin picker endpoints reusing the 04-04 customers service — walk-in stays valid with zero extra writes.
- GET /sales/lookup now binds `code[]`/`name[]`/`price[]` via FastAPI `Query(alias=...)`, closing the Phase 4 UAT gap where the basket's per-line code lookup never autofilled «Название» because the route only declared bare, unaliased query param names.
- WRITEOFF_REASONS + OPERATION_TYPE_LABELS RU-label constants wired as Jinja globals, plus four Wave-0 RED test files (test_writeoffs/returns/corrections/history) that fix the OPS-01..04 interface contract before any service exists.
- Write-off vertical slice (OPS-01): `register_writeoff()` writes one `writeoff` op (qty_delta<0) through `record_operation`, `/writeoff` routes + 5 templates reuse the receipt save-and-next form and the Phase-4 sale oversell warn-but-allow pattern, with a server-side WRITEOFF_REASONS allow-list and no price fields.
- Sale-linked return vertical slice (OPS-02): `register_return()` writes one `return` op (qty_delta>0) copying the FROZEN origin sale op's unit_price_cents/unit_cost_cents through `record_operation`, `/returns` routes + a compact return-form template reuse the recent-sales/purchase-history entry points, with a server-enforced returnable cap (sold − already-returned) and no editable price field.
- Two-mode stock correction (OPS-03): `register_correction()` writes exactly one `correction` op via `record_operation` — counted mode computes `qty_delta = counted − current cached quantity`, delta mode writes the signed value as-is, a zero net delta is rejected with zero writes — `/corrections` routes + a mode-toggle form template, and the walking-skeleton `POST /ops` is deleted so `/corrections` is the single correction path (D-12).
- The authoritative /history audit trail (OPS-04): a paginated (fetch-one-extra sentinel, 50/page), type+product-filterable read over every operation across every product, newest-first, with RU-labeled types, signed quantities, cents-formatted price/cost with an em-dash fallback, and a payload-derived reason column — completing all four Phase 5 requirements (OPS-01..04) and the "История" nav link (D-17).
- Closed the OPS-01 UI gap: base.html nav bar and home.html now both link to /writeoff, with a regression test guarding against it silently regressing again.
- Fixed GET /returns's origin-not-found 404->422 (htmx-swap discard bug) and added defensive session.rollback() to all three write routes' bare exception handlers, closing CR-02/CR-03/WR-03 from the code review.
- Closed the last blocking gap-closure item (CR-01) by keying `/history`'s chrome-vs-partial decision solely on the real `HX-Request` header, so a plain top-level reload/bookmark/shared filtered URL always gets the full navigable page instead of a bare rows fragment a real browser silently drops.
- Moved the /history "Показать ещё" pagination control out of `<tbody id="history-tbody">` into its own `<tfoot>`, fixing a bug where any filter-select change permanently destroyed the control on a >50-row filtered result set (new CR-01/OPS-04), plus the related button-click reposition defect (WR-01).
- Migration 0005 + Product/Settings threshold fields + product-form UI wiring so RPT-02 (low-stock) and RPT-04 (stale-products) have a per-product "effective threshold" (own value if set, else global default) to read from.
- local_day_bounds_utc half-open UTC boundary helper, NULL-cost-safe sales_profit_report aggregation, and /reports + /reports/sales with a shared one-code-path period filter (preset buttons + от/по dates)
- GET /reports/stock with a Pitfall-3-safe effective-threshold low-stock action list (explicit 0 never falls back to global default) plus the full active-product stock table.
- Three streaming CSV exports (products/sales/customers) with BOM-once utf-8-sig encoding, semicolon delimiter, and formula-injection hardening, served from a dedicated /export page with plain (non-htmx) download links
- GET /reports/writeoffs groups period write-offs by the exact Phase 5 WRITEOFF_REASONS categories, in their declared key order, reusing Plan 06-02's period filter and local-day boundary math unchanged.
- GET /reports/products with SQL-side top-selling ranking (func.sum/.group_by()/.order_by()/.limit()) and an always-current, LEFT-OUTER-JOIN-based stale/never-sold products list honoring per-product zero-day overrides — the phase's final plan.

---

## v1.1 Multi-Warehouse & Batch Tracking (Shipped: 2026-07-13)

**Delivered:** Multi-warehouse stock organization, batch/lot-level tracking with expiry dates and per-batch pricing (mandatory manual selection at every stock-affecting operation), category browsing, minimum-price guardrails, warehouse-to-warehouse transfers preserving cost history, an expiring-batches report, and a dedicated mobile flow — simplified single-purpose screens for every core operation, additive to the unchanged desktop UI.

**Phases completed:** 5 phases (7-11), 28 plans
**Timeline:** 2026-07-10 → 2026-07-13 (3 days)
**Git range:** `95455f6` (docs(07): create phase plan) → `97b8c38` (docs(phase-11): add security threat verification) — 254 files changed, +28,067/-340 lines, 249 commits
**Known deferred items at close:** 1 carried forward from v1.0 (Phase 1 offline run.bat human-verification, still not executed) + 2 advisory (non-blocking) code-review warnings in transfers.py/writeoffs.py (batch-ownership leak, unstripped qty echo)

**Key accomplishments:**

- "Товары на складе" category-grouped browsing page and an optional per-product minimum sale price that warns-but-allows underselling, same pattern as the existing oversell guardrail (Phase 7, CAT-01/PRICE-01)
- Full warehouse CRUD with soft-delete/restore, migrated on top of a seeded default warehouse so every pre-existing v1.0 stock row attributes cleanly with zero data loss (Phase 8, WH-01)
- Batch/lot tracking woven into the append-only ledger: every product code can carry multiple batches (warehouse, expiry, price, comment), and every stock-affecting operation — sale, write-off, return, correction — requires picking a specific batch with oversell/over-removal warnings scoped to that batch, not the product total (Phase 9, WH-02/LOT-01..05)
- Warehouse-to-warehouse transfers that preserve the moved batch's original cost/price history instead of resetting it, recorded in operation history like any other op, plus a read-only expiring-batches report (Phase 10, WH-03/LOT-06)
- A dedicated mobile flow — not a CSS reflow — with simplified single-purpose wizards for search, receipts, sales, write-offs/returns/corrections, transfers, and history, each reusing the same batch-picker and guardrail logic as desktop, fully additive with the unchanged desktop layout (Phase 11, UI-01)
- Closed 4 UAT-found gaps in the batch-tracking phase (htmx OOB batch-picker duplication, missing /history return-entry link, receipt batch-chooser UX, missing batch name field) and 1 blocker + 1 major UAT gap in the mobile phase (invisible batch-card text, sale wizard's Назад skipping the batch step)
- Security threat verification completed for the mobile flow (11-SECURITY.md, 2026-07-13); 6/6 UAT scenarios passed on re-test

---
