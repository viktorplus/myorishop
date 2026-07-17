# MyOriShop — Oriflame Warehouse Inventory

## What This Is

A warehouse inventory and sales tracking application for a single Oriflame reseller. It manages product stock, goods receipts, sales, customers, and reports — running locally without internet, with a browser-based UI. Future versions add multi-operator sync across countries via a central server.

## Core Value

The operator can quickly and reliably record receipts and sales so stock counts and profit figures are always correct — without losing any data.

## Current State

**Shipped: v2.0 UX Overhaul & Navigation Restructure (2026-07-17)**

Delivered the two-price model consolidation (ДЦ/ПЦ with a colour cue against the catalog reference, editable everywhere), a code-grouped products page with batch breakout, warehouse CRUD via dedicated forms plus batch-split transfers, extended customer profiles (multi-value contacts, address, spend/favorites), a rebuilt sales page (plain table, live running total, single new/existing/anonymous control), a rebuilt Главная/История, and a full navigation restructure nesting every secondary action under its owning page with a new Настройки hub and mobile tab parity. All 46 requirements (NAV-01..08, DASH-01..05, PROD-01..08, WH-01..03, XFER-01, SALE-01..07, CUST-01..08, HIST-01..04, RPT-01, MOB-01) shipped complete. `/gsd-audit-milestone` passed with status `tech_debt` (no blockers): 46/46 requirements satisfied, cross-phase integration PASS, 919/919 tests green. One open item carried forward: Phase 22 (Sales) has 4 human-verification test cases never confirmed in a live browser (unlike the equivalent Phase 18/20 items, both UAT-confirmed) — see `.planning/v2.0-MILESTONE-AUDIT.md`. See `.planning/milestones/v2.0-ROADMAP.md`, `v2.0-REQUIREMENTS.md`, and `.planning/MILESTONES.md` for full details.

**Shipped: v1.3 Финансы / Касса (2026-07-15)**

Delivered a cash ledger (`cash_movements`, append-only) that auto-credits on every sale and auto-debits symmetrically on every return, with the live balance shown in a new «Финансы» section (desktop + mobile); manual withdrawal (mandatory category + comment) and deposit entry with a warn-but-allow negative-balance gate; a paginated/filterable movement history; a period cash-flow report broken down by income vs. expense category; CSV export of period movements; and a Финансы dashboard showing gross profit, net profit, and stock valuation (at cost and at sale price). All 12 requirements (FIN-01..12) shipped complete. No `/gsd-audit-milestone` or `17-SECURITY.md` threat-verification pass was run before close (operator chose to skip both gates). See `.planning/milestones/v1.3-ROADMAP.md`, `v1.3-REQUIREMENTS.md`, and `.planning/MILESTONES.md` for full details.

## Current Milestone

None yet — v2.0 shipped 2026-07-17. Run `/gsd-new-milestone` to scope the next milestone (multi-operator sync, multi-currency, and user roles are the leading candidates — see Future below).

<details>
<summary>Archived: v2.0 UX Overhaul & Navigation Restructure (SHIPPED 2026-07-17)</summary>

**Goal:** Rework navigation into nested/secondary menus, add an operational dashboard to the home page, unify the product price model to two fields (cost/sale), and rebuild the Products/Warehouses/Sales/History/Customers pages around the operator's real workflow instead of their original one-feature-at-a-time shape.

**Target features (all delivered):**
- Home-page dashboard: current date/weekday/time, active catalog number + days until it closes, day/week/month totals (revenue, profit, expenses), total stock codes + valuation, an enriched recent-operations feed (type-specific columns including customer)
- Navigation restructured into nested menus: Приход/Списание/Справочник under Товары; Склады/Резервные копии under Настройки; Экспорт under Резервные копии; Перемещение under Товар
- Products page: remove the "Добавить товар" button (receipt already covers it), delete becomes a text link (not a button), rows grouped by product code showing total quantity across batches (batches broken out with their own expiry/name), price model collapsed to exactly two fields — ДЦ (cost) and ПЦ (sale price) — editable at any stage (product card, receipt, sale) with color-coded deviation from the dictionary's reference price, category shown and filterable
- Warehouses page rebuilt: add/edit/delete via links into dedicated forms, delete only when the warehouse holds no stock, list shows item count + last-receipt date per warehouse
- Transfers: fix the batch-split scenario when moved stock has a different expiry date or condition than the source batch
- Sales page rebuilt: code/name/qty/price table, a live running total shown directly under the form, a new/existing/anonymous customer flow with autocomplete on existing, customer name shown in the recent-sales list
- Customers: extended profile (multiple phones/Telegram/emails/social profiles/address) plus purchase stats and recommendations (last order date, spend by month/quarter/year, favorite products by frequency/quantity)
- History page rebuilt: nested menu by operation type with type-specific columns, filters (code/date/customer/category), sort, pagination
- Reports: a "Back to Reports" navigation link from any report detail page
- Mobile navigation reaches parity with desktop's main tabs (excluding Настройки)

