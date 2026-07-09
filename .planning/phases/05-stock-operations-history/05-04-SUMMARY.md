---
phase: 05-stock-operations-history
plan: 04
subsystem: inventory
tags: [fastapi, htmx, jinja2, sqlalchemy, sqlite, ru-labels]

# Dependency graph
requires:
  - phase: 05-stock-operations-history (05-01)
    provides: OPERATION_TYPE_LABELS constant, tests/test_corrections.py RED contract (count_vs_delta, zero_net_noop, ledger_equals_cache, ops_replaced)
  - phase: 05-stock-operations-history (05-03)
    provides: analog write-service/route/template shape (register_return/routes/return_form.html) reused for the correction slice
provides:
  - app/services/corrections.py - register_correction() (count/delta modes, D-09/D-10, single write path via record_operation) + lookup_prefill() (name + current cached quantity)
  - app/routes/corrections.py - GET /corrections, GET /corrections/lookup, POST /corrections
  - app/templates/pages/correction_form.html + partials/correction_form.html (mode-toggle form, current-qty hint) + partials/correction_lookup.html (name fill + oob current-qty hint)
  - app.include_router(corrections.router) wired in app/main.py
  - Retired app/routes/ops.py (walking-skeleton POST /ops) — /corrections is now the SINGLE correction path (D-12)
  - OPS-03 fully functional: operator can correct stock in counted or delta mode, always via a `correction` op, never a direct products.quantity edit
affects: [05-05-history, 06-reports]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-mode form posting a single `value` field name: both the counted and delta inputs share name=\"value\"; the client-side radio toggle (hx-on::change) disables the inactive input so only the active mode's value is submitted — no server-side disambiguation needed beyond the `mode` field itself"
    - "Route-level context passes `mode`/`current_qty` as TOP-LEVEL template variables (not nested under `form`) — distinct from receipts/writeoffs' flat `form` dict, needed because the mode toggle and current-qty hint are cross-cutting UI state, not raw form-field echoes"

key-files:
  created:
    - app/services/corrections.py
    - app/routes/corrections.py
    - app/templates/pages/correction_form.html
    - app/templates/partials/correction_form.html
    - app/templates/partials/correction_lookup.html
  modified:
    - app/main.py
    - app/templates/pages/home.html
    - tests/test_smoke.py
  deleted:
    - app/routes/ops.py

key-decisions:
  - "Zero-net rejection applies uniformly to the qty_delta==0 case AFTER parsing in BOTH modes (including a delta entry of \"-0\", which parses to 0) — matches D-10's plain-language rule (\"a zero net delta\") rather than special-casing \"-0\" as a separate parse error"
  - "home.html's retired /ops form was replaced with two plain links (/corrections, /history) per D-17 — /history does not exist yet (lands in Wave 5/05-05), so that link is a placeholder that resolves once 05-05 ships; this mirrors the phase's own intra-phase sequencing (Wave 4 before Wave 5)"
  - "tests/test_smoke.py's two POST /ops assertions were removed (not just left to fail) — they directly contradicted tests/test_corrections.py::test_web_ops_replaced (one asserted 200, the other now must assert 404/405 per D-12); the walking-skeleton smoke coverage they provided is superseded by test_corrections.py"

requirements-completed: [OPS-03]

# Metrics
duration: 13min
completed: 2026-07-10
---

# Phase 5 Plan 4: Stock Correction Slice Summary

**Two-mode stock correction (OPS-03): `register_correction()` writes exactly one `correction` op via `record_operation` — counted mode computes `qty_delta = counted − current cached quantity`, delta mode writes the signed value as-is, a zero net delta is rejected with zero writes — `/corrections` routes + a mode-toggle form template, and the walking-skeleton `POST /ops` is deleted so `/corrections` is the single correction path (D-12).**

## Performance

