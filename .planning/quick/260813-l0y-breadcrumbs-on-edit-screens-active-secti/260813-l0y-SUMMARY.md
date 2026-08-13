---
phase: quick
plan: 260813-l0y
subsystem: ui
tags: [jinja2, htmx, breadcrumbs, navigation, nav-highlight]

# Dependency graph
requires: []
provides:
  - "app/routes/__init__.py::nav_section(path) — one shared prefix->section table read by both desktop and mobile nav"
  - "app/routes/__init__.py::batch_identity_label(batch, product) — name/derived/bare-product-name identity label"
  - "app/templates/partials/breadcrumbs.html — shared breadcrumb partial (crumbs list of {label, href})"
  - "breadcrumb trails + identity lines on batch/product/customer/warehouse edit forms (desktop + mobile)"
affects: [ui, mobile, nav]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared template globals in app/routes/__init__.py registered the established way (templates.env.globals[...] = ...)"
    - "Active-nav-highlight now reads one path->section lookup table instead of per-link startswith"

key-files:
  created:
    - app/templates/partials/breadcrumbs.html
  modified:
    - app/routes/__init__.py
    - app/static/style.css
    - app/templates/base.html
    - app/templates/mobile_base.html
    - app/templates/pages/batch_form.html
    - app/templates/pages/product_form.html
    - app/templates/pages/customer_form.html
    - app/templates/pages/warehouse_form.html
    - app/templates/mobile_pages/batch_edit.html
    - app/templates/mobile_partials/search_product_detail.html
    - app/__init__.py
    - tests/test_nav.py
    - tests/test_batches.py
    - tests/test_catalog.py
    - tests/test_customers.py
    - tests/test_warehouses.py
    - tests/test_mobile_batches.py
    - tests/test_mobile_search.py

key-decisions:
  - "nav_section() table lists /settings only (not /settings/users separately) — /settings already covers it via startswith, avoiding a prefix-of-a-prefix violation of the table's mutual-exclusivity invariant while still satisfying the behavior spec (verified by a dedicated test case)."
  - "/m/reports/expiry used verbatim as the reports prefix (not the broader /m/reports) per the plan's <behavior> block — harmless in practice since it is the only mobile reports route today."
  - "/returns and /m/returns map to history for the shared table's completeness even though the route today only ever renders as an HTMX fragment inside /history — proven by a direct nav_section() unit test only, not an HTTP round-trip (documented staleness, matches the plan's own note)."

patterns-established:
  - "Breadcrumb partial: crumbs = list of {label, href}; last crumb (href: none) renders as plain <span aria-current=page> text, never a link — reusable for any future edit/detail screen."

requirements-completed: []

# Metrics
duration: ~35min
completed: 2026-08-13
---

# Quick Task 260813-l0y: Breadcrumbs on edit screens + active-section nav highlight fix

**Shared `nav_section()` prefix table + `breadcrumbs.html` partial: six edit/detail screens now show a breadcrumb trail and object-identity line, and both desktop/mobile navs correctly highlight the owning section on every nested Товары/История screen instead of nothing.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 3 automated (Task 4 is a `checkpoint:human-verify` — deliberately not executed by this agent; see below)
- **Files modified:** 17 (1 new template partial, 16 modified)

## Accomplishments

- `nav_section(path)` — one shared, mutually-exclusive path-prefix→section table in `app/routes/__init__.py`, read by both `base.html` and `mobile_base.html` as a template global. Replaces two independently-maintained `startswith` chains that only ever matched a section's own top-level prefix (so every nested screen like `/batches/{id}/edit`, `/receipts/new`, `/m/search` previously highlighted nothing).
- `batch_identity_label(batch, product)` — stored `batch.name` wins; else derives `"{product.name} — dd.mm.yyyy"` from expiry; else bare `product.name`.
- `partials/breadcrumbs.html` — shared partial rendering a `crumbs` list; every crumb except the last is a link, the last is plain `<span aria-current="page">` text (never a link, never `|safe`).
- Six locked-scope screens now show a breadcrumb trail + (where the object has identifying fields) an object-identity line under the h1: desktop `batch_form.html` / `product_form.html` / `customer_form.html` / `warehouse_form.html`, mobile `batch_edit.html` / `search_product_detail.html`.
- Both mobile target screens replace the generic `← Главная` link with the breadcrumb (no duplicate back affordance) via a new `{% block back %}` override.
- `mobile_base.html`'s back/logout region is now a real `.mobile-header-row` flex row (fixes a pre-existing bug where `margin-left:auto` never actually right-aligned the logout link on inline-level boxes) — needed because the back slot can now render a multi-crumb `<nav>` that wraps onto several lines.
- `__version__` bumped `1.31` → `1.32`.

## Task Commits

1. **Task 1: Foundation — nav_section()/batch_identity_label() globals, breadcrumbs.html partial, CSS, both navs wired** - `03a5fdb` (feat)
2. **Task 2: Desktop breadcrumbs + identity lines (batch, product, customer, warehouse forms)** - `14b60cd` (feat)
3. **Task 3: Mobile breadcrumbs + identity line (batch edit, product detail), version bump** - `879a03e` (feat)

Task 4 (`checkpoint:human-verify`) is a visual/manual verification step — not executed by this agent per orchestrator instructions. See "Pending Human Verification" below for exactly what to check.

