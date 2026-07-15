# Phase 16: Manual Cash Movements & History - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-15
**Phase:** 16-manual-cash-movements-history
**Areas discussed:** Schema (type vs category), Comment requirement, Entry form placement, History filters & placement
**Mode:** advisor (table-first, codebase-grounded — calibration tier: standard; no web-research subagents spawned since every decision was grounded in existing in-repo patterns)

---

## Schema: movement type vs category

| Option | Description | Selected |
|--------|-------------|----------|
| A. Extend `category` | Manual keys added to CASH_CATEGORIES; no new column/migration; sign encodes direction; deposit gets Остаток/Коррекция select; labels via existing dict | ✓ |
| B. `type` column + sub-category | New `type` column (sale/return/withdrawal/deposit) + category as sub-reason; cleaner for Phase 17 reporting; requires migration | |
| C. Type from amount sign + category | No column, but can't distinguish sale-credit from manual deposit (both +) — breaks "system vs manual" | (dropped) |

**User's choice:** A — extend `category`.
**Notes:** Minimal change, one operator, reuses the latin-key→RU-label dict pattern. Deposit reasons become a 2-item select (Начальный остаток / Корректировка). Category keys should make the 4 coarse buckets trivially derivable.

---

## Comment requirement

| Option | Description | Selected |
|--------|-------------|----------|
| Mandatory only for «прочее» / «коррекция» | Category already gives structure; comment required only for catch-all/correction | ✓ |
| Always mandatory | Max context, more friction on obvious categories | |
| Always optional | Fastest, but «прочее»/«коррекция» without explanation are useless | |

**User's choice:** Mandatory only for «прочее» and «коррекция».
**Notes:** Enforced server-side, zero writes on failure.

---

## Entry form placement

| Option | Description | Selected |
|--------|-------------|----------|
| B. Two forms (Снять / Внести) | Explicit; warn-but-allow logic only in withdrawal form; matches app's server-rendered style | ✓ |
| A. One form with direction toggle | Compact on mobile, single code path; confirm must remember direction | |
| C. Modal dialogs | Visually clean, but modals complicate the warn-but-allow re-render; foreign to the server-rendered style | (dropped) |

**User's choice:** B — two separate forms below the balance.
**Notes:** Desktop + mobile parity; exact mobile layout left to planner/UI-SPEC.

---

## History filters & placement

| Option | Description | Selected |
|--------|-------------|----------|
| Type filter + pagination | 1:1 with `/history`; filter by coarse type + pages; minimal code | ✓ |
| Type + date range | Adds period filter (good for reconciliation); needs a new date-picker UI | |
| Type + date + category | Max slicing, overkill for one operator | (dropped) |

**User's choice:** Type filter + pagination.
**Notes:** Placement fixed by ROADMAP — on the Финансы page below the balance/forms. Reuses pagination.py + the `/history` partial pattern. Filter buckets: Продажа / Возврат / Снятие / Внесение.

## Claude's Discretion

- Exact category-key spelling; service/function names; route paths; template structure; desktop/mobile partial sharing.
- SQL-filter vs Python-slice for the history read (follow `operations.history_view`).
- Mobile layout specifics (single page vs subpage).

## Deferred Ideas

- Date-range filter on cash history → possible follow-up.
- Separate `type` DB column (Option B) → revisit only if Phase 17 reporting needs it.
- Reports / CSV export / profit & stock-valuation dashboard → Phase 17.