- **Duration:** 13 min
- **Started:** 2026-07-10T01:14:48+02:00 (approx., prior plan's doc commit)
- **Completed:** 2026-07-10T01:24:08+02:00
- **Tasks:** 3
- **Files modified:** 8 (5 created, 3 modified, 1 deleted)

## Accomplishments

- `app/services/corrections.py`: `register_correction(session, *, code, mode, value_raw, note)` — server-side allow-list on `mode` (T-05-12), active-only product lookup, unsigned-int parse for counted mode (`qty_delta = counted − product.quantity`, using the cached projection per RESEARCH A4, never `compute_stock`), signed-int parse for delta mode (explicit single-leading-`-` handling, T-05-13), D-10 zero-net-delta rejection with ZERO writes, and a single write through `record_operation(type_="correction", payload={"note", "mode"})` wrapped in `try/except (IntegrityError, ValueError)`. `lookup_prefill(session, code)` returns name + current cached quantity for the counted-mode hint (active product), name-only for a dictionary-only match, `None` for unknown.
- `app/routes/corrections.py`: `GET /corrections` (fresh form, `mode="count"` default, `current_qty=None`), `GET /corrections/lookup` (204-or-fragment pattern, server decides fill vs 204, never overwrites a typed name), `POST /corrections` (try/except → `logger.exception` + RU 422; validation errors → 422 preserving `mode`/entered value; success → 200 fresh form reset to `mode="count"`, success line, focus back to «Код»). Registered in `app/main.py`.
- Templates: `pages/correction_form.html` (page shell), `partials/correction_form.html` (mode-toggle radios defaulting to «Пересчёт (фактический остаток)» per D-11, both quantity inputs share `name="value"` with the inactive one disabled via `hx-on::change` so only the active mode posts, a `#current-qty-hint` element beside the counted input, no price fields anywhere), `partials/correction_lookup.html` (fills Название + oob-swaps `#current-qty-hint`). All three parse under the shared Jinja environment; no `|safe` used.
- **Retired the walking skeleton (D-12):** deleted `app/routes/ops.py`; removed `ops` from `app/main.py`'s import and router-registration blocks; replaced `home.html`'s `<form hx-post="/ops">` with plain links to `/corrections` and `/history` (D-17). `tests/test_smoke.py`'s two `POST /ops` assertions were removed — they directly contradicted the new `test_web_ops_replaced` contract (which now requires `/ops` to 404/405). `grep -rn "/ops" app/` returns nothing outside one docstring comment in `corrections.py` documenting the retirement.
- `tests/test_corrections.py` is now fully GREEN (4/4: `test_count_vs_delta`, `test_zero_net_noop`, `test_ledger_equals_cache`, `test_web_ops_replaced`). Full suite (excluding the still-RED Wave-5 `test_history.py`) is green: 159 passed.

## Task Commits

Each task was committed atomically:

1. **Task 1: corrections service — register_correction (count/delta, zero-net reject) + lookup_prefill** - `1259d26` (feat)
2. **Task 2: correction templates — form page/partial (mode toggle + current-qty) + lookup** - `fc74603` (feat)
3. **Task 3: /corrections routes + main.py wiring; RETIRE POST /ops and update home; web tests GREEN** - `8972b93` (feat)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified

- `app/services/corrections.py` - `register_correction()`, `lookup_prefill()`
- `app/routes/corrections.py` - `GET /corrections`, `GET /corrections/lookup`, `POST /corrections`
- `app/templates/pages/correction_form.html` - page shell (h1 + form include)
- `app/templates/partials/correction_form.html` - mode-toggle form (whole-form swap on every POST response)
- `app/templates/partials/correction_lookup.html` - name fill + oob current-qty hint fragment
- `app/main.py` - removed `ops` import/router, added `corrections` import/router
- `app/templates/pages/home.html` - retired `/ops` correction form, replaced with links to `/corrections` and `/history`
- `tests/test_smoke.py` - removed the two `POST /ops` assertions superseded by `test_corrections.py::test_web_ops_replaced`
- `app/routes/ops.py` - DELETED (walking-skeleton correction path)

## Decisions Made

- Counted-mode and delta-mode quantity inputs both post under `name="value"`; the client-side radio toggle disables whichever input is inactive, so exactly one value reaches the server regardless of which mode is selected — no need for two separate field names or server-side "which one wins" logic.
- Route context passes `mode` and `current_qty` as top-level template variables (distinct from the `form` dict used for raw field echoes elsewhere) since they represent cross-cutting UI state (which block is visible/enabled) rather than a value typed into a specific input.
- `home.html`'s replacement links include `/history`, which does not exist until Wave 5 (05-05) — this is intentional per the plan's own D-17 instruction and the phase's Wave-4-before-Wave-5 sequencing; it resolves automatically once 05-05 ships.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed the two `tests/test_smoke.py` `POST /ops` assertions**

- **Found during:** Task 3 (retiring `app/routes/ops.py`)
- **Issue:** `tests/test_smoke.py::test_post_ops_records_correction` and `test_post_ops_unknown_product_returns_404` asserted `POST /ops` returns `200`/`404` respectively — the walking-skeleton happy path from Phase 1. Once `app/routes/ops.py` is deleted per D-12, `POST /ops` returns `404` unconditionally, breaking `test_post_ops_records_correction`'s `200` assertion. Leaving both tests in place would either fail the suite or force keeping the retired route around — directly contradicting `tests/test_corrections.py::test_web_ops_replaced`, which requires `POST /ops` to be gone (404/405).
- **Fix:** Removed both `POST /ops` tests from `tests/test_smoke.py`, keeping `test_home_page_renders` (unrelated to `/ops`) and updating the module docstring to note the walking-skeleton correction round-trip was retired in this plan, with `test_corrections.py::test_web_ops_replaced` now the authoritative contract for `/ops`'s removal.
- **Files modified:** `tests/test_smoke.py`
- **Commit:** `8972b93` (Task 3 commit)

This is explicitly anticipated by the plan's own verification section ("home/ledger tests updated for the /ops removal if any referenced it") — not scope creep, but the plan's directed migration duty.

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug/contradiction from planned route retirement)
**Impact on plan:** Necessary to keep the full suite green after the plan's own explicitly-directed `/ops` retirement (D-12). No scope creep — no other test files were touched.

## Issues Encountered

None beyond the deviation documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `/corrections` is reachable and functional end to end (GET page, GET lookup, POST create in both modes); `tests/test_corrections.py` is fully GREEN (4/4).
- Full suite green (159 passed) except the one intentionally-RED Wave-0 file (`tests/test_history.py`) — exactly as designed; it turns GREEN in Wave 5 (05-05).
- `app/routes/ops.py` is gone; `grep -rn "/ops" app/` returns nothing outside a comment; the walking skeleton has no remaining functional footprint.
- `home.html`'s new `/history` link is a forward reference that will resolve once 05-05 lands `/history` — not a blocker for this plan, and no blocker for 05-05 (this plan did not touch `app/services/operations.py`, `app/routes/history.py`, or `partials/ledger_rows.html`'s eventual OPS-04 extension).

---
*Phase: 05-stock-operations-history*
*Completed: 2026-07-10*

## Self-Check: PASSED

All created files (`app/services/corrections.py`, `app/routes/corrections.py`, `app/templates/pages/correction_form.html`, `app/templates/partials/correction_form.html`, `app/templates/partials/correction_lookup.html`, this SUMMARY.md) verified present on disk; `app/routes/ops.py` confirmed deleted; all task commits (`1259d26`, `fc74603`, `8972b93`, `022e7aa`) verified present in git log.
