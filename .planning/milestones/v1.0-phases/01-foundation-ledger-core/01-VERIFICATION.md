---
phase: 01-foundation-ledger-core
verified: 2026-07-08T14:05:00Z
status: human_needed
score: 12/12 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Offline run.bat launch + browser correction flow + restart persistence (deferred human-check from 01-03-PLAN.md Task 3, human_verify_mode=end-of-phase). 1) Disable Wi-Fi/network. 2) Double-click run.bat at E:\\dev\\myorishop. 3) Browser opens http://127.0.0.1:8000 within ~3 s (or refresh once). 4) Enter 3 in 'Изменение количества (±)' and click 'Записать корректировку'. 5) Ctrl+C the console, run run.bat again."
    expected: "Page shows 'MyOriShop — склад' with product 'Демо-товар' and the operations table; after submit a new row appears WITHOUT page reload showing type 'correction', qty 3, operator name, local timestamp; 'Остаток (кэш)' and 'Пересчёт по журналу' both show 3; after restart the row and stock survive."
    why_human: "Real-browser behavior (window opening via start command, HTMX swap without full-page reload, offline network state, cross-restart persistence of the real data/myorishop.db) cannot be reproduced in-process; TestClient evidence covers serving and rendering but not the OS-level launch story."
---

# Phase 1: Foundation & Ledger Core Verification Report

**Phase Goal (ROADMAP):** The app runs locally in the browser on a data foundation where every stock change is an immutable ledger entry and no schema decision blocks future sync
**Phase User Story (MVP mode, carried verbatim in all 3 plans):** As a shop operator, I want to start MyOriShop locally with run.bat and record a stock change in the browser as an immutable ledger entry, so that stock counts stay provably correct and no schema decision blocks future sync.
**Verified:** 2026-07-08T14:05:00Z
**Status:** human_needed (all 12 automated must-haves verified; 1 deferred human check remains)
**Re-verification:** No — initial verification
**Verified against:** post-review-fix state (commits 550fa92..a6c44bd all present in git log; suite 23 passed, ruff clean)

## MVP Mode Notes

Phase mode is `mvp`. The ROADMAP Goal line fails `user-story.validate` (outcome prose, not canonical story format) — this was flagged by the planner in all three PLAN files, which carry an assembled User Story that DOES validate (`role: shop operator / capability: start MyOriShop locally with run.bat and record a stock change in the browser as an immutable ledger entry / outcome: stock counts stay provably correct and no schema decision blocks future sync`). Verification was performed against that validated story plus all 4 ROADMAP Success Criteria (the roadmap contract was NOT reduced). Informational: run `/gsd mvp-phase 1` if the ROADMAP goal line should be canonicalized.

## User Flow Coverage (MVP)

| Step | Expected | Evidence in codebase | Status |
| ---- | -------- | -------------------- | ------ |
| Start MyOriShop locally with run.bat | Migrations applied, server on loopback, browser opens | run.bat: `cd /d "%~dp0"` → `uv run alembic upgrade head` with errorlevel abort (WR-05) → delayed `start http://127.0.0.1:8000` → `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000`; no `--reload`, no `0.0.0.0` | ✓ structure verified; launch behavior → HUMAN |
| Open in browser | Page renders product + ledger | Live TestClient probe against real app + real data/myorishop.db: GET / → 200, contains `/static/htmx.min.js`, "MyOriShop", "Демо-товар", "Пересчёт по журналу"; GET /static/htmx.min.js → 200, 51,238 bytes | ✓ VERIFIED |
| Record a stock change as immutable ledger entry | POST /ops appends row, swaps partial, DB rejects mutation | ops.py → `record_operation(session, type_="correction", ...)`; home.html form `hx-post="/ops" hx-target="#ledger" hx-swap="outerHTML"`; test_smoke green; raw-sqlite3 probe on DB copy: UPDATE and DELETE on operations both abort with "operations ledger is append-only" | ✓ VERIFIED |
| Outcome: stock provably correct | Cached vs ledger-recomputed stock both visible; cache repairable | ledger_rows.html renders `product.quantity` AND `computed_qty`; `compute_stock` = COALESCE(SUM(qty_delta)); `rebuild_stock` repairs tampered cache (test green) | ✓ VERIFIED |
| Outcome: no schema decision blocks sync | Sync-ready columns and migration tooling | operations carries `device_id`, `seq` (UNIQUE per device), `synced_at` cursor; UUID4 TEXT PKs everywhere; `render_as_batch=True` x2 in alembic/env.py; naming convention on MetaData | ✓ VERIFIED |

## Goal Achievement

### Observable Truths (merged: 4 ROADMAP Success Criteria + plan must_haves, deduplicated)

