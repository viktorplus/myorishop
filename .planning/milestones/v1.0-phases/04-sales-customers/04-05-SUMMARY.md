---
phase: 04-sales-customers
plan: 05
subsystem: sales
tags: [fastapi, sqlalchemy, htmx, jinja2, customer-link]

# Dependency graph
requires: ["04-02", "04-03", "04-04"]
provides:
  - "app/routes/sales.py: GET /sales/customer-search, POST /sales/customer"
  - "partials/sale_customer.html: customer header (search + quick-create + selected chip)"
  - "partials/customer_picker.html: search rows for the sale-form picker"
  - ".customer-chip CSS rule"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Customer header lives OUTSIDE <form id=\"sale-form\"> (avoids nesting a second <form>) and associates its inputs via form=\"sale-form\" (same pattern the oversell confirm button already uses) so the hidden customer_id still submits with the basket"
    - "Picking a customer from the picker is a pure client-side swap: rows carry the customer's id/name/surname as data-* attributes (HTML-attribute-escaped by Jinja autoescape) and a hx-on:click handler reads them via .dataset and writes via .textContent — no extra server round trip, no string-built HTML/JS from untrusted names (T-4-01/T-4-05)"

key-files:
  created:
    - app/templates/partials/sale_customer.html
    - app/templates/partials/customer_picker.html
  modified:
    - app/routes/sales.py
    - app/templates/partials/sale_form.html
    - app/static/style.css

key-decisions:
  - "Renamed the quick-create route's generic error key from \"form\" to \"quick_create\": sale_customer.html is included inside sale_form.html on the normal basket routes, which already renders its own errors.form; a shared key would double-render the identical error block if both happened to be set at once (Rule 1 fix, not in the original plan text)"
  - "Customer-picker rows are a compact <table> (reusing existing table/th/td/mark rules), not a new list — matches the plan's \"no CSS for the picker beyond existing table/mark rules\" instruction"
  - "Selecting a picker row is fully client-side (plan's explicitly allowed alternative: \"a button carrying the id\") rather than a server round trip, since the row already carries the customer's full id/name/surname"

requirements-completed: [SAL-03]

# Metrics
duration: 30min
completed: 2026-07-09
---

# Phase 4 Plan 5: Customer Picker for the Sale Form Summary

**Sale-form customer header (Cyrillic autocomplete search + inline quick-create + selected chip with hidden customer_id) backed by two thin picker endpoints reusing the 04-04 customers service — walk-in stays valid with zero extra writes.**

## Performance

- **Duration:** ~30 min
- **Tasks:** 2
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments

