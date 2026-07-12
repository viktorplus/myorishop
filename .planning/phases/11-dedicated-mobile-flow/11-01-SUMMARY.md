---
phase: 11-dedicated-mobile-flow
plan: 01
subsystem: ui
tags: [jinja2, htmx, fastapi, mobile, css]

# Dependency graph
requires: []
provides:
  - "app/templates/mobile_base.html — standalone mobile base layout (no desktop nav), with back/step_indicator/content Jinja blocks"
  - "Viewport-width auto-redirect script in app/templates/base.html, scoped to pathname === \"/\""
  - "Mobile CSS classes appended to app/static/style.css (.mobile-shell, .mobile-back, .mobile-step-indicator, .mobile-tile-grid, .mobile-tile, .mobile-card/.selected, .mobile-actions)"
  - "app/templates/mobile_partials/batch_card_picker.html — shared D-07 batch-selection card fragment"
  - "mobile_client_factory fixture in tests/conftest.py — isolated TestClient factory for any future mobile router"
affects: [11-02, 11-03, 11-04, 11-05, 11-06, 11-07, 11-08, 11-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Standalone mobile base template (no {% extends %} from base.html) carrying its own copy of the viewport meta + htmx-config meta + vendored htmx script tags"
    - "Client-side matchMedia(max-width:599px) redirect scoped strictly to pathname === \"/\", not every desktop route"
    - "Scalar batch_input_name default (\"batch_id\") for mobile wizards, vs. desktop's array-shaped batch_id[]"
    - "mobile_client_factory: factory fixture returning a TestClient bound to a fresh bare FastAPI() instance (not app.main.app), letting each later plan test its own router in isolation without touching app/main.py or tests/conftest.py again"

key-files:
  created:
    - app/templates/mobile_base.html
    - app/templates/mobile_partials/batch_card_picker.html
    - tests/test_mobile_foundation.py
  modified:
    - app/templates/base.html
    - app/static/style.css
    - tests/conftest.py

key-decisions:
  - "Redirect script scoped to window.location.pathname === \"/\" only (Pitfall 2 / Assumption A1 from RESEARCH.md) — keeps /products, /categories, /warehouses, /customers, /dictionary, /backup, /export, and non-expiry reports reachable from phone-width browsers, since none have a mobile equivalent this phase"
  - "mobile_base.html duplicates the viewport/htmx-config meta tags and vendored htmx script verbatim from base.html rather than extending it, per D-03 (no desktop nav) and Pitfall 3/4 (422 swap config and viewport scaling must not be silently dropped)"

requirements-completed: [UI-01]

# Metrics
duration: 18min
completed: 2026-07-12
---

# Phase 11 Plan 01: Mobile Foundation Summary

Standalone mobile base layout, viewport-width auto-redirect into /m/, additive mobile CSS classes, a shared D-07 batch-selection card partial, and an isolated `mobile_client_factory` test fixture — the shared foundation every later Phase 11 plan (02-09) builds on.

## Performance

- **Duration:** 18 min
- **Started:** 2026-07-12T20:XX:XXZ
- **Completed:** 2026-07-12
- **Tasks:** 2 completed
- **Files modified:** 6 (3 created, 3 modified)

## Accomplishments
- `mobile_base.html` created as a standalone layout (no `{% extends %}`, no desktop `<nav>`), with `back`/`step_indicator`/`content` overridable blocks
- One new inline `<script>` in `base.html`'s `<head>` redirects phone-width (`<600px`) visitors landing on `/` into `/m/`, strictly scoped to `pathname === "/"` so no other desktop route is affected
- Mobile CSS classes appended additively to `style.css` (`.mobile-shell`, `.mobile-tile-grid`, `.mobile-tile`, `.mobile-card`/`.selected`, `.mobile-actions`, `.mobile-back`, `.mobile-step-indicator`) — no new colors/spacing values beyond the documented 44px touch-target exception
- `batch_card_picker.html` renders one full-width tappable card per open batch with all four LOT-02 fields visible (price, expiry, remaining qty, location/comment), a single-batch auto-select note, and an empty state that blocks forward wizard progress (consumer's responsibility to check `show_empty`)
- `mobile_client_factory` fixture added to `tests/conftest.py`, letting every later Phase 11 plan spin up an isolated `TestClient` for its own new router without touching `app/main.py` or `tests/conftest.py` again
- 5 new tests in `tests/test_mobile_foundation.py` cover the factory round-trip and the card partial's rendering/selection/empty-state/auto-note behavior

## Task Commits

Each task was committed atomically:

1. **Task 1: Mobile base layout + viewport-width auto-redirect + mobile CSS classes** - `2d7bff8` (feat)
2. **Task 2: Shared batch-selection card partial + isolated mobile test-client fixture** - `a91a0e6` (feat)

_Note: no TDD tasks this plan._

## Files Created/Modified
- `app/templates/mobile_base.html` - new standalone mobile base layout with back/step_indicator/content blocks
- `app/templates/base.html` - added the D-02 viewport-width redirect script to `<head>`, scoped to `/` only
- `app/static/style.css` - appended the mobile CSS class block (additive only)
- `app/templates/mobile_partials/batch_card_picker.html` - new shared D-07 batch-selection card fragment
- `tests/conftest.py` - added `mobile_client_factory` fixture
- `tests/test_mobile_foundation.py` - new test file covering both foundation pieces (5 tests)

## Decisions Made
- Redirect scope locked to `pathname === "/"` per RESEARCH.md Pitfall 2/Assumption A1 — the safer reading that keeps desktop-only pages reachable.
- `batch_target` default `"#batch-wrap"` (overridable via the `{% set batch_target = batch_target | default("#batch-wrap") %}` line) so each Phase 11 consumer can point the OOB/htmx swap target at its own wrapper id, matching the desktop partial's per-row-id targeting convention but scalar-shaped for mobile's one-batch-per-screen design.

## Deviations from Plan

None - plan executed exactly as written. One self-caught issue during Task 1: the first draft of `mobile_base.html`'s explanatory comment contained the literal substring `{% extends` inside prose text (describing why the file doesn't extend `base.html`), which would have failed the plan's own acceptance-criteria grep check for that substring. Reworded the comment before committing — no functional change, caught before the commit, not logged as a formal deviation since it never reached a committed state.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
`mobile_base.html`, `batch_card_picker.html`, the mobile CSS classes, the `base.html` redirect, and `mobile_client_factory` are all in place and covered by passing tests (`uv run pytest tests/test_smoke.py tests/test_mobile_foundation.py -x -q` and the full 363-test suite both green). Wave 2 plans (mobile home, search, and each operation wizard) can build directly on this foundation without further foundation work.

---
*Phase: 11-dedicated-mobile-flow*
*Completed: 2026-07-12*