| #  | Truth | Status | Evidence |
| -- | ----- | ------ | -------- |
| 1  | SC-1: Operator can start with run.bat, open in browser at localhost, no internet | ✓ VERIFIED (automated portion) | run.bat line-by-line correct (loopback, migrate-first with abort, browser open, single worker); htmx vendored — zero `http(s)://` in any template; app serves / and /static/htmx.min.js in-process against the real DB. OS-level launch → human item |
| 2  | SC-2: Every stock change is an append-only ledger row; stock recomputable from ledger alone | ✓ VERIFIED | Triggers `operations_no_update`/`operations_no_delete` live in data/myorishop.db sqlite_master; raw sqlite3 UPDATE/DELETE probe on a DB copy rejected with "operations ledger is append-only"; `compute_stock`/`rebuild_stock` implemented; test_ledger green (part of 23 passed) |
| 3  | SC-3: Every operation shows who performed it and when | ✓ VERIFIED | `created_by` VARCHAR(100) NOT NULL + `created_at` VARCHAR(32) NOT NULL in real DB; stamped from `settings.operator_name`/`utcnow_iso()` in record_operation; rendered as Кто/Когда columns via `local_dt` filter; test_audit + test_smoke assertions green |
| 4  | SC-4: DB inspection confirms integer cents, UTC timestamps, UUID identifiers | ✓ VERIFIED | Direct pragma_table_info inspection: `unit_cost_cents`/`unit_price_cents` INTEGER, PKs VARCHAR(36), timestamps VARCHAR(32); seed row `created_at='2026-07-08T12:52:59+00:00'` (UTC offset); product id parses as uuid version 4; metadata-wide Numeric/Float guard test green |
| 5  | htmx 2.0.10 vendored, no CDN reference anywhere | ✓ VERIFIED | app/static/htmx.min.js exists (51,238 bytes, contains "htmx"); base.html loads `/static/htmx.min.js`; grep templates for `http://`/`https://` → 0 matches |
| 6  | uv project imports fastapi/sqlalchemy/alembic/jinja2 under Python 3.13 | ✓ VERIFIED | Full suite executed under `uv run` importing entire stack; .python-version present; 3.13 per 01-01-SUMMARY (no fallback used) |
| 7  | products + operations exist via Alembic migration 0001 with locked conventions | ✓ VERIFIED | data/myorishop.db tables: products, operations, alembic_version; migration 0001 hand-written with named constraints (pk_/fk_/uq_/ix_), matches models |
| 8  | Every pooled connection has WAL / foreign_keys=1 / busy_timeout=5000 | ✓ VERIFIED | build_engine connect-listener with autocommit save/restore dance; test_pragmas green on a live pooled connection |
| 9  | Demo product exists in data/myorishop.db | ✓ VERIFIED | Row `('00000000-0000-4000-8000-000000000001', 'DEMO-001', 'Демо-товар', 0, ...)` present |
| 10 | Operator sees demo product with cached AND recomputed stock plus who/when table on / | ✓ VERIFIED | TestClient GET / (real DB) renders "Демо-товар" and "Пересчёт по журналу"; partial shows both figures + Тип/Кол-во/Кто/Когда table |
| 11 | record_operation is the ONLY write path; seq same-transaction; audit stamped from settings | ✓ VERIFIED | grep: `session.add(` outside services/ledger.py → 0 in app/; `quantity` in app/routes/ → 0; next_seq called only inside record_operation; IN-02 atomic SQL-side increment; UNIQUE(device_id, seq) backstop in real DB |
| 12 | Full pytest suite GREEN and ruff clean | ✓ VERIFIED | `uv run pytest -q` → 23 passed, exit 0 (run once by verifier); `uv run ruff check .` → "All checks passed!", exit 0 |

**Score:** 12/12 truths verified (automated); SC-1's OS-level launch behavior routed to human verification.