## Files Created/Modified

- `app/routes/__init__.py` - `NAV_SECTION_PREFIXES` table + `nav_section(path)` + `batch_identity_label(batch, product)`, registered as template globals
- `app/templates/partials/breadcrumbs.html` (new) - shared breadcrumb trail partial
- `app/static/style.css` - `.breadcrumbs` (`overflow-wrap: anywhere` so a long name wraps instead of forcing horizontal scroll) + `.mobile-header-row` (real flex row for the back/logout region)
- `app/templates/base.html` - desktop nav reads `active_section = nav_section(request.url.path)` instead of 7 per-link `startswith` conditions
- `app/templates/mobile_base.html` - mobile tabbar reads the same `active_section`; back/logout wrapped in `.mobile-header-row`
- `app/templates/pages/batch_form.html` / `product_form.html` / `customer_form.html` / `warehouse_form.html` - breadcrumb trail + identity line
- `app/templates/mobile_pages/batch_edit.html` / `mobile_partials/search_product_detail.html` - `{% block back %}` breadcrumb override + (batch screen only) identity line
- `app/__init__.py` - `__version__` `1.31` → `1.32`
- `tests/test_nav.py`, `tests/test_batches.py`, `tests/test_catalog.py`, `tests/test_customers.py`, `tests/test_warehouses.py`, `tests/test_mobile_batches.py`, `tests/test_mobile_search.py` - new regression coverage for all of the above (17 new test functions total)

## Decisions Made

- `/settings/users` is not a separate `NAV_SECTION_PREFIXES` entry — `/settings` already covers it via `startswith`, and adding it separately would violate the table's own "no listed prefix is a prefix of another listed prefix" invariant for no behavioral gain. Covered by a `nav_section("/settings/users") == "settings"` test case instead.
- `/m/reports/expiry` (not the broader `/m/reports`) used verbatim as specified in the plan's `<behavior>` block — currently identical in effect since it's the only mobile reports route.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## Pending Human Verification (Task 4 — not executed by this agent)

Task 4 is `type="checkpoint:human-verify"` and was intentionally skipped by this executor per the orchestrator's instructions — it performs the visual check in a real browser against the deployed/running server. What to look at:

1. **Desktop batch edit** (`/products` → expand «Партии» → «Изменить»): breadcrumb reads `Главная › Товары › {product name (code)} › Партия`; identity line under the h1 correctly names batch/warehouse/quantity; «Товары» highlighted in the top nav.
2. **Desktop nested-screen highlight**: `/receipts/new`, `/writeoff`, `/warehouses`, `/categories` all keep «Товары» highlighted; `/customers` and `/finance` highlight their own tab and NOT «Товары».
3. **Mobile** (narrow viewport, e.g. 375px): `/m/` → search → product detail — breadcrumb replaces `← Главная` (only ONE back affordance visible), no horizontal scrollbar even with a long product name, «Выйти» logout control renders sensibly next to/below the breadcrumb without overlapping. Repeat on the batch edit screen via «Изменить», also confirming the identity line renders.
4. **Mobile nested-screen highlight**: `/m/receipts`, `/m/writeoff`, `/m/search` all keep the «Товары» tab highlighted.

## Verification

Full suite: `uv run pytest tests/ -q --junitxml=reports/quick-260813-l0y.xml`

```
FAILED tests/test_sync_ui.py::test_sync_run_returns_oob_partial - assert 'Син...
FAILED tests/test_sync_ui.py::test_offline_run_returns_200_ru - assert 'Нет с...
FAILED tests/test_sync_ui.py::test_not_configured_run_is_a_noop - assert 'Син...
FAILED tests/test_sync_ui.py::test_lock_hit_returns_locked_partial - assert F...
4 failed, 1277 passed, 13 skipped, 3 warnings in 436.90s (0:07:16)
```

The 4 failures are the documented pre-existing `tests/test_sync_ui.py` failures (deterministic local-suite-order flakiness from `sync_client._run_lock` held by the lifespan auto-sync thread — see MEMORY.md `preexisting-sync-ui-test-failures`), unrelated to this plan's scope. All 17 new tests added by this plan pass; task-scoped runs (`test_nav.py`+`test_batches.py`, then `test_batches.py`+`test_catalog.py`+`test_customers.py`+`test_warehouses.py`, then `test_mobile_batches.py`+`test_mobile_search.py`) were each green before their respective commit.

Artifacts:
- `reports/quick-260813-l0y.xml` (junit)
- `reports/quick-260813-l0y.sha` (HEAD at `879a03e15fed60dd52d592296cdfb0aa5c1128fe`)
- `reports/quick-260813-l0y.dirty` (working tree clean of tracked changes — only pre-existing untracked files remain, none touched by this plan)

## Next Phase Readiness

Code + tests complete and committed. Task 4 (visual/manual verification) is owned by the orchestrator against a real browser session; nothing further required from this executor.

---
*Phase: quick*
*Completed: 2026-08-13*

## Self-Check: PASSED

All 16 created/modified source files, the SUMMARY.md itself, and all 3 reports artifacts (`.xml`/`.sha`/`.dirty`) confirmed present on disk; all 3 task commits (`03a5fdb`, `14b60cd`, `879a03e`) confirmed present in `git log`.
