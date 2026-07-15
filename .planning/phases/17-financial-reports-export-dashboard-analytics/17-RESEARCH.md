# Phase 17: Financial Reports, Export & Dashboard Analytics - Research

**Researched:** 2026-07-15
**Domain:** Read-only period/point-in-time aggregation over an existing SQLAlchemy 2.0 / SQLite ledger; HTMX server-rendered reporting UI; streamed CSV export.
**Confidence:** HIGH (all findings verified against the actual repository source in this session)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Carry-forward (do not re-litigate):** money is signed Integer cents rendered via `format_cents` with no currency symbol; `finance.record_cash_movement` is the SINGLE write path and Phase 17 is 100% READ-ONLY (SELECT only); portable ORM only, no SQLite-specific SQL; cash category keys group into 4 buckets (sale +, return −, `withdrawal_*` −, `deposit_*` +); period handling reuses `reports.py::_resolve_period` + week/month presets (Monday-start RU) + `local_day_bounds_utc`.
- **D-01 (FIN-11 net profit = Option C):** net = gross profit **plus** the already-negative `SUM(amount_cents)` where `category IN (withdrawal_supplier, withdrawal_salary, withdrawal_rent, withdrawal_utilities, withdrawal_other, return)` within the period. Manual withdrawals AND return-debits count as outflow; `deposit_*` and `sale` credits excluded.
- **D-01a:** rows are already negative → plain addition, no sign-flip. Select the `withdrawal_*` + `return` set via the existing coarse-bucket grouping map — do NOT hardcode the category list if a map exists.
- **D-01b (KNOWN CAVEAT — surface in UI, do not hide):** `sales_profit_report` counts a returned sale's margin as gross profit but does NOT reverse it on return; subtracting the full return amount here understates net profit by the returned item's cost. Accepted trade-off; add a label/tooltip on the net-profit tile clarifying it is a **cash-outflow** view, not strict accounting profit. Correct fix (net returns inside gross profit) is deferred.
- **D-02 (FIN-12 stock valuation = Option A, product-level):** two sums over ACTIVE products (`Product.deleted_at IS NULL`): purchase-cost value `Σ(quantity × cost_cents)`, sale-price value `Σ(quantity × sale_cents)`. Batch-level cost NOT used (`Batch` has no cost column).
- **D-02a:** NULL prices EXCLUDED from the sum (never treated as zero), mirroring `sales_profit_report`; surface `cost_unknown_count` / `sale_unknown_count` beside the totals.
- **D-02b:** point-in-time (current stock), NO period filter — independent of the period selector.
- **D-03 (FIN-09 CSV = Option C, period-filtered):** export accepts a validated `from`/`to` range via the SAME `_resolve_period` helper; exports only `cash_movements` rows within `[start_iso, end_iso)` UTC bounds.
- **D-03a:** keep every `export.py` convention intact — one UTF-8 BOM at stream start (`_encode_once`), `;` delimiter, `_csv_safe` formula-escape on every free-text cell; add a new `stream_*_csv`-style function.
- **D-03b:** update the T-06-09 security docstring in `export.py` to record the validated-date-range exception (a clamped calendar range consumed only as an ORM `.where` bound — a documented, bounded relaxation, not "arbitrary params allowed").
- **D-03c:** CSV columns = planner discretion following `stream_sales_csv` shape; minimum: local datetime, тип/категория label from `CASH_CATEGORIES`, comment (`note`), signed amount.
- **D-04 (Финансы layout = Option C, hybrid):** three tiles (gross, net, stock) WITH a period selector on the existing `/finance` and `/m/finance`; balance + entry forms + history from Phases 15–16 stay untouched.
- **D-04a:** heavier cash-flow report (FIN-08) + CSV button live on a NEW `/finance/report` sub-page (+ mobile), near-verbatim reuse of `/reports/sales` pattern (`_resolve_period`, HX-Request full-vs-partial branch, week/month presets, `page_window` if long).
- **D-04b:** stock tile is point-in-time; gross/net tiles follow the dashboard period selector. TWO period controls exist (light dashboard one + full `/finance/report` one) — give a clear UX cue they are independent.
- **D-04c:** desktop/mobile parity via shared partials / `finance_base`-style prefix, following FIN-03..07; exact mobile layout = planner/UI-SPEC discretion.
- **D-05 (FIN-08 structure):** one income section (sale credits) vs expense rows grouped by `withdrawal_*` category, plus returns and deposits per bucket. Exact grouping = planner discretion, but numbers MUST match the D-01 net-profit definition so report and tile never disagree.

