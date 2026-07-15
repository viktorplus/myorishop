---
phase: 17-financial-reports-export-dashboard-analytics
reviewed: 2026-07-15T00:00:00Z
depth: standard
files_reviewed: 13
files_reviewed_list:
  - app/routes/finance.py
  - app/routes/mobile_finance.py
  - app/services/export.py
  - app/services/finance_reports.py
  - app/static/style.css
  - app/templates/mobile_pages/finance.html
  - app/templates/mobile_pages/finance_report.html
  - app/templates/pages/finance.html
  - app/templates/pages/finance_report.html
  - app/templates/partials/cash_flow_report.html
  - app/templates/partials/finance_tiles.html
  - tests/test_export.py
  - tests/test_finance_reports.py
findings:
  critical: 2
  warning: 2
  info: 2
  total: 6
status: issues_found
---

# Phase 17: Code Review Report

**Reviewed:** 2026-07-15T00:00:00Z
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

Reviewed the Phase 17 financial-reports/export/dashboard-analytics surface: the two finance routers
(desktop + mobile), the new read-only `finance_reports` service, the CSV export extension
(`stream_cash_movements_csv`), the dashboard-tiles and cash-flow-report templates/partials, and both
test modules. The money math (`cash_expense_total`, `stock_valuation`, `cash_flow_report`), the
NULL-price exclusion discipline, the half-open period bounds, and the CSV BOM/delimiter/formula-injection
hardening are all correct and are exercised by good tests.

However, two BLOCKER-level defects were found by tracing the same page templates the routes render, and
by actually invoking the routes:

1. `GET /finance/history` and `GET /m/finance/history`, when hit as a plain (non-htmx) request, crash
   with an unhandled `500` — reproduced live (see CR-01). Every history/pagination/filter control that
   drives these routes uses `hx-push-url="true"`, so a page refresh, browser back-button, or a shared/
   bookmarked filtered-history URL will 500 in production.
2. The FIN-08/FIN-09 cash-flow report page (`/finance/report`, `/m/finance/report`) and its CSV export
   have **no link anywhere in the UI** — not from `/finance`, not from the `/reports` landing page, not
   from the mobile home tile grid. The feature is only reachable by typing the URL directly.

Both are fixed with small, localized changes (see fixes below). Two further WARNINGs (a non-responsive
3-column tile grid reused on the 480px mobile shell, and near-total code duplication between the desktop
and mobile finance routers — the same duplication pattern that produced CR-01) and two INFO items round
out the findings.

## Critical Issues

### CR-01: `GET /finance/history` and `GET /m/finance/history` 500 on any non-htmx request

**File:** `app/routes/finance.py:139-157`, `app/routes/mobile_finance.py:159-184`

**Issue:** Phase 17 added a "Показатели" (dashboard tiles + period filter) section to
`pages/finance.html` and `mobile_pages/finance.html`, which now unconditionally `{% include
"partials/period_filter.html" %}` and `{% include "partials/finance_tiles.html" %}`. Those partials
require `presets`, `from_date`, `to_date`, `active_preset`, `error`, `metrics`, and `valuation` in the
render context (see `_metrics_context` in both routers).

`finance_page`, `finance_metrics`'s full-page fallback, and their mobile mirrors were all updated to
merge `**_metrics_context(...)` into the context before rendering `pages/finance.html` /
`mobile_pages/finance.html`. `finance_history` and `mobile_finance_history` were **not** — their non-htmx
fallback branch renders the full page with only `_history_context(...)` plus `balance_cents`/`form`/
`errors`, so `presets` (and `metrics`/`valuation`) are undefined in the template.

