# Phase 24: Navigation Restructure & Settings - Context

**Gathered:** 2026-07-17
**Status:** Ready for planning

<domain>
## Phase Boundary

Collapse the current flat 17-item top-level desktop nav down to the 8 first-class pages (Главная, Товары, Продажи, Покупатели, История, Отчёты, Финансы, Настройки). Nest Приход, Списание, Справочник, Категории, and Каталоги under a new secondary menu on the Товары page. Nest Перемещение as a per-row action in the product list. Create a new Настройки page hosting Склады, Резервные копии, and Экспорт кассы. Move Экспорт (CSV) into the Резервные копии page as an embedded section (the standalone `/export` route goes away as a nav destination). Add "Назад к отчётам" back-links to every report detail page. Build mobile's first persistent tab bar (7 tabs, mirroring desktop minus Настройки) and retire the current 10-tile mobile home grid, giving mobile the same nested-menu pattern as desktop for the items that don't fit in a tab.

**Explicitly NOT in this phase:** No new capabilities — this is a pure reachability/IA restructure, every destination page already exists and keeps its current functionality. No mobile entry point for Настройки-hosted pages (Склады/Резервные копии/Экспорт кассы) — confirmed desktop-only. No changes to the Главная dashboard content itself (Phase 23 already shipped it) beyond removing the old 10-tile grid on mobile.

</domain>

<decisions>
## Implementation Decisions

### Товары page secondary menu (NAV-01, NAV-02, NAV-03, NAV-07 partial)
- **D-01: A button/toolbar panel above the product list** — plain HTML, no JS, no new dropdown component. Rejected: dropdown/flyout menu (no existing component in the project, would be new JS/CSS surface), `<details>/<summary>` (existing precedent in `product_rows.html` for batches, but operator wants the actions always visible, not click-to-reveal), and tabs (wrong metaphor for actions vs. views).
- **D-02: Категории (currently a top-level nav item, not in NAV-01..08) folds into this same Товары toolbar**, alongside Приход/Списание/Справочник. Its standalone `/categories` page and route stay as-is; only its top-nav entry moves.
- **D-03: Каталоги (`/catalogs` — active catalog number + close date, added in Phase 23 D-02) also folds into this same Товары toolbar**, not into Настройки. Operator's mental model groups it with product/assortment management, not with admin settings.
- **D-04: Toolbar items are grouped by meaning**, not one flat row — e.g. "Действия" (Приход, Списание, Перемещение-related) vs "Справочники" (Категории, Справочник, Каталоги). Exact grouping/labels are Claude's discretion (see below) as long as the two-group shape is followed.
- **D-05: The toolbar is always visible/expanded on the Товары page**, never collapsed behind a click — Приход and Списание are frequent daily operations and the operator wants zero extra clicks to reach them.

### Настройки page (NAV-05, NAV-06, NAV-04)
- **D-06: `/settings` is a hub page with a short status summary next to each link**, not a bare list of links. Confirmed scope: количество складов next to the Склады link, and the date of the last backup next to the Резервные копии link — both computed from existing services, no new tracking needed. (Каталоги/`/catalogs` is NOT on this page — see D-03.)
- **D-07: Экспорт (NAV-04, currently the standalone `/export` page) is embedded as a section directly on the Резервные копии (`/backup`) page**, not linked to as a separate destination. The `/export` route itself may still exist as a backing endpoint, but it is no longer a nav destination in its own right.
- **D-08: Экспорт кассы (`/finance/report`, currently a top-level nav item, not in NAV-01..08) moves under Настройки**, alongside Склады and Резервные копии — grouped with backups/data-export administrative actions rather than staying under Финансы.

