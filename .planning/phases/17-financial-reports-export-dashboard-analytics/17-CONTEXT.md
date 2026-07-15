# Phase 17: Financial Reports, Export & Dashboard Analytics - Context

**Gathered:** 2026-07-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Add READ-ONLY analytics to the «Финансы» section: a period cash-flow report
(income vs expense by category), a period-scoped CSV export of cash movements,
and three dashboard metrics — gross profit, net profit, and stock valuation.
Everything here is period / point-in-time aggregation over data already written
by Phases 14–16; NO new write paths, NO schema change, NO new ledger categories.

**In scope:** FIN-08 (period cash-flow report by income/expense category),
FIN-09 (period-filtered CSV export of cash movements), FIN-10 (gross profit for
period, reusing `sales_profit_report`), FIN-11 (net profit = gross − cash
expenses in period), FIN-12 (stock valuation at purchase cost and at sale
price). Desktop (`/finance`) AND mobile (`/m/finance`) parity.

**Out of scope (later / other phases):** any write to `cash_movements` or
`operations`; new DB columns / migrations; netting returns *inside*
`sales_profit_report` (see Deferred); per-batch purchase-cost tracking (batch
schema has no cost column); date-range filter on the *history* list (that stays
the Phase 16 type-filter list).

Requirements delivered: FIN-08, FIN-09, FIN-10, FIN-11, FIN-12.
</domain>

<decisions>
## Implementation Decisions

### Carrying forward (locked — do not re-litigate)
- Money is signed Integer cents; render via `app.core.format_cents`; NO currency
  symbol (single currency v1). Cash balance = live `SUM(amount_cents)` over
  `cash_movements` (Phase 15 D-00b).
- `finance.record_cash_movement` is the SINGLE write path; Phase 17 is 100%
  READ-ONLY — every new function only SELECTs (mirrors `reports.py` discipline).
- Portable ORM only, no SQLite-specific SQL (sync-readiness for future Postgres).
- Cash category keys group into 4 buckets: sale (auto +), return (auto −),
  `withdrawal_*` (manual −), `deposit_*` (manual +) — from Phase 16 D-01a.
- Period handling reuses `app/routes/reports.py::_resolve_period` + presets
  (week/month, Monday-start RU convention) + `local_day_bounds_utc`.

### Net profit — expense set (FIN-11)  → Option C
- **D-01:** Net profit = gross profit **plus** the (already-negative) sum of
  `cash_movements.amount_cents` where `category IN (withdrawal_supplier,
  withdrawal_salary, withdrawal_rent, withdrawal_utilities, withdrawal_other,
  return)` within the period. I.e. manual withdrawals **and** return-debits both
  count as cash outflow; `deposit_*` and `sale` credits are excluded.
- **D-01a:** Because the rows are already negative, net profit is a plain
  addition — no sign-flipping. Use the coarse-bucket grouping from Phase 16
  D-01a to select the `withdrawal_*` + `return` set, don't hardcode a category
  list in the query if a grouping map already exists.
- **D-01b — KNOWN CAVEAT (must surface in UI, not hide):** `sales_profit_report`
  (FIN-10) counts a returned sale's *margin* as gross profit but does NOT
  reverse it on return. Subtracting the *full* return amount here therefore
  understates net profit by the returned item's cost when a return occurs.
  Accepted trade-off for a single-operator app (returns are rare); the correct
  fix (net returns inside gross profit) is deferred. Add a short label/tooltip
  on the net-profit tile clarifying it is a cash-outflow view, so the number is
  never read as strict accounting profit.

### Stock valuation (FIN-12)  → Option A (product-level)
- **D-02:** Compute two sums over ACTIVE products (`Product.deleted_at IS NULL`):
  purchase-cost value = `Σ(quantity × cost_cents)`, sale-price value =
  `Σ(quantity × sale_cents)`. Batch-level cost is NOT used — `Batch` stores only
  a sale-price snapshot (`price_cents`), never a purchase cost; real cost lives
  on the receipt `Operation.unit_cost_cents` and reconstructing per-batch cost is
  an unjustified join for a dashboard tile.
- **D-02a:** NULL-price handling mirrors `sales_profit_report`: a product with
  NULL `cost_cents` is EXCLUDED from the cost sum (never treated as zero), same
  for NULL `sale_cents` in the sale sum. Surface `cost_unknown_count` /
  `sale_unknown_count` (count of in-stock products missing that price) beside the
  totals so the operator sees a caveat instead of a silently understated number.
