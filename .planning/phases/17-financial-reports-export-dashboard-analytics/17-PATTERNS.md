# Phase 17: Financial Reports, Export & Dashboard Analytics - Pattern Map

**Mapped:** 2026-07-15
**Files analyzed:** 13 (5 new, 8 modified) + 2 test targets
**Analogs found:** 13 / 13 (all reuse-heavy; only mobile report page is new-construction)

> This is a **100% read-only, reuse-heavy** phase. Almost every new function/file
> has a verbatim analog already in the repo. The risk is *wiring* (mobile parity,
> tile-refresh endpoint, docstring exception), not algorithms. All line numbers
> below are verified against source this session.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `app/services/finance.py` (+3 read fns) *or* new `app/services/finance_reports.py` | service | CRUD (read) | `app/services/reports.py::sales_profit_report` / `top_selling_products` | exact |
| `app/services/export.py::stream_cash_movements_csv` (new fn + docstring edit) | service | streaming / file-I/O | `app/services/export.py::stream_sales_csv` | exact (same module) |
| `app/routes/finance.py` (+ `/finance/report`, `/finance/metrics`, CSV route) | route | request-response | `app/routes/reports.py::reports_sales_page` | exact |
| `app/routes/mobile_finance.py` (+ `/m/finance/report`, `/m/finance/metrics`) | route | request-response | `app/routes/reports.py::reports_sales_page` + `mobile_finance.py` parity mechanics | role-match (NEW construction — see below) |
| `app/templates/pages/finance_report.html` (new) | template | request-response | `app/templates/pages/reports_sales.html` | exact |
| `app/templates/partials/cash_flow_report.html` (new) | template | request-response | `app/templates/partials/sales_report_results.html` | role-match |
| `app/templates/partials/finance_tiles.html` (new) | template | request-response | `sales_report_results.html` totals table + `.mobile-tile` CSS | partial |
| `app/templates/pages/finance.html` (modify: add tiles section) | template | request-response | own structure + `reports_sales.html` `{% with %}` include | exact |
| `app/templates/mobile_pages/finance.html` (modify) + mobile report page/partial (new) | template | request-response | `mobile_pages/finance.html` + `period_filter.html` | NEW construction |
| `app/static/style.css` (add `.metric-grid`/`.metric-tile`) | config/style | — | existing `.mobile-tile` / `.mobile-tile-grid` tokens | exact (token reuse) |
| `tests/test_finance_reports.py` (new) | test | — | `tests/test_reports.py` + `tests/test_export.py` | role-match |

**Aggregation-function home** = planner discretion (CONTEXT canonical_refs): add to
`app/services/finance.py` or a sibling `finance_reports.py`. Either is valid; a
sibling keeps the single-write-path `finance.py` focused.

---

## Pattern Assignments

### New read services — `cash_expense_total`, `stock_valuation`, `cash_flow_report` (service, read)

**Analog:** `app/services/reports.py::sales_profit_report` (lines 20–82) and `top_selling_products` (lines 144–167).

**Module docstring / discipline to copy** (`app/services/reports.py:1-7`): 100% read-only, "every function only ever SELECTs. Portable ORM only, no SQLite-specific SQL." Repeat this contract at the top of any new module.

**Imports pattern** (`app/services/reports.py:9-17`):
```python
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.config import settings
from app.models import ...  # add CASH_BUCKETS, CashMovement, Product
```

**Half-open period predicate** (used verbatim in every report fn, `reports.py:37-41`):
```python
.where(
    Operation.created_at >= start_iso,
    Operation.created_at < end_iso,
)
```
Apply to `CashMovement.created_at` for FIN-08/09/11 (ISO text sorts chronologically).

**Bucket → `.in_()` set pattern** (source: `app/services/finance.py::cash_history_view`, lines 195-198):
```python
cats = CASH_BUCKETS.get(bucket) if bucket else None
if cats:
    stmt = stmt.where(CashMovement.category.in_(cats))
```
FIN-11 (`cash_expense_total`) composes the expense set from the map — **do not hardcode the 6 strings** (D-01a):
```python
cats = CASH_BUCKETS["withdrawal"] + CASH_BUCKETS["return"]  # 5 + 1 keys
select(func.coalesce(func.sum(CashMovement.amount_cents), 0)).where(
    CashMovement.category.in_(cats),
    CashMovement.created_at >= start_iso,
    CashMovement.created_at < end_iso,
)
```
Rows are already negative → net = `profit_cents + expense_total` is a plain **addition** (D-01a; Pitfall 1 — never subtract).