</details>

<details>
<summary>Archived: v1.3 Финансы / Касса (SHIPPED 2026-07-15)</summary>

**Goal:** Ввести кассу как агрегированный учёт денежных средств — автопополнение с каждой продажи, расход с обязательным указанием назначения, история движений и баланс — в виде отдельного модуля «Финансы».

**Target features (all delivered):**
- Касса пополняется автоматически с каждой продажи и списывается автоматически при возврате товара (текущий баланс)
- Списание из кассы с указанием категории (оплата поставщику / зарплата / аренда / коммунальные / прочее) и комментарием; ручное пополнение (начальный остаток/корректировка)
- История движений кассы (приход с продаж + расход по категориям), отчёт за период, CSV-экспорт
- Отдельный раздел UI «Финансы»: баланс кассы, валовая и чистая прибыль за период, стоимость товара на складе (по закупочным и по продажным ценам)

</details>

<details>
<summary>Archived: v1.1 Multi-Warehouse & Batch Tracking (SHIPPED 2026-07-13)</summary>

**Goal:** Support multiple physical warehouses with in-warehouse locations, batch/lot-level stock (distinct expiry dates and prices per batch, chosen manually at sale time), category browsing, minimum-price guardrails, and a dedicated mobile flow.

**Target features (all delivered):**
- Multiple warehouses, each stock item tagged with a free-text storage location
- Stock transfer between warehouses (moves quantity from one warehouse/batch to another without erasing cost/price history)
- "Товары на складе" page grouping products by category/rubric
- Batch/lot tracking: one product code can have several batches with different expiry dates and prices; operator manually picks a batch at sale time from a list showing price, expiry, remaining quantity, and comment
- Batch selection also applies to write-offs, returns, and stock corrections (not just sales)
- Optional expiry date per batch, plus an "expiring soon" report
- Optional per-product minimum sale price — selling below it shows a warning but allows override (same pattern as oversell)
- Optional free-text comment per batch, shown in the sale-time batch picker
- A dedicated mobile flow: simpler single-purpose screens/steps for core operations, instead of squeezing the same dense desktop pages into a phone screen via CSS alone

</details>

<details>
<summary>Archived: v1.2 Catalog Pricing UX & List Ergonomics (SHIPPED 2026-07-14)</summary>

**Goal:** Finish the ad-hoc catalog/pricing feature (extend autofill to goods receipt, add name autofill), close the mobile wizard context gaps found on audit, add code/name cross-autofill and pagination/filter/sort to sales and every list page, and add quick-delete to warehouse/product lists.

**Target features (all delivered):**
- Catalog/consultant price + name autofill by product code on both the product-add form and goods receipt (desktop + mobile), for codes not yet in the product catalog
- Mobile wizards (sale/receipt/writeoff/correction/transfer) show product code/name/warehouse at every step, consistent "Назад" navigation, sale basket gets a step indicator, quick actions from search detail
- Sales page: name-on-code and code-dropdown-on-name-fragment autocomplete
- Pagination on every list page
- Filtering and sorting on every list page
- Quick delete for warehouses and products directly from their list pages

</details>

## Requirements

### Validated