Note on Plan 01-01 truth "Full pytest run exits non-zero (RED)": this was a wave-state contract for Wave 0 only, explicitly superseded by Plan 01-03's truth "Full pytest suite is GREEN". Evidence of the RED state at the time is in 01-01-SUMMARY; the final-state truth (GREEN) is what the phase goal requires and is verified. Not counted as a gap.

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| pyproject.toml | pinned deps + pytest/ruff config | ✓ VERIFIED | tool query passed; contains [tool.pytest.ini_options] |
| app/static/htmx.min.js | vendored htmx 2.0.10 | ✓ VERIFIED | 51,238 bytes; served at /static/htmx.min.js (200) |
| tests/conftest.py | tmp-path engine/session/product/client fixtures | ✓ VERIFIED | build_engine + APPEND_ONLY_TRIGGERS imported; file-based tmp_path DB; lazy app.main import; no ":memory:" |
| tests/test_ledger.py, test_pragmas.py, test_smoke.py | FND-01/02/03 + e2e contract | ✓ VERIFIED | All green within the 23-test run |
| app/config.py | pydantic-settings Settings + singleton | ✓ VERIFIED | tool query passed (contains BaseSettings) |
| app/core.py | new_id/utcnow_iso/to_cents/format_cents/iso_to_local | ✓ VERIFIED | Imported by models/services; review fixes WR-02/WR-03 applied (half-up rounding, non-finite rejection) |
| app/db.py | build_engine + PRAGMA listener + APPEND_ONLY_TRIGGERS + get_session | ✓ VERIFIED | Read in full; substantive; module engine from settings.db_path |
| app/models.py | Base + naming convention, Product, Operation, OPERATION_TYPES | ✓ VERIFIED | 2.0-style, UNIQUE(device_id, seq), IN-05 default=new_id on Operation.id |
| alembic/versions/0001_initial_schema.py | tables + triggers + demo seed | ✓ VERIFIED | Hand-written, frozen trigger DDL (WR-06), applied to data/myorishop.db |
| app/services/ledger.py | single write path + recompute + view | ✓ VERIFIED | Read in full; WR-01 pre-staging validation, IN-02 atomic increment |
| app/routes/home.py, ops.py, __init__.py | thin routes + shared templates | ✓ VERIFIED | ops.py delegates to record_operation, WR-04 404 on unknown product |
| app/main.py | FastAPI app + /static mount + routers | ✓ VERIFIED | Wired and live (TestClient probe) |
| app/templates/base.html, pages/home.html, partials/ledger_rows.html | ru layout + form + ledger partial | ✓ VERIFIED | lang="ru", charset utf-8, hx-post form, div#ledger with both stock figures |
| run.bat | migrate + serve loopback + open browser | ✓ VERIFIED | ASCII, WR-05 abort-on-migration-failure, no --reload / 0.0.0.0 |
| README.md, app/static/style.css, .env.example, .python-version | supporting files | ✓ VERIFIED | All exist on disk |

### Key Link Verification

