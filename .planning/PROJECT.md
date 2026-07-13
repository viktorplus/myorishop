# MyOriShop — Oriflame Warehouse Inventory

## What This Is

A warehouse inventory and sales tracking application for a single Oriflame reseller. It manages product stock, goods receipts, sales, customers, and reports — running locally without internet, with a browser-based UI. Future versions add multi-operator sync across countries via a central server.

## Core Value

The operator can quickly and reliably record receipts and sales so stock counts and profit figures are always correct — without losing any data.

## Current State

**Shipped: v1.1 Multi-Warehouse & Batch Tracking (2026-07-13)**

Delivered multi-warehouse stock organization, batch/lot-level tracking with expiry dates and per-batch pricing (mandatory manual selection at every stock-affecting operation), category browsing, minimum-price guardrails, warehouse-to-warehouse transfers preserving cost history, an expiring-batches report, and a dedicated mobile flow. See `.planning/milestones/v1.1-ROADMAP.md` and `.planning/MILESTONES.md` for full details.

## Next Milestone Goals

v2.0 is next (see Active requirements and Context below): multi-operator sync across countries, multi-currency, user roles, and customer intelligence features. Run `/gsd-new-milestone` to scope it formally.

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

### Active

Next milestone (v2.0) requirements — to be scoped formally via `/gsd-new-milestone`:

- [ ] Multi-operator sync across countries via a central server, server-based (online) + USB flash-drive (offline) (SYNC-V2-01)
- [ ] Multi-currency support (CUR-V2-01)
- [ ] User roles: administrator, operator, report viewer (AUTH-V2-01)
- [ ] Customer purchase-frequency analysis and "running low" reminders (CST-V2-01)
- [ ] On goods receipt, show customers likely interested in the product based on purchase history (CST-V2-02)
- [ ] CSV export includes warehouse/batch columns (EXP-V2-01)

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
- **v2.0 (next):** multi-operator sync across countries via a central server, with both server-based sync (when online) and USB flash-drive sync (when offline) in the same milestone; multi-currency support; user roles (administrator, operator, report viewer); customer purchase-frequency analysis and reminders; showing likely-interested customers on goods receipt. Was deferred from v1.1 because it first needed the local data model changes (multi-warehouse, batches) that sync must now account for — those changes are now shipped.

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
*Last updated: 2026-07-13 after v1.1 milestone (Multi-Warehouse & Batch Tracking)*
