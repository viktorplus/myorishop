# Phase 24: Navigation Restructure & Settings - Research

**Researched:** 2026-07-17
**Domain:** Server-rendered navigation/information-architecture restructure (FastAPI + Jinja2 + HTMX 2.0.10, no SPA, no new backend capability)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Товары page secondary menu (NAV-01, NAV-02, NAV-03, NAV-07 partial)**
- D-01: A button/toolbar panel above the product list — plain HTML, no JS, no new dropdown component. Rejected: dropdown/flyout menu, `<details>/<summary>` (click-to-reveal, operator wants always-visible), tabs (wrong metaphor).
- D-02: Категории folds into the Товары toolbar, alongside Приход/Списание/Справочник. Its `/categories` page/route stay as-is; only its top-nav entry moves.
- D-03: Каталоги (`/catalogs`) also folds into the Товары toolbar, not Настройки.
- D-04: Toolbar items are grouped by meaning (two semantic groups, e.g. "Действия" vs "Справочники"), not one flat row. Exact grouping/labels are Claude's discretion.
- D-05: The toolbar is always visible/expanded on the Товары page, never collapsed behind a click.

**Настройки page (NAV-05, NAV-06, NAV-04)**
- D-06: `/settings` is a hub page with a short status summary next to each link — количество складов next to Склады, date of last backup next to Резервные копии, both computed from existing services, no new tracking. (Каталоги is NOT on this page — see D-03.)
- D-07: Экспорт (currently standalone `/export` page) is embedded as a section directly on the Резервные копии (`/backup`) page, not linked to as a separate destination. The `/export` route itself may still exist as a backing endpoint, but is no longer a nav destination in its own right.
- D-08: Экспорт кассы (`/finance/report`, currently top-level nav) moves under Настройки, alongside Склады and Резервные копии.