Reproduced live against this codebase (`TestClient`, no `HX-Request` header):
```
GET /finance/history?bucket=withdrawal   -> 500 Internal Server Error
GET /m/finance/history?bucket=withdrawal -> 500 Internal Server Error
```
Traceback bottoms out at:
```
File "app/templates/partials/period_filter.html", line 8, in top-level template code
    <a href="{{ period_action }}?from={{ presets.today.from }}&amp;to={{ presets.today.to }}"
jinja2.exceptions.UndefinedError: 'presets' is undefined
```
Every control that targets these routes (`bucket` filter, desktop pagination links, mobile "Показать
ещё") sets `hx-push-url="true"`, which pushes the filtered/paged URL into browser history. A refresh,
back/forward navigation, or a bookmarked/shared link to that URL issues a plain (non-htmx) GET and hits
this exact 500. This is untested: every existing test for these two routes
(`tests/test_finance.py`, e.g. lines 730-775 and 960-1022) sends `headers=_HX` and never exercises the
non-htmx fallback branch, so the regression shipped without a failing test.

**Fix:** Merge `_metrics_context(session, "", "")` into the full-page fallback context, mirroring
`finance_page`/`finance_metrics`:
```python
# app/routes/finance.py
@router.get("/finance/history")
def finance_history(...):
    context = _history_context(session, bucket=bucket, page=page)
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "partials/cash_history_rows.html", context)
    context = {
        **context,
        "balance_cents": compute_balance(session),
        "form": {},
        "errors": {},
        **_metrics_context(session, "", ""),
    }
    return templates.TemplateResponse(request, "pages/finance.html", context)
```
Apply the identical merge in `app/routes/mobile_finance.py::mobile_finance_history`. Add a regression
test that hits both routes without the `HX-Request` header and asserts `200`.

### CR-02: FIN-08/FIN-09 cash-flow report page is unreachable from the UI

**File:** `app/templates/pages/finance.html`, `app/templates/mobile_pages/finance.html`,
`app/templates/pages/reports_landing.html`, `app/templates/mobile_pages/home.html`

**Issue:** `/finance/report` (and its mobile mirror `/m/finance/report`, plus the
`/finance/report.csv` / `/m/finance/report.csv` downloads) implement the whole FIN-08/FIN-09
cash-flow report + CSV export feature, and are fully covered by tests — but no template anywhere in
the app links to them:

- `app/templates/pages/finance.html` / `mobile_pages/finance.html` (the "Финансы" page itself) render
  balance, forms, history and the new dashboard tiles, but never link to `/finance/report`.
- `app/templates/pages/reports_landing.html:5` lists every other period report
  (`/reports/sales`, `/reports/stock`, `/reports/writeoffs`, `/reports/products`, `/reports/expiry`)
  but omits the cash-flow report entirely.
- `app/templates/mobile_pages/home.html` has a tile per top-level feature (`/m/sales`, `/m/receipts`,
  ... `/m/finance`) but no tile or link for `/m/finance/report`.

Confirmed via `grep -rn "finance/report" app/templates` — the only occurrences are inside
`finance_report.html`/`mobile_pages/finance_report.html` themselves (the CSV download link and the
`period_filter` `hx-get` target), i.e. self-references. A user has no way to discover this page short of
typing the URL by hand.

**Fix:** Add a link from the finance page(s) to the report, e.g. in `app/templates/pages/finance.html`:
```html
<h2>Показатели</h2>
...
<p><a href="/finance/report">Отчёт по кассе за период</a></p>
```
and mirror in `mobile_pages/finance.html` (or add an entry point on `/m/finance`'s tile grid), and add
the cash-flow report to the reports landing page:
```html
<p><a href="/reports/sales">Продажи и прибыль</a> · ... · <a href="/finance/report">Движения кассы</a></p>
```

## Warnings

### WR-01: `.metric-grid` uses a fixed 3-column layout with no responsive breakpoint, applied to the 480px mobile shell

**File:** `app/static/style.css:331-335`
**Issue:** `.metric-grid { grid-template-columns: repeat(3, 1fr); }` is shared verbatim between
`partials/finance_tiles.html` on the desktop page (`.container`, `max-width: 960px`) and the mobile page
(`.mobile-shell`, `max-width: 480px`). The stylesheet has no `@media` queries at all (verified: zero
matches for `@media` in `app/static/style.css`), so on a real ~360-414px phone viewport each of the
three tiles gets roughly 100-120px of width while containing a heading, a bold money figure (e.g.
"12 345,67 ₽"), and often 1-2 additional `.muted` caveat lines — this will wrap/overflow badly. Contrast
with the existing `.mobile-tile-grid { grid-template-columns: 1fr 1fr; }` (2 columns), which was
deliberately chosen for the same 480px shell for exactly this reason.
**Fix:** Add a mobile override, e.g.:
```css
@media (max-width: 480px) {
  .metric-grid { grid-template-columns: 1fr; }
}
```
or give `.metric-grid` its own mobile-scoped variant analogous to `.mobile-tile-grid`.

### WR-02: `_metrics_context` (and most of the surrounding helpers) are byte-for-byte duplicated between the desktop and mobile finance routers

**File:** `app/routes/finance.py:69-99`, `app/routes/mobile_finance.py:65-95`
**Issue:** `_metrics_context` in both files is an identical copy (same body, same docstring modulo one
word). `_history_context` and `_movement_success` are near-duplicates that diverge only in the target
markup (rows table vs. card stack). This is called out in the docstrings as an intentional "near-verbatim
clone" pattern already used elsewhere in the codebase, but it is exactly the kind of duplication that
allowed CR-01 to happen: the desktop and mobile `finance_history` handlers had to be fixed identically
and one was missed. Any future change to the metrics/history context shape has to be applied twice by
hand with no compiler/test enforcing parity beyond manual mirroring.
**Fix:** Not blocking, but consider extracting `_metrics_context` (which takes no `finance_base`-dependent
behavior beyond passing the constant through) into a shared module (e.g. `app/services/finance_reports.py`
or a small `app/routes/_finance_shared.py`) parameterized by `finance_base`, so a fix only needs to land
once.

## Info

### IN-01: `stream_sales_csv`'s "Кто" column bypasses `_csv_safe`, unlike every other free-text cell in the module

**File:** `app/services/export.py:140`
**Issue:** Every free-text CSV cell in this module (`product.code`, `product.name`, `product.category`,
`customer.name`, `customer.surname`, `customer.consultant_number`, the sales `buyer` string, the
cash-movement `note`/category label) is wrapped in `_csv_safe(...)` per the module's own documented
CSV-formula-injection policy (T-06-10). `op.created_by` (rendered under the "Кто" header) is emitted raw:
```python
op.created_by,
```
Risk is low today because `created_by` is stamped from `settings.operator_name` (local deployment
config, not per-request user input — see `app/config.py:15`), not attacker-controlled per the current
single-operator design. Still, it is an inconsistency with the module's stated "every free-text value"
escaping policy, and would become exploitable the moment `operator_name`/`created_by` becomes
configurable by an untrusted actor (e.g. multi-operator sync, mentioned as a future milestone in
CLAUDE.md).
**Fix:** `_csv_safe(op.created_by)` for consistency/defense-in-depth.

### IN-02: `finance.py`/`mobile_finance.py` import a private helper across a route-module boundary

**File:** `app/routes/finance.py:21`, `app/routes/mobile_finance.py:26`
**Issue:** Both routers do `from app.routes.reports import _resolve_period` — an underscore-prefixed
(by Python convention, module-private) function defined in a sibling *routes* module, not a service.
Reaching into another route module's private API works today but is a minor architectural smell: routes
are supposed to stay thin and call services, and a leading-underscore name signals "not a stable
cross-module contract."
**Fix:** No urgency, but consider promoting `_resolve_period` to a shared service (e.g.
`app/services/periods.py`) the next time it's touched, so its cross-module usage is an explicit public
contract instead of a private-name import.

---

_Reviewed: 2026-07-15T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
