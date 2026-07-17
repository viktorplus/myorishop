---
phase: 24-navigation-restructure-settings
reviewed: 2026-07-17T21:00:00Z
depth: standard
files_reviewed: 43
files_reviewed_list:
  - app/main.py
  - app/routes/__init__.py
  - app/routes/mobile_customers.py
  - app/routes/mobile_products.py
  - app/routes/settings.py
  - app/routes/transfers.py
  - app/services/settings.py
  - app/static/style.css
  - app/templates/base.html
  - app/templates/mobile_base.html
  - app/templates/mobile_pages/customers.html
  - app/templates/mobile_pages/finance.html
  - app/templates/mobile_pages/home.html
  - app/templates/mobile_pages/products.html
  - app/templates/mobile_partials/products_toolbar.html
  - app/templates/pages/backup.html
  - app/templates/pages/products_list.html
  - app/templates/pages/reports_expiry.html
  - app/templates/pages/reports_products.html
  - app/templates/pages/reports_sales.html
  - app/templates/pages/reports_stock.html
  - app/templates/pages/reports_writeoffs.html
  - app/templates/pages/settings.html
  - app/templates/partials/product_rows.html
  - app/templates/partials/products_toolbar.html
  - app/templates/partials/transfer_form.html
  - tests/test_backup.py
  - tests/test_catalog.py
  - tests/test_dictionary.py
  - tests/test_export.py
  - tests/test_finance_reports.py
  - tests/test_mobile_customers.py
  - tests/test_mobile_home.py
  - tests/test_mobile_products.py
  - tests/test_mobile_wiring.py
  - tests/test_receipts.py
  - tests/test_reports.py
  - tests/test_settings.py
  - tests/test_smoke.py
  - tests/test_transfers.py
  - tests/test_warehouses.py
  - tests/test_writeoffs.py
findings:
  critical: 1
  warning: 3
  info: 1
  total: 5
status: issues_found
---

# Phase 24: Code Review Report

**Reviewed:** 2026-07-17T21:00:00Z
**Depth:** standard
**Files Reviewed:** 43
**Status:** issues_found

## Summary

Reviewed the navigation-restructure-and-settings phase: desktop nav reduction to 8 items, the new `/settings` hub, the Товары toolbar (desktop + mobile), report back-links, the `/transfers?code=` prefill refactor, and the new persistent mobile tab bar that replaces the old 10-tile `/m/` home grid.

Most of the diff is mechanical and well-covered by tests (nav reduction, back-links, `_resolve_transfer_lookup` extraction — verified byte-identical to the pre-refactor `/transfers/lookup` contract, autoescaped `?code=` echo, no `|safe` anywhere). The one substantive problem is a navigation regression: removing the old mobile home tile grid (D-10) also removed the *only* remaining path to three previously-reachable mobile features — Поиск, Корректировка, and Перемещение — none of which were given a replacement entry point anywhere in the new tab bar or the new mobile Товары toolbar, even though `24-CONTEXT.md`'s own D-11 decision explicitly names Перемещение as an item that should mirror the desktop toolbar shape on mobile. The routes still work (proven by direct-URL tests), but they are now orphaned in the live UI — a real functionality-reachability loss, not just a discoverability nit, on the phase whose entire goal statement is "every secondary action is reachable ... on desktop and mobile alike."

Also flagged: a test-coverage gap against the phase's own stated acceptance criteria, a minor active-nav-state inconsistency, and a probable touch-target shortfall on the new mobile toolbar buttons.

## Critical Issues

### CR-01: Поиск, Корректировка, and Перемещение become unreachable from the mobile UI (D-11 violation)

**File:** `app/templates/mobile_partials/products_toolbar.html:1-17`, `app/templates/mobile_pages/home.html` (git diff removing the tile grid), `app/templates/mobile_pages/products.html:1-20`

**Issue:** Before this phase, `mobile_pages/home.html`'s 10-tile grid was the only navigation path to `/m/search`, `/m/corrections`, and `/m/transfers` (Поиск, Корректировка, Перемещение). Plan 24-05 deliberately removed that grid (D-10) and replaced it with the new 7-tab bar, which by design excludes these three destinations (they don't fit in the 7 tabs). Plan 24-06 then added the mobile Товары toolbar as the D-11-mandated replacement path for the items that don't fit in the tabs — but the toolbar it shipped only contains `Приход` (`/m/receipts`), `Списание` (`/m/writeoff`), `Категории`, `Справочник`, `Каталоги` (`app/templates/mobile_partials/products_toolbar.html:1-17`). It omits `Перемещение` entirely, even though `24-CONTEXT.md` D-11 explicitly lists it: *"Items that don't fit in the 7 mobile tabs (Приход, Списание, **Перемещение**, Справочник, Каталоги) are reached mirroring the desktop pattern ... living on the mobile Товары tab."*

The desktop equivalent of Перемещение reachability (D-13) is a per-row "Переместить" link in `partials/product_rows.html` — but the mobile product list (`app/templates/mobile_pages/products.html:9-15`) renders bare `.mobile-card` divs with no action links at all, so that path wasn't mirrored to mobile either.

`Поиск` and `Корректировка` aren't mentioned in any D-decision as intentionally dropped (unlike `Настройки`/`Экспорт кассы`, which D-12 explicitly and correctly retires from mobile) — they simply fell out when the tile grid was deleted, with no replacement anywhere.

Net effect: an operator on the phone UI now has *zero* discoverable path to search, stock corrections, or inter-warehouse transfers — despite full, working, mobile-optimized wizards existing for all three (`mobile_pages/search.html`, `mobile_pages/corrections.html`, `mobile_pages/transfers.html` + their step partials). `tests/test_mobile_wiring.py::test_every_mobile_tile_path_is_reachable` only proves the routes return 200 by direct URL — it does not (and cannot) prove they're reachable via any rendered link, so this regression shipped without a failing test.