`gsd-tools query verify.key-links` reported 6 of 9 links unverified — all six are tool false negatives (double-escaped regex patterns treated literally). Each was re-verified manually by grep:

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| tests/conftest.py | app/db.py | from app.db import | ✓ WIRED | conftest.py:13 `from app.db import APPEND_ONLY_TRIGGERS, build_engine` |
| tests/test_ledger.py | app/services/ledger.py | from app.services.ledger import | ✓ WIRED | test_ledger.py:19 (ruff-sorted symbol order, same four symbols) |
| alembic/env.py | app/models.py | target_metadata + render_as_batch | ✓ WIRED | render_as_batch=True x2 confirmed |
| alembic/versions/0001 | app/db.py | APPEND_ONLY_TRIGGERS | ✓ WIRED (intentional deviation) | WR-06 review fix (commit 70c5f4e) replaced the import with a FROZEN in-file copy `_APPEND_ONLY_TRIGGERS` — migrations must never import mutable app code. DDL byte-identical to app.db source; deviation documented in migration docstring and REVIEW. Achieves the link's intent (triggers installed by migration) more robustly |
| app/db.py | app/config.py | settings.db_path | ✓ WIRED | db.py:56 `engine = build_engine(settings.db_path)` |
| app/routes/ops.py | app/services/ledger.py | record_operation( | ✓ WIRED | ops.py:26 |
| pages/home.html | /ops | hx-post targeting #ledger | ✓ WIRED | home.html:6 |
| base.html | app/static/htmx.min.js | script tag | ✓ WIRED | base.html:8; file served 200 |
| run.bat | app.main:app | alembic upgrade head + uvicorn | ✓ WIRED | run.bat:3,10 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| pages/home.html + partials/ledger_rows.html | product, operations, computed_qty | ledger_view(session) → SELECT on products/operations + SUM(qty_delta) | Yes — TestClient GET / against real DB rendered "Демо-товар" and recompute label | ✓ FLOWING |
| POST /ops response partial | same context re-read after write | record_operation INSERT + atomic UPDATE, then ledger_view re-query | Yes — test_smoke asserts operator name + updated stock in response; session.expire_all() confirms persisted quantity | ✓ FLOWING |
| product.quantity projection | cached column | SQL-side `quantity = quantity + ?` in record_operation (IN-02) | Yes — test asserts cache == compute_stock after ops; rebuild_stock repairs tampering | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full suite green | `uv run pytest -q` (run once) | 23 passed, exit 0 | ✓ PASS |
| Lint clean | `uv run ruff check .` | "All checks passed!", exit 0 | ✓ PASS |
| App serves / with real data | TestClient(app).get("/") | 200; htmx script, title, Демо-товар, recompute label all present | ✓ PASS |
| Static htmx served | TestClient(app).get("/static/htmx.min.js") | 200, 51,238 bytes | ✓ PASS |
| DB append-only at raw driver level | sqlite3 UPDATE/DELETE probe on throwaway DB copy | Both rejected: "operations ledger is append-only" | ✓ PASS |
| DB conventions | pragma_table_info + uuid.UUID parse | INTEGER _cents, VARCHAR(36) PKs, UTC ISO text, uuid v4 | ✓ PASS |
| Offline browser launch via run.bat | — | Not automatable in-process | ? SKIP → human |

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes exist or are declared in any PLAN/SUMMARY for this phase — SKIPPED (not a probe-declaring phase). DB-level immutability was probed directly by the verifier (see spot-checks).

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
| ----------- | ------------ | ----------- | ------ | -------- |
| FND-01 | 01-01, 01-02, 01-03 | Append-only operations ledger; stock derived from it | ✓ SATISFIED | DB triggers reject UPDATE/DELETE (live probe); compute_stock/rebuild_stock; single write path grep-verified; test_ledger green |
| FND-02 | 01-01, 01-02, 01-03 | Integer minor units, UTC timestamps, UUID identifiers | ✓ SATISFIED | Direct DB inspection (INTEGER _cents, VARCHAR(36) PKs, UTC ISO text); metadata-wide Numeric/Float guard test green |
| FND-03 | 01-01, 01-02, 01-03 | Every operation records who and when | ✓ SATISFIED | created_by/created_at NOT NULL, stamped from settings in record_operation, rendered Кто/Когда in UI; audit test green |

No orphaned requirements: REQUIREMENTS.md maps exactly FND-01/02/03 to Phase 1 (marked Complete) and all three are claimed by every plan.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| — | — | none | — | Zero TBD/FIXME/XXX/TODO/HACK/placeholder markers in app/, tests/, run.bat, alembic/versions/; zero `\| safe`; zero CDN URLs; zero write-path leaks outside services/ledger.py |

Info (non-blocking): StarletteDeprecationWarning ("install httpx2") from FastAPI testclient internals during pytest — third-party, already logged in deferred-items.md.

### Human Verification Required

#### 1. Offline run.bat launch, browser correction flow, restart persistence

**Test:** (deferred human-check from 01-03-PLAN.md Task 3, human_verify_mode=end-of-phase) 1) Disable Wi-Fi/network. 2) Double-click run.bat at E:\dev\myorishop. 3) Browser opens http://127.0.0.1:8000 within ~3 s (or refresh once). 4) Enter 3 in "Изменение количества (±)", click "Записать корректировку". 5) Ctrl+C the console, run run.bat again.
**Expected:** Page shows "MyOriShop — склад" with "Демо-товар" and the operations table; new row appears WITHOUT page reload (type "correction", qty 3, operator name, local timestamp); "Остаток (кэш)" and "Пересчёт по журналу" both show 3; after restart the row and stock survive.
**Why human:** OS-level browser launch, real-browser HTMX no-reload swap, offline network state, and cross-restart persistence of the real DB cannot be verified in-process. Everything automatable about this flow (run.bat structure, serving, rendering, DB persistence semantics) already passed.

### Gaps Summary

No gaps. All 12 merged must-have truths are verified against the current (post-review-fix) codebase: the append-only ledger is enforced at the database level and was probed with a raw sqlite3 connection; the data conventions (integer cents, UTC ISO text, UUID4 TEXT keys) are confirmed by direct DB inspection; the walking-skeleton UI renders live ledger data through the single write path; the full suite is green (23 passed) and ruff is clean. The only remaining item is the real-world offline run.bat launch flow, which is inherently human-only — hence status `human_needed` rather than `passed`.

Informational notes for the orchestrator:
1. MVP-mode goal format: the ROADMAP Phase 1 Goal line is outcome prose and fails user-story.validate; all plans carry a validating assembled story that was used for User Flow Coverage. Consider `/gsd mvp-phase 1` to canonicalize.
2. WR-06 intentional deviation: migration 0001 no longer imports APPEND_ONLY_TRIGGERS from app.db (frozen in-file copy instead). Documented, byte-identical DDL, improves migration replay immutability — treated as WIRED, not a gap.

---

_Verified: 2026-07-08T14:05:00Z_
_Verifier: Claude (gsd-verifier)_