### Claude's Discretion
- Service/function names (follow `reports.py` / `finance.py` naming); route paths for the report sub-page; exact CSV column set (D-03c); tile visual design; whether desktop and mobile share report partials; SQL-side vs Python-side aggregation (follow whatever the nearest existing report does).

### Deferred Ideas (OUT OF SCOPE)
- Net returns inside gross profit (accounting-correct fix for D-01b).
- Per-batch purchase-cost valuation (FIN-12 Option B) — needs a real cost column on `Batch`.
- Date-range filter on the Phase 16 history list.
- Any write to `cash_movements` / `operations`; new DB columns / migrations; new ledger categories.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FIN-08 | Отчёт по движениям кассы за период (приход/расход по категориям) | New read service groups `cash_movements` in `[start_iso,end_iso)` by `CASH_BUCKETS`; new `/finance/report` page copies the `/reports/sales` route shape (`_resolve_period` → `local_day_bounds_utc` → service → HX full/partial branch) and the shared `partials/period_filter.html`. |
| FIN-09 | CSV-экспорт движений кассы | New `stream_cash_movements_csv(session, start_iso, end_iso)` in `app/services/export.py` reusing `_encode_once`/`_csv_rows`/`_csv_safe` verbatim; new route with `from`/`to` query params validated via `_resolve_period`; T-06-09 docstring updated (D-03b). |
| FIN-10 | Валовая прибыль за период | Reuse `sales_profit_report(session, start_iso, end_iso)` verbatim → `report["totals"]["profit_cents"]` + `cost_unknown_count`. |
| FIN-11 | Чистая прибыль = валовая − расходы кассы за период | New `cash_expense_total(session, start_iso, end_iso)` = signed `SUM(amount_cents)` over `CASH_BUCKETS["withdrawal"] + CASH_BUCKETS["return"]` in the period; net = `profit_cents + expense_total` (plain add, D-01a). |
| FIN-12 | Стоимость склада по закупке и по продаже | New `stock_valuation(session)` over active products: `Σ(quantity × cost_cents)` and `Σ(quantity × sale_cents)` excluding NULL prices, plus unknown counts (D-02/D-02a). |
</phase_requirements>

## Summary

Phase 17 is a **reuse-heavy, 100% read-only** analytics phase. Every capability maps to an existing, verified seam in the codebase: `_resolve_period` + `local_day_bounds_utc` for period handling, `sales_profit_report` for gross profit, `CASH_BUCKETS` for the expense-category set, `Product.quantity/cost_cents/sale_cents` for valuation, and the `_encode_once`/`_csv_rows`/`_csv_safe` stack for CSV. No external package is added; no schema, migration, or write path is introduced.

The plan's real work is: (1) three new read-only aggregation functions (net-profit expense sum, cash-flow-by-category, stock valuation) plus verbatim reuse of `sales_profit_report`; (2) a new `/finance/report` sub-page (+ mobile) that copies the `/reports/sales` route/template pattern; (3) dashboard tiles + a light period selector added to the existing `/finance` and `/m/finance` pages; (4) a period-filtered cash-movements CSV export that extends `export.py` and its T-06-09 docstring.

**Primary recommendation:** Add three functions to `app/services/finance.py` (or a sibling `finance_reports.py`), reuse `sales_profit_report` untouched, build the report sub-page as a direct clone of `reports_sales_page`, and extend `export.py` with one new streaming function. The single highest-risk area is **mobile parity for the report sub-page**, because — contrary to what the CONTEXT wording implies — **no mobile sales-report precedent exists to copy** (see Discrepancies). Treat the mobile `/m/finance/report` as newly assembled from existing seams, not copied.

## Discrepancies Between CONTEXT.md and Actual Code (highest-value findings)

1. **No mobile report precedent exists.** `app/routes/mobile_reports.py` contains ONLY `/m/reports/expiry` — there is NO `/m/reports/sales` or any mobile period-report to clone. CONTEXT D-04a ("a mobile counterpart... near-verbatim reuse of the `/reports/sales` pattern") and D-04c ("the same way FIN-03..07 did it") therefore describe a **new construction**, not a copy. The reusable seams that DO exist: the shared, already-parameterised `partials/period_filter.html` (takes `period_action` + `period_target`), and the `finance_base`-prefix convention proven by the Phase 16 finance forms. The mobile report page must be assembled from these; there is no drop-in mobile template.

2. **`compute_balance` is whole-till and unfiltered — it CANNOT serve FIN-11.** `compute_balance` is `select(func.coalesce(func.sum(CashMovement.amount_cents), 0))` with **no WHERE clause**. FIN-11 needs a NEW period+category-scoped sum. Do not try to parameterise `compute_balance`; add a separate `cash_expense_total(session, start_iso, end_iso)`.