- ✓ Operation audit log (who did what and when) — Phase 1 (append-only ledger with created_by/created_at, visible in UI)
- ✓ Product catalog: code, name, category, prices; editable product cards with soft delete/restore and price history — Phase 2
- ✓ Reference dictionary: product code → name with debounced auto-fill (never overwrites typed name) — Phase 2
- ✓ Fast search by code/name with in-place HTMX updates and match highlighting — Phase 2 (part of operator UI requirement)
- ✓ Goods receipt: add stock by product code with quantity/cost/catalog/sale price, dictionary auto-fill, price history preserved — Phase 3 (RCP-01, RCP-02)
- ✓ Automated WAL-safe backups (VACUUM INTO) with proven restore path — Phase 3 (BCK-01)
- ✓ Sales: by product code with auto-fill, custom sale price, optional customer link, oversell warning, frozen cost/price snapshot per line — Phase 4 (SAL-01..05)
- ✓ Customer profiles (name, surname, consultant number) and purchase history (what/when/at what price) — Phase 4 (CST-01, CST-02)
- ✓ Other operations: write-off, sale-linked return, stock correction — all logged in operation history, with a dedicated /history browsing view (OPS-01..04) — Phase 5
- ✓ Reports: day/week/month/custom period — sales, profit, stock levels, write-offs, top products, stale products, low-stock items — Phase 6 (RPT-01..04)
- ✓ Data export: full products/sales/customers dump as three Excel-compatible CSV files — Phase 6 (BCK-02)
- ✓ Simple operator UI: minimal clicks, autocomplete, oversell warnings — delivered incrementally across Phases 2-5
- ✓ "Товары на складе" page groups products by category/rubric — Phase 7 (CAT-01)
- ✓ Optional minimum sale price per product — selling below it warns but allows override, same pattern as oversell — Phase 7 (PRICE-01)
- ✓ User can create and manage multiple warehouses — Phase 8 (WH-01)
- ✓ Stock item has an optional free-text storage location tag within its warehouse — Phase 9 (WH-02)
- ✓ User can transfer stock (a batch or part of it) from one warehouse to another without losing cost/price history — Phase 10 (WH-03)
- ✓ Product code can have multiple batches (lots) with distinct expiry date and price — Phase 9 (LOT-01)
- ✓ At sale, operator sees a list of matching batches (price, expiry, remaining qty, comment) and manually selects one — Phase 9 (LOT-02)
- ✓ Optional expiry date field per batch — Phase 9 (LOT-03)
- ✓ Optional free-text comment per batch, shown in the sale-time batch picker — Phase 9 (LOT-04)
- ✓ Write-off, return, and stock correction also require selecting the specific batch, not just the product — Phase 9 (LOT-05)
- ✓ Report of batches with an approaching/passed expiry date — Phase 10 (LOT-06)
- ✓ Dedicated mobile flow — simpler single-purpose screens/steps for core operations, not a CSS-only adaptation of the desktop pages — Phase 11 (UI-01)
- ✓ Catalog/consultant price + name autofill by product code on the product-add form and goods receipt (desktop + mobile), for codes not yet in the product catalog — Phase 12 (PRICE-02, PRICE-03, PRICE-04)
- ✓ Sales page name-on-code and code-dropdown-on-name-fragment autocomplete — Phase 12 (SAL-06)
- ✓ Every list page (products, warehouses, customers, dictionary, catalogs, history) paginates 20 rows/page, filters by its relevant columns, and sorts via a dropdown — Phase 14 (LIST-01, LIST-02, LIST-03)
- ✓ Quick-delete a warehouse directly from its list row, guarded by a non-overridable stock check — Phase 14 (LIST-04)
- ✓ Quick-delete a product directly from its list row, guarded by a non-overridable stock check — Phase 14 (LIST-05)
- ✓ Cash ledger: auto-credit on every sale, symmetric auto-debit on return, current balance shown in a new «Финансы» section — Phase 15 (FIN-01, FIN-02, FIN-06)
- ✓ Manual cash movements: withdrawal with mandatory category + comment, manual deposit, warn-but-allow negative balance, paginated/filterable history (desktop `/finance` + mobile `/m/finance`) — Phase 16 (FIN-03, FIN-04, FIN-05, FIN-07)
- ✓ Period cash-flow report (income vs. expense by category) and CSV export of cash movements — Phase 17 (FIN-08, FIN-09)
- ✓ Финансы dashboard: gross profit, net profit, and stock valuation (at cost and at sale price) for a selected period — Phase 17 (FIN-10, FIN-11, FIN-12)
- ✓ Products page groups rows by product code with a total-quantity column, batches broken out per code (expiry/name) in a collapsed expander; "Добавить товар" removed, delete is a text link; category display/filter unchanged — Phase 19 (PROD-01, PROD-02, PROD-03, PROD-04, PROD-08)
- ✓ Product pricing reduced to exactly two fields — ДЦ (cost) and ПЦ (sale) — editable from product card/dictionary/receipt/sale, with a colour cue against the catalog reference price; `min_sale_cents` guardrail kept, PRICE-01 regression intact — Phase 18 (PROD-05, PROD-06, PROD-07)
- ✓ Warehouse list shows item count + last-receipt date; add/edit/delete via dedicated forms; delete blocked while stock > 0; batch-split transfer under a different expiry/condition creates a new destination batch without corrupting the source — Phase 20 (WH-01, WH-02, WH-03, XFER-01)
- ✓ Customer profile supports multiple phones/Telegram/emails/social links and a physical address; shows most-recent-order date, month/quarter/year spend totals (net of returns), and favorite products ranked by frequency then quantity — Phase 21 (CUST-01..08)
- ✓ Sales page rebuilt as a code/name/qty/price table with a live running total shown directly under it, and a new/existing/anonymous customer flow (radio control, autocomplete on existing, inline optional fields on new) replacing the old free-text customer field; recent-sales list shows each sale's customer name — Phase 22 (SALE-01..07)
- ✓ Home-page dashboard: date/weekday/time, active catalog number + days until close, day/week/month revenue/profit/expense totals, total stock codes + valuation, type-adaptive recent-operations feed with customer column — Phase 23 (DASH-01..05)
- ✓ History page rebuilt: operation-type-first selection with type-specific columns, filters by code/date-range/customer/category, sort, pagination (desktop + mobile parity) — Phase 23 (HIST-01..04)
- ✓ Top-level navigation reduced to 8 first-class pages (Главная, Товары, Продажи, Покупатели, История, Отчёты, Финансы, Настройки); Приход/Списание/Справочник nested under Товары, Перемещение under the product context, Склады/Резервные копии under a new Настройки page, Экспорт under Резервные копии, a back-link on every report detail page, mobile nav parity (7 tabs, excluding Настройки) — Phase 24 (NAV-01..08, RPT-01, MOB-01)

