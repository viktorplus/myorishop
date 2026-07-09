---
phase: 04-sales-customers
plan: 02
subsystem: sales
tags: [fastapi, sqlalchemy, htmx, jinja2, ledger, basket]

# Dependency graph
requires: ["04-01"]
provides:
  - "app/services/sales.py: register_sale, lookup_prefill, recent_sales"
  - "app/routes/sales.py: GET /sales/new, /sales/lookup, /sales/row, POST /sales"
  - "sale basket templates: pages/sale_form.html, partials/sale_form.html, sale_row.html, sale_lookup.html, recent_sales.html"
  - "Продажи nav link + sales.router wired into app.main"
  - ".basket td input CSS rule"
affects: ["04-03", "04-04", "04-05"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Dynamic per-row DOM ids: the first basket row keeps bare ids (code/name-wrap/qty/price-wrap) so the existing single-line focus/oob-swap idiom from receipt_form.html keeps working unmodified; rows added via \"Добавить строку\" get a generated row_id suffix to avoid oob-swap collisions"
    - "Sale price is REQUIRED per line (D-12 divergence from receipts, where an empty price is silently NULL) — register_sale rejects an empty/invalid price with a per-line RU error and writes nothing"

key-files:
  created:
    - app/services/sales.py
    - app/routes/sales.py
    - app/templates/pages/sale_form.html
    - app/templates/partials/sale_form.html
    - app/templates/partials/sale_row.html
    - app/templates/partials/sale_lookup.html
    - app/templates/partials/recent_sales.html
  modified:
    - app/main.py
    - app/templates/base.html
    - app/static/style.css
    - .planning/phases/04-sales-customers/deferred-items.md

key-decisions:
  - "Oversell aggregate check (SAL-04) left as an explicit commented insertion point in register_sale — this plan accepts every basket unconditionally; confirm is accepted but unused until 04-03"
  - "Customer header (search/quick-create/chip, D-05) left as an explicit commented insertion point in partials/sale_form.html; this plan only posts a hidden empty customer_id (walk-in) — 04-05 wires the picker in"
  - "Basket row DOM ids: bare ids (code/name-wrap/qty/price-wrap) for the first/default row, generated-suffix ids for added rows — keeps the existing receipt_form.html focus-after-swap and oob-swap-guard idioms working with zero changes while supporting N rows"

requirements-completed: [SAL-01, SAL-02, SAL-05]

# Metrics
duration: 45min
completed: 2026-07-09
---

# Phase 4 Plan 2: Sale Basket Slice Summary

**Multi-line walk-in sale basket (service + routes + templates): entered price and frozen cost snapshot per line, one-transaction commit, «Продажи» nav wiring, and an oob-refreshed recent-sales list.**

## Performance

- **Duration:** ~45 min
- **Tasks:** 3
- **Files modified:** 10 (7 created, 3 modified, plus 1 doc log update)

## Accomplishments

- `app/services/sales.py::register_sale` writes a multi-line walk-in basket sale in ONE transaction: validates every line (qty strictly positive, price required and parsed via `to_cents`, product resolved by active code) BEFORE staging anything, then stages the `Sale` header + one `record_operation(type_="sale", qty_delta=-qty, ..., commit=False)` per line, closing with a single `session.commit()`. Any invalid line (including an unknown code) aborts the whole basket with zero writes (D-02/D-03).
- Per-line snapshot: the operator's entered price becomes `unit_price_cents` (overrides the card `sale_cents`, which is only a pre-fill — SAL-02/D-10); `Product.cost_cents` is frozen into `unit_cost_cents` at write time and may be `NULL` without blocking the sale (SAL-05/D-11/D-12). Re-verified this freezes correctly even after the card's prices are later mutated.
- `lookup_prefill`/`recent_sales` mirror the receipts analogs; `lookup_prefill` only pre-fills the sale price (not cost/catalog, since a sale line has no such fields).
- `app/routes/sales.py`: thin routes over the service — `GET /sales/new`, debounced `GET /sales/lookup` (204 vs. name+price fill, per-row targeted via a `row` query param), `GET /sales/row` (fresh row for `hx-swap="beforeend"`), and `POST /sales` binding the repeated basket arrays via explicit `Form([], alias="code[]")`-style params plus explicit `customer_id`/`confirm` (T-4-05 — no implicit form binding of extra fields). Wired `sales.router` into `app.main`; added the «Продажи» nav link between Приход and Справочник.
- Templates: a full-width `.basket` table (`partials/sale_form.html` + `partials/sale_row.html`) with per-line code→name/price lookup, in-flight-typing guards (mirrors the receipt form's before-swap/oob-before-swap idiom, generalized to a dynamic row-id prefix check), a neutral success line, and an oob-refreshed `partials/recent_sales.html`. Left explicit, commented insertion points for the 04-03 oversell block and the 04-05 customer header so those waves can drop straight in.

## Task Commits

Each task was committed atomically:

1. **Task 1: sales service — register_sale, lookup_prefill, recent_sales** - `f7c9ab5` (feat)
2. **Task 2: sales routes + nav + router wiring** - `861f9e5` (feat)
3. **Task 3: sale templates (basket, row, lookup, recent) + .basket CSS** - `d23bec3` (feat)

_Note: this is a worktree execution; STATE.md/ROADMAP.md are updated centrally by the orchestrator after all wave-2 worktree agents complete._

## Files Created/Modified

- `app/services/sales.py` - `register_sale`, `lookup_prefill`, `recent_sales`; RU error constants (`PRICE_REQUIRED_ERROR`, `EMPTY_BASKET_ERROR`, `PRODUCT_NOT_FOUND_TMPL`, `QTY_ERROR`, `SAVE_ROLLBACK`)
- `app/routes/sales.py` - `GET /sales/new`, `/sales/lookup`, `/sales/row`, `POST /sales`; `_build_lines` helper rebuilding echoed basket rows from submitted arrays + service errors on 422
- `app/templates/pages/sale_form.html` - page shell (extends base, includes the form + recent-sales partials)
- `app/templates/partials/sale_form.html` - the whole basket form, swapped whole on every POST response
- `app/templates/partials/sale_row.html` - one basket line, array-named inputs, dynamic ids
- `app/templates/partials/sale_lookup.html` - per-line name/price lookup fill fragment
- `app/templates/partials/recent_sales.html` - oob-refreshable recent-sales list
- `app/main.py` - `sales` router include
- `app/templates/base.html` - «Продажи» nav link
- `app/static/style.css` - `.basket td input` rule
- `.planning/phases/04-sales-customers/deferred-items.md` - logged 2 pre-existing `I001` findings in `tests/test_sales.py`/`tests/test_customers.py` (both authored entirely by 04-01, untouched by this plan)

## Decisions Made

- **Bare vs. suffixed row DOM ids:** the first/default basket row uses bare ids (`code`, `name-wrap`, `qty`, `price-wrap`) so the plan's specified `#sale-form-wrap` focus hook (`document.getElementById('code').focus()`, copied verbatim from the receipt-form precedent) works without modification. Any row added via «Добавить строку» gets a generated `row_id` suffix (`code-{uuid}`, etc.) so oob price-fill swaps never collide across rows. The top-level swap guards match by id **prefix** (`startsWith('name')`/`startsWith('price')`) rather than one fixed id, generalizing the receipt form's single-line guard to N rows.
- **`zip(..., strict=False)` for basket arrays:** `code[]`/`qty[]`/`price[]` are untrusted repeated form fields (T-4-05); mismatched lengths are truncated to the shortest rather than raising, avoiding an unhandled exception path for malformed submissions while the route's own `try/except Exception` still catches any other unexpected error as a 422.
- **`SAVE_ROLLBACK` RU error text:** not explicitly named in the plan's artifact list; added as the commit-time `IntegrityError` fallback message («Не удалось сохранить продажу. Попробуйте ещё раз.»), mirroring the receipts `IntegrityError`→RU-error pattern (there is no natural duplicate-key race for a sale, but the guard costs nothing and matches the single-write-path contract).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - correctness] Added `strict=False` to the basket-line `zip()` call**
- **Found during:** Task 1 (`uv run ruff check app/services/sales.py`)
- **Issue:** `ruff` B905 flagged `zip(codes, qtys, prices)` for missing an explicit `strict=` parameter — a real ambiguity given these three arrays arrive as untrusted, independently-lengthed repeated form fields (T-4-05).
- **Fix:** Added `strict=False` explicitly, documenting the choice (truncate to shortest rather than raise) so a malformed submission degrades gracefully instead of throwing from inside `zip` before the route's `try/except` wrapper is even reached.
- **Files modified:** `app/services/sales.py`
- **Verification:** `uv run ruff check app/services/sales.py` exits 0; the 9 Task-1 service tests still pass unchanged.
- **Committed in:** `f7c9ab5` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 — a ruff-flagged correctness/ambiguity gap in untrusted-input handling, not a bug in existing behavior).
**Impact on plan:** No scope creep — purely a one-line defensive addition inside the already-planned `register_sale` implementation.

## Issues Encountered

- The plan's own Task 1 `<verify>` command (`-k "... or empty_basket or ..."`) incidentally also selects `test_web_sale_post_empty_basket_422` (a Task-2/3-dependent web test) via substring match on `empty_basket`. Ran the intended narrower service-level slice instead (9/9 passed) and confirmed the full intended set (13/13, including that web test) passes once Tasks 2-3 landed. No plan or code defect — just a `-k` substring overlap between a service test and a web test sharing a keyword.
- Pre-existing ruff `I001` findings in `tests/test_sales.py`/`tests/test_customers.py` (both authored entirely by Plan 04-01, confirmed via `git diff --stat` showing zero changes from this plan) were logged to `deferred-items.md` per the SCOPE BOUNDARY rule rather than fixed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `uv run pytest -q --ignore=tests/test_customers.py` shows 131 passed, 5 failed — exactly the oversell (`test_oversell_blocks_without_confirm`, `test_oversell_aggregates_duplicate_lines`, `test_web_sale_oversell_shows_warning_and_confirm_writes`) and customer-picker (`test_web_customer_search_returns_rows`, `test_web_customer_quick_create_returns_chip`) tests deferred to Plans 04-03/04-05. `tests/test_customers.py` still fails to collect (`ModuleNotFoundError: app.services.customers`) — expected until Plan 04-04.
- Plan 04-03 can implement the oversell aggregate check directly at the commented `--- 04-03 INSERTION POINT ---` in `app/services/sales.py::register_sale` (between line validation and header staging) and add the corresponding warning render branch already stubbed (as a no-op `if result and result.get("oversell")`) in `app/routes/sales.py::sale_create`.
- Plan 04-05 can implement the customer picker directly at the commented `04-05 INSERTION POINT` in `app/templates/partials/sale_form.html`, reusing the existing hidden `customer_id` input already wired into the POST body.
- No blockers.

---
*Phase: 04-sales-customers*
*Completed: 2026-07-09*

## Self-Check: PASSED

All created/modified files verified present on disk (`app/services/sales.py`, `app/routes/sales.py`, `app/templates/pages/sale_form.html`, `app/templates/partials/sale_form.html`, `app/templates/partials/sale_row.html`, `app/templates/partials/sale_lookup.html`, `app/templates/partials/recent_sales.html`, this summary). All 4 task/plan commits (`f7c9ab5`, `861f9e5`, `d23bec3`, `f6e80a5`) verified present in git log.