- **D-02b:** Point-in-time (current stock), no period filter — independent of the
  period selector.

### CSV export scope (FIN-09)  → Option C (period-filtered, shared validation)
- **D-03:** The cash-movements CSV export accepts a validated `from`/`to` date
  range via the SAME `_resolve_period` helper used by the reports pages — NOT a
  new ad-hoc parser. It exports only `cash_movements` rows within the resolved
  `[start_iso, end_iso)` UTC bounds.
- **D-03a:** Keep every existing export convention from
  `app/services/export.py` INTACT: exactly one UTF-8 BOM at stream start
  (`_encode_once`), `;` delimiter (RU-Excel), `_csv_safe` formula-injection
  escaping on every free-text cell. Add the export as a new `stream_*_csv`-style
  function following that module's shape.
- **D-03b:** Update the T-06-09 security docstring in `export.py` to record the
  explicit exception: a *validated calendar date range* is allowed (it is not a
  path/filename/arbitrary string, is clamped by `_resolve_period`, and is
  consumed only as an ORM `.where(created_at …)` bound). This is a documented,
  bounded relaxation — not a blanket "exports may take arbitrary params".
- **D-03c:** CSV columns = planner discretion, following `stream_sales_csv`
  shape; at minimum: local datetime (`iso_to_local`), тип/категория label (from
  `CASH_CATEGORIES`), comment (`note`), signed amount (`format_cents`).

### Финансы page layout (FIN-08/10/11/12)  → Option C (hybrid)
- **D-04:** The three dashboard metrics (gross profit, net profit, stock value)
  render as tiles WITH a period selector directly on the existing `/finance` and
  `/m/finance` pages (ROADMAP requires them "on the Финансы dashboard"). The
  existing balance + manual-entry forms + movement history from Phases 15–16 stay
  untouched on that page.
- **D-04a:** The heavier detailed cash-flow report (FIN-08, income vs expense by
  category) + the CSV export button live on a NEW sub-page `/finance/report`
  (and its mobile counterpart), a near-verbatim reuse of the `/reports/sales`
  pattern: `_resolve_period`, HX-Request full-chrome-vs-partial branch, week/month
  presets, and (if the report is long) the `page_window`/load-more precedent.
- **D-04b:** Stock valuation tile (D-02) is point-in-time; the gross/net-profit
  tiles (D-01) follow the dashboard period selector. Two period controls exist
  (a light one for the dashboard tiles, the full one on `/finance/report`) — give
  a clear UX cue they are independent.
- **D-04c:** Desktop/mobile parity achieved the same way FIN-03..07 did it
  (shared partials / `finance_base`-style prefix), following existing mobile
  patterns. Exact mobile layout = planner / UI-SPEC discretion.

### Cash-flow report structure (FIN-08)
- **D-05:** One income section (sale credits) vs expense rows grouped by
  `withdrawal_*` category, plus returns and deposits shown per their bucket.
  Exact row grouping (single «Продажи» line vs per-category, whether returns net
  against income visually) = planner discretion, but the numbers MUST be
  consistent with the net-profit definition in D-01 so the report and the tile
  never disagree.

### Claude's Discretion
- Service/function names (follow `reports.py` / `finance.py` naming); route
  paths for the report sub-page; exact CSV column set (D-03c); tile visual
  design; whether desktop and mobile share report partials; SQL-side vs
  Python-side aggregation (follow whatever the nearest existing report does).
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements / roadmap
- `.planning/ROADMAP.md` §Phase 17 — goal, depends-on (Phase 16), 5 success criteria.
- `.planning/REQUIREMENTS.md` — FIN-08, FIN-09, FIN-10, FIN-11, FIN-12 wording.
- `.planning/phases/16-manual-cash-movements-history/16-CONTEXT.md` — locked cash
  ledger decisions D-00…D-07 (categories, buckets, single write path, format).
- `.planning/phases/15-cash-ledger-foundation/15-CONTEXT.md` — `cash_movements`
  shape, `compute_balance`, format/label rules.

### Period filter + report pattern (mirror verbatim)
- `app/routes/reports.py` — `_resolve_period` (from/to, week/month presets,
  safe RU-error fallback), `local_day_bounds_utc` usage, and the
  `/reports/sales` route's HX-Request full-page-vs-partial branch to copy for
  `/finance/report`.
- `app/services/reports.py` §`sales_profit_report(session, start_iso, end_iso)`
  — REUSE directly for FIN-10 gross profit; note its nullable-cost handling
  (`cost_unknown_count`, excludes NULL cost, does NOT filter `deleted_at`).

