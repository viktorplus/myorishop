---
phase: 04-sales-customers
plan: 04
subsystem: customers
tags: [fastapi, sqlalchemy, htmx, jinja2, search, purchase-history]

# Dependency graph
requires: ["04-01", "04-02"]
provides:
  - "app/services/customers.py: create_customer, update_customer, get_customer, search_customers, customer_search_view, purchase_history"
  - "app/routes/customers.py: GET/POST /customers CRUD, /customers/search, /customers/{id}, /customers/{id}/edit"
  - "customer templates: pages/customers_list.html, partials/customer_rows.html, pages/customer_form.html, pages/customer_detail.html, partials/purchase_history.html"
  - "Покупатели nav link + customers.router wired into app.main"
affects: ["04-05"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "search_lc Cyrillic-safe shadow (mirrors Product.name_lc, D-27): maintained in Python str.lower() on create/update, never SQL lower()"
    - "purchase_history joins Operation -> Sale -> Product on Operation.sale_id == Sale.id, filtered to Operation.type == 'sale' and Sale.customer_id ==, reading the FROZEN op.unit_price_cents (never the current Product.sale_cents)"

key-files:
  created:
    - app/services/customers.py
    - app/routes/customers.py
    - app/templates/pages/customers_list.html
    - app/templates/partials/customer_rows.html
    - app/templates/pages/customer_form.html
    - app/templates/pages/customer_detail.html
    - app/templates/partials/purchase_history.html
  modified:
    - app/main.py
    - app/templates/base.html

key-decisions:
  - "customer_search_view mirrors catalog.search_view exactly, reusing catalog.split_match (single source for highlight-segment building — never built HTML in Python)"
  - "No IntegrityError/duplicate guard on Customer writes — A2 explicitly allows duplicate names/consultant numbers (walk-in quick-create tolerance), unlike Product/Dictionary which have unique-code guards"

requirements-completed: [CST-01, CST-02]

# Metrics
duration: 20min
completed: 2026-07-09
---

# Phase 4 Plan 4: Customers CRUD + Purchase History Summary

**Full customer CRUD at `/customers` with Cyrillic-safe instant search (Python-folded `search_lc` shadow) and a customer detail page showing frozen-price purchase history via an Operation→Sale→Product join.**

## Performance

- **Duration:** ~20 min
- **Tasks:** 3
- **Files modified:** 9 (7 created, 2 modified)

## Accomplishments

- `app/services/customers.py`: `create_customer`/`update_customer` strip inputs, require a non-blank name (`NAME_REQUIRED_ERROR`), and maintain a lowercased `search_lc` shadow of "name surname consultant" — mirrors the Phase 2 `Product.name_lc` pattern since SQLite cannot fold Cyrillic. `search_customers` lowers the query in Python and matches via `Customer.search_lc.contains(q_lc, autoescape=True)`, capped at 20. `customer_search_view` mirrors `catalog.search_view`, reusing `catalog.split_match` for highlight segments (name and consultant number). `purchase_history` joins `Operation → Sale → Product` on `Operation.sale_id == Sale.id`, filters `Sale.customer_id ==` and `Operation.type == "sale"`, ordered newest first — and reads the FROZEN `op.unit_price_cents`, verified unchanged after mutating the product's current `sale_cents` (CST-02 anti-pattern guard).
- `app/routes/customers.py`: thin CRUD routes over the service — `GET /customers` (list via `customer_search_view(session, "")`), `GET /customers/search` (rows partial only), `GET /customers/new`, `POST /customers` (create, 422 + re-render on error), `GET /customers/{id}` (detail + purchase history, 404 on unknown), `GET /customers/{id}/edit`, `POST /customers/{id}` (update, 422 + re-render on error). Literal paths declared before the parameterized `/customers/{customer_id}` route (route-order rule, mirrors `products.py`). Wired `customers.router` into `app.main` and added the «Покупатели» nav link between «Продажи» and «Справочник» in `base.html`.
- Five templates: `customers_list.html` (search + «Добавить покупателя»), `customer_rows.html` (highlighted name/consultant segments via the `split_match` idiom, empty-state and empty-search copy), `customer_form.html` (single-column `.stacked-form`, required «Имя» autofocused, optional «Фамилия»/«Номер консультанта»), `customer_detail.html` (h1 name/surname, muted consultant-number meta, «История покупок» section), `purchase_history.html` (table Когда/Код/Название/Кол-во/Цена/Сумма rendering the frozen `unit_price_cents`, empty state «Покупок пока нет.»). No `|safe` used anywhere — autoescape only.

## Task Commits

Each task was committed atomically:

1. **Task 1: customers service — CRUD, Cyrillic search, purchase history** - `6f2b11e` (feat)
2. **Task 2: customers routes + nav + router wiring** - `0519340` (feat)
3. **Task 3: customer templates (list, rows, form, detail, purchase history)** - `f2b06fe` (feat)

_Note: this is a worktree execution; STATE.md/ROADMAP.md are updated centrally by the orchestrator after all wave-3 worktree agents complete._

## Files Created/Modified

- `app/services/customers.py` - `create_customer`, `update_customer`, `get_customer`, `search_customers`, `customer_search_view`, `purchase_history`; `NAME_REQUIRED_ERROR`
- `app/routes/customers.py` - `/customers` CRUD + detail routes, thin over the service
- `app/templates/pages/customers_list.html` - list page with instant search
- `app/templates/partials/customer_rows.html` - search results rows partial
- `app/templates/pages/customer_form.html` - create/edit form
- `app/templates/pages/customer_detail.html` - detail page + purchase history section
- `app/templates/partials/purchase_history.html` - frozen-price history table
- `app/main.py` - `customers` router include
- `app/templates/base.html` - «Покупатели» nav link

## Decisions Made

- **No unique-constraint guard on Customer writes:** unlike `Product`/`Dictionary`, `Customer` has no unique code/name constraint (RESEARCH A2 — duplicates are allowed for walk-in quick-create tolerance), so `create_customer`/`update_customer` need no `IntegrityError` translation, simplifying the write path relative to the catalog/dictionary precedents.
- **`customer_search_view` mirrors `catalog.search_view` exactly**, importing `split_match` from `app.services.catalog` rather than duplicating the highlight-segment logic — single source of truth for how highlighted text is built (never built as HTML in Python; the template renders `<mark>` literally).

## Deviations from Plan

None — plan executed exactly as written. One line-length ruff fix (docstring shortened in `customer_search_view`) applied inline during Task 1, not tracked as a formal deviation since it was a trivial style correction with zero behavior change.

## Issues Encountered

- The Task 1 `<verify>` command's `-k "crud or search or history or history_frozen"` filter incidentally also selects `test_web_customer_detail_history` (a Task-2/3-dependent web test, via substring match on "history") — the same known `-k` overlap pattern documented in the 04-02 SUMMARY. Confirmed via a narrower `-k "... and not web"` run that all 6 intended service-level tests passed after Task 1; the full 12-test suite (including the web test) passed once Tasks 2-3 landed.
- Pre-existing `ruff check`/`ruff format --check` findings in `tests/test_customers.py`, `tests/test_sales.py`, and several Phase 1-2 files were confirmed pre-existing and already logged in `deferred-items.md` by Plans 04-01/04-02 — not re-logged here since no new instances were introduced by this plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `uv run pytest tests/test_customers.py -q` is fully green (12/12).
- `uv run pytest -q` shows 143 passed, 5 failed — exactly the oversell (04-03) and customer-picker (04-05) tests already deferred by Plan 04-02's SUMMARY; no new failures introduced by this plan.
- Plan 04-05 (sale-form customer picker) can call `search_customers`/`create_customer` directly from `app/services/customers.py` at the commented insertion points already left in `app/templates/partials/sale_form.html` and `app/services/sales.py` by Plan 04-02.
- No blockers.

---
*Phase: 04-sales-customers*
*Completed: 2026-07-09*

## Self-Check: PASSED

All 7 created files verified present on disk (`app/services/customers.py`,
`app/routes/customers.py`, `app/templates/pages/customers_list.html`,
`app/templates/partials/customer_rows.html`, `app/templates/pages/customer_form.html`,
`app/templates/pages/customer_detail.html`, `app/templates/partials/purchase_history.html`),
plus this summary. All 4 task/plan commits (`6f2b11e`, `0519340`, `f2b06fe`, `fbed336`)
verified present in git log.
