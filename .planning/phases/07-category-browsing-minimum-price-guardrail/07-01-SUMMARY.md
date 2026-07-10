---
phase: 07-category-browsing-minimum-price-guardrail
plan: 01
subsystem: ui
tags: [fastapi, jinja2, sqlalchemy, htmx, catalog-browsing]

# Dependency graph
requires: []
provides:
  - "app.services.catalog.products_by_category(session) -> list[dict], groups shaped {label, products}"
  - "GET /categories route rendering products grouped by category"
  - "app/templates/pages/categories.html page template"
  - "base.html nav link to /categories"
affects: [07-02, 07-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Python-side dict grouping for category buckets (never a SQL NULL-ordering trick) to guarantee a fixed uncategorized-group position"

key-files:
  created:
    - app/routes/categories.py
    - app/templates/pages/categories.html
  modified:
    - app/services/catalog.py
    - app/templates/base.html
    - app/main.py
    - tests/test_catalog.py

key-decisions:
  - "products_by_category() groups Python-side (dict keyed by category or ''), not via SQL ORDER BY category IS NULL, so the 'Без категории' bucket's last position never depends on dict iteration order"

patterns-established:
  - "Plain full-page GET for browsing screens with no filter/search control (mirrors reports_stock_page) — no HX-Request branching needed"

requirements-completed: [CAT-01]

# Metrics
duration: 4min
completed: 2026-07-10
---

# Phase 7 Plan 01: Category Browsing Summary

**New `/categories` page groups all active products by category alphabetically, with a "Без категории" bucket always last, via `products_by_category()` and a plain thin route.**

## Performance

- **Duration:** ~4 min (task-commit window)
- **Started:** 2026-07-10T21:25:22+02:00
- **Completed:** 2026-07-10T21:29:19+02:00
- **Tasks:** 2 completed
- **Files modified:** 6 (2 created, 4 modified)

## Accomplishments
- `products_by_category(session)` service query: active products only, grouped by category, named groups alphabetical, uncategorized (`NULL`/`""`) bucket always last and never hidden
- New `GET /categories` route + `pages/categories.html` template rendering "Товары на складе" with per-group Код/Название/Остаток/Закупочная/Продажа/Каталог/Действия tables and an "Изменить" edit link per row
- Nav bar exposes a dedicated "Категории" link (placed right after "Товары") from every page, with active-class matching
- Empty-state block (verbatim reuse of the `/products` "Товаров пока нет" copy) when there are zero active products at all

## Task Commits

Each task was committed atomically, following RED → GREEN TDD sequencing:

1. **Task 1: products_by_category() service query**
   - `490c150` test(07-01): add failing test for products_by_category grouping
   - `1ceca93` feat(07-01): add products_by_category() grouped catalog query
2. **Task 2: /categories route, page template, nav link**
   - `8180ac4` test(07-01): add failing tests for /categories route, page, and nav link
   - `ae87b7e` feat(07-01): add /categories page, nav link, and router registration

_Note: for each task, the RED commit was verified to genuinely fail (ImportError / 404) before the GREEN commit was applied — confirmed via `uv run pytest` between commits, not just asserted._

## Files Created/Modified
- `app/services/catalog.py` - added `products_by_category(session) -> list[dict]`
- `app/routes/categories.py` (new) - `GET /categories` thin route
- `app/templates/pages/categories.html` (new) - grouped product listing page, empty-state fallback
- `app/templates/base.html` - new nav `<a href="/categories">Категории</a>` after "Товары"
- `app/main.py` - imports `categories`, registers `app.include_router(categories.router)` after `products.router`
- `tests/test_catalog.py` - 7 new tests (3 service-level `products_by_category` tests, 4 `test_web_categories_*`/`test_web_nav_has_categories_link` route/e2e tests)

## Decisions Made
- Followed PATTERNS.md verbatim for the grouping function and route shape (both flagged "exact" analog match) — no deviation needed.

## Deviations from Plan

None - plan executed exactly as written.

The plan's `<verification>` block lists `app/templates/base.html` as a `ruff check` target alongside the `.py` files. `ruff` cannot parse `.html` files as Python (confirmed: passing it explicitly produces a wall of `invalid-syntax` errors from treating Jinja/HTML markup as Python source, not a real lint finding). This is a pre-existing quirk of how the verification command is written, not a defect introduced by this plan — `ruff check app/services/catalog.py app/routes/categories.py app/main.py` (the actual Python files) passes clean with zero findings.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- CAT-01 fully delivered and independently verifiable; no schema dependency, so plans 07-02/07-03 (PRICE-01, min-sale-price guardrail) can proceed independently.
- `_PRICE_FIELDS` tuple and `parse_optional_cents` in `app/services/catalog.py` remain unchanged by this plan and are ready for 07-02/07-03 to extend with `min_sale_cents` per PATTERNS.md.

---
*Phase: 07-category-browsing-minimum-price-guardrail*
*Completed: 2026-07-10*