3. **The "coarse-bucket grouping map" D-01a references is `CASH_BUCKETS` in `app/models.py`** (lines 88–99). It already defines `"withdrawal"` (5 keys) and `"return"` (1 key). FIN-11's expense set = `CASH_BUCKETS["withdrawal"] + CASH_BUCKETS["return"]`. The query must compose from this map — do NOT hardcode the six-string list (D-01a). `CASH_BUCKETS` is server-side only (never a Jinja global), so it is available in services but not templates.

4. **`sales_profit_report` returns `cost_unknown_count` as a count of sale LINES (operations), not products.** Verified in source: it increments per operation row whose `unit_cost_cents is None`. Fine for FIN-10's caveat, but the FIN-12 `*_unknown_count` values are a different quantity (count of in-stock products missing a price) — do not conflate them.

5. **Existing `/finance` GET does not accept `from`/`to`.** Adding dashboard tiles with a period selector (D-04) requires either new query params on `/finance` (and `/m/finance`) or a dedicated tiles-partial endpoint (e.g. `/finance/metrics?from=&to=`). A dedicated partial endpoint keeps the two period controls independent (D-04b) most cleanly and avoids entangling tile refresh with the existing history pagination on the same page.

6. **Desktop finance history renders `None` for empty notes (pre-existing cosmetic bug, STATE.md blocker).** `partials/cash_history_rows.html` line 49 is `{{ mv.note }}` — a NULL note renders literal "None". The FIN-09 CSV must guard this: `_csv_safe(movement.note or "")`. Opportunistically fixing the template cell (`{{ mv.note or "" }}`) while touching finance templates is advisable but is a Phase-16 carry-over, not a Phase-17 requirement.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Period resolution / validation (FIN-08/09/10/11) | API / service (`_resolve_period`) | — | V5 input validation must be server-side; malformed/inverted ranges fall back to today, never reach SQL. |
| Gross profit aggregation (FIN-10) | API / service (`sales_profit_report`) | DB (SELECT) | Existing verified read service; reuse verbatim. |
| Net-profit expense sum (FIN-11) | API / service (new `cash_expense_total`) | DB (SELECT) | Signed SUM over a bounded category set + period; portable ORM. |
| Stock valuation (FIN-12) | API / service (new `stock_valuation`) | DB (SELECT) | Point-in-time SUM over active products. |
| Cash-flow-by-category (FIN-08) | API / service (new fn) | DB (SELECT) | Group `cash_movements` by bucket within period. |
| CSV streaming (FIN-09) | API / service (`export.py`) | — | Reuse BOM-once/delimiter/injection-escape stack; StreamingResponse. |
| Tiles + report rendering | Frontend server (Jinja/HTMX) | Browser (HTMX swap) | Server-rendered partials swapped by HTMX; no client state. |

## Standard Stack

No new packages. Every dependency is already in the project (see CLAUDE.md Technology Stack: FastAPI 0.139.0, SQLAlchemy 2.0.51, Jinja2 3.1.6, htmx 2.0.10 vendored, pytest 9.1.1, httpx 0.28.1). Python stdlib `csv`/`io` already power `export.py`.

**Package Legitimacy Audit:** N/A — this phase installs no external packages. All code reuses in-repo modules.

**Environment Availability:** N/A — no external tools/services/runtimes beyond the already-running app. Pure code/template changes.

## Verified Existing Seams (call exactly these)

### `app/routes/reports.py`
- `_resolve_period(from_raw: str, to_raw: str, tz_name: str) -> dict` — returns `{from_date: date, to_date: date, active_preset: str|None, error: str|None, presets: {key: {"from": iso, "to": iso}}}`. Empty both = today's preset (not an error). Malformed → `INVALID_DATE_ERROR`, inverted → `INVERTED_RANGE_ERROR`, both fall back to `today`. **This is a module-level function in a routes file, not a service** — import it as `from app.routes.reports import _resolve_period`, or (cleaner) copy the same call shape. Pass `settings.display_tz`. [VERIFIED: app/routes/reports.py:32]
- `/reports/sales` route body is the exact template to clone for `/finance/report`: `period = _resolve_period(...)` → guard `if not period["error"]` → `start_iso, end_iso = local_day_bounds_utc(period["from_date"], period["to_date"], settings.display_tz)` → call report fn → build context (from_date/to_date isoformat, active_preset, presets, error, report) → `if bool(request.headers.get("HX-Request"))` return the results **partial**, else the full **page**. [VERIFIED: app/routes/reports.py:91-119]

