# Milestones

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