This contradicts the phase's own Goal statement in `ROADMAP.md`: *"every secondary action is reachable from the page it belongs to — on desktop and mobile alike."*

**Fix:** At minimum, add `Перемещение` to `mobile_partials/products_toolbar.html`'s "Действия" group per D-11's explicit wording:
```html
<div class="toolbar-group">
  <span class="muted">Действия</span>
  <div class="form-actions">
    <a class="button" href="/m/receipts">Приход</a>
    <a class="button" href="/m/writeoff">Списание</a>
    <a class="button" href="/m/transfers">Перемещение</a>
  </div>
</div>
```
For Поиск and Корректировка, either restore a minimal entry point (e.g. an action in the mobile toolbar, or a link on `/m/` below the metric tiles) or get an explicit operator decision recorded in `24-CONTEXT.md` that these two are intentionally desktop/tile-only casualties (matching the rigor already applied to the `Настройки`/`Экспорт кассы` D-12 decision). Shipping this silently is the failure mode — either fix the reachability or document the trade-off as a deliberate, operator-approved decision.

## Warnings

### WR-01: Mobile Товары toolbar has zero automated test coverage despite being a stated acceptance criterion

**File:** `tests/test_mobile_products.py:1-27`

**Issue:** `24-06-PLAN.md`'s own acceptance criteria for Task 1 require: *"Response contains `<h1>Товары</h1>`, the toolbar's 5 hrefs (`/m/receipts`, `/m/writeoff`, `/categories`, `/dictionary`, `/catalogs`), and a `.mobile-card` per seeded product."* The shipped `tests/test_mobile_products.py` only asserts `product.code`/`product.name` presence and the empty-state text — no test anywhere in the suite asserts the toolbar's hrefs are present on `/m/products`. Had such a test existed, it would likely have also caught CR-01 (an explicit toolbar-content assertion is exactly what would have forced someone to notice `Перемещение` is missing from D-11's list).

**Fix:**
```python
def test_mobile_products_toolbar_hrefs(mobile_client_factory):
    client = mobile_client_factory(mobile_products.router)
    response = client.get("/m/products")
    for href in ("/m/receipts", "/m/writeoff", "/categories", "/dictionary", "/catalogs"):
        assert f'href="{href}"' in response.text
```

### WR-02: New mobile toolbar buttons likely fall short of the project's own 44px touch-target minimum

**File:** `app/templates/mobile_partials/products_toolbar.html:1-17`, `app/static/style.css:211-222` (`button, a.button` rule)

**Issue:** `24-UI-SPEC.md` claims the mobile toolbar's `a.button` links "already clear 44px" (padding `8px 16px` + `font-size: 16px`), flagged there as "verify at execution." Computing it: `line-height: 1.5` (inherited from `body`) × `16px` font ⇒ ~24px line box, plus `8px + 8px` padding, plus the button's own `1px + 1px` border (content-box model — no `box-sizing: border-box` reset exists anywhere in `style.css`) ⇒ ≈42px total height, under the 44px minimum the project enforces everywhere else touch targets appear (`.mobile-back`, `.mobile-card`, `nav.mobile-tabbar a`, `.mobile-actions button` all get an explicit `min-height: 44px` override). This is the first phase to place plain `.button`/`.form-actions` elements (as opposed to `.mobile-tile`/`.mobile-actions`, which already override the height) inside a touch context (`.mobile-shell`), and no corresponding override was added.

**Fix:** Add a mobile-scoped override, e.g. `.mobile-shell .toolbar a.button { min-height: 44px; box-sizing: border-box; display: inline-flex; align-items: center; }` (mirrors the existing `.mobile-actions button, .mobile-actions a.button { min-height: 44px }` precedent at `style.css:391`).

### WR-03: `/finance/report` now highlights the wrong top-nav tab as active

**File:** `app/templates/base.html:41`

**Issue:** `24-01-PLAN.md` intentionally simplified the Финансы active-state check from `startswith("/finance") and not startswith("/finance/report")` to plain `startswith("/finance")`, reasoning that Экспорт кассы "is leaving the nav entirely." But Экспорт кассы didn't leave reachability entirely — D-08 moved it under `/settings` (`app/templates/pages/settings.html:12-14`, `href="/finance/report"`). As a result, an operator who reaches `/finance/report` via Настройки now sees the **Финансы** tab highlighted as active, not **Настройки** — a misleading "you are here" indicator for a page that is, per the new IA, hosted under Настройки.

**Fix:** Either accept this as a documented trade-off (Финансы and Экспорт кассы genuinely are the same data domain), or scope the Финансы active check back to exclude `/finance/report` while leaving Настройки's own check (`startswith("/settings")`) as the sole match for that page — whichever direction, the current behavior appears to be an unintended side effect of the "no longer needed" reasoning in the plan rather than a deliberate choice.

## Info

### IN-01: "N складов" is grammatically incorrect for N=2 in Russian

**File:** `app/services/settings.py:16-24`, `app/templates/pages/settings.html:4-7`

**Issue:** `settings_summary` renders `"{N} складов"` regardless of N (e.g. "2 складов" instead of the grammatically correct "2 склада"). `24-UI-SPEC.md` explicitly sanctions this simplification for MVP ("use existing pluralization convention if present, otherwise the numeral + «складов» form is acceptable"), so this is a documented trade-off, not a defect — flagged here only as a low-priority polish item if RU pluralization is ever centralized elsewhere in the app.

**Fix:** Not required for this phase; revisit only if/when a shared RU-pluralization helper is introduced.

---

_Reviewed: 2026-07-17T21:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
