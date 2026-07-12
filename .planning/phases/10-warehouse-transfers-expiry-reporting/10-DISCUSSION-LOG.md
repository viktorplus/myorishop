# Phase 10: Warehouse Transfers & Expiry Reporting - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-12
**Phase:** 10-Warehouse Transfers & Expiry Reporting
**Areas discussed:** Transfer entry point, Transfer ledger representation, Expiry report threshold & scope, Expiry report actions & placement

**Overarching steer from the user:** *«надо сделать максимально примитивно»* — take the simplest satisfying option in every area.

---

## Transfer entry point (WH-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated `/transfers` page | code → source-batch picker → destination-warehouse select → qty → submit, reusing `batch_picker.html` | ✓ |
| Per-batch "Переместить" button | Requires a batch-management surface that does not exist (D-03) | |

**User's choice:** Dedicated `/transfers` page (part of the confirmed recommended set).
**Notes:** Only viable option given no batch-management page; also the simplest.

---

## Transfer ledger representation (WH-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Two `transfer` rows, destination batch always new | −qty on source, +qty on destination; destination inherits price/expiry/comment/location | ✓ |
| Two rows, destination resolve-or-create (top-up matching) | Fewer batch duplicates but reintroduces NULL-expiry matching complexity | |

**User's choice:** Two rows, destination batch **always created new** (recommended primitive path; user did not switch to top-up when offered).
**Notes:** Cost/price history preserved by copying source `price_cents`. New op type `"transfer"` in `STOCK_AFFECTING_TYPES`.

---

## Expiry report — threshold & scope (LOT-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Fixed 30-day window | Show expired + batches expiring within 30 days | |
| No threshold — show ALL batches with an expiry | List every open batch that has a set expiry, sorted by date, expired marked | ✓ |
| Configurable threshold | `?days=N` param | |

**User's choice:** **No threshold — show all expiry dates** (user explicitly picked this over the recommended fixed 30-day window as even more primitive).
**Notes:** Scope = open batches (qty>0) with non-NULL expiry; legacy NULL-expiry excluded; earliest first; expired visually marked; no warehouse/period filter.

---

## Expiry report — actions & placement (LOT-06)

| Option | Description | Selected |
|--------|-------------|----------|
| Read-only `/reports/expiry` + landing link | Mirrors `/reports/stock`; no inline actions | ✓ |
| Actionable report (inline write-off link) | Extra wiring | |

**User's choice:** Read-only `/reports/expiry` under the existing `/reports/*` family (confirmed recommended).
**Notes:** Operator uses the existing write-off page to remove expired batches.

---

## Claude's Discretion

- Route/handler and template/partial filenames for `/transfers` and `/reports/expiry`.
- How the destination-warehouse select excludes the source warehouse.
- RU label for the `transfer` op type and how paired rows render in `/history`.
- Which module hosts the transfer service and the expiry query.
- Whether any migration is needed (likely none — `transfer` is a value in the existing `operations.type` column).

## Deferred Ideas

- Configurable expiry threshold / "expiring within N days" filter.
- Warehouse filter on the expiry report.
- Inline "write off expired batch" action from the report.
- Resolve-or-create / top-up of the destination batch (merge with existing matching batch).