### `app/core.py`
- `local_day_bounds_utc(start_day: date, end_day: date, tz_name: str) -> tuple[str, str]` — half-open `[start, end)` UTC ISO bounds; `end` is local midnight of the day AFTER `end_day`. The ONLY sanctioned local-range→UTC conversion. [VERIFIED: app/core.py:75]
- `format_cents(cents: int) -> str` → `"12,50"` / `"-12,50"`; `iso_to_local(iso_str, tz_name) -> "dd.mm.yyyy HH:MM"`. Jinja filters `| cents` and `| local_dt` are registered globally; the CSV service calls the functions directly (as `stream_sales_csv` does). [VERIFIED: app/core.py:49,69; app/routes/__init__.py:16-17]

### `app/services/reports.py`
- `sales_profit_report(session, start_iso, end_iso) -> dict` — reuse verbatim for FIN-10. Returns `{"totals": {"units_sold", "revenue_cents", "cost_cents", "profit_cents", "cost_unknown_count"}, "by_product": [...], "cost_unknown_count": int}`. NULL `unit_cost_cents` lines are EXCLUDED from cost/profit and counted in `cost_unknown_count`; deliberately does NOT filter `Product.deleted_at` (historical). FIN-10 uses `report["totals"]["profit_cents"]`. [VERIFIED: app/services/reports.py:20-82]

### `app/services/finance.py`
- `compute_balance(session) -> int` — live whole-till SUM, **no WHERE** (do not reuse for FIN-11; see Discrepancy 2). [VERIFIED: app/services/finance.py:165-171]
- `cash_history_view(...)` — shows the established `CASH_BUCKETS.get(bucket)` → `category.in_(cats)` filter pattern that the new aggregation queries should mirror. [VERIFIED: app/services/finance.py:174-211]
- `record_cash_movement` / `record_manual_movement` — the write path; Phase 17 must NOT call these.

### `app/services/export.py`
- `_csv_safe(value) -> str` (leading `= + - @` → prefix `'`), `_csv_rows(header, rows) -> Generator[str]` (`;` delimiter, header first), `_encode_once(chunks) -> Generator[bytes]` (utf-8-sig on first chunk only). `stream_sales_csv` is the shape to copy: build `header` list + `rows` list of lists, wrap `StreamingResponse(_encode_once(_csv_rows(header, rows)), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=cash_movements.csv"})`. [VERIFIED: app/services/export.py:35-141]
- **T-06-09 docstring** (module docstring, lines 12–18) currently states "no function here accepts a filename, path, or any other externally-supplied parameter — every export is a full, unfiltered table dump." D-03b requires editing it to record the validated `from`/`to` exception. [VERIFIED: app/services/export.py:1-18]

### `app/routes/export.py`
- Existing export routes are param-less hardcoded dumps (`test_web_export_ignores_client_params` pins that products.csv ignores query params). The new cash-movements CSV route **intentionally departs** by taking `from`/`to` — this is exactly what D-03b documents. Decide placement: the route may live in `export.py` (alongside the other CSVs) or on the finance surface (`/finance/report.csv`); the button is on `/finance/report` (D-04a). [VERIFIED: app/routes/export.py; tests/test_export.py:203-208]

### `app/models.py`
- `CASH_BUCKETS: dict[str, tuple[str, ...]]` — `"withdrawal"` = 5 keys, `"return"` = `("return",)`, `"sale"`, `"deposit"`. FIN-11 expense set = `CASH_BUCKETS["withdrawal"] + CASH_BUCKETS["return"]`. Server-side only. [VERIFIED: app/models.py:88-99]
- `CASH_CATEGORIES` — key→RU label (Jinja global), used for report/CSV category labels. [VERIFIED: app/models.py:69-81]
- `CashMovement`: `category` (String20), signed `amount_cents` (Integer), `note` (nullable String300), `created_at` (UTC ISO text), `sale_id` (nullable). Filter period via `created_at >= start_iso` AND `created_at < end_iso` (ISO text sorts chronologically). [VERIFIED: app/models.py:370-401]
- `Product`: `quantity` (Integer, not null), `cost_cents`/`sale_cents` (nullable Integer), `deleted_at` (nullable). FIN-12 filters `deleted_at IS NULL`. [VERIFIED: app/models.py:129-170]
- `Batch`: has `price_cents` (sale snapshot) but **NO cost column** — confirms D-02 (no batch-level cost valuation). [VERIFIED: app/models.py:194-232]

### `app/services/pagination.py`
- `page_window(page, total_pages, spread=2)`, `paginate(rows, page)`, `LIST_PAGE_SIZE=20`. Use only if the FIN-08 movement list is long enough to page (D-04a "if the report is long"). [VERIFIED: app/services/pagination.py]

