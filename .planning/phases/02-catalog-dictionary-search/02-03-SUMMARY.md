---
phase: 02-catalog-dictionary-search
plan: 03
subsystem: catalog
tags: [fastapi, sqlalchemy, sqlite, jinja2, htmx]

# Dependency graph
requires:
  - phase: 02-catalog-dictionary-search
    provides: "Plan 02-01: name_lc shadow column + ix_products_name_lc, create_product maintaining name_lc, #product-rows swap target; Plan 02-02: «Действия» column in product_rows, literal-before-parameterized route ordering"
provides:
  - search_products (ranked case() exact-code > code-prefix > name-substring, LIKE-escaped, LIMIT 20, deleted excluded)
  - split_match segment helper + search_view context builder shared by list page and search partial
  - GET /products/search returning ONLY partials/product_rows.html (HTMX partial rule)
  - active-search input on /products (debounce 300ms, hx-sync this:replace, Enter trigger, autofocus)
  - <mark> highlight via autoescaped pre/match/post segments + accent-tinted mark CSS rule
  - CAT-03 executable contract (tests/test_search.py, 11 tests)
affects: [02-04 dictionary, phase-3 receipt product picker, phase-4 sale product picker]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ranked search: sqlalchemy case() rank in ORDER BY + name_lc tie-break + LIMIT 20, portable ORM only"
    - "Cyrillic-safe matching: query lowered in Python vs name_lc shadow column; func.lower only on ASCII code column"
    - "segment highlighting: service returns (pre, match, post) tuples, template wraps match in literal <mark> — autoescape stays on"
    - "shared view context: one search_view feeds both the full page and the HTMX partial, keeping rendering uniform"

key-files:
  created:
    - tests/test_search.py
  modified:
    - app/services/catalog.py
    - app/routes/products.py
    - app/templates/pages/products_list.html
    - app/templates/partials/product_rows.html
    - app/static/style.css

key-decisions:
  - "Empty-search message gated by {% elif q and q.strip() %} so a whitespace-only query with an empty catalog still shows «Товаров пока нет», not a quoted blank query"
  - "GET /products now renders through search_view(session, '') — list_products kept in the service (still used by 02-01/02-02 tests) but no longer wired to the page"

patterns-established:
  - "search_view row dicts {product, code_seg, name_seg} — reusable shape for Phase 3/4 product pickers"

requirements-completed: [CAT-03]

# Metrics
duration: 6min
completed: 2026-07-08
---

# Phase 2 Plan 03: Instant Search Summary

**Ranked instant search on /products: Cyrillic case-insensitive matching via the Python-lowered name_lc shadow column, exact-code > code-prefix > name-substring ordering, LIKE-wildcard-safe, capped at 20 rows, with debounced HTMX partial updates and autoescaped `<mark>` highlighting**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-07-08T15:07:26Z
- **Completed:** 2026-07-08T15:12:30Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- CAT-03 delivered end-to-end: typing «губная» (any case) instantly finds «Губная Помада» — proven by Cyrillic-fixture tests, never by ASCII stand-ins (Pitfall 1)
- D-26 ranking proven by test: query "1234" orders exact code "1234" > prefix "12345" > name «Набор 1234»; 21 matching products return exactly 20 rows
- LIKE injection closed (T-2-02): `%` and `_` in the query match only literal occurrences — `.contains(autoescape=True)` for name substring, `_escape_like` + `escape="\\"` for the manual code-prefix LIKE
- XSS-safe highlighting (T-2-03): split_match returns (pre, match, post) segments rendered autoescaped around a literal template `<mark>`; the `no |safe` gate holds across all templates
- One search_view context feeds both GET /products (q="") and GET /products/search — uniform rendering, empty query shows first 20 active products by name, zero results show «Ничего не найдено по запросу „{q}“…», deleted products excluded (D-20)
- Active-search input per RESEARCH Pattern 1: all five htmx attributes (hx-get, hx-trigger with delay:300ms + Enter, hx-target #product-rows, hx-swap outerHTML, hx-sync this:replace); «Действия»/«Изменить» column from Plan 02-02 preserved

## Task Commits

Each task was committed atomically:

1. **Task 1: Failing tests — Cyrillic search, ranking, cap, LIKE escape, partial response (RED)** - `23c4519` (test)
2. **Task 2: Implement ranked Cyrillic-safe search + HTMX active-search UI (GREEN)** - `c122b5e` (feat)

## Files Created/Modified

- `tests/test_search.py` - 11-test CAT-03 contract: Cyrillic case fold, ranking, 21→20 cap, %/_ literals, empty/whitespace query, deleted exclusion, split_match segments, search_view shape, 3 web e2e (partial with `<mark>`, no-results copy, active-search attributes)
- `app/services/catalog.py` - `_escape_like`, `search_products` (case() rank + LIMIT 20), `split_match`, `search_view`
- `app/routes/products.py` - GET /products now uses search_view(session, ""); new GET /products/search returns the rows partial only, declared before parameterized routes
- `app/templates/pages/products_list.html` - active-search input (autofocus, debounce 300ms, hx-sync replace, placeholder «Код или название товара…»)
- `app/templates/partials/product_rows.html` - rows rendered from search_view dicts with segment `<mark>` highlighting; two empty states (no products vs no matches); «Действия» column preserved
- `app/static/style.css` - single new rule: `mark { background: #e8effd; color: inherit; }`

## Decisions Made

- No-results message condition is `{% elif q and q.strip() %}` — a whitespace-only query on an empty catalog falls through to «Товаров пока нет» instead of quoting a blank query (matches Pitfall 6 semantics: whitespace q behaves as empty)
- `list_products` retained in the catalog service (Plan 02-01/02-02 tests import it) even though the list page now renders via `search_view` — smallest safe change, no test churn

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Added an 11th test for the search_view contract**
- **Found during:** Task 1
- **Issue:** The plan's must_haves list `search_view` as a provided artifact, but the 10 enumerated tests never asserted its context shape (q + rows with code_seg/name_seg), leaving the artifact contract untested
- **Fix:** Added `test_search_view_segments`-style test (`test_search_view_shape`) asserting the row-dict shape and segment values
- **Files modified:** tests/test_search.py
- **Commit:** 23c4519

No other deviations — plan executed as written.

## Issues Encountered

None — RED failed on import as designed, GREEN passed the full suite on the first run, ruff clean throughout.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 02-04 (dictionary autofill) is the last Phase 2 plan; #name-wrap contract untouched by this plan
- Phase 3/4 product pickers can reuse `search_products`/`search_view` verbatim (artifact table in PLAN)
- Full suite 57 passed, ruff clean; all grep gates green (no ilike / func.lower on name, no `| safe`, routes write-free, LIMIT 20 in the search path)
- Human check deferred to end-of-phase per workflow.human_verify_mode: browser feel of the 300ms debounce on /products (listed in 02-VALIDATION.md Manual-Only)

## Known Stubs

None — no placeholder values or unwired components introduced.

## Threat Flags

None — the only new surface (GET /products/search with free-text q) is already in the plan's threat model with mitigations implemented (T-2-01 ORM-only, T-2-02 autoescape + LIMIT 20, T-2-03 autoescaped segments).

## Self-Check: PASSED

All 7 files verified on disk; both task commits (23c4519, c122b5e) verified in git log.

---
*Phase: 02-catalog-dictionary-search*
*Completed: 2026-07-08*