### CSV export conventions (extend, keep intact)
- `app/services/export.py` — `_encode_once` (BOM-once), `_csv_rows` (`;`
  delimiter), `_csv_safe` (formula-injection escape), `stream_sales_csv` shape;
  §T-06-09 docstring to UPDATE per D-03b.
- `app/routes/export.py` — route wiring pattern for a `StreamingResponse` CSV.

### Cash ledger data (read side)
- `app/models.py` §`CASH_CATEGORIES` (sale/return + Phase 16 manual keys) and
  §`CashMovement` (`category`, signed `amount_cents`, `note`, `sale_id`, audit
  cols); §`Product` (`quantity`, nullable `cost_cents`/`sale_cents`,
  `deleted_at`) for FIN-12; §`Batch` (has `price_cents` sale snapshot, NO cost
  column — confirms D-02).
- `app/services/finance.py` — `compute_balance`; add the read-only period
  aggregation + stock-valuation service functions here or in a sibling module.

### Finance surfaces to extend
- `app/routes/finance.py`, `app/routes/mobile_finance.py` — add the dashboard
  tiles (period query params) + the new `/finance/report` route + CSV route.
- `app/templates/pages/finance.html`, `app/templates/mobile_pages/finance.html`
  — add metric tiles + period selector; new report page + partial templates.
- `app/core.py` §`format_cents`, `iso_to_local` — money / datetime display.
- `app/services/pagination.py` — `page_window` / `paginate` if the report list
  is long enough to paginate.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `reports.py::sales_profit_report` — drop-in for FIN-10 gross profit; already
  returns `totals.profit_cents` + `cost_unknown_count`.
- `reports.py::_resolve_period` + `local_day_bounds_utc` — the entire period /
  preset / validation seam for both the dashboard tiles and `/finance/report`
  and the FIN-09 export (D-03).
- `export.py` `_encode_once` / `_csv_rows` / `_csv_safe` — the whole safe-CSV
  stack; new export reuses them verbatim (D-03a).
- `core.format_cents` / `iso_to_local` — money + local datetime formatting.
- `pagination.paginate` / `page_window` — if the cash-flow report needs paging.

### Established Patterns
- Read services only SELECT; portable ORM, no SQLite-specific SQL.
- Nullable prices are EXCLUDED from money sums and surfaced as a separate
  `*_unknown_count`, never treated as zero (FIN-12 follows this — D-02a).
- Latin-key → RU-label dicts (`CASH_CATEGORIES`) drive labels — extend/read the
  dict, never hardcode labels in templates.
- Reports pages: `_resolve_period` → `local_day_bounds_utc` → report fn →
  HX-Request branch (full chrome vs partial). Desktop/mobile parity via shared
  partials.

### Integration Points
- New read-only aggregation fns (net-profit expense sum, cash-flow-by-category,
  stock valuation) in `finance.py` or a sibling report module.
- `/finance` + `/m/finance` gain dashboard tiles + a period selector.
- New `/finance/report` (+ mobile) route + templates for FIN-08 report + FIN-09
  CSV button.
</code_context>

<specifics>
## Specific Ideas

- Net profit explicitly includes `return` outflows alongside `withdrawal_*`
  (user chose Option C) — surface the cash-outflow caveat in the tile label.
- Stock valuation shown at BOTH purchase cost and sale price, point-in-time,
  with unknown-price counts.
- CSV export is period-scoped (from/to), reusing the reports period selector,
  not a full-table dump.
- Metrics on the dashboard itself; the detailed movement report + CSV on a
  separate `/finance/report` sub-page mirroring `/reports/sales`.
</specifics>

<deferred>
## Deferred Ideas

- **Net returns inside gross profit** — the accounting-correct fix for D-01b
  (reverse a returned sale's margin in `sales_profit_report` instead of
  subtracting the full return amount in net profit). Changes FIN-10's locked
  reuse; revisit if return volume grows or the net-profit caveat proves
  confusing.
- **Per-batch purchase-cost valuation (FIN-12 Option B)** — needs a real cost
  column on `Batch` (or a receipt-Operation join); revisit only if cost drift
  across receipts becomes material.
- **Date-range filter on the Phase 16 history list** — already noted deferred in
  Phase 16; the period report (FIN-08) partially covers the need.

</deferred>

---

*Phase: 17-financial-reports-export-dashboard-analytics*
*Context gathered: 2026-07-15*