### Templates
- `partials/period_filter.html` — shared preset bar + от/по form; parameterised by `period_action` + `period_target` via `{% with %}`. Reuse verbatim for `/finance/report` and (with a distinct target) the dashboard tile selector. [VERIFIED: app/templates/partials/period_filter.html]
- `pages/reports_sales.html` + `partials/sales_report_results.html` — the page-wraps-results-in-a-target-div pattern (`<div id="sales-results">{% include results %}</div>`); the results partial is also the HX swap payload. Clone this structure for the report page. [VERIFIED]
- `pages/finance.html`, `mobile_pages/finance.html` — where tiles + a light period selector get added (above/below the existing balance/forms/history includes). [VERIFIED]

## Architecture Patterns

### System data flow (report + tiles)

```
Browser (HTMX GET /finance/report?from=&to=  or preset link)
   │
   ▼
route: _resolve_period(from,to,tz) ──error?──► render page with inline RU error, no query
   │ ok
   ▼
local_day_bounds_utc(from_date,to_date,tz) → (start_iso, end_iso)
   │
   ├─► cash_flow_report(session,start_iso,end_iso)   [FIN-08: group by CASH_BUCKETS]
   │
   ▼
HX-Request header?  ── yes ─► return results PARTIAL (swapped into #target)
                     ── no  ─► return full PAGE (chrome + period_filter + results)

Dashboard tiles (/finance or /finance/metrics?from=&to=):
   sales_profit_report → profit_cents           [FIN-10 gross]
   cash_expense_total(start,end) → signed sum    [FIN-11: net = gross + expense_sum]
   stock_valuation(session) → cost/sale/unknowns [FIN-12: period-INDEPENDENT tile]
```

### Recommended additions (structure)
```
app/services/finance.py         # add cash_expense_total, stock_valuation, cash_flow_report
                                #   (or a sibling app/services/finance_reports.py — Claude's discretion)
app/services/export.py          # add stream_cash_movements_csv(session, start_iso, end_iso)
app/routes/finance.py           # add /finance/report (+ metrics/tiles), delegate CSV route
app/routes/mobile_finance.py    # add /m/finance/report (+ mobile tiles) via finance_base prefix
app/templates/
  partials/finance_tiles.html        # gross/net/stock tiles + dashboard period selector
  partials/cash_flow_report.html     # FIN-08 results partial (HX swap payload)
  pages/finance_report.html          # /finance/report full page (wraps results in target div)
  mobile_partials/ + mobile_pages/   # mobile counterparts (new — no precedent to copy)
```

### Pattern 1: period-scoped read service (mirror `sales_profit_report`)
```python
# Source: app/services/reports.py (verified pattern), adapted for FIN-11
from app.models import CASH_BUCKETS, CashMovement
from sqlalchemy import func, select

def cash_expense_total(session, start_iso: str, end_iso: str) -> int:
    """Signed SUM(amount_cents) of outflow categories in [start_iso, end_iso).
    Rows are already negative (D-01a) → the caller adds this to gross profit."""
    cats = CASH_BUCKETS["withdrawal"] + CASH_BUCKETS["return"]
    return session.scalar(
        select(func.coalesce(func.sum(CashMovement.amount_cents), 0)).where(
            CashMovement.category.in_(cats),
            CashMovement.created_at >= start_iso,
            CashMovement.created_at < end_iso,
        )
    )
```

### Pattern 2: point-in-time valuation excluding NULL prices (FIN-12)
```python
# SQL-side: NULL cost_cents makes (quantity*cost_cents) NULL, which SUM skips —
# this reproduces "exclude NULL, never treat as zero" (D-02a). coalesce guards
# the all-NULL case. Unknown counts are a SEPARATE COUNT.
from app.models import Product
def stock_valuation(session) -> dict:
    active = Product.deleted_at.is_(None)
    cost_value = session.scalar(select(func.coalesce(
        func.sum(Product.quantity * Product.cost_cents), 0)).where(active))
    sale_value = session.scalar(select(func.coalesce(
        func.sum(Product.quantity * Product.sale_cents), 0)).where(active))
    cost_unknown = session.scalar(select(func.count()).where(
        active, Product.cost_cents.is_(None), Product.quantity > 0))
    sale_unknown = session.scalar(select(func.count()).where(
        active, Product.sale_cents.is_(None), Product.quantity > 0))
    return {"cost_value_cents": cost_value, "sale_value_cents": sale_value,
            "cost_unknown_count": cost_unknown, "sale_unknown_count": sale_unknown}
```
**Decision point (planner):** whether the unknown counts restrict to `quantity > 0` (recommended — a zero-stock product missing a price contributes 0 to the sum and is not a meaningful caveat). Either way, follow the `is_(None)` discipline, never a bare `or`.

