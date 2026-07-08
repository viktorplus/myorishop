---
phase: 01-foundation-ledger-core
plan: 01
subsystem: infra
tags: [uv, python-3.13, fastapi, sqlalchemy, alembic, pytest, ruff, htmx, sqlite]

# Dependency graph
requires: []
provides:
  - uv-managed Python 3.13.13 project with hash-pinned runtime + dev deps (uv.lock)
  - vendored htmx 2.0.10 at app/static/htmx.min.js (offline, no CDN)
  - RED Wave-0 test suite encoding FND-01/02/03 as executable contract
  - fixed interface contract for Plans 01-02/01-03 (app.db, app.models, app.core, app.config, app.services.ledger, app.main)
affects: [01-02, 01-03, foundation-ledger-core]

# Tech tracking
tech-stack:
  added:
    [
      fastapi 0.139.0,
      uvicorn 0.51.0,
      sqlalchemy 2.0.51,
      alembic 1.18.5,
      jinja2 3.1.6,
      python-multipart 0.0.32,
      pydantic-settings 2.14.2,
      pytest 9.1.1,
      httpx 0.28.1,
      ruff 0.15.20,
      htmx 2.0.10 (vendored),
    ]
  patterns:
    - tests-first RED contract (walking skeleton)
    - file-based tmp_path SQLite test fixtures (never in-memory)
    - lazy app.main import in client fixture for wave-partial collectability

key-files:
  created:
    - pyproject.toml
    - uv.lock
    - .python-version
    - .gitignore
    - .env.example
    - app/__init__.py
    - app/static/htmx.min.js
    - tests/conftest.py
    - tests/test_pragmas.py
    - tests/test_ledger.py
    - tests/test_smoke.py
  modified: []

key-decisions:
  - "Python 3.13.13 installed via uv — NO 3.12 fallback was needed (internet available)"
  - "pytest pythonpath=['.'] added so the app package resolves once Plans 01-02/01-03 implement it"
  - "Ruff isort reordered the contracted ledger import to alphabetical symbol order (same symbols, same module)"

patterns-established:
  - "RED contract: full pytest run must fail until Plans 01-02/01-03 land; do not fix"
  - "Test DBs on tmp_path files with PRAGMA listener + APPEND_ONLY_TRIGGERS applied in fixture"
  - "app.main imported lazily inside client fixture only"

requirements-completed: [FND-01, FND-02, FND-03]

# Metrics
duration: 8min
completed: 2026-07-08
---

# Phase 01 Plan 01: Scaffold & RED Test Suite Summary

**uv project on Python 3.13.13 with hash-pinned FastAPI/SQLAlchemy/Alembic stack, vendored htmx 2.0.10, and a 4-file RED pytest suite locking the FND-01/02/03 ledger contract for Plans 01-02/01-03**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-08T12:37:01Z
- **Completed:** 2026-07-08T12:44:42Z
- **Tasks:** 2
- **Files modified:** 12

## Accomplishments

- Python 3.13.13 installed via uv (preferred runtime — the 3.12.13 fallback documented in the plan was NOT needed); `requires-python = ">=3.13"` and `.python-version` pinned to 3.13
- All runtime deps resolve and import at pinned versions: fastapi 0.139.0, uvicorn 0.51.0, sqlalchemy 2.0.51, alembic 1.18.5, jinja2 3.1.6, python-multipart 0.0.32, pydantic-settings 2.14.2; dev deps pytest 9.1.1, httpx 0.28.1, ruff 0.15.20; uv.lock hash-pins everything (T-1-SC mitigation)
- htmx 2.0.10 vendored at app/static/htmx.min.js (51,238 bytes, version string verified, fetched from unpkg at the pinned version) — no CDN reference anywhere
- Wave-0 test suite written and verified RED: `uv run pytest -q` exits 4 with `ModuleNotFoundError: No module named 'app.core'` — the exact contracted failure mode (app.db / app.core / app.models / app.config / app.services.ledger / app.main arrive in Plans 01-02 and 01-03)
- Ruff clean (`uv run ruff check .` passes); all four test files compile via py_compile

## Task Commits

Each task was committed atomically:

1. **Task 1: Scaffold uv project, pin dependencies, vendor htmx 2.0.10** - `157ae69` (chore)
2. **Task 2: Write the FAILING Wave-0 test suite** - `aabfe33` (test)