- `app/routes/sales.py` gained two literal routes reusing `app/services/customers.py` (04-04) directly, with no changes to `register_sale` or the existing `/sales` routes: `GET /sales/customer-search` renders `partials/customer_picker.html` via `customer_search_view`; `POST /sales/customer` calls `create_customer` and renders `partials/sale_customer.html` — a selected chip on success, or the echoed quick-create inputs + inline `errors.name` («Укажите имя покупателя.») on validation failure (422), with an unexpected-exception fallback wrapped in `try/except` rendering the existing block-error text (never a raw 500).
- `partials/sale_customer.html`: the customer header, root `id="customer-header"`. Two states share one hidden `customer_id` input (`form="sale-form"` association, since the header lives OUTSIDE `<form id="sale-form">` to avoid nesting a second `<form>` — mirrors the oversell confirm button's existing `form=` pattern): a default state (search input + empty `#customer-picker` + «Новый покупатель» quick-create sub-region + muted «Без покупателя (розница)» note), and a selected state (`.customer-chip` «Покупатель: {имя} {фамилия}» + neutral «Убрать»). Toggling between the two states after a picker pick or «Убрать» is pure client-side (`hidden` attribute flips); a quick-create POST re-renders the whole block from the server instead.
- `partials/customer_picker.html`: a compact `<table>` of matching customers (reuses existing table/`<mark>` CSS, no new picker-specific styling), each row a button carrying the customer's id/name/surname as `data-*` attributes; clicking reads them via `.dataset`/writes via `.textContent` (never interpolates untrusted names into JS/HTML strings) to populate the chip and flip visibility — zero extra HTTP round trip for selection. Empty-search copy «Ничего не найдено по запросу „{q}“. …» matches the `product_rows.html`/`customer_rows.html` precedent.
- `partials/sale_form.html`: the 04-05 insertion point now includes `sale_customer.html`; the old standalone hidden `customer_id` input (04-02's walk-in placeholder, living inside `<form id="sale-form">`) was removed since `sale_customer.html`'s own hidden input (outside the form, `form="sale-form"`-associated) now owns that field — avoids submitting two same-named fields.
- `app/static/style.css`: `.customer-chip` (white surface, 1px `#d9d9d9` border, 4px radius, 8px padding, inline-flex, 8px gap, 16px/400 text) — the only new CSS this plan adds, per UI-SPEC.

## Task Commits

Each task was committed atomically:

1. **Task 1: picker routes — customer search + inline quick-create** - `79834b7` (feat)
2. **Task 2: customer header + picker partials, sale_form integration, chip CSS** - `6edf1fc` (feat)

_Note: this is a worktree execution; STATE.md/ROADMAP.md are updated centrally by the orchestrator after all wave-4 worktree agents complete._

## Files Created/Modified

- `app/routes/sales.py` - `GET /sales/customer-search`, `POST /sales/customer`; imports `create_customer`/`customer_search_view` from `app.services.customers`
- `app/templates/partials/sale_customer.html` (new) - the customer header: hidden `customer_id`, search input, empty-search picker mount point, quick-create sub-region, selected-chip state
- `app/templates/partials/customer_picker.html` (new) - search-result rows for the sale-form picker
- `app/templates/partials/sale_form.html` - wires the 04-05 insertion point; removes the now-redundant standalone hidden `customer_id` input
- `app/static/style.css` - `.customer-chip` rule

## Decisions Made

- See `key-decisions` in frontmatter: the `errors.quick_create` rename (avoids a double-rendered error block when `sale_customer.html` is included inside `sale_form.html`), the `<table>`-based picker (reuses existing CSS, adds none), and the fully client-side picker-row selection (the plan's own explicitly allowed alternative).
- The hidden `customer_id` input's default value falls back to the outer `customer_id` context variable (`{{ selected.id if selected else (customer_id or '') }}`) rather than only `selected` — this preserves the submitted customer link across a 422/oversell basket re-render (the existing `/sales` routes were left untouched per the plan's explicit "keep the existing GET/POST /sales routes intact" instruction, so those paths don't look up and re-pass a `selected` Customer object; the hidden field's *value* still carries the right id even though the header visually falls back to its default/unselected state on that round trip — data integrity is preserved, only the visual chip does not survive a validation-error redisplay).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Renamed the quick-create error key from `errors.form` to `errors.quick_create`**
- **Found during:** Task 2, while wiring `sale_customer.html` into `sale_form.html`'s shared include context
- **Issue:** `sale_form.html` already renders its own `{% if errors.form %}` block for basket-level failures. Since Jinja's `{% include %}` shares the parent's context by default, and my quick-create route's exception handler originally used the same `"form"` key, an unhandled exception on the *basket* POST would also make the *included* customer header's own `errors.form` check true — rendering the identical error text twice on screen.
- **Fix:** Renamed the quick-create route's generic-exception error key to `"quick_create"` (route side) and the corresponding template check to `errors.quick_create` (template side) — no longer collides with the basket's `errors.form` key.
- **Files modified:** `app/routes/sales.py`, `app/templates/partials/sale_customer.html`
- **Verification:** Full test suite green (148/148); manually verified via a scratch pytest test (removed before commit) that a basket-level failure only shows one error block and a quick-create failure shows the inline `errors.name` message.
- **Committed in:** `6edf1fc` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — a genuine template-namespace collision bug that would only surface on the rare unhandled-exception fallback path, not caught by the plan's own test list).
**Impact on plan:** No scope creep — a one-key rename inside code this plan itself introduced in Task 1.

## Issues Encountered

None beyond the deviation above. `uv run pytest tests/test_sales.py -q` (22/22) and the full suite (`uv run pytest -q`, 148/148) are green; `uv run ruff check app/routes/sales.py` and `uv run ruff format --check app/routes/sales.py` both exit 0 (the pre-existing, already-logged `ruff` findings in unrelated files — `alembic/versions/0001_initial_schema.py`, `app/models.py`, `app/services/catalog.py`, `app/services/ledger.py`, `tests/test_catalog.py`, `tests/test_ledger.py`, `tests/test_receipts.py`, `tests/test_sales.py`, `tests/test_customers.py` — are untouched by this plan, confirmed via `git diff --stat` against the pre-plan commit).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `uv run pytest -q` — 148 passed, 0 failed. All of SAL-01..05 and CST-01/02 are now fully green; this was the last plan in Phase 4.
- Manual UAT (per plan's `<human-check>`): type a name in the sale-form search → picker shows matching rows with `<mark>` highlight; click a row → chip appears with «Убрать»; quick-create a new customer inline → chip appears without leaving the sale; finalize with a selected customer → the sale links (verified programmatically via `test_web_sale_links_selected_customer`); walk-in (no selection) still finalizes (`test_web_sale_walkin_success` and friends, unchanged).
- No blockers.

---
*Phase: 04-sales-customers*
*Completed: 2026-07-09*

## Self-Check: PASSED

All created/modified files verified present on disk (`app/routes/sales.py`, `app/templates/partials/sale_customer.html`, `app/templates/partials/customer_picker.html`, `app/templates/partials/sale_form.html`, `app/static/style.css`, this summary). Both task commits (`79834b7`, `6edf1fc`) verified present in git log.