**Mobile navigation (MOB-01)**
- D-09: New persistent tab bar is docked at the TOP of the screen, not the bottom (operator's explicit choice — flag for UI-spec/planning attention, deviates from typical mobile ergonomics).
- D-10: The existing 10-tile mobile home grid (`mobile_pages/home.html`) is removed entirely once the tab bar ships.
- D-11: Items that don't fit in the 7 mobile tabs (Приход, Списание, Перемещение, Справочник, Каталоги) are reached mirroring the desktop pattern — the same toolbar/grouped-button shape from D-01..D-04, adapted for touch, living on the mobile Товары tab.
- D-12: Настройки has NO mobile entry point at all — Склады, Резервные копии, Экспорт кассы, Экспорт are unreachable from `/m/*` by design. Confirmed intentional, not an oversight.

**Перемещение entry point (NAV-07)**
- D-13: Перемещение is reached via a per-row action in the product list (`product_rows.html`), not a product detail page.
- D-14: Opening Перемещение from a product row pre-selects that product on the transfer form automatically — no re-selection step. The transfer form needs to accept an incoming product parameter and pre-fill/lock the product field.

### Claude's Discretion
- Exact Russian button/group labels and layout for the Товары toolbar (D-01/D-04) — as long as it's an always-visible button panel with two semantic groups.
- Exact wording and placement of "Назад к отчётам" on each report detail page (RPT-01) — follow the existing `catalog_detail.html:3` "← Все каталоги" precedent.
- Exact visual treatment of the Настройки summary line (D-06).
- Whether the pre-selected product on the transfer form (D-14) is passed via query param (mirroring History's `?product=` convention) or another mechanism.
- Icon/label choices for the 7 mobile tabs and the top tab bar's exact markup/CSS — no existing mobile tab-bar component to follow.
- Whether `/export` and `/finance/report` keep their existing route paths as backing endpoints (D-07/D-08) or get renamed.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope across all 4 discussed areas. No new capabilities were proposed; every decision was about where an existing page/action becomes reachable from.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| NAV-01 | Приход reached as nested action from Товары, not top-level | Товары toolbar pattern (D-01/D-04); `app/templates/base.html:39` current entry to move; `.form-actions`/`.filter-bar` CSS reuse identified |
| NAV-02 | Списание reached as nested action from Товары | Same toolbar pattern; `base.html:41` entry to move; `tests/test_writeoffs.py:286` nav-presence test WILL break, needs update |
| NAV-03 | Справочник reached from Товары secondary menu | Same toolbar pattern; `base.html:49` entry to move; `tests/test_dictionary.py:321` nav-presence test WILL break |
| NAV-04 | Экспорт reached from Резервные копии page | `app/routes/export.py` + `app/templates/pages/export.html` embed pattern identified; `app/routes/backup.py` extension point identified |
| NAV-05 | Склады reached from Настройки secondary menu | New `/settings` route pattern; `list_warehouses(session)["total"]` identified as the count source (D-06) |
| NAV-06 | Резервные копии reached from Настройки secondary menu | `backup_service.list_backups(...)[0]["created_iso"]` identified as the "last backup date" source (D-06) |
| NAV-07 | Перемещение reached as nested action from product context | `product_rows.html:61-64` per-row actions `<td>` identified as insertion point (D-13) |
| NAV-08 | Top-level nav reduced to 8 pages | `base.html:34-52` full current 17-item nav read and mapped; reduction table below |
| RPT-01 | Every report detail page has "Назад к отчётам" link to /reports | `catalog_detail.html:3` precedent read verbatim; all 5 report detail templates read, all share identical `{% block content %}\n<h1>` opening — trivial, uniform insertion point |
| MOB-01 | Mobile nav includes same main tabs as desktop, excluding Настройки | Mobile route inventory done — **Товары and Покупатели have NO existing mobile page/route today** (critical gap, see Pitfall 1) |
</phase_requirements>

## Summary

This phase touches **zero business logic, zero schema, zero new packages** — it is pure template/route wiring over pages that already exist and already work. The desktop nav (`app/templates/base.html:34-52`) is a flat, hand-rolled 17-`<a>` list with inline Jinja active-state conditionals; reducing it to 8 items plus a new Товары toolbar and a new `/settings` hub page is mechanical. All the CSS building blocks already exist and are reusable without inventing new components: `nav`/`nav a.active` (lines 20-36 of `style.css`), `.form-actions` (flex+gap, already used for grouped buttons), `.filter-bar` (the closest existing "toolbar" precedent), `.button`, and the mobile `.mobile-shell`/`.mobile-actions`/44px-touch-target conventions established in Phase 11.

Three findings materially change what the planner needs to scope, beyond what CONTEXT.md's canonical_refs already flagged:

1. **MOB-01's mobile tab set requires two mobile pages that do not exist yet** — Товары and Покупатели have no `app/routes/mobile_*.py` or `mobile_pages/*.html` today. `mobile_search.py` is a read-only stock lookup, not a Товары-equivalent page, and there is no mobile customer page at all. D-11 explicitly requires the Товары toolbar to "live on the mobile Товары tab," which only makes sense if that tab is a real page. This phase must create these as new thin mobile routes reusing existing desktop services (mirroring `mobile_search.py`'s and `mobile_finance.py`'s established pattern), not just link an existing page.
2. **D-12 ("Настройки has no mobile entry point") has a second, non-obvious enforcement point**: `app/templates/mobile_pages/finance.html:15` already has an in-page `<a class="button" href="/m/finance/report">Отчёт и экспорт CSV</a>` button, independent of the home-grid tile being removed by D-10. If this in-page link is left in place, Экспорт кассы stays reachable from `/m/finance`, contradicting D-12. Both the removed home-tile link AND this in-page finance button link need to go.
3. **A large, precisely enumerable set of existing tests assert on exact nav-link presence/text** and will fail once the nav shrinks — not hypothetically, these are exact string matches against `GET /`. Full list under Common Pitfalls / Pitfall 3.

**Primary recommendation:** Treat this as a template-and-route-wiring phase with a test-migration sub-task as a first-class deliverable (not an afterthought) — the nav-presence test suite is large enough that skipping it will leave the phase looking broken even though the actual behavior is correct.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Top-level nav rendering | Frontend Server (SSR) | — | `base.html`/`mobile_base.html` Jinja templates, rendered per-request, no client state |
| Товары toolbar | Frontend Server (SSR) | — | Static HTML block on `pages/products.html` (or its container), server-rendered per request |
| `/settings` hub page | API/Backend (thin route) + Frontend Server (SSR) | — | New route composes existing service calls (warehouse count, last backup date) then renders a template |
| Report back-links | Frontend Server (SSR) | — | Static `<a>` in each report template, no logic |
| Mobile top tab bar | Frontend Server (SSR) | — | Static chrome block in `mobile_base.html`, re-rendered on every full page navigation (no `hx-boost` in this project — see Pitfall 4) |
| Transfer product pre-selection (D-14) | API/Backend (route param handling) | Frontend Server (form pre-fill) | `GET /transfers?code=` resolves server-side via existing `lookup_prefill`/`open_batches` services, same pattern as `/products/new?code=` |
| Настройки summary counts | API/Backend (service composition) | — | CONTEXT.md explicitly requires this in a service function, not inline in the route |

## Standard Stack

No new packages, no version changes. This phase uses only what is already in `pyproject.toml` (FastAPI 0.139.x, Jinja2 3.1.x, SQLAlchemy 2.0.x, htmx 2.0.10 vendored) `[VERIFIED: codebase — pyproject.toml]`. No installation step is required.

### Alternatives Considered
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|--------------------------|
| Plain `<div>` toolbar with two `.form-actions`-style groups (D-01) | `<details>/<summary>` disclosure | Rejected by operator (D-01) — always-visible was explicitly requested |
| Server-side prefill of `/transfers?code=` (mirrors `/products/new?code=`) | Client-side `hx-trigger="load"` added to the existing debounced code input | Only if a future phase needs the SAME input to both accept typed codes AND auto-fire on programmatic value changes — adds complexity not needed here |

## Package Legitimacy Audit

Not applicable — this phase installs no external packages (no new `pip`/`uv add` dependencies). Skipping this section per the protocol's install-triggered condition.

## Architecture Patterns

### Current Desktop Nav → Reduced Nav (NAV-08)

Read verbatim from `app/templates/base.html:34-52` `[VERIFIED: codebase]`:

| Current top-nav item | Destination after Phase 24 |
|---|---|
| Главная | stays top-level |
| Товары | stays top-level |
| Категории | moves into Товары toolbar (D-02) |
| Склады | moves into Настройки (D-06) |
| Приход | moves into Товары toolbar (D-01/NAV-01) |
| Продажи | stays top-level |
| Списание | moves into Товары toolbar (D-01/NAV-02) |
| Перемещение | removed from nav entirely — becomes per-row action (D-13/NAV-07) |
| Покупатели | stays top-level |
| История | stays top-level |
| Отчёты | stays top-level |
| Экспорт | embedded into `/backup` (D-07/NAV-04), no longer a nav destination |
| Финансы | stays top-level |
| Экспорт кассы | moves into Настройки (D-08) |
| Справочник | moves into Товары toolbar (D-01/NAV-03) |
| Каталоги | moves into Товары toolbar (D-03) |
| Резервные копии | moves into Настройки (D-06/NAV-06) |
| *(new)* Настройки | added, top-level |

Result: 8 top-level items (Главная, Товары, Продажи, Покупатели, История, Отчёты, Финансы, Настройки) — matches NAV-08 and the success criteria exactly.

### System Architecture Diagram

```
Operator (browser)
        |
        v
  base.html <nav> (8 items)              mobile_base.html top tab bar (7 items, D-09)
        |                                            |
        v                                            v
  GET /products  ---------->  Товары toolbar (D-01/D-04, always visible)
        |                          |            |            |
        |                          v            v            v
        |                     /receipts/new  /writeoff   /dictionary
        |                     (Действия)      (Действия)  (Справочники)
        |                          |
        |                     /categories, /catalogs (Справочники group)
        |
        v
  product_rows.html row  ---->  "Перемещение" action  --> GET /transfers?code={code}  (D-13/D-14)
                                                                |
                                                                v
                                                    transfers_page resolves code server-side
                                                    (mirrors /products/new?code= pattern) -->
                                                    pre-filled form, no client JS trigger needed

  GET /settings (new)  ---->  Настройки hub (D-06)
        |            |             |
        v            v             v
   /warehouses   /backup      (Экспорт кассы) /finance/report
                     |
                     v
              embedded Экспорт section (D-07) -- CSV download links unchanged
                     (/export/products.csv etc., still hardcoded server-side dumps, V12)

  GET /reports/{sales,writeoffs,stock,expiry,products}  ---->  "← Назад к отчётам" link --> GET /reports (RPT-01)
```

### Recommended Structure (no new top-level dirs — additive within existing trees)
```
app/
├── routes/
│   ├── settings.py          # NEW — /settings hub route (D-06)
│   ├── mobile_products.py   # NEW — mobile Товары tab (MOB-01 gap, see Pitfall 1)
│   ├── mobile_customers.py  # NEW — mobile Покупатели tab (MOB-01 gap, see Pitfall 1)
│   ├── transfers.py         # MODIFIED — GET /transfers accepts ?code= (D-14)
│   ├── backup.py            # MODIFIED — embeds export section (D-07)
│   ├── products.py          # MODIFIED — page gains toolbar include
│   └── reports.py           # unchanged (back-link is template-only, RPT-01)
├── services/
│   └── settings.py          # NEW (optional but recommended) — settings_summary(session)
├── templates/
│   ├── base.html            # MODIFIED — 8-item nav (NAV-08)
│   ├── mobile_base.html     # MODIFIED — persistent top tab bar block (D-09)
│   ├── partials/
│   │   └── products_toolbar.html   # NEW — the D-01/D-04 two-group toolbar, {% include %}'d
│   ├── pages/
│   │   ├── settings.html    # NEW
│   │   ├── reports_*.html   # MODIFIED (x5) — back-link insertion (RPT-01)
│   │   └── backup.html      # MODIFIED — embedded export section (D-07)
│   └── mobile_pages/
│       ├── home.html        # MODIFIED — 10-tile grid removed (D-10)
│       ├── products.html    # NEW
│       └── customers.html   # NEW
```

### Pattern 1: Server-side query-param prefill (recommended for D-14)
**What:** Resolve the product server-side in the GET route itself and populate the form's initial render — do NOT rely on a client-side `hx-trigger="load"` hack on the existing debounced input.
**When to use:** Any "pre-fill a create-style form from a link elsewhere in the app" scenario — this codebase already has the identical pattern for products.

```python
# Source: app/routes/products.py (existing /products/new?code= handler, read verbatim)
@router.get("/products/new")
def product_new(request: Request, code: str = "", session: Session = Depends(get_session)):
    code_clean = code.strip()
    if code_clean:
        existing = session.scalars(
            select(Product).where(Product.code == code_clean, Product.deleted_at.is_(None))
        ).first()
        if existing is not None:
            return RedirectResponse(f"/products/{existing.id}/edit")
    context = {
        "product": None,
        ...
        "form": {"code": code_clean} if code_clean else {},
        ...
    }
    return templates.TemplateResponse(request, "pages/product_form.html", context)
```

**Why this beats a client-side trigger for `/transfers`:** the existing `code` input on `partials/transfer_form.html:30-36` uses `hx-trigger="input changed delay:300ms"` — no `load` trigger. Pre-filling `value="{{ form.code }}"` alone will NOT fire the lookup, so `name`/batches would stay empty even though `code` shows a value — a broken-looking pre-fill. The fix consistent with this codebase's existing "server decides fill" philosophy (see the `D-04` comment at `transfer_form.html:29`) is to have `transfers_page` itself call the same resolution logic `transfers_lookup` already uses (`lookup_prefill` + `open_batches`, both already imported in `app/routes/transfers.py`) and populate `form.name` and the batch picker directly in the initial context — no client JS trigger needed at all. Recommend extracting a small shared helper (e.g. `_resolve_transfer_lookup(session, code)`) used by both `transfers_page` (new `?code=` branch) and the existing `transfers_lookup` endpoint, to avoid duplicating the product/batch resolution logic.

### Pattern 2: Always-visible two-group toolbar (D-01/D-04)
**What:** A `<div>` (not `<nav>` — that tag is reserved for the page's single primary navigation landmark, per `base.html`'s existing usage) containing two labeled groups of plain `<a class="button">`/`<a>` links, reusing the existing `.form-actions` flex/gap pattern per group.
**When to use:** The Товары toolbar (desktop and, per D-11, the mobile Товары tab).

```html
{# Source: pattern synthesized from app/static/style.css's existing .form-actions
   (flex, gap:16px, align-items:center) and .filter-bar (flex, gap:16px,
   align-items:flex-end) — no new CSS class strictly required; a labeled
   wrapper around two .form-actions groups reuses both verbatim. #}
<div class="toolbar">
  <div class="toolbar-group">
    <span class="muted">Действия</span>
    <div class="form-actions">
      <a class="button" href="/receipts/new">Приход</a>
      <a class="button" href="/writeoff">Списание</a>
    </div>
  </div>
  <div class="toolbar-group">
    <span class="muted">Справочники</span>
    <div class="form-actions">
      <a class="button" href="/categories">Категории</a>
      <a class="button" href="/dictionary">Справочник</a>
      <a class="button" href="/catalogs">Каталоги</a>
    </div>
  </div>
</div>
```
Only `.toolbar`/`.toolbar-group` (simple flex wrappers) are new CSS — everything inside reuses `.form-actions`, `.button`, `.muted` verbatim, honoring the phase framing's "no new JS/CSS component" instruction in spirit (this is layout composition, not a new interactive component).

### Pattern 3: `/settings` hub with computed summaries (D-06)
```python
# Source: pattern synthesized from existing app/routes/warehouses.py and
# app/services/backup.py, both read verbatim above.
# app/services/settings.py (NEW, recommended per CONTEXT.md's explicit
# "belongs in a service function, not inline in the route" instruction)
def settings_summary(session: Session, backup_dir: Path) -> dict:
    warehouse_count = list_warehouses(session)["total"]  # active-only by default
    backups = list_backups(backup_dir)  # newest-first, per app/services/backup.py
    last_backup_iso = backups[0]["created_iso"] if backups else None
    return {"warehouse_count": warehouse_count, "last_backup_iso": last_backup_iso}
```
`list_warehouses` already defaults to `status=""` -> active rows only (`app/services/warehouses.py`), which matches "количество складов" as the operator would read it. `list_backups` is already newest-first, so `backups[0]` is the last backup — no new sorting logic needed.

### Pattern 4: Embedding `/export` into `/backup` (D-07)
The 3 CSV links in `app/templates/pages/export.html` are plain `<a class="button" href="/export/products.csv">` — no form, no htmx, a direct browser download link. Embedding them into `backup.html` is a template `{% include %}` (or literal copy) of those 3 `<a>` tags; `app/routes/export.py`'s `/export/products.csv` etc. streaming endpoints are untouched (they take no params — V12 pattern, per the module's own docstring), so there is **no routing/htmx gotcha**: a plain `<a href>` download link works identically whether it lives on its own page or embedded inside another page's markup. The only route-level decision is whether `GET /export` (the page, not the CSV endpoints) stays registered as a dead/unlinked route or is removed — CONTEXT.md marks this Claude's discretion.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Active-nav-item highlighting | New JS-based active-state logic | The existing `{% if request.url.path.startswith(...) %} class="active"{% endif %}` Jinja pattern already used 17 times in `base.html` | Zero-JS, already proven, trivially extends to 8 items |
| Mobile tab bar "current tab" indicator | New client-side router/state | Same `request.url.path` Jinja pattern, applied to `mobile_base.html` | Consistent with desktop, no new mechanism |
| Warehouse count / last-backup-date computation | New tracking table/column | Existing `list_warehouses()["total"]` and `list_backups()` (newest-first) | Both already computed correctly by existing services; CONTEXT.md explicitly forbids new tracking |

**Key insight:** Every piece of data this phase needs to display (warehouse count, last backup date, product code/name for transfer prefill) is already computed by an existing service function. There is no data-modeling work in this phase — only wiring.

## Common Pitfalls

### Pitfall 1: Two mobile tabs (Товары, Покупатели) have no existing page to link to
**What goes wrong:** MOB-01 requires the 7-tab mobile bar to include Товары and Покупатели, but grepping `app/routes/mobile_*.py` shows only Sales, History, Reports, Finance, Receipts, Writeoff, Corrections, Returns, Search, Home — no Товары or Покупатели equivalent. `mobile_search.py` (`GET /m/search`) is a read-only stock-lookup-by-code/name tool, not a product list/management page, and cannot simply be relabeled "Товары" without misleading the operator (it's missing the D-11 toolbar entirely, and its results view is a search-results list, not the grouped-by-code product list PROD-03/04 established on desktop).
**Why it happens:** Mobile was built feature-by-feature (Phase 11 onward) targeting specific workflows (search, receipts, writeoff, transfers, sales, history, finance, reports) — a general "browse all products" or "browse all customers" mobile page was never a separate requirement until MOB-01 now names them as tabs.
**How to avoid:** Plan this phase to explicitly create `app/routes/mobile_products.py` and `app/routes/mobile_customers.py` as new thin routes, reusing existing desktop services (`app.services.catalog` product listing, `app.services.customers.list_customers_view`), mirroring the established pattern of `mobile_search.py`/`mobile_finance.py` (thin route + existing service + new mobile-only template). This is NOT "new capability" in the CONTEXT.md sense (no new business logic, no new data) — it is exposing existing read paths via a new mobile entry point, consistent with the phase's own framing ("changes HOW operators reach those pages"). Recommend the mobile Товары page host the D-11 toolbar exactly as D-11 specifies.
**Warning signs:** If the plan only adds `<a>` tags to a tab bar without creating backing routes/templates for Товары/Покупатели, `/m/products` and `/m/customers` will 404.

### Pitfall 2: D-12 requires removing an in-page link, not just a home-grid tile
**What goes wrong:** `app/templates/mobile_pages/finance.html:15` has `<p><a class="button" href="/m/finance/report">Отчёт и экспорт CSV</a></p>` — this is independent of the home-grid tile grid being removed by D-10. If left in place, Экспорт кассы stays one tap away from `/m/finance`, contradicting D-12's "unreachable from `/m/*` by design."
**Why it happens:** D-12 was framed around the mobile tab set and the home-grid removal; this in-page CTA link predates Phase 24 (added in Phase 17 per `test_web_mobile_home_tile_links_to_finance_report`/`test_web_mobile_finance_page_report_link_is_button_styled`-style tests in `tests/test_finance_reports.py`) and is easy to miss because it isn't part of "the nav."
**How to avoid:** Explicitly task removing this line (or gating it out) alongside D-10's home-grid removal. Decide whether the `/m/finance/report` **route** itself should be deleted or just left unlinked (harmless either way, but the in-page link must go either way to honor D-12).
**Warning signs:** UAT/verification finds Экспорт кассы reachable from `/m/finance` after the phase ships.

### Pitfall 3: A large, specific set of existing tests hard-assert nav-link presence and WILL fail
**What goes wrong:** Multiple existing tests do `client.get("/")` (or `/finance/report`, or `/products`) and assert an exact `href="..."` substring is present. These are not incidental — they were written as gap-closure regression guards in earlier phases and will genuinely fail once the corresponding nav item moves off `/`.
**Confirmed list (read verbatim, file:line):**
| Test | File:line | Why it breaks |
|---|---|---|
| `test_web_nav_has_dictionary_link` | `tests/test_dictionary.py:321` | Справочник leaves top nav (D-01/NAV-03) |
| `test_web_nav_has_categories_link` | `tests/test_catalog.py:890` | GETs `/products` not `/` — MAY still incidentally pass once Категории lands in the Товары toolbar (toolbar is on `/products`), but its docstring ("Nav bar exposes...") becomes inaccurate; verify at execution time |
| `test_web_nav_has_warehouses_link` | `tests/test_warehouses.py:453` | Склады leaves top nav for Настройки (D-06/NAV-05) |
| `test_web_writeoff_reachable_from_nav` | `tests/test_writeoffs.py:286` | Списание leaves top nav (D-01/NAV-02); this test's own docstring calls itself a "gap-closure guard," so update rather than delete |
| `test_web_nav_has_receipts_link` | `tests/test_receipts.py:584` | Приход leaves top nav (D-01/NAV-01) |
| `test_web_nav_has_export_link` | `tests/test_export.py:330` | Экспорт leaves nav entirely, embedded in `/backup` (D-07/NAV-04) |
| `test_web_nav_has_backup_link` | `tests/test_backup.py:267` | Резервные копии leaves top nav for Настройки (D-06/NAV-06) |
| `test_web_home_nav_links_to_finance_report` | `tests/test_finance_reports.py:570` | Экспорт кассы leaves top nav for Настройки (D-08) |
| `test_web_finance_report_nav_item_marks_active` | `tests/test_finance_reports.py:580` | Same — asserts exact `<a href="/finance/report" class="active">` nav markup that no longer exists |
| `test_mobile_home_renders_all_tiles_in_order` | `tests/test_mobile_home.py:28` | 10-tile grid removed (D-10) |
| `test_mobile_home_dashboard_content_is_below_the_untouched_nav_grid` | `tests/test_mobile_home.py:41` | Same — asserts `href="/m/finance/report"` precedes `<h2>Показатели</h2>`, both gone |
| `test_mobile_home_lists_all_eight_tile_hrefs` | `tests/test_mobile_wiring.py:38` | Same tile-grid removal |
| `test_web_mobile_home_tile_links_to_finance_report` | `tests/test_finance_reports.py:606` | Same |
| `test_web_mobile_finance_page_report_link_is_button_styled` | `tests/test_finance_reports.py` (~line 619) | Only breaks if Pitfall 2's in-page link is also removed (recommended) |

Tests confirmed to **stay green** (destination page, not top nav, or item remains top-level): `test_web_nav_has_customers_link` (`test_customers.py:679`, Покупатели stays top-level), `test_web_nav_has_sales_link` (`test_sales.py:775`, Продажи stays top-level), `test_web_nav_has_reports_link` (`test_reports.py:319`, Отчёты stays top-level), `test_every_preexisting_desktop_nav_route_still_returns_200` (`tests/test_mobile_wiring.py:66-69`, hits routes directly by URL, not by parsing nav — every route in `DESKTOP_NAV_PATHS` stays registered even after leaving the visible nav, so this test is unaffected by the restructure itself; only fails if a route is deleted).
**Why it happens:** Earlier phases wrote gap-closure regression tests naming the top nav specifically (several docstrings literally say "Nav bar exposes the new /X link" or "closes N-UAT.md Gap"). Restructuring the nav is a deliberate, in-scope change to exactly what these tests guard.
**How to avoid:** Plan an explicit task to update (not silently delete) each of these tests to assert the NEW reachability path instead (e.g., `test_web_nav_has_dictionary_link` becomes "GET /products contains href=\"/dictionary\" inside the toolbar"; `test_web_nav_has_warehouses_link`/`test_web_nav_has_backup_link`/`test_web_home_nav_links_to_finance_report` become assertions against `GET /settings`). This preserves the regression-guard intent (never let these pages become unreachable again) while matching the new architecture.
**Warning signs:** Running the full suite after the nav change without touching these tests — expect ~13 failures that are 100% attributable to this phase's own intended change, not a real regression.

### Pitfall 4: The "htmx oob-swap disrupts persistent chrome" risk flagged in the phase description does not actually apply here — but a related, milder risk does
**What goes wrong (the flagged risk, de-risked):** The phase description asks whether the new persistent mobile top tab bar could be disrupted by htmx partial-swap bugs like Phase 9's `<template>`-wrap fix for OOB `<tr>` fragments. Grepping the entire `app/templates/` tree for `hx-boost` found **zero occurrences** `[VERIFIED: codebase grep]` — this project never uses htmx-boosted full-page navigation. Every existing page-to-page navigation (including tapping any current mobile tile) is a plain browser `<a href>` GET, causing a full page reload where `mobile_base.html` (and therefore the new tab bar) is rendered fresh from scratch by the server every time. HTMX `hx-swap`/oob-swap only ever targets specific `id="..."` elements INSIDE a `{% block content %}` (e.g. `#transfer-form-wrap`, `#cash-history-rows`), never the page shell itself.
**The residual, milder risk:** If the tab bar is placed inside `{% block content %}` on a per-page basis (copy-pasted into every mobile template) rather than once in `mobile_base.html` itself (like the existing `{% block back %}`), a future partial's oob-swap could theoretically target an `id` that collides with something inside the tab bar markup, or an editor could accidentally include the tab bar inside a fragment template that IS an htmx swap target.
**How to avoid:** Add the tab bar as a new `{% block %}` in `mobile_base.html` itself (sibling to the existing `{% block back %}`/`{% block step_indicator %}`), never duplicated per-page. Give tab-bar elements namespaced, non-generic ids/classes (e.g. `.mobile-tabbar`, not `.nav` or `#tabs`) to avoid any accidental collision with existing oob-swap target ids used elsewhere in the mobile templates (e.g. `#cash-history-cards`, `#cash-history-load-more`, `#finance-metrics`).
**Warning signs:** N/A if implemented as a `mobile_base.html` block — this is a preventive recommendation, not an observed bug.

### Pitfall 5: `<nav>` tag is a taken semantic landmark — don't reuse it for the toolbar or tab bar
**What goes wrong:** `base.html:34` already uses a bare `<nav>` tag for the primary top nav. Some existing report tests assert `"<nav" not in response.text` for HX-partial responses (`tests/test_reports.py:316,459`) to prove a chrome-less fragment doesn't accidentally include the page shell.
**Why it happens:** It's tempting to reuse `<nav>` for the new Товары toolbar or the mobile tab bar since both are "navigational" in a loose sense.
**How to avoid:** Use `<div class="toolbar">` for the Товары toolbar (it's a set of actions on the current page, not a landmark to a different page's nav) and `<nav class="mobile-tabbar">` (a second, legitimately distinct nav landmark — HTML permits multiple `<nav>` elements) for the mobile tab bar specifically, but never let the toolbar itself be a bare `<nav>` sibling of the existing one, since that would make `"<nav" not in response.text`-style negative assertions ambiguous about which `<nav>` they're checking for.
**Warning signs:** A report-page HX-partial test starts failing because the products toolbar markup leaked `<nav` into a fragment that's supposed to be chrome-less — unlikely given toolbar is Товары-page-only, but worth a note since the assertion pattern exists in this codebase.

## Code Examples

### Existing "code -> prefill" pattern (D-14 precedent)
```html
<!-- Source: app/templates/pages/catalog_detail.html:37 -->
<td><a href="/products/new?code={{ entry.code }}">изменить цену</a></td>
```
```python
# Source: app/routes/products.py:190-203 (product_new), read verbatim.
# The exact server-side resolve-then-prefill shape to mirror for
# GET /transfers?code=.
```

### Existing per-row actions cell (D-13 insertion point)
```html
<!-- Source: app/templates/partials/product_rows.html:61-64, read verbatim -->
<td>
  <a href="/products/{{ product.id }}/edit">Изменить</a>
  <a href="#" class="link-danger" hx-post="/products/{{ product.id }}/quick-delete?page={{ page }}{{ extra_qs }}" hx-confirm="..." hx-target="#product-rows" hx-swap="outerHTML">Удалить</a>
  <!-- NEW (D-13): <a href="/transfers?code={{ product.code }}">Переместить</a> -->
</td>
```

### Report back-link precedent (RPT-01)
```html
<!-- Source: app/templates/pages/catalog_detail.html:1-4, read verbatim -->
{% extends "base.html" %}
{% block content %}
<p><a href="/catalogs">← Все каталоги</a></p>
<h1>{{ catalog.label }}</h1>
```
Every one of the 5 report detail templates (`reports_sales.html`, `reports_writeoffs.html`, `reports_stock.html`, `reports_expiry.html`, `reports_products.html`) opens with the identical `{% extends "base.html" %}\n{% block content %}\n<h1>...` shape — insert `<p><a href="/reports">← Назад к отчётам</a></p>` immediately before each `<h1>`, using RPT-01's mandated exact link text.

### Existing summary-data sources for Настройки (D-06)
```python
# Source: app/services/warehouses.py:21-... (list_warehouses), read verbatim.
# result["total"] is already the active-warehouse count (status defaults to "active").

# Source: app/services/backup.py:59-78 (list_backups), read verbatim.
# Returns newest-first; entries[0]["created_iso"] is the last backup timestamp.
```

## State of the Art

Not applicable — no external library/framework has changed; this phase reorganizes this codebase's own templates and routes only. No deprecated APIs, no version bumps.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|----------------|
| A1 | Mobile Товары and Покупатели tabs should be built as new thin routes reusing existing desktop services (mirroring `mobile_search.py`), rather than deep-linking to `/m/search` or omitting real content | Pitfall 1 / Architecture Patterns | If wrong, planner might instead point these tabs at `/m/search` (Товары) or leave Покупатели unimplemented, which would violate MOB-01's plain reading ("same main tabs as desktop") — recommend confirming this scope explicitly since CONTEXT.md's canonical_refs did not call out this gap |
| A2 | `?code=` (not `?product=`/id) is the right query param for D-14, mirroring `/products/new?code=` rather than History's `?product={id}` filter convention | Pattern 1 | Low risk — either works functionally since `transfers.py` resolves everything by `code` internally anyway (`Product.code == code_clean`); `?product=` with an id would require an extra id->code lookup with no benefit. If the planner strongly prefers id-based (mirroring History), it's a straightforward substitution, not a redesign |
| A3 | `.toolbar`/`.toolbar-group` need ~2 small new CSS rules (flex wrappers) even though the task framing says "no new JS/CSS component" | Pattern 2 | Low risk — this is layout composition (a labeled wrapper) around 100% existing classes (`.form-actions`, `.button`, `.muted`), not a new interactive component; flagged so the planner doesn't over-interpret "no new CSS" as "zero new CSS lines" |

**If this table is empty:** N/A — see entries above; all are LOW risk and clearly scoped, none touch money/security paths.

## Open Questions

1. **Should `/export` (page) and `/finance/report` (page) routes be deleted or left registered-but-unlinked?**
   - What we know: CONTEXT.md marks this explicitly as Claude's discretion ("no operator-visible difference"). The CSV/report *data* endpoints (`/export/products.csv`, `/finance/report.csv`) are untouched either way.
   - What's unclear: Whether `tests/test_mobile_wiring.py:66-69`'s `DESKTOP_NAV_PATHS` list (which includes `/export`) should be updated to remove it if the route is deleted, or left as-is if the route stays registered.
   - Recommendation: Leave both routes registered (simplest, zero risk, matches "backing endpoint" language in D-07/D-08) — only remove nav `<a>` entries and in-page CTAs. Update `DESKTOP_NAV_PATHS` only if a route path is actually deleted.

2. **Does the mobile Товары toolbar (D-11) need its own template partial shared with desktop, or a fully separate mobile-only markup?**
   - What we know: "Desktop and mobile are fully separate route/template trees reusing the same underlying service functions" is the established convention since Phase 11 (per CONTEXT.md's own canonical_refs).
   - What's unclear: Whether the toolbar's underlying two-group *data* (which links belong in which group) should live in one shared Python constant (e.g. a list of `(label, href, group)` tuples in a service or route module) imported by both desktop and mobile templates, to avoid the groupings drifting apart over time.
   - Recommendation: Define the toolbar's link groups once (e.g. as a small constant in `app/routes/products.py`, passed into context) and render it via two separate template partials (`partials/products_toolbar.html` for desktop, `mobile_partials/products_toolbar.html` for mobile) that share the same context shape — keeps the "separate template trees" convention while avoiding duplicated grouping logic.

## Environment Availability

Skipped — this phase has no external tool/service dependencies beyond the existing installed stack (Python 3.13, FastAPI/SQLAlchemy/Jinja2/htmx already verified present via `pyproject.toml` and running tests). `pytest 9.1.1` and `uv` both confirmed present on the target machine `[VERIFIED: command -v / --version]`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 `[VERIFIED: pytest --version]` |
| Config file | `pyproject.toml` (`[tool.pytest.ini_options]`, `testpaths = ["tests"]`) |
| Quick run command | `uv run pytest tests/test_<module>.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|--------------------|-------------|
| NAV-01/02/03 | Приход/Списание/Справочник reachable from Товары toolbar | web/integration | `uv run pytest tests/test_receipts.py tests/test_writeoffs.py tests/test_dictionary.py -k nav -x` | ✅ existing tests to be UPDATED (Pitfall 3) |
| NAV-04 | Экспорт reachable from /backup | web/integration | `uv run pytest tests/test_export.py tests/test_backup.py -x` | ✅ existing, `test_web_nav_has_export_link` to be UPDATED |
| NAV-05/06 | Склады/Резервные копии reachable from /settings | web/integration | `uv run pytest tests/test_warehouses.py tests/test_backup.py -k settings -x` | ❌ Wave 0 — new `tests/test_settings.py` needed |
| NAV-07/D-14 | Перемещение per-row action, product pre-fill | web/integration | `uv run pytest tests/test_transfers.py -x` | ✅ existing file, new test cases to ADD |
| NAV-08 | Top nav is exactly 8 items | web/integration | `uv run pytest tests/test_smoke.py -k nav -x` (or a new dedicated test) | ❌ Wave 0 — recommend one new assertion enumerating the final 8 hrefs on `GET /` |
| RPT-01 | Back-link on every report detail page | web/integration | `uv run pytest tests/test_reports.py -k back -x` | ❌ Wave 0 — no existing back-link assertions for reports; ADD 5 (one per detail page) |
| MOB-01 | Mobile tab bar has 7 tabs, excludes Настройки | web/integration | `uv run pytest tests/test_mobile_wiring.py tests/test_mobile_home.py -x` | ⚠️ existing tests to be REPLACED (Pitfall 3), new mobile Товары/Покупатели routes need new test files |

### Sampling Rate
- **Per task commit:** targeted `uv run pytest tests/test_<touched_module>.py -x`
- **Per wave merge:** `uv run pytest` (full suite — this phase touches enough shared chrome, e.g. `base.html`/`mobile_base.html`, that isolated module runs won't catch cross-file breakage)
- **Phase gate:** Full suite green before `/gsd-verify-work`, with special attention to the ~13 tests enumerated in Pitfall 3 (expected to fail until explicitly updated — verify each is updated, not skipped)

### Wave 0 Gaps
- [ ] `tests/test_settings.py` — new file, covers NAV-05/06/D-06 (`/settings` route existence, warehouse-count summary, last-backup-date summary, links present)
- [ ] `app/routes/mobile_products.py` + `tests/test_mobile_products.py` — new mobile Товары tab (MOB-01, Pitfall 1)
- [ ] `app/routes/mobile_customers.py` + `tests/test_mobile_customers.py` — new mobile Покупатели tab (MOB-01, Pitfall 1)
- [ ] Update (not delete) the 13 nav-presence tests enumerated in Pitfall 3 to assert the new reachability paths
- [ ] New back-link assertions in `tests/test_reports.py` (5 report detail pages, RPT-01)
- [ ] New assertions for the D-13/D-14 transfer per-row action + pre-fill in `tests/test_transfers.py` and `tests/test_catalog.py`/`test_receipts.py` (wherever `product_rows.html` output is already asserted)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | Single local operator, no auth in v1 (per CLAUDE.md/PROJECT.md constraints) |
| V3 Session Management | No | No sessions used anywhere in this app |
| V4 Access Control | No | No new privilege boundary introduced |
| V5 Input Validation | Yes | The new `?code=` query param on `GET /transfers` must follow the SAME pattern already used at `GET /products/new?code=`: `.strip()` the raw string, look it up via a parameterized ORM `select()` (never string-interpolated SQL — already the project-wide convention, see `app/routes/transfers.py`'s existing `select(Product).where(Product.code == code_clean, ...)`), and treat "code not found" as a silent no-prefill (empty form), never a 500 or an error message that echoes unsanitized input |
| V6 Cryptography | No | No new secret/credential handling in this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|-----------------------|
| Reflected content in a query-param-driven prefill (`?code=`) | Tampering / Info disclosure | Already mitigated by Jinja2's autoescaping (default in this project, per existing `{{ }}` usage throughout) — the new `?code=` value is only ever echoed back inside an `<input value="{{ form.code }}">`-style attribute, never rendered with `|safe`. Continue this convention; do not introduce any `|safe` filter for the new prefill path |
| Route enumeration of newly-unlinked-but-still-registered pages (`/export`, `/finance/report`) | Info disclosure (very low severity) | Not a real concern for a single-operator offline local app with no auth boundary — these pages exposed the same data before this phase too; noted only for completeness |

## Sources

### Primary (HIGH confidence — direct codebase inspection this session)
- `app/templates/base.html` — current 17-item nav, read verbatim `[VERIFIED: codebase]`
- `app/templates/mobile_base.html` — mobile shell, confirmed no persistent nav today `[VERIFIED: codebase]`
- `app/templates/mobile_pages/home.html` — 10-tile grid + its own "temporary until Phase 24" comment `[VERIFIED: codebase]`
- `app/templates/partials/product_rows.html` — per-row actions cell, `<details>` precedent `[VERIFIED: codebase]`
- `app/templates/pages/catalog_detail.html` — back-link precedent, `?code=` prefill precedent `[VERIFIED: codebase]`
- `app/static/style.css` (405 lines, read in full) — every reusable CSS class cited above `[VERIFIED: codebase]`
- `app/routes/{reports,export,backup,catalogs,finance,warehouses,transfers,products,customers,mobile_home,mobile_search,mobile_reports,mobile_finance}.py` — read verbatim `[VERIFIED: codebase]`
- `app/services/backup.py`, `app/services/warehouses.py` (`list_warehouses` signature) — read verbatim `[VERIFIED: codebase]`
- `tests/*.py` — grepped and read for every nav-presence assertion cited in Pitfall 3, plus `tests/conftest.py` fixtures and `pyproject.toml` test config `[VERIFIED: codebase]`
- `command -v pytest` / `pytest --version` / `command -v uv` — confirmed present on target machine `[VERIFIED: shell]`
- `grep -r hx-boost app/templates` — zero matches, confirms no htmx-boosted navigation anywhere in the project `[VERIFIED: codebase grep]`

### Secondary (MEDIUM confidence)
None — this phase required no external documentation lookups (no new libraries, no API changes); all research providers in `.planning/config.json` are disabled (`brave_search`/`exa_search`/`tavily_search`/`firecrawl`/`ref_search`/`perplexity`/`jina` all `false`), consistent with this being a pure internal-codebase-archaeology phase.

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, nothing to verify externally
- Architecture: HIGH — every pattern cited is read verbatim from this codebase, not inferred
- Pitfalls: HIGH — every pitfall in this document is backed by a specific file:line reference confirmed via Read/Grep this session, not speculation

**Research date:** 2026-07-17
**Valid until:** Until this phase's plan is executed (codebase-internal research has no external staleness window; re-verify only if other phases land first and change these files)