## Files Created/Modified

- `pyproject.toml` - project metadata, pinned deps, `[tool.pytest.ini_options]` (testpaths + pythonpath), `[tool.ruff]` (line-length 100, py313, E/F/I/UP/B)
- `uv.lock` - hash-pinned dependency lock (supply-chain mitigation T-1-SC)
- `.python-version` - pinned to 3.13
- `.gitignore` - .venv/, caches, data/, *.db*, .env (T-1-05: .env never committed)
- `.env.example` - DB_PATH, OPERATOR_NAME, DEVICE_ID, DISPLAY_TZ with English comments
- `app/__init__.py` - empty package marker
- `app/static/htmx.min.js` - vendored htmx 2.0.10
- `tests/conftest.py` - engine (tmp_path file DB + triggers), session, product (seeded "Тестовый товар"), client (lazy app.main import + get_session override) fixtures
- `tests/test_pragmas.py` - WAL / foreign_keys / busy_timeout asserted on a live pooled connection (D-14)
- `tests/test_ledger.py` - FND-01 (append + projection, UPDATE/DELETE rejected, rebuild_stock), FND-02 (UUID4/cents/UTC conventions incl. metadata-wide Numeric/Float guard), FND-03 (created_by/created_at audit, seq per device), UNIQUE(device_id, seq)
- `tests/test_smoke.py` - e2e happy path: GET / (htmx script + product name) and POST /ops (operator name + updated stock)

## Decisions Made

- **Python 3.13, not the fallback:** `uv python install 3.13` succeeded (internet available), so the plan's documented 3.12.13 fallback was not used. `target-version = "py313"` in ruff.
- **Ruff isort ordering:** the contracted import line in tests/test_ledger.py carries the same four symbols from `app.services.ledger`, but in ruff-sorted order (`compute_stock, next_seq, rebuild_stock, record_operation`). Semantically identical contract; keeps `ruff check` green with the `I` rule enabled.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added `pythonpath = ["."]` to pytest config**

- **Found during:** Task 2 (RED verification)
- **Issue:** Without it, pytest failed with `No module named 'app'` (project root not on sys.path) — the suite could NEVER turn GREEN in Plans 01-02/01-03 even after implementation, since `uv init --bare` installs no package
- **Fix:** Added `pythonpath = ["."]` under `[tool.pytest.ini_options]`; failure mode became the contracted `No module named 'app.core'`
- **Files modified:** pyproject.toml
- **Verification:** `uv run pytest -q` now fails exactly on the missing contract modules
- **Committed in:** aabfe33 (Task 2 commit)

**2. [Rule 1 - Bug] Removed literal ":memory:" string from conftest docstring**

- **Found during:** Task 2 (acceptance-criteria check)
- **Issue:** Acceptance criterion requires conftest.py NOT to contain ":memory:"; the docstring warning mentioned the literal string, which would trip a grep-based verifier
- **Fix:** Reworded docstring to "never an in-memory one"
- **Files modified:** tests/conftest.py
- **Verification:** `grep -c ":memory:" tests/conftest.py` returns 0
- **Committed in:** aabfe33 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 bug)
**Impact on plan:** Both fixes required for the RED contract to be implementable/verifiable. No scope creep.

## Issues Encountered

- `uv init --bare` does not create `.python-version`; added it explicitly via `uv python pin 3.13` (file is listed in the plan's files_modified).

## Known Stubs

None in the traditional sense — the four test files intentionally import not-yet-existing modules (`app.db`, `app.core`, `app.models`, `app.config`, `app.services.ledger`, `app.main`). This is the plan's contracted RED state, resolved by Plans 01-02 and 01-03.

## User Setup Required

None - no external service configuration required. Runtime is fully offline from here; internet was only needed once for installs and the htmx download.

## Next Phase Readiness

- Interface contract locked for Plan 01-02 (`app.db.build_engine` / `APPEND_ONLY_TRIGGERS`, `app.models`, `app.core`, `app.config.settings`) and Plan 01-03 (`app.services.ledger.*`, `app.main`, `GET /`, `POST /ops`)
- Full suite MUST remain RED until those plans land — do not "fix" the import failures
- No blockers

---

*Phase: 01-foundation-ledger-core*
*Completed: 2026-07-08*

## Self-Check: PASSED

All 12 claimed files exist on disk; commits 157ae69 and aabfe33 verified in git log.