### Pattern 3: CSV export function (mirror `stream_sales_csv`, add period bounds)
```python
# Guard note against None (Discrepancy 6). Use CASH_CATEGORIES for the label,
# format_cents for the signed amount, iso_to_local for the timestamp.
def stream_cash_movements_csv(session, start_iso, end_iso):
    rows_q = session.scalars(select(CashMovement).where(
        CashMovement.created_at >= start_iso, CashMovement.created_at < end_iso
    ).order_by(CashMovement.created_at)).all()
    header = ["Когда", "Категория", "Комментарий", "Сумма"]
    rows = [[iso_to_local(m.created_at, settings.display_tz),
             _csv_safe(CASH_CATEGORIES.get(m.category, m.category)),
             _csv_safe(m.note or ""), format_cents(m.amount_cents)] for m in rows_q]
    return StreamingResponse(_encode_once(_csv_rows(header, rows)),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cash_movements.csv"})
```

### Anti-Patterns to Avoid
- **Reusing `compute_balance` for net profit** — it is unfiltered whole-till; you will get the wrong number. Use a period+category-scoped sum.
- **Hardcoding the 6 outflow category strings** — compose from `CASH_BUCKETS` (D-01a).
- **Treating NULL price as 0** in valuation — silently understates; exclude and count instead (D-02a).
- **SQLite-specific SQL** (`strftime`, `INSERT OR REPLACE`) — portable ORM only.
- **Filtering `Product.deleted_at` inside gross profit** — `sales_profit_report` is historical by design; do not modify it.
- **hx-get on the CSV download link** — must be a plain `<a href>` (htmx would swap the CSV into the DOM; pinned by `test_web_export_page` in test_export.py).
- **Rendering the CSV formula-escape or bucket sum on the client** — all aggregation and escaping stay server-side.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Parse/validate a date range | A new from/to parser | `_resolve_period` (D-03) | Handles presets, inverted/malformed ranges, RU error fallback, V5 safety. |
| Local-day → UTC filter bounds | Manual string slicing of `created_at` | `local_day_bounds_utc` | Half-open bounds; avoids the near-midnight day-shift bug. |
| Gross profit | Re-aggregate sale operations | `sales_profit_report` (FIN-10) | Already NULL-cost-safe; verbatim reuse is the locked decision. |
| Outflow category set | Hardcode 6 strings | `CASH_BUCKETS["withdrawal"] + ["return"]` | Single source of truth; survives category changes. |
| CSV BOM / delimiter / injection | New csv writer | `_encode_once`/`_csv_rows`/`_csv_safe` | RU-Excel correctness + T-06-10 hardening already solved and tested. |
| Money rendering | `f"{x/100}"` | `format_cents` | Integer-cents, comma separator, sign handling. |
| Pagination window | New "1 2 … 9" math | `page_window` / `paginate` | Single shared algorithm (Phase 14 rule). |
| Preset bar + от/по form | New template | `partials/period_filter.html` | Already parameterised by action/target. |

**Key insight:** almost nothing here is new logic — it is composition of verified seams. The risk is in *wiring* (mobile parity, tile refresh endpoint, docstring exception), not in algorithms.

## Common Pitfalls

### Pitfall 1: Net-profit sign confusion
**What goes wrong:** subtracting `cash_expense_total` from gross profit.
**Why:** the rows are stored negative (withdrawals/returns), so `net = gross + expense_sum` is a plain addition (D-01a). Subtracting double-counts the sign.
**How to avoid:** add, do not subtract; assert in a test that a period with one −1000 withdrawal yields `net == gross - 1000`.
**Warning sign:** net profit larger than gross when expenses exist.

### Pitfall 2: The D-01b return caveat rendered as fact
**What goes wrong:** the net tile reads like accounting profit; a return understates it by the returned item's cost.
**How to avoid:** the tile MUST carry the cash-outflow label/tooltip (D-01b). This is a hard UI requirement, not decoration.

### Pitfall 3: Two period controls entangled
**What goes wrong:** the dashboard tile selector and the `/finance/report` selector share query params / target and move together.
**How to avoid:** independent controls (D-04b) — distinct `period_target` on the shared partial, and ideally a separate tiles endpoint (Discrepancy 5). The stock tile ignores both (point-in-time).

### Pitfall 4: NULL note breaks CSV / renders "None"
**What goes wrong:** `mv.note` is None → CSV writes "None" or the desktop cell shows "None".
**How to avoid:** `_csv_safe(m.note or "")`; optionally fix the desktop template cell.

### Pitfall 5: Mobile report assumed to be a copy
**What goes wrong:** planner writes "clone `/m/reports/sales`" — it does not exist.
**How to avoid:** build the mobile report from `period_filter.html` + `finance_base` prefix; treat it as new (Discrepancy 1).

