---
phase: 01-foundation-ledger-core
plan: 03
subsystem: services-ui
tags: [fastapi, htmx, jinja2, sqlalchemy, ledger, run-bat]

# Dependency graph
requires:
  - phase: 01-01
    provides: RED test contract (test_ledger/test_smoke), vendored htmx, pinned deps
  - phase: 01-02
    provides: app.config/app.core/app.db/app.models, migration 0001, demo product
provides:
  - app.services.ledger — single write path (record_operation) + compute/rebuild/view helpers
  - GET / page (ledger table + correction form) and POST /ops HTMX partial endpoint
  - app.main FastAPI app with /static mount
  - run.bat v1 deployment story (migrate + serve loopback + open browser)
  - full Wave-0 suite GREEN, ruff clean
affects: [phase-02, phase-03, phase-04]

# Tech tracking
tech-stack:
  added: [tzdata 2026.2]
  patterns:
    - thin routes / fat services (routes never touch session.add or quantity)
    - shared Jinja2Templates in app/routes/__init__.py with local_dt and cents filters
    - HTMX outerHTML partial swap on div#ledger with hx-disabled-elt double-submit guard

key-files:
  created:
    - app/services/__init__.py
    - app/services/ledger.py
    - app/routes/__init__.py
    - app/routes/home.py
    - app/routes/ops.py
    - app/main.py
    - app/templates/base.html
    - app/templates/pages/home.html
    - app/templates/partials/ledger_rows.html
    - app/static/style.css
    - run.bat
    - README.md
  modified:
    - pyproject.toml
    - uv.lock
    - tests/conftest.py
    - tests/test_ledger.py

key-decisions:
  - "tzdata added as runtime dep — Windows has no system IANA tz database, ZoneInfo needs it"
  - "ruff B008 handled via lint.flake8-bugbear.extend-immutable-calls for fastapi.Depends/Form (documented ruff approach, not noqa)"
  - "record_operation raises ValueError on unknown product_id (defensive guard beyond plan spec)"

patterns-established:
  - "All stock mutations go through record_operation; grep gate keeps routes write-free"
  - "HTMX endpoints return partials only; pages include the same partial template"

requirements-completed: [FND-01, FND-02, FND-03]

# Metrics
duration: 7min
completed: 2026-07-08
---

# Phase 01 Plan 03: Ledger Service, HTMX UI & Launcher Summary

**Walking skeleton complete: record_operation as the sole ledger write path, HTMX-driven GET / + POST /ops UI showing who/when and recomputed stock, and run.bat migrate-serve-open launcher — full suite GREEN, ruff clean**

## Performance

- **Duration:** 7 min
- **Started:** 2026-07-08T13:01:15Z
- **Completed:** 2026-07-08T13:07:40Z
- **Tasks:** 3
- **Files modified:** 16

## Accomplishments

- `app/services/ledger.py`: `next_seq` (same-transaction MAX+1, UNIQUE(device_id, seq) backstop), `record_operation` (validates type against OPERATION_TYPES, stamps id/device_id/seq/created_at/created_by, updates cached quantity in the same transaction), `compute_stock` (COALESCE(SUM(qty_delta),0)), `rebuild_stock` (repairs all products incl. soft-deleted), `ledger_view` (first active product + latest 50 ops + recomputed qty)
- HTMX UI slice: `GET /` renders Russian-language page with correction form; `POST /ops` records a correction and returns only `partials/ledger_rows.html`, which HTMX swaps into `div#ledger` (`hx-swap="outerHTML"`, `hx-disabled-elt` double-submit guard); partial shows cached stock, ledger-recomputed stock, and Тип/Кол-во/Кто/Когда table
- `run.bat`: cd to script dir, delayed browser open (2 s), `alembic upgrade head`, uvicorn on 127.0.0.1:8000 single worker — pure ASCII, no `--reload`, no `0.0.0.0`
- Full suite GREEN (10 passed: test_pragmas + test_ledger + test_smoke) and `ruff check .` clean
- Grep gates verified: no `session.add(`/quantity mutation outside services/ledger.py; no `| safe`, no CDN/http(s) asset URLs in templates; base.html has `lang="ru"` + `<meta charset="utf-8">`

## Task Commits

Each task was committed atomically:

1. **Task 1: Ledger service — single write path** - `34a7a17` (feat)
2. **Task 2: HTMX UI slice — routes, templates, static** - `b909b1f` (feat)
3. **Task 3: run.bat launcher + README** - `3e5c752` (chore)

## Files Created/Modified

- `app/services/ledger.py` - single write path + stock recompute + ledger_view read helper
- `app/routes/__init__.py` - shared Jinja2Templates with `local_dt` and `cents` filters
- `app/routes/home.py` - `GET /` page endpoint (plain def, thin)
- `app/routes/ops.py` - `POST /ops` form endpoint (typed Form fields, returns partial)
- `app/main.py` - FastAPI app, /static mount, router includes
- `app/templates/base.html` - ru layout, vendored htmx script, utf-8
- `app/templates/pages/home.html` - correction form + included ledger partial; "Нет товаров" fallback
- `app/templates/partials/ledger_rows.html` - div#ledger: stock summary + operations table
- `app/static/style.css` - minimal system-font styling, no framework
- `run.bat` - migrate + serve loopback + delayed browser open
- `README.md` - setup/run/test/lint (English)
- `pyproject.toml` / `uv.lock` - tzdata dep + ruff extend-immutable-calls
- `tests/conftest.py` / `tests/test_ledger.py` - ruff I001 auto-fix (import block ordering; same symbols)

