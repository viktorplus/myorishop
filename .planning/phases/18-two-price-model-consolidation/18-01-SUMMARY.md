---
phase: 18-two-price-model-consolidation
plan: 01
subsystem: database
tags: [sqlalchemy, pricing, tdd]

# Dependency graph
requires: []
provides:
  - "Unfiltered latest_price_for_code (D-22 fix-in-place — no longer gates on consumer_cents)"
  - "reference_prices_for_code(session, code) -> (ДЦ, ПЦ) tuple contract (D-05/D-07/D-08)"
affects: [18-05, 18-07, 18-08]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "reference_prices_for_code wraps latest_price_for_code and returns (consultant_cents, consumer_cents) or (None, None) — the honest ДЦ/ПЦ reference contract the cue-wiring plans (18-07, 18-08) consume"

key-files:
  created: []
  modified:
    - app/services/pricing.py
    - tests/test_pricing_feature.py

key-decisions:
  - "D-22 fix-in-place: dropped CatalogPrice.consumer_cents.is_not(None) from latest_price_for_code's .where() clause instead of introducing a parallel unfiltered function — verified blast radius is 1 code, strictly additive"

patterns-established:
  - "reference_prices_for_code(session, code) -> tuple[int | None, int | None]: thin service wrapper returning (ДЦ, ПЦ) independently, with (None, None) as a first-class unknown-code result"

requirements-completed: [PROD-06]

# Metrics
duration: ~5min
completed: 2026-07-16
---

# Phase 18 Plan 01: ДЦ/ПЦ Reference Lookup Fix Summary

**Dropped the `consumer_cents` filter from `latest_price_for_code` in place and added `reference_prices_for_code` returning an honest `(ДЦ, ПЦ)` tuple, closing 3 pre-existing autofill starvation bugs at zero extra query cost.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-07-16T08:57:00Z (approx.)
- **Completed:** 2026-07-16T09:01:28Z
- **Tasks:** 2 (TDD RED + GREEN)
- **Files modified:** 2

## Accomplishments
- `latest_price_for_code` no longer filters on `CatalogPrice.consumer_cents.is_not(None)` — the 3 live starved callers (`app/routes/products.py:147,244`, `app/services/receipts.py:289`) now receive a row for consultant-only (ДЦ-without-ПЦ) codes instead of `None`, a strictly additive autofill improvement (D-22).
- New `reference_prices_for_code(session, code) -> tuple[int | None, int | None]` gives the colour-cue plans (18-07, 18-08) a reference source that never gates ДЦ on ПЦ's presence (D-05 pairing, D-07 unknown-code first-class result, D-08 starvation fix).
- Rewrote the module docstring and `latest_price_for_code`'s docstring to state the true D-09 shape (one row per code = that code's last catalog appearance, not a multi-catalog history) and drop the now-false "always has consumer_cents set" claim — closes the deferred `pricing.py:3-5` docstring item.
- All decision IDs (D-05/D-07/D-08/D-09/D-22) cited in code comments per the 18-PATTERNS.md decision-ID convention.

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Reference-lookup tests for the ДЦ-without-ПЦ and unknown-code paths** - `3ee3eab` (test)
2. **Task 2 (GREEN): Drop the consumer filter in place + add reference_prices_for_code + rewrite docstrings** - `19b5fac` (feat)

_TDD plan: RED confirmed ImportError on `reference_prices_for_code` before implementation; GREEN made all 19 tests in `test_pricing_feature.py` pass. No REFACTOR commit needed — docstring rewrites were part of the GREEN task per plan instructions._

## Files Created/Modified
- `app/services/pricing.py` - Dropped the `consumer_cents.is_not(None)` filter from `latest_price_for_code`; added `reference_prices_for_code`; rewrote module + function docstrings (D-09, D-08/D-22)
- `tests/test_pricing_feature.py` - Added consultant-only "300" row to the `priced` fixture; added 4 new tests (unfiltered `latest_price_for_code` + 3 `reference_prices_for_code` tests); updated `test_prices_for_catalog_maps_by_code`'s code-set assertion to include "300"

## Decisions Made
- D-22 fix-in-place confirmed as planned: removing the `.where()` clause directly (not adding a parallel function) kept the change to exactly one line plus the new wrapper, per the plan's verified-blast-radius analysis.

## Deviations from Plan

None - plan executed exactly as written. The `test_prices_for_catalog_maps_by_code` set-assertion update was a direct, expected consequence of adding "300" to the shared `priced` fixture (same catalog issue 2026/1) — not independent scope.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `reference_prices_for_code` is available for plans 18-07/18-08 (price-cue.js wiring) to consume the `(ДЦ, ПЦ)` tuple directly.
- The autofill fix (D-22) is live for the 3 previously-starved callers without any further wiring needed — `app/routes/products.py` and `app/services/receipts.py` automatically benefit since they call the now-unfiltered `latest_price_for_code`.
- No PRICE-01 test (`tests/test_sales.py`, `tests/test_mobile_sales.py` — 69 tests) was modified; both suites pass unmodified, confirming no collateral impact on the below-minimum-price guardrail.

---
*Phase: 18-two-price-model-consolidation*
*Completed: 2026-07-16*

## Self-Check: PASSED

All claimed files (`app/services/pricing.py`, `tests/test_pricing_feature.py`, this SUMMARY.md) and both task commits (`3ee3eab`, `19b5fac`) verified present.
