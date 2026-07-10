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
- ✓ Other operations: write-off, sale-linked return, stock correction — all logged in operation history, with a dedicated /history browsing view (OPS-01..04) — Phase 5
- ✓ Reports: day/week/month/custom period — sales, profit, stock levels, write-offs, top products, stale products, low-stock items — Phase 6 (RPT-01..04)
- ✓ Data export: full products/sales/customers dump as three Excel-compatible CSV files — Phase 6 (BCK-02)

### Active

- [ ] Goods receipt: add stock by product code with quantity, cost, catalog and sale prices; price change history preserved
- [ ] Sales: by product code with auto-fill, custom sale price, optional customer (name, surname, consultant number); stock decremented; sale saved to history
- [ ] Customers: profile, purchase history, purchase frequency, "running low" reminders, interested-customers list on new stock arrival
- [ ] Simple operator UI: minimal clicks, autocomplete, warnings (e.g., selling more than in stock) — search/autocomplete shipped in Phase 2
- [ ] Operation audit log (who did what and when)

### Out of Scope

- Multi-operator sync between countries — deferred; MVP is local single-operator first (user decision)
- Multi-currency — deferred; single currency in v1 (user decision)
- Excel/CSV import of initial data — no existing data; everything entered manually from scratch (user decision)
- User roles (admin/operator/viewer) — single user in year one; revisit with sync milestone
- Barcodes, Oriflame campaign catalog integration, batch FIFO costing, notifications — best-practice extras for later milestones

## Context

- Idea document: `agent.md` in repo root (detailed feature spec in Russian).
- The user is learning programming; the stack and code should stay simple and beginner-friendly.
- Architecture must not paint us into a corner: local-first design (SQLite + operation/event log) should keep the door open for later server sync (PostgreSQL) without rework.

## Constraints

- **Tech stack**: Python, FastAPI, SQLAlchemy, SQLite, HTMX server-rendered UI — user's choice; simple to learn and maintain
- **Deployment**: Runs locally, UI in browser at localhost — no internet required for v1
- **Users**: 1 operator in year one — no auth complexity needed in v1
- **Currency**: Single currency in v1

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Local-first MVP, sync deferred | Sync is the hardest part; ship working local app first | — Pending |
| FastAPI + HTMX + SQLite | Simplest maintainable stack for a learning solo developer | — Pending |
| Event/operation log from day one | Cheap now, enables future sync and full audit history | — Pending |
| Single currency, no roles in v1 | One user, one country initially | — Pending |
| Per-product threshold with global fallback (`is not None`, never bare `or`) for low-stock/stale-days | An explicit zero threshold must stay meaningful, not collapse into "use the default" | Shipped Phase 6 |
| Single shared period-filter + local-day-boundary helper reused unchanged across all four period-based reports | One code path for date math avoids drift between sales/stock/writeoffs/top-selling reports | Shipped Phase 6 |
| CSV export: BOM-once + `;` delimiter + apostrophe-escape of formula-injection prefixes, zero client-supplied params | Must open correctly in Excel with Cyrillic and be safe against formula injection, with a minimal server attack surface | Shipped Phase 6 |

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
*Last updated: 2026-07-10 after Phase 6 (milestone v1.0 — all 6 phases complete)*