### Active

None yet — v2.0 shipped 2026-07-17, next milestone not scoped. Run `/gsd-new-milestone` to define the next set of requirements.

### Future (next milestone, deferred)

- [ ] Multi-operator sync across countries via a central server, server-based (online) + USB flash-drive (offline) (SYNC-V2-01)
- [ ] Multi-currency support (CUR-V2-01)
- [ ] User roles: administrator, operator, report viewer (AUTH-V2-01)
- [ ] Customer purchase-frequency analysis and "running low" reminders (CST-V2-01)
- [ ] On goods receipt, show customers likely interested in the product based on purchase history (CST-V2-02)
- [ ] CSV export includes warehouse/batch columns (EXP-V2-01)
- [ ] Mobile CRUD parity: warehouses, products/catalog, customers, dictionary, full reports (deferred from v1.2 mobile audit)

### Out of Scope

- Barcodes — no scanner hardware; code entry is fast enough for one operator
- Oriflame campaign catalog integration — not needed for core value
- Automatic FEFO/FIFO batch selection — v1.1 introduced batches (LOT-01..06) but selection stays manual (operator picks the batch)
- Invoicing/payments, notifications — not needed for core value
- Excel/CSV import of initial data — no existing data; everything entered manually from scratch (user decision)

## Context

- Idea document: `agent.md` in repo root (detailed feature spec in Russian).
- The user is learning programming; the stack and code should stay simple and beginner-friendly.
- Architecture must not paint us into a corner: local-first design (SQLite + operation/event log) should keep the door open for later server sync (PostgreSQL) without rework.
- **v1.0 shipped 2026-07-10** (started 2026-07-08, 3 days): 6 phases, 31 plans, 263 files changed, ~35.5k insertions, ~9,000 LOC Python.
- **v1.1 shipped 2026-07-13** (started 2026-07-10, 3 days): 5 phases (7-11), 28 plans, 254 files changed, +28,067/-340 lines, 249 commits. Stack held unchanged: FastAPI + SQLAlchemy 2.0 + SQLite (WAL) + HTMX 2.0.10 (vendored) + Jinja2, uv, Alembic. UAT (6/6 passed) and a security threat-verification pass both completed 2026-07-13.
- One Phase 1 human-verification item (offline `run.bat` launch + browser correction flow + restart persistence) remains unexecuted since v1.0 close — still deferred (see STATE.md Deferred Items). Recommend running it before relying on the app for real daily data entry.
- Two advisory (non-blocking) code-review warnings remain in `transfers.py`/`writeoffs.py` from Phase 10 (batch-ownership leak, unstripped qty echo) — revisit if those files are touched again.
- **Phase 12 shipped 2026-07-13**: catalog/name autofill extended to goods receipt (desktop + mobile) and sales-page name↔code cross-autofill. Code review caught a genuine data-loss bug (CR-01: mobile receipt wizard silently discarded operator-typed prices on a Назад→Далее round trip) — fixed and re-verified before phase completion, along with 3 other warnings (misleading autofill hint text, dead code branch, missing row-ID validation on a new HTMX partial).
- **Phase 13 shipped 2026-07-14**: mobile wizard context/navigation gaps closed (UI-02..05) — all 5 wizards (sale/receipt/write-off/correction/transfer) now show code/name/warehouse as visible text, use a uniform hx-get/hx-post "Назад" pattern (write-off's `history.back()` retired), sale basket has a step indicator, and search product-detail links jump straight into sale/receipt. First-pass verification found the sale wizard alone missing the warehouse line; gap-closure plan 13-06 fixed it and re-verification passed 4/4. Code review: 0 critical, 6 advisory warnings carried/found (e.g. inconsistent "Далее" batch-pick guards across wizards) — non-blocking.
- **Phase 14 shipped 2026-07-14 (final phase of v1.2)**: pagination/filter/sort added uniformly to all six list pages (products, warehouses, customers, dictionary, catalogs, history) via a shared `app/services/pagination.py` helper — SQL LIMIT/OFFSET for the two large lists (dictionary's 6,856 rows, history), Python-side slicing for the four small ones. Quick-delete added to warehouse and product lists (LIST-04/LIST-05), each with a new non-overridable stock guard checked ahead of any existing soft-block guard. Code review found 1 genuine blocker (filter/sort/page state was dropped on write-response re-render, silently hiding row-specific error/blocked messages off the reset default page) — fixed and behaviorally re-verified end-to-end before phase completion, along with 3 advisory warnings (missing `autoescape` on a filter, a template gate ordering issue, a line-length lint fix).
- **v1.2 shipped 2026-07-14** (started 2026-07-13, 2 days): 3 phases (12-14), 17 plans, 41 tasks, 186 files changed, +12,808/-882 lines, 142 commits. Stack held unchanged. Milestone audit (`/gsd-audit-milestone`) passed clean: 13/13 requirements satisfied across three independent sources (REQUIREMENTS.md traceability, VERIFICATION.md, SUMMARY.md frontmatter), cross-phase integration checker found no wiring gaps or broken flows across Phase 12→13→14 (autofill → wizard context → list management). Phases 12/13 carry a discovery-only Nyquist gap (draft VALIDATION.md, `nyquist_compliant: false`) — both independently verified passed regardless; Phase 14 is fully Nyquist-compliant. No new tech debt introduced; the two advisory transfers.py/writeoffs.py warnings from v1.1 remain the only carried-forward debt.
- **Phase 17 shipped 2026-07-15 (final phase of v1.3)**: read-only aggregation services (`cash_expense_total`, `stock_valuation`, `cash_flow_report`) plus period-scoped CSV export, Финансы dashboard tiles (gross/net profit, stock valuation) on desktop and mobile, a cash-flow report page with CSV download, and mobile parity via shared `finance_base`-parameterised partials. Gap-closure plan 17-05 added missing navigation entry points to the new report pages (desktop top-nav, mobile home tile, dashboard buttons), found by UAT Test 2.
- **v1.3 shipped 2026-07-15** (started 2026-07-14, 2 days): 3 phases (15-17), 13 plans, 102 commits, 142 files changed, +11,114/-10,521 lines. Stack held unchanged: FastAPI + SQLAlchemy 2.0 + SQLite (WAL) + HTMX 2.0.10 (vendored) + Jinja2, uv, Alembic. All 12 requirements (FIN-01..12) shipped complete. No `/gsd-audit-milestone` or `17-SECURITY.md` threat-verification pass was run before close — both skipped by explicit operator decision at completion time (2026-07-15), a deviation from the v1.0/v1.1/v1.2 pattern of auditing/security-checking before archiving. One new advisory (non-blocking) warning: desktop `/finance` history renders literal `None` for an empty comment (mobile cards handle it correctly); guard with `{{ movement.note or "" }}` when next touching finance templates. The two advisory transfers.py/writeoffs.py warnings from v1.1 remain untouched.
- **v2.0 shipped 2026-07-17** (started 2026-07-16, 2 days): 7 phases (18-24), 42 plans, 103 tasks, 339 files changed, +39,747/-9,967 lines, 354 commits (since v1.3 tag). Stack held unchanged. `/gsd-audit-milestone` run (full scope, all 7 phases) passed with status `tech_debt`: 46/46 requirements satisfied across three independent sources, cross-phase integration checker found no wiring gaps or dangling `catalog_cents` references across Phase 18→19→20→22→23, 919/919 tests green. Open item: Phase 22 (Sales) shipped 4 human-verification test cases (live JS basket-total math, incomplete-row marker, customer-mode round-trip, mobile basket preservation) with no completed UAT confirming them in a live browser — unlike the structurally identical Phase 18/20 items, both of which have a passed UAT file. Roughly half of REQUIREMENTS.md's checkboxes were stale (marked unchecked despite being fully verified) at every phase's own VERIFICATION.md — a tracking-doc lag only, not a code gap; see `.planning/v2.0-MILESTONE-AUDIT.md` for the full breakdown.
- **Next milestone (not yet scoped):** leading candidates carried from the v1.1-era Future list — multi-operator sync across countries via a central server (server-based online + USB flash-drive offline), multi-currency support, user roles (administrator, operator, report viewer), customer purchase-frequency "running low" reminders, likely-interested-customer suggestions on goods receipt. Run `/gsd-new-milestone` to scope and prioritize.

## Constraints

- **Tech stack**: Python, FastAPI, SQLAlchemy, SQLite, HTMX server-rendered UI — user's choice; simple to learn and maintain
- **Deployment**: Runs locally, UI in browser at localhost — no internet required for v1
- **Users**: 1 operator in year one — no auth complexity needed in v1
- **Currency**: Single currency in v1

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Local-first MVP, sync deferred | Sync is the hardest part; ship working local app first | ✓ Good — v1.0 shipped local-only, no rework forced |
| FastAPI + HTMX + SQLite | Simplest maintainable stack for a learning solo developer | ✓ Good — held for all 6 phases, no stack changes |
| Event/operation log from day one | Cheap now, enables future sync and full audit history | ✓ Good — enabled Phase 5 history view and Phase 6 reports directly off the ledger |
| Single currency, no roles in v1 | One user, one country initially | ✓ Good — no friction encountered |
| `record_operation()` as the single ledger write path (IN-01/IN-02 guards) | One choke point makes append-only + stock-cache consistency and future sync conflict resolution tractable | ✓ Good — Phase 1 rule, held through Phase 5 (retired the walking-skeleton `POST /ops` once `/corrections` shipped) |
| Sale-linked return copies the frozen origin sale's price/cost rather than current prices | Profit reports must reflect the price actually charged, not today's price | ✓ Good — Phase 5 |
| Per-product threshold with global fallback (`is not None`, never bare `or`) for low-stock/stale-days | An explicit zero threshold must stay meaningful, not collapse into "use the default" | ✓ Good — Shipped Phase 6 |
| Single shared period-filter + local-day-boundary helper reused unchanged across all four period-based reports | One code path for date math avoids drift between sales/stock/writeoffs/top-selling reports | ✓ Good — Shipped Phase 6 |
| CSV export: BOM-once + `;` delimiter + apostrophe-escape of formula-injection prefixes, zero client-supplied params | Must open correctly in Excel with Cyrillic and be safe against formula injection, with a minimal server attack surface | ✓ Good — Shipped Phase 6, security-audited (14/14 threats closed) |
| Python-side category grouping (dict keyed by category or "") instead of a SQL NULL-ordering trick | Guarantees the "Без категории" bucket always sorts last regardless of dict iteration order | ✓ Good — Shipped Phase 7 |
| Every money field parse (including sale-line price) rejects negative values via the same `PRICE_ERROR` convention as `parse_optional_cents` | A negative sale-line price must never bypass the price-floor guardrail just because the product has no minimum configured | ✓ Good — Shipped Phase 7 (gap-closure plan 07-04, found by code review CR-01) |
| v1.1 phase order: Category/Price → Warehouses → Batches → Transfers/Expiry → Mobile Flow | Isolates the riskiest ledger-schema work (batches) after lower-risk work ships; mobile flow built once against the finished feature set | ✓ Good — held for all 5 phases, no reordering needed |
| WH-02 (per-batch storage location) mapped to Phase 9, not Phase 8 | Location tag is a field on `Batch`, not `Warehouse` — can't be delivered until batches exist | ✓ Good — Shipped Phase 9 |
| UI-01 re-scoped mid-milestone as a dedicated mobile flow (separate screens), not a CSS-only adaptation, and moved from Phase 8 to Phase 11 | User clarified the requirement; building it last avoids extending it piecemeal every time a later phase adds an operation | ✓ Good — Shipped Phase 11 in one self-contained pass covering the full final operation set |
| Batch selection made mandatory (not optional) on every stock-affecting operation via a D-12 guard flip once all services were batch-aware | Partial batch adoption would have left oversell/expiry guarantees inconsistent across operation types | ✓ Good — Shipped Phase 9 |
| Mobile flow reuses existing services (register_sale, register_receipt, etc.) unchanged — new templates/routes only, no service-layer duplication | Keeps a single source of truth for business rules (guardrails, ledger writes) across desktop and mobile | ✓ Good — Shipped Phase 11, zero desktop regressions |
| Shared `sale_name_field.html` partial included by both the initial basket-row render and every code-triggered OOB lookup swap | A debounced name-search dropdown wired only into the initial render would silently stop working after any code-based `/sales/lookup` swap replaced the row | ✓ Good — Shipped Phase 12 |
| Price consolidation (PROD-05/06/07) sequenced first as its own phase (18), ahead of every page rebuild that reads the price shape | Only schema-affecting change in v2.0; receipts/sales/product cards/dictionary/stock-valuation reports all read it — mirrors v1.1's "riskiest schema work before the UI that reads it" ordering | ✓ Good — Shipped Phase 18, zero rework forced on Phases 19-24 |
| `Product.min_sale_cents` exempted from the two-price consolidation — kept as a guardrail threshold, not folded into ДЦ/ПЦ | It's read by the Phase 7 below-minimum-sale warning (PRICE-01), not displayed as a price the operator reads off the card (operator decision, 2026-07-15) | ✓ Good — Shipped Phase 18, PRICE-01 regression-verified unchanged |
| Navigation restructure (NAV-01..08) sequenced last (Phase 24), not first | NAV-01/02/03/07 all soft-depend on the pages they nest into being in final shape (19/20); NAV-08's top-level tab set can only be settled once Главная is rebuilt (23) | ✓ Good — Shipped Phase 24, no re-nesting needed after earlier phases shipped |
| CUST-01..08 (Phase 21) sequenced before SALE-01..07 (Phase 22) | SALE-05's inline new-customer form needs the extended profile fields to already exist, or the sale rebuild would ship against a profile shape it then has to redo | ✓ Good — Shipped Phase 21 then 22, no redo |
| DASH-01..05 and HIST-01..04 combined into one phase (23) | Both are read-only presentations over the same ledger; DASH-05's per-type feed columns and HIST-01's per-type column sets are the same mapping — building separately would duplicate it | ✓ Good — Shipped Phase 23 |
| Colour-only price-deviation cue shipped without a text badge, despite the original design note calling for one (D-14) — a documented WCAG 1.4.1 (Use of Color) deviation | Code review (WR-03) found no badge was ever implemented; rather than retrofit one, the deviation was surfaced explicitly for an operator decision | ✓ Good — Operator confirmed colour-only is acceptable (18-UAT.md, 2026-07-16) |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-18 — v2.0 milestone archived after v1.3*