## Decisions Made

- **tzdata as runtime dependency:** `ZoneInfo("Europe/Moscow")` raised `ZoneInfoNotFoundError`-adjacent `ModuleNotFoundError: tzdata` on Windows (no system IANA database). `tzdata` is the CPython-documented first-party fallback package — added via `uv add tzdata`, install verified (2026.2).
- **B008 via extend-immutable-calls, not noqa:** FastAPI's DI requires `Depends(...)`/`Form(...)` in argument defaults; ruff's documented FastAPI accommodation is `lint.flake8-bugbear.extend-immutable-calls`. Scoped to exactly `fastapi.Depends` and `fastapi.Form`.
- **Unknown product guard:** `record_operation` raises `ValueError` if `session.get(Product, product_id)` returns None — prevents an opaque `AttributeError` on the projection update (defensive addition beyond the plan text).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added tzdata dependency for zoneinfo on Windows**

- **Found during:** Task 2 (test_smoke POST /ops — `local_dt` filter)
- **Issue:** `ModuleNotFoundError: No module named 'tzdata'` from `zoneinfo` — Windows ships no system tz database, so `iso_to_local` could never work at runtime either
- **Fix:** `uv add tzdata` (legitimate first-party PyPI package, install succeeded cleanly at 2026.2)
- **Files modified:** pyproject.toml, uv.lock
- **Verification:** full suite green afterwards
- **Commit:** b909b1f

**2. [Rule 3 - Blocking] Ruff B008 on FastAPI Depends/Form defaults**

- **Found during:** Task 2 lint check
- **Issue:** B008 flags function calls in argument defaults; FastAPI's DI pattern requires them
- **Fix:** `[tool.ruff.lint.flake8-bugbear] extend-immutable-calls = ["fastapi.Depends", "fastapi.Form"]` (ruff-documented approach; justification per plan's "do not suppress without cause")
- **Files modified:** pyproject.toml
- **Commit:** b909b1f

**3. [Rule 3 - Blocking] Ruff I001 import-order findings in existing test files**

- **Found during:** Task 2 lint check
- **Issue:** `tests/conftest.py` and `tests/test_ledger.py` import blocks flagged un-sorted (first-party `app.*` imports now separated from third-party); previously reported clean in 01-01
- **Fix:** `ruff check --fix` — same symbols, same modules, only block ordering changed; contract semantics untouched; suite re-verified green
- **Files modified:** tests/conftest.py, tests/test_ledger.py
- **Commit:** b909b1f

**4. [Rule 2 - Missing Critical] Unknown-product guard in record_operation**

- **Found during:** Task 1
- **Issue:** A bad `product_id` would produce `AttributeError: 'NoneType' object has no attribute 'quantity'` after the operation row was already staged
- **Fix:** Explicit `ValueError(f"unknown product: ...")` before mutating the projection
- **Files modified:** app/services/ledger.py
- **Commit:** 34a7a17

---

**Total deviations:** 4 auto-fixed (3 blocking, 1 missing critical). No scope creep, no architectural changes.

## Issues Encountered

- `StarletteDeprecationWarning` ("install httpx2") emitted from FastAPI testclient internals during pytest — third-party, out of scope; logged to `deferred-items.md`.

## Known Stubs

None. Every template renders live data from `ledger_view`; no placeholders, no hardcoded empty values.

## Threat Flags

None — all surfaces introduced (POST /ops form input, loopback bind, template rendering) are already registered in the plan's threat model as T-1-01/T-1-02/T-1-04 and their mitigations are implemented (typed Form → 422, `--host 127.0.0.1` hard-coded, autoescape on with zero `| safe`).

## User Setup Required

None for development. **End-of-phase human check pending** (human_verify_mode=end-of-phase): offline double-click of `run.bat` at E:\dev\myorishop — browser opens http://127.0.0.1:8000, shows "MyOriShop — склад" with "Демо-товар"; entering 3 and clicking "Записать корректировку" appends a row without reload; restart preserves data. See Task 3 human-check in 01-03-PLAN.md.

## Next Phase Readiness

- Phase 1 walking skeleton is complete end-to-end in-process; all ROADMAP Phase 1 success criteria are automated-verified except the offline run.bat launch (human check above)
- `record_operation` is ready to serve receipt/sale/writeoff/return in Phases 2-4 (types already in OPERATION_TYPES; price fields accepted)
- `ledger_view` is intentionally single-product (walking skeleton); Phase 2 catalog replaces it with real product listing

---

*Phase: 01-foundation-ledger-core*
*Completed: 2026-07-08*

## Self-Check: PASSED

All 10 key created files exist on disk; commits 34a7a17, b909b1f, 3e5c752 verified in git log; `uv run pytest -q` 10 passed; `uv run ruff check .` clean.