### Mobile navigation (MOB-01)
- **D-09: New persistent tab bar is docked at the TOP of the screen**, not the bottom (operator's explicit choice, overriding the more common bottom-tab-bar mobile convention — flag this for planning/UI-spec attention since it deviates from typical mobile ergonomics).
- **D-10: The existing 10-tile mobile home grid (`mobile_pages/home.html`) is removed entirely** once the tab bar ships — it was always meant to be temporary scaffolding (see the explicit code comment at `mobile_pages/home.html:18-22` anticipating this). All mobile navigation goes through the new tab bar plus per-page nested menus.
- **D-11: Items that don't fit in the 7 mobile tabs (Приход, Списание, Перемещение, Справочник, Каталоги) are reached mirroring the desktop pattern** — the same toolbar/grouped-button shape from D-01..D-04, adapted for touch, living on the mobile Товары tab. No separate mobile-only navigation scheme for these.
- **D-12: Настройки has NO mobile entry point at all** — Склады, Резервные копии, Экспорт кассы, Экспорт are unreachable from `/m/*` by design. This matches MOB-01 excluding Настройки from the mobile tab set; the operator confirmed this is intentional (admin/backup tasks are desktop-only), not an oversight to patch later.

### Перемещение entry point (NAV-07)
- **D-13: Перемещение is reached via a per-row action in the product list** (`product_rows.html`), not from a product detail page — there is currently no dedicated single-product detail page/route to hang it off, and the operator wants it reachable directly from the list they're already scanning.
- **D-14: Opening Перемещение from a product row pre-selects that product on the transfer form automatically** — no re-selection step. The transfer form (`/transfers`, Phase 20) needs to accept an incoming product parameter and pre-fill/lock the product field.

### Claude's Discretion
- Exact Russian button/group labels and layout for the Товары toolbar (D-01/D-04) — as long as it's an always-visible button panel with the two semantic groups.
- Exact wording and placement of the "Назад к отчётам" link on each report detail page (RPT-01) — not separately discussed; follow the existing `catalog_detail.html:3` "← Все каталоги" precedent (a `<p><a href="/reports">...</a></p>` immediately under the page title).
- Exact visual treatment of the Настройки summary line (D-06) — e.g. inline with the link vs. a small subtitle underneath.
- Whether the pre-selected product on the transfer form (D-14) is passed via query param (mirroring History's `?product=` convention from Phase 23) or another mechanism — implementation detail.
- Icon/label choices for the 7 mobile tabs and the top tab bar's exact markup/CSS — no existing mobile tab-bar component to follow (this is the first one).
- Whether `/export` and `/finance/report` keep their existing route paths as backing endpoints for the embedded sections (D-07/D-08) or get renamed — implementation detail, no operator-visible difference as long as the destinations described above are reachable.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements and scope
- `.planning/REQUIREMENTS.md` §Navigation — NAV-01..08 (lines 12-19), §Reports — RPT-01 (line 80), §Mobile — MOB-01 (line 84).
- `.planning/ROADMAP.md` §"Phase 24: Navigation Restructure & Settings" (lines 267-281) — goal, 5 success criteria, depends-on note (Phases 19/20/23 must be in final shape first).
- `.planning/PROJECT.md` §Current Milestone target features (lines 17-31) — navigation restructure bullets, matches NAV-01..08 exactly.
- `.planning/STATE.md` (lines 66-68) — why navigation is sequenced last in v2.0 (soft-depends on Товары/Склады/Главная being in final shape).
- `.planning/phases/23-dashboard-history-rebuild/23-CONTEXT.md` — D-01/D-02 note that Настройки does not exist before this phase, and that `/catalogs` already gained the active-catalog-number/close-date fields this phase must now also nest into the Товары menu (D-03 above).

### Prior art this phase restructures (not replaces functionality of)
- `app/templates/base.html:34-52` — current flat desktop top-nav, 17 hand-rolled `<a>` items with inline active-state Jinja conditionals; the file this phase reduces to 8 items plus the new Товары toolbar and Настройки link.
- `app/static/style.css:20-36` — nav styling / `class="active"` pattern, reusable for the new toolbar and tab bar.
- `app/templates/mobile_base.html:31` — mobile's current single back-link block (`{% block back %}`), no persistent nav; the anchor point for the new top tab bar.
- `app/templates/mobile_pages/home.html:5-16` (`.mobile-tile-grid`, 10 tiles) and its explicit `home.html:18-22` comment flagging this grid as scaffolding until "Phase 24's tab bar ships" — confirms D-10 is expected, not a surprise removal.
- `app/templates/partials/product_rows.html:75-76` — existing `<details>/<summary>` disclosure precedent (product batches); considered and rejected as the Товары-toolbar pattern (D-01) but still the closest existing per-row-action precedent for D-13's transfer button.
- `app/templates/pages/catalog_detail.html:3` — `<a href="/catalogs">← Все каталоги</a>` back-link precedent to follow for RPT-01.
- `app/routes/reports.py:86-181` — the 6 report routes needing a back-link: `/reports/sales`, `/reports/writeoffs`, `/reports/stock`, `/reports/expiry`, `/reports/products` (`/reports` itself is the landing page, not a detail page).
- `app/routes/export.py` — the `/export` (CSV) route being embedded into `/backup` per D-07.
- `app/routes/backup.py` — the `/backup` (Резервные копии) page gaining the embedded export section (D-07) and being linked from the new Настройки page (D-06).
- `app/routes/catalogs.py`, `app/services/catalogs.py` — `/catalogs` page, moving its nav entry point into the Товары toolbar (D-03).
- `app/routes/finance.py` (`/finance/report`) — Экспорт кассы, moving its nav entry point into Настройки (D-08).
- `app/routes/warehouses.py` (Склады) — linked from the new Настройки page (D-06), with a warehouse-count summary.

### Precedent patterns to follow
- `app/services/operations.py::history_view` / History's `?product={id}` query-param convention (Phase 23) — precedent for how D-14's product pre-selection could pass a product into the transfer form.
- Desktop/mobile separation established since Phase 11 (`app/routes/mobile_*.py`, `app/templates/mobile_pages/`) — this phase's mobile tab bar and Товары-toolbar-on-mobile follow this same separate-tree-same-services convention, not a shared-template approach.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/static/style.css:20-36` — existing nav bar styling and active-state class pattern, extendable to the new toolbar/tab bar rather than inventing new CSS conventions.
- `app/templates/pages/catalog_detail.html:3` — ready-made back-link markup pattern for RPT-01.
- `app/templates/partials/product_rows.html` — the product list partial that gains the Перемещение row action (D-13).

### Established Patterns
- Server-rendered Jinja2 + HTMX 2.0.10 (vendored, offline). No SPA, no build step — the Товары toolbar and mobile tab bar must be plain HTML/CSS, no new JS dependency.
- Thin routes, all logic in `app/services/*.py` — the Настройки summary counts (warehouse count, last-backup date) belong in a service function, not inline in the route.
- Desktop and mobile are fully separate route/template trees reusing the same underlying service functions (Phase 11-23 convention, unbroken) — the mobile tab bar and Товары toolbar are new mobile templates calling existing services, not a shared component with desktop.

### Integration Points
- `app/templates/base.html` — top-nav rewrite (8 items) + Товары toolbar partial include.
- New `app/routes/settings.py` (or similar) + `app/templates/pages/settings.html` — the new Настройки page (D-06), likely composing `app/services/warehouses.py` (count) and `app/services/backup.py`/`app/routes/backup.py` (last-backup date) — check `app/routes/backup.py` for whether a "last backup timestamp" is already tracked or needs adding.
- `app/routes/backup.py` + its template — gains the embedded Экспорт section (D-07).
- `app/routes/transfers.py` (or wherever `/transfers` lives, Phase 20) — needs to accept a pre-selected product parameter (D-14).
- `app/templates/mobile_base.html` — new persistent top tab bar block, replacing/extending the current back-link-only block.
- `app/templates/mobile_pages/home.html` — tile grid removal (D-10).
- Every `app/templates/pages/reports_*.html` — back-link addition (RPT-01).

</code_context>

<specifics>
## Specific Ideas

- Operator wants the Товары toolbar grouped into two semantic clusters (actions vs. reference/lookup pages), not one flat row — mirrors how they think about Приход/Списание/Перемещение as "things I do" versus Категории/Справочник/Каталоги as "things I look up."
- Operator explicitly chose a top-docked mobile tab bar over the more conventional bottom-docked one — worth flagging to the UI-spec/planning stage as a deliberate deviation, not an oversight.
- Operator confirmed Настройки is intentionally desktop-only with no mobile fallback — administrative/backup tasks aren't something they'd do from the field.
- Операторская логика по каталогам: и `/catalogs` (номер каталога/дата закрытия), и `/categories` (категории товаров) относятся к "товарному" контексту и должны жить в меню Товаров, а не в Настройках, хотя формально это "справочные" данные, а не операции над одним товаром.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope across all 4 discussed areas (Товары menu, Настройки page, mobile navigation, Перемещение entry point). No new capabilities were proposed; every decision was about where an existing page/action becomes reachable from.

</deferred>

---

*Phase: 24-Navigation Restructure & Settings*
*Context gathered: 2026-07-17*