### Pitfall 6: `_resolve_period` import coupling
**What goes wrong:** `_resolve_period` lives in `app/routes/reports.py` (a routes module), so importing it into `finance.py`/`mobile_finance.py` couples two route modules.
**How to avoid:** acceptable to import it (it is pure/side-effect-free), or lift it to a shared location — Claude's discretion. If lifted, keep the exact behaviour and update `reports.py` to import from the new home.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Full-table unfiltered CSV dumps (BCK-02) | Period-validated CSV via `_resolve_period` bounds | Phase 17 (this) | First export to accept a client param; T-06-09 docstring must document the bounded exception (D-03b). |
| Balance-only `/finance` | Dashboard with profit/net/stock tiles | Phase 17 | `/finance` GET gains period-aware tiles; keep existing balance/forms/history intact. |

**Deprecated/outdated:** none introduced. No package upgrades. htmx stays 2.0.10 (vendored); do not touch htmx 4 (CLAUDE.md).

## Validation Architecture

Nyquist validation ENABLED. Framework already present.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + FastAPI `TestClient` (httpx 0.28.1) |
| Config file | none dedicated; tests live in `tests/`, fixtures in `tests/conftest.py` (`engine`, `session`, `product`, `client`) |
| Quick run command | `uv run pytest tests/test_finance_reports.py -x` (new file) |
| Full suite command | `uv run pytest` |
| Naming convention (VERIFIED in test_export.py) | route/web tests prefixed `test_web_*`; service-level tests MUST NOT use that prefix |

### Phase Requirements → Test Map
| Req | Behavior | Test Type | Automated Command | File |
|-----|----------|-----------|-------------------|------|
| FIN-08 | Movements grouped by income vs expense category for a period; empty period → empty-state; period bounds are half-open | service + web | `uv run pytest tests/test_finance_reports.py -x` | ❌ Wave 0 |
| FIN-08 | `/finance/report` returns full page on plain GET, results partial on HX-Request | web | `uv run pytest tests/test_finance_reports.py -k report_hx -x` | ❌ Wave 0 |
| FIN-09 | CSV roundtrip: `;`-delimited, one BOM, `CASH_CATEGORIES` label, signed `format_cents` amount, NULL note → "", formula-escape on note | service + web | `uv run pytest tests/test_finance_reports.py -k csv -x` | ❌ Wave 0 |
| FIN-09 | Only rows in `[start_iso,end_iso)` exported (boundary rows correct) | service | same file | ❌ Wave 0 |
| FIN-10 | Gross profit tile == `sales_profit_report` profit_cents for the period; NULL-cost caveat surfaced | service + web | `-k gross` | ❌ Wave 0 |
| FIN-11 | net == gross + signed expense sum; withdrawal AND return count, deposit/sale excluded; sign is addition | service | `-k net` | ❌ Wave 0 |
| FIN-11 | Net tile shows the cash-outflow caveat label (D-01b) | web | `-k net_caveat` | ❌ Wave 0 |
| FIN-12 | cost/sale sums over active products; NULL price excluded (not zero); unknown counts surfaced; deleted product excluded; point-in-time (ignores period) | service + web | `-k valuation` | ❌ Wave 0 |

### Sampling points (observable outputs)
- **Per task commit:** `uv run pytest tests/test_finance_reports.py -x` (< 5 s).
- **Per wave merge:** `uv run pytest` (full suite green).
- **Phase gate:** full suite green before `/gsd-verify-work`; plus a manual browser check of `/finance`, `/m/finance`, `/finance/report`, `/m/finance/report` and one CSV download opened in Excel (BOM/`;`/RU labels).

### Wave 0 Gaps
- [ ] `tests/test_finance_reports.py` — service-level tests for `cash_expense_total`, `stock_valuation`, `cash_flow_report` and web tests for the report page + CSV route. Reuse the `_ensure_batch` / `_record_sale_at` helpers proven in `tests/test_reports.py` and the CSV-roundtrip assertions proven in `tests/test_export.py`.
- [ ] Fixtures for NULL-price products and mixed cash movements (withdrawal + return + deposit + sale) in the same period — seed a covering balance where relevant (Phase 16 precedent: pre-seed so the negative gate is irrelevant to read tests).
- No framework install needed.

## Security Domain

`security_enforcement` treated as enabled (no config override found). This is a read-only phase; the surface is small but real.