**NULL-price exclusion pattern** (source discipline: `sales_profit_report` lines 61-66 — `if op.unit_cost_cents is not None`; and `stale_products` uses `Product.deleted_at.is_(None)` at line 189). FIN-12 `stock_valuation`:
- `func.coalesce(func.sum(Product.quantity * Product.cost_cents), 0)` — a NULL `cost_cents` makes the product term NULL, which `SUM` skips (reproduces "exclude, never zero", D-02a). `coalesce` guards the all-NULL/empty case.
- Unknown counts are a SEPARATE `select(func.count()).where(active, Product.cost_cents.is_(None), Product.quantity > 0)`.
- `active = Product.deleted_at.is_(None)` (D-02). Point-in-time, NO period arg (D-02b).
- Do NOT conflate FIN-12's product-count unknowns with `sales_profit_report`'s line-count `cost_unknown_count` (RESEARCH Discrepancy 4).

**`compute_balance` is NOT reusable for FIN-11** (`finance.py:165-171`) — it is `SUM(amount_cents)` with NO WHERE (whole-till). Add a separate period+category-scoped fn (RESEARCH Discrepancy 2).

**FIN-10 gross profit — verbatim reuse, do NOT modify** `sales_profit_report`. Read `report["totals"]["profit_cents"]` and `report["totals"]["cost_unknown_count"]`.

---

### `stream_cash_movements_csv` — `app/services/export.py` (service, streaming)

**Analog:** `stream_sales_csv` (lines 105-141) in the SAME module.

**Reuse verbatim (D-03a):** `_csv_safe` (lines 35-39, leading `= + - @` → `'`), `_csv_rows` (lines 42-54, `;` delimiter, header first), `_encode_once` (lines 57-69, BOM once via `utf-8-sig` on first chunk only).

**Shape to copy** (lines 137-141):
```python
return StreamingResponse(
    _encode_once(_csv_rows(header, rows)),
    media_type="text/csv",
    headers={"Content-Disposition": "attachment; filename=cash_movements.csv"},
)
```

