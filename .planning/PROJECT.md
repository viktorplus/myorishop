# MyOriShop — Oriflame Warehouse Inventory

## What This Is

A warehouse inventory and sales tracking application for a single Oriflame reseller. It manages product stock, goods receipts, sales, customers, and reports — running locally without internet, with a browser-based UI. Future versions add multi-operator sync across countries via a central server.

## Core Value

The operator can quickly and reliably record receipts and sales so stock counts and profit figures are always correct — without losing any data.

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

### Active

- [ ] Multi-operator sync across countries via a central server (PostgreSQL), conflict resolution over the operations ledger (SYNC-V2-01)
- [ ] Multi-currency support (CUR-V2-01)
- [ ] User roles: administrator, operator, report viewer (AUTH-V2-01)
- [ ] Customer purchase-frequency analysis and "running low" reminders — needs months of sales history (CST-V2-01)
- [ ] On goods receipt, show customers likely interested in the product based on purchase history (CST-V2-02)

### Out of Scope

- Barcodes — no scanner hardware; code entry is fast enough for one operator
- Oriflame campaign catalog integration — not needed for core value
- Batch FIFO costing — average/snapshot cost is sufficient for profit reports
- Invoicing/payments, notifications — not needed for core value
- Excel/CSV import of initial data — no existing data; everything entered manually from scratch (user decision)

## Context

- Idea document: `agent.md` in repo root (detailed feature spec in Russian).
- The user is learning programming; the stack and code should stay simple and beginner-friendly.
- Architecture must not paint us into a corner: local-first design (SQLite + operation/event log) should keep the door open for later server sync (PostgreSQL) without rework.
- **v1.0 shipped 2026-07-10** (started 2026-07-08, 3 days): 6 phases, 31 plans, 263 files changed, ~35.5k insertions, ~9,000 LOC Python. Stack held as planned: FastAPI + SQLAlchemy 2.0 + SQLite (WAL) + HTMX 2.0.10 (vendored) + Jinja2, uv, Alembic.
- One Phase 1 human-verification item (offline `run.bat` launch + browser correction flow + restart persistence) remains unexecuted — acknowledged and deferred at milestone close (see STATE.md Deferred Items). Recommend running it before relying on the app for real daily data entry.

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
*Last updated: 2026-07-10 after v1.0 milestone (6 phases, 31 plans, shipped)*