### Applicable ASVS Categories
| ASVS | Applies | Standard Control |
|------|---------|------------------|
| V5 Input Validation | yes | `_resolve_period` clamps `from`/`to`; malformed/inverted → today + RU error, never reaches SQL. `bucket`/category filters use `.in_()` over a server-side allow-list (`CASH_BUCKETS`), never string-interpolated SQL. |
| V5 / CSV injection (T-06-10) | yes | `_csv_safe` on every free-text cell (note, category label) — keep verbatim. |
| V12 File download (T-06-09) | yes | Departure documented: the CSV route now takes a validated calendar range consumed only as an ORM `.where(created_at …)` bound — not a path/filename. Update the docstring (D-03b); do NOT accept filename/path params. |
| V6 Cryptography | no | — |
| V2/V3/V4 Auth/Session/Access | no | Single-operator local app, no auth in v1. |

### Threat patterns for this stack
| Pattern | STRIDE | Mitigation |
|---------|--------|-----------|
| SQL injection via from/to/bucket | Tampering | Parameterised ORM + `_resolve_period` validation + `.in_()` allow-list. |
| CSV formula injection (Excel) | Tampering/Exec | `_csv_safe` leading-apostrophe escape (already tested). |
| XSS via note/category in report HTML | Tampering | Jinja autoescape only; never apply `| safe` to `note`/labels (T-16-06 rule already in cash_history_rows). |
| Unbounded export (DoS) | DoS | Period-scoped stream (streamed, not buffered); single-operator scale. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A dedicated tiles-partial endpoint (e.g. `/finance/metrics`) is the cleanest way to keep the two period controls independent | Discrepancy 5 / Pitfall 3 | LOW — planner may instead add `from`/`to` to `/finance`; both satisfy D-04b if kept independent. |
| A2 | FIN-12 unknown counts should restrict to `quantity > 0` | Pattern 2 | LOW — cosmetic on the caveat number; either interpretation honors D-02a's "exclude NULL". |
| A3 | Importing `_resolve_period` from `app/routes/reports.py` (vs lifting it to a shared module) is acceptable coupling | Pitfall 6 | LOW — behaviour identical; refactor is optional and Claude's discretion. |
| A4 | CSV route placement (export.py vs finance surface) is discretionary | export.py seam | LOW — D-04a only fixes the *button* location (`/finance/report`), not the endpoint path. |

## Open Questions

1. **Where do the new aggregation functions live — `finance.py` or a new `finance_reports.py`?**
   - Known: CONTEXT allows "here or in a sibling module" (canonical_refs) and names are Claude's discretion.
   - Recommendation: a sibling `app/services/finance_reports.py` keeps the single-write-path `finance.py` focused; but adding to `finance.py` is equally valid. Planner picks; not blocking.

2. **Does the FIN-08 movement list need pagination?**
   - Known: `page_window`/`paginate` exist; D-04a says "if the report is long".
   - Recommendation: for a single operator the per-period movement count is small; start without pagination, add `page_window` only if a real period exceeds ~`LIST_PAGE_SIZE` rows. Mirror `_history_context` if added.

## Sources

### Primary (HIGH confidence — verified against repo source this session)
- `app/routes/reports.py` — `_resolve_period`, `local_day_bounds_utc` usage, `/reports/sales` HX branch.
- `app/services/reports.py` — `sales_profit_report` signature/return/NULL-cost/deleted_at handling.
- `app/services/export.py` + `app/routes/export.py` + `tests/test_export.py` — CSV stack, T-06-09 docstring, param-less contract.
- `app/services/finance.py` — `compute_balance` (unfiltered), `cash_history_view` bucket pattern.
- `app/models.py` — `CASH_BUCKETS`, `CASH_CATEGORIES`, `CashMovement`, `Product`, `Batch`.
- `app/core.py` — `format_cents`, `iso_to_local`, `local_day_bounds_utc`.
- `app/routes/finance.py`, `app/routes/mobile_finance.py`, `app/routes/mobile_reports.py`, `app/routes/__init__.py`, `app/main.py` — surfaces, parity mechanics, router registration, Jinja globals.
- Templates: `partials/period_filter.html`, `partials/sales_report_results.html`, `pages/reports_sales.html`, `pages/finance.html`, `mobile_pages/finance.html`, `partials/cash_history_rows.html`.
- `.planning/STATE.md` — the desktop `None`-note advisory (Phase 16 blocker).

### Secondary / Tertiary
- None — no external documentation or WebSearch needed (self-contained internal phase).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all seams verified in source.
- Architecture: HIGH — every reuse target read and confirmed; discrepancies explicitly surfaced.
- Pitfalls: HIGH — derived from actual code (sign convention, unfiltered balance, missing mobile precedent, NULL note).

**Research date:** 2026-07-15
**Valid until:** 2026-08-14 (stable internal codebase; re-verify only if Phases 15/16 seams change).