**Row build** — mirror lines 118-136; per D-03c minimum columns:
```python
header = ["Когда", "Категория", "Комментарий", "Сумма"]
rows = [[
    iso_to_local(m.created_at, settings.display_tz),
    _csv_safe(CASH_CATEGORIES.get(m.category, m.category)),
    _csv_safe(m.note or ""),                 # Discrepancy 6 / Pitfall 4: guard None
    format_cents(m.amount_cents),
] for m in movements]
```
Import `CASH_CATEGORIES` (add to line 30 import from `app.models`). Query filters the half-open period on `CashMovement.created_at`, `.order_by(CashMovement.created_at)` (oldest-first, matching `stream_sales_csv`'s chronological dump convention, line 106).

**Docstring edit (D-03b):** the module docstring lines 12-18 currently asserts "no function here accepts a filename, path, or any other externally-supplied parameter — every export is a full, unfiltered table dump." Add the documented exception: a *validated calendar `from`/`to` range* (clamped by `_resolve_period`, consumed only as an ORM `.where(created_at …)` bound — not a path/filename). Keep the T-06-10 `_csv_safe` line intact.

---

### `/finance/report`, `/finance/metrics`, CSV route — `app/routes/finance.py` (route, request-response)

**Analog:** `app/routes/reports.py::reports_sales_page` (lines 91-119).

**Period seam** (import; RESEARCH Pitfall 6 — importing `_resolve_period` from a routes module is acceptable coupling, it is pure/side-effect-free):
```python
from app.routes.reports import _resolve_period
from app.core import local_day_bounds_utc
```

**Route body to clone** (`reports.py:98-119`):
```python
period = _resolve_period(from_, to, settings.display_tz)
report = None
if not period["error"]:
    start_iso, end_iso = local_day_bounds_utc(
        period["from_date"], period["to_date"], settings.display_tz)
    report = cash_flow_report(session, start_iso, end_iso)   # FIN-08 fn
context = {
    "from_date": period["from_date"].isoformat(),
    "to_date": period["to_date"].isoformat(),
    "active_preset": period["active_preset"],
    "presets": period["presets"],
    "error": period["error"],
    "report": report,
    "finance_base": FINANCE_BASE,          # existing module const, line 32
}
if bool(request.headers.get("HX-Request")):
    return templates.TemplateResponse(request, "partials/cash_flow_report.html", context)
return templates.TemplateResponse(request, "pages/finance_report.html", context)
```
Query params use the same alias trick: `from_: str = Query("", alias="from"), to: str = Query("", alias="to")` (`reports.py:94-95`).

**Tiles endpoint (`/finance/metrics`, Discrepancy 5 / A1):** same `_resolve_period` → `local_day_bounds_utc` shape, but calls `sales_profit_report` (gross) + `cash_expense_total` (net) and `stock_valuation` (period-independent). Return `partials/finance_tiles.html` on HX-Request. Keep a **distinct** target from the report (`#finance-metrics` vs `#cashflow-results`, Pitfall 3 / D-04b).

**CSV route** — placement is discretionary (D-04a fixes only the *button* on `/finance/report`). Recommended `@router.get("/finance/report.csv")` delegating to `export_service.stream_cash_movements_csv` after `_resolve_period` + `local_day_bounds_utc`. Thin-route pattern from `app/routes/export.py:23-35`:
```python
@router.get("/finance/report.csv")
def export_cash_movements(from_: str = Query("", alias="from"), to: str = Query("", alias="to"),
                          session: Session = Depends(get_session)):
    period = _resolve_period(from_, to, settings.display_tz)
    start_iso, end_iso = local_day_bounds_utc(period["from_date"], period["to_date"], settings.display_tz)
    return export_service.stream_cash_movements_csv(session, start_iso, end_iso)
```

**Existing `/finance` GET** (lines 63-72) stays; add the tiles section to its context (or refresh tiles via the dedicated `/finance/metrics` endpoint — cleaner independence). Do NOT entangle tile refresh with the existing history pagination on the same page.

---

### `/m/finance/report` + `/m/finance/metrics` — `app/routes/mobile_finance.py` (route — NEW construction)

**⚠ No mobile report precedent exists** (RESEARCH Discrepancy 1 / Pitfall 5): `app/routes/mobile_reports.py` has ONLY `/m/reports/expiry`. Treat this as **new construction assembled from existing seams**, NOT a clone.

Reusable mechanics to mirror:
- Same `_resolve_period` → `local_day_bounds_utc` → HX-Request branch as the desktop route above.
- `FINANCE_BASE = "/m/finance"` prefix convention (`mobile_finance.py:33`) — pass into the shared `period_filter.html` as `period_action="/m/finance/report"`.
- Thin-route + delegate-to-service discipline (mobile_finance module docstring, lines 1-10).
- The same aggregation service fns (no mobile-specific service).

Mobile results partial: either share `partials/cash_flow_report.html` or a mobile variant (D-04c, planner discretion).

---

### Templates

**`pages/finance_report.html` (new)** — clone `pages/reports_sales.html` (lines 1-12) structure exactly:
```jinja
{% extends "base.html" %}
{% block content %}
<h1>Движения кассы за период</h1>
{% with period_action = "/finance/report", period_target = "#cashflow-results" %}
{% include "partials/period_filter.html" %}
{% endwith %}
<a class="button" href="/finance/report.csv?from={{ from_date }}&to={{ to_date }}">Скачать CSV</a>
<div id="cashflow-results">{% include "partials/cash_flow_report.html" %}</div>
{% endblock %}
```
CSV link MUST be a plain `<a href>`, never `hx-get` (RESEARCH anti-pattern; htmx would swap CSV into the DOM, pinned by `test_web_export_page`).

**`partials/cash_flow_report.html` (new)** — clone `sales_report_results.html` (lines 1-48) branch structure:
- `{% if report is none %}` → `.error-block` with «Не удалось загрузить отчёт…» (lines 5-8).
- empty period → `<p class="empty-state muted">За выбранный период движений не было.</p>` (mirror line 10).
- else → two `<table>` sections «Приход» / «Расход» with `.num` right-aligned money cells (D-05). Category labels from `CASH_CATEGORIES` global (never hardcoded). Expense subtotal MUST equal `cash_expense_total` so report and tile reconcile (D-01/D-05).

**`partials/finance_tiles.html` (new)** — three `.metric-tile` in a `.metric-grid`. Figure = `<p class="num"><strong>{{ value | cents }}</strong></p>` (matches balance treatment). Net tile carries MANDATORY `.muted` caveat line (D-01b, hard requirement, always-visible — not a `title=` tooltip; Q3). Stock tile shows «на текущий момент» cue + two lines (по закупке / по продаже) + unknown-count caveats. See UI-SPEC §A copy table.

**`pages/finance.html` (modify)** — add a «Показатели» section with `period_filter.html` (distinct `period_target="#finance-metrics"`, `period_action="/finance/metrics"`) + the tiles include, ABOVE the existing untouched balance/forms/history includes (lines 3-13 stay byte-for-byte, D / regression guard).

**`static/style.css`** — add `.metric-grid` (grid, 16px gap, desktop `repeat(3,1fr)`) + `.metric-tile` (white `#ffffff`, `1px solid #d9d9d9`, `4px` radius, `16px` padding). All existing tokens — mirror `.mobile-tile` / `.mobile-tile-grid`; introduce NO new color/size/spacing (UI-SPEC Q1).

---

## Shared Patterns

### Period resolution + validation (V5)
**Source:** `app/routes/reports.py::_resolve_period` (lines 32-83) + `app/core.local_day_bounds_utc`.
**Apply to:** `/finance/report`, `/finance/metrics`, CSV route (+ mobile). Import from `app.routes.reports`. Malformed/inverted ranges fall back to today with a RU error, never reach SQL. Pass `settings.display_tz`.

### HX-Request full-page-vs-partial branch
**Source:** `reports.py:117-119` (`if bool(request.headers.get("HX-Request"))` → results partial else full page).
**Apply to:** `/finance/report` and `/finance/metrics` (+ mobile).

### Label maps — never hardcode
**Source:** `app/models.py::CASH_CATEGORIES` (lines 69-81), `CASH_BUCKETS` (lines 88-99), `CASH_BUCKET_LABELS` (lines 103+).
**Apply to:** the FIN-11 expense set (`CASH_BUCKETS["withdrawal"] + ["return"]`, server-side only), CSV category column, report row labels. `CASH_CATEGORIES`/`CASH_BUCKET_LABELS` are Jinja globals (`app/routes/__init__.py:27-28`); `CASH_BUCKETS` is server-side ONLY (never a template global).

### CSV safety stack
**Source:** `export.py` `_csv_safe` / `_csv_rows` / `_encode_once` (lines 35-69).
**Apply to:** `stream_cash_movements_csv` — reuse verbatim; `_csv_safe(m.note or "")` on every free-text cell.

### Money / datetime rendering
**Source:** `app/core.format_cents` (`| cents` filter), `iso_to_local` (`| local_dt` filter), registered `app/routes/__init__.py:16-17`. Services call the functions directly (as `stream_sales_csv` does, lines 127/131). Metric numbers NOT sign-colored (UI-SPEC Q4).

### Router registration
Both `app/routes/finance.py` and `mobile_finance.py` routers are already wired; new routes on existing routers need no `main.py` change. (Verify existing include in `app/main.py` when adding — not re-read here.)

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `app/routes/mobile_finance.py::/m/finance/report` + mobile report page/partial | route + template | request-response | **No `/m/reports/sales` mobile period-report exists to clone** (RESEARCH Discrepancy 1). Assemble from `period_filter.html` + `finance_base` prefix + the desktop route's `_resolve_period`/HX branch. Treat as new construction, not a copy. |
| `.metric-grid` / `.metric-tile` CSS | style | — | No desktop tile/card class exists (only `.mobile-tile`). New structural CSS reusing existing token values only. |

---

## Test Patterns

**New file:** `tests/test_finance_reports.py` (RESEARCH Wave 0).
- **Service tests** (no `test_web_` prefix): `cash_expense_total` (add == gross − withdrawal, deposit/sale excluded), `stock_valuation` (NULL excluded not zeroed, deleted excluded, unknown counts, ignores period), `cash_flow_report` grouping + half-open boundary.
- **Web tests** (`test_web_*` prefix per `tests/test_export.py` convention): `/finance/report` full-page-vs-HX-partial, CSV roundtrip (`;`, one BOM, `CASH_CATEGORIES` label, signed `format_cents`, NULL note → "", formula-escape), net-tile caveat present.
- Reuse `_ensure_batch` / `_record_sale_at` helpers from `tests/test_reports.py` and CSV-roundtrip assertions from `tests/test_export.py`. Seed a covering balance for mixed-movement fixtures (Phase 16 precedent).
- Quick run: `uv run pytest tests/test_finance_reports.py -x`.

---

## Metadata

**Analog search scope:** `app/routes/` (reports, finance, mobile_finance, export), `app/services/` (reports, finance, export), `app/models.py`, `app/core.py`, `app/routes/__init__.py`, `app/templates/{pages,partials}/`.
**Files scanned:** 12 source + 4 template (all read this session; line numbers verified).
**Pattern extraction date:** 2026-07-15
</content>
</invoke>
