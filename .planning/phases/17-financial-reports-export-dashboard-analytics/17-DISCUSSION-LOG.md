# Phase 17: Financial Reports, Export & Dashboard Analytics - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-15
**Phase:** 17-financial-reports-export-dashboard-analytics
**Areas discussed:** Net-profit expense set, Stock valuation, CSV export scope, Финансы page layout
**Mode:** advisor (research-backed comparison tables; 4 parallel gsd-advisor-researcher agents, model sonnet; calibration tier `standard` from vendor_philosophy=pragmatic)

---

## Net-profit expense set (FIN-11)

| Option | Description | Selected |
|--------|-------------|----------|
| A | Only manual `withdrawal_*` rows count as expenses (matches ROADMAP "cash expenses" wording; no return distortion) | |
| C | Withdrawals + return-debits count as expenses (whole cash outflow) | ✓ |

**User's choice:** C — Снятия + возвраты
**Notes:** Claude recommended A (literal ROADMAP alignment, no cost-side skew). User chose C to capture total cash outflow. Known caveat recorded in CONTEXT D-01b: because `sales_profit_report` does not reverse a returned sale's margin, subtracting the full return amount understates net profit by the returned item's cost — must be surfaced as a cash-outflow tooltip on the net-profit tile, not hidden. Accounting-correct fix (net returns inside gross profit) deferred.

---

## Stock valuation (FIN-12)

| Option | Description | Selected |
|--------|-------------|----------|
| A | Product-level: `Σ(quantity × cost_cents)` / `Σ(quantity × sale_cents)`, active products, unknown-price counts | ✓ |
| B | Batch-level cost | |

**User's choice:** A — По товару
**Notes:** Research confirmed `Batch` has no purchase-cost column (only a sale-price snapshot `price_cents`); real cost lives on `Operation.unit_cost_cents`, so batch-level is a nontrivial join not justified for a dashboard tile. Option A also mirrors `sales_profit_report`'s nullable-price discipline (exclude NULL, surface `*_unknown_count`).

---

## CSV export scope (FIN-09)

| Option | Description | Selected |
|--------|-------------|----------|
| B | Full-table dump only (strict T-06-09) — misses "за период" criterion | |
| C | Period-filtered reusing `_resolve_period`; keep BOM/`;`/formula-escape; update T-06-09 docstring | ✓ |

**User's choice:** C — За период через `_resolve_period`
**Notes:** A validated calendar date range is not the class of input T-06-09 guards against (paths/filenames/arbitrary strings); it is clamped by the existing `_resolve_period` and consumed only as an ORM `.where`. Reuses battle-tested validation, satisfies FIN-09 literally, and preserves all Excel/RU-CSV conventions.

---

## Финансы page layout (FIN-08/10/11/12)

| Option | Description | Selected |
|--------|-------------|----------|
| A | Everything on one `/finance` page, one shared period selector | |
| B | Everything (incl. metrics) on a separate `/finance/report` sub-page | |
| C | Hybrid: metric tiles + period on `/finance` & `/m/finance`; detailed report + CSV on `/finance/report` | ✓ |

**User's choice:** C — Гибрид
**Notes:** ROADMAP requires the metrics "on the Финансы dashboard" (rules out B); Option A overloads the already-dense page and risks mobile-layout regression on the Phase 15/16 flow. C keeps lightweight numbers on the dashboard and isolates the heavier tabular report + CSV on a sub-page that reuses the proven `/reports/sales` pattern.

---

## Claude's Discretion

- Service / function names, report sub-page route paths, exact CSV column set,
  tile visual design, shared-vs-separate desktop/mobile report partials, and
  SQL-side vs Python-side aggregation (follow nearest existing report).

## Deferred Ideas

- Net returns inside gross profit (accounting-correct fix for the FIN-11 caveat).
- Per-batch purchase-cost valuation (needs a real cost column on `Batch`).
- Date-range filter on the Phase 16 history list.
