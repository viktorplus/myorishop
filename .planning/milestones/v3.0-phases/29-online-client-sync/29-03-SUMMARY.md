---
phase: 29-online-client-sync
plan: 03
subsystem: sync-client
tags: [sync, httpx, sqlalchemy, tdd, offline-first, merge]

# Dependency graph
requires:
  - phase: 29-online-client-sync
    plan: 01
    provides: SyncState model, synced_at partial indexes, sync_server_url/sync_token config, httpx runtime dep
  - phase: 29-online-client-sync
    plan: 02
    provides: SyncResult, record_sync_result, read_autosync_config, unsynced_count, format_sync_message
  - phase: 28-central-server-sync
    provides: POST /api/sync/push + GET /api/sync/pull (token-auth, composite cursor), merge engine
provides:
  - run_sync_once(session, *, client) — the ONE push+pull network driver (offline-safe SyncResult)
  - _collect_push_records — unsynced ledger + D-13 transitive FK-parent closure in FK order
  - _apply_pull_page — D-14 client server-wins reference upsert (insert-new + update-existing except id/quantity)
  - _pull_all — composite-cursor pagination echoing BOTH X-Sync-Next headers
  - run_sync_tick — lock + fresh Session + client + record-result-in-finally (the Plan-05 loop calls this)
  - build_sync_client — httpx.Client with strict SYNC_TIMEOUT; _run_lock (D-09 single-run guard)
  - sync_driver_pair test fixture — sync httpx.Client over a portal-bridged ASGITransport + minted server-side token
affects: [29-04 manual sync button, 29-05 auto-sync loop]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Injectable httpx.Client is the test seam: ASGITransport(real app) for integration, MockTransport for offline/5xx"
    - "Sync httpx.Client drives the async ASGITransport via an anyio blocking portal (D-04 sync-Session rule preserved)"
    - "Separate empty server DB in the integration fixture so a push genuinely crosses the client→server boundary (D-13 really exercised)"
    - "Stamp synced_at ONLY after raise_for_status (Pitfall 3); merge idempotency makes a re-push harmless"

key-files:
  created: []
  modified:
    - app/services/sync_client.py
    - tests/test_sync_client.py
    - tests/conftest.py

key-decisions:
  - "The push+pull driver was written cohesively in one GREEN commit (mirrors Plan 02): the push half, D-13 closure, error mapping, and the pull half share one function body and imports, so splitting them would leave dead imports; Task-2 tests land as a test commit against the already-present pull code"
  - "The D-14 update path uses a Core update() with the server's values explicitly set, so SQLAlchemy's updated_at onupdate does NOT override the server's timestamp (server truly wins on master data)"
  - "quantity and id are excluded from the D-14 update SET; recompute_derived rebuilds Product/Batch quantity from the LOCAL ledger so a stale server cache never clobbers local stock (Pitfall 2)"
  - "The integration fixture uses a SEPARATE server database (not the shared session) so the D-13 FK closure is genuinely tested — an empty server would FK-fail without the reference parents"

patterns-established:
  - "_SyncASGITransport: a sync httpx.BaseTransport that runs httpx.ASGITransport via a blocking portal and buffers the response — the reusable in-process seam for a SYNC driver"

requirements-completed: [SYNC-01, SYNC-06, SRV-03]

# Metrics
duration: ~40min (plus ~5min full-suite gate)
completed: 2026-07-20
---

# Phase 29 Plan 03: Online Client Sync Network Driver Summary

**The network heart of client sync: one injectable `run_sync_once` driver that pushes unsynced ledger rows plus their D-13 FK-parent closure, stamps `synced_at` only after the server's 2xx, then pulls server-authoritative reference data down with the D-14 client server-wins upsert — offline-safe (never raises), single-run-locked (D-09), and reused by both the manual button and the background `run_sync_tick`.**

## Performance

- **Duration:** ~40 min (implementation) + ~5 min full-suite gate
- **Completed:** 2026-07-20
- **Tasks:** 2 (both `tdd="true"`)
- **Files:** 3 modified (1 service, 1 test module, 1 conftest fixture)

## Accomplishments
- `run_sync_once(session, *, client)` — the ONE driver: (1) collect unsynced `Operation`/`CashMovement` + the D-13 reference closure; (2) `merge.serialize_exchange` → NDJSON; (3) POST `/api/sync/push` with the `Authorization: Bearer` header only; (4) stamp `synced_at` ONLY after `raise_for_status()`; (5) paginate `/api/sync/pull` applying the D-14 upsert. Offline-safe status mapping: `not_configured` (blank URL/token), `offline` (transport error), `error` (non-2xx push), `partial` (push landed, pull failed), `ok`. It NEVER re-raises an `httpx` error (SYNC-06).
- `_collect_push_records` — the D-13 transitive FK closure: the `product`/`batch`/`sale` parents of unsynced operations, the `sale` parents of unsynced cash movements, each sale's `customer`, and each batch's `product` + `warehouse` — emitted in `merge._REFERENCE_INSERT_ORDER` then the two ledger kinds. Over-inclusion is safe (the server upsert is idempotent/server-wins). Users are NOT a sync kind, so `author_id` is carried verbatim but no `user` record is emitted.
- `_apply_pull_page` — the D-14 client reference upsert, the one genuinely new algorithm: split each page's records into new-by-UUID (insert via the quantity-zeroing `merge._reference_row`) and existing-by-UUID (UPDATE every column EXCEPT `id` and the cached `quantity`, server wins on master data). Then `recompute_derived` rebuilds stock from the LOCAL ledger. This is the OPPOSITE of `merge._upsert_reference` (which discards existing rows).
- `_pull_all` — the composite-cursor loop: echoes BOTH `X-Sync-Next-Since` and `X-Sync-Next-After-Id` back (a lone `since` loops forever across identical timestamps); each page applied in ONE owned transaction (mirrors the push route) so a poisoned page rolls back (T-29-05).
- `run_sync_tick()` — acquires `_run_lock` non-blocking (D-09), opens a FRESH `SessionLocal()`, and when auto-sync is enabled (read fresh, D-15) builds a client, runs one sync, and records the D-10 result in a `finally`; swallows an offline tick (D-08) — the Plan-05 loop calls this.
- `build_sync_client()` with the strict `SYNC_TIMEOUT = httpx.Timeout(connect=3, read=10, write=10, pool=3)` (D-05/A1); `_run_lock` module-level `threading.Lock` (D-09).
- `sync_driver_pair` test fixture — a SYNC `httpx.Client` over a portal-bridged `httpx.ASGITransport` against the in-process app, backed by a SEPARATE empty server DB with a server-side minted device token, so a push genuinely crosses the client→server boundary and the D-13 FK closure is really exercised.

## Task Commits

TDD (RED → GREEN) commits, atomic per gate:

1. **Task 1 RED — failing driver tests + ASGITransport fixture** - `e7540c6` (test)
2. **Driver GREEN — push D-13 closure + pull D-14 upsert + tick + lock** - `53802ba` (feat)
3. **Task 2 tests — pull D-14, offline/partial mapping, run_sync_tick** - `f749344` (test)

## Files Created/Modified
- `app/services/sync_client.py` (modified) — added `_run_lock`, `SYNC_TIMEOUT`, `build_sync_client`, `_load_by_ids`, `_collect_push_records`, `run_sync_once`, `_apply_pull_page`, `_pull_all`, `run_sync_tick`; new imports (`httpx`, `insert`/`update`, `settings`, `utcnow_iso`, `SessionLocal`, the reference models, `merge`, `recompute_derived`, `current_schema_version`/`DEFAULT_PULL_LIMIT`).
- `tests/test_sync_client.py` (modified) — 14 new tests: push-marks-synced, D-13 closure, idempotent noop, stamp-after-200, single-run lock, not_configured, pull D-14 update, new-row insert, local-quantity-not-clobbered, offline, partial, local-work-unaffected, tick toggle, offline-tick-swallowed; plus a rate-limit-bucket autouse reset.
- `tests/conftest.py` (modified) — `sync_driver_pair` fixture (`_SyncASGITransport` portal bridge + separate server DB + server-side token mint).

## Decisions Made
- **Cohesive driver write:** the whole push+pull driver landed in one GREEN `feat` commit because the push half, D-13 closure, error mapping, and the pull half share one function body and import set — splitting push/pull across two GREEN commits would leave dead imports (`insert`, `recompute_derived`, `DEFAULT_PULL_LIMIT`) in the first. Task-2 tests are therefore a `test(...)` commit against the already-present, already-green pull code (the exact Plan-02 precedent). Both `test` and `feat` gate commits exist for the plan.
- **D-14 preserves the server's `updated_at`:** the update path uses a Core `update()` with the server's values set explicitly, so SQLAlchemy's `onupdate=utcnow_iso` does NOT fire (it only fills columns absent from the SET) — the client's row reflects the server's timestamp, which is what "server wins" means for the cursor.
- **Local stock is never taken from the wire:** `id` and `quantity` are excluded from the D-14 update SET and `recompute_derived` rebuilds quantity from the LOCAL ledger, so a stale/bogus server cache cannot corrupt local stock (Pitfall 2).
- **Separate server DB in the integration fixture:** the driver's local session and the server's session are DIFFERENT sessions on DIFFERENT databases, so a push actually transmits rows and D-13 is genuinely under test (a shared DB would make "present on server" trivially true and never FK-fail).

## Deviations from Plan
None — plan executed as written. The only judgment call (writing push+pull in one GREEN rather than two) is documented under Decisions Made; it changes commit shape, not behavior or scope. The plan explicitly allowed a "direct lock probe" for the Task-1 lock test, which is what `test_single_run_lock_refuses_overlap` uses (via `run_sync_tick`).

## Threat Model Compliance
- **T-29-04 (Information Disclosure):** the Bearer `sync_token` travels ONLY in the `Authorization` header (push and pull), never a query string, never logged. Read from `.env` (Plan 01).
- **T-29-05 (Tampering):** `merge.parse_exchange` validates every pulled page before any DB touch; each page is applied in one owned `session.begin()` transaction that rolls back on error.
- **T-29-06 (Integrity):** `synced_at` is stamped ONLY after `resp.raise_for_status()` — a failed push leaves rows unsynced (asserted by `test_push_failure_does_not_stamp`), and merge idempotency makes a re-push harmless.
- **T-29-10 (DoS/availability):** strict `SYNC_TIMEOUT`; every `httpx.HTTPError` is caught → `SyncResult`, never raised (`test_offline_returns_offline_not_raise`).
- **T-29-11 (plain-HTTP):** operational — `sync_server_url` must be `https://…` for internet deployment (Caddy TLS, Phase 28); not a code change here.
- **T-29-12 (concurrency):** the module-level `_run_lock` is acquired non-blocking in `run_sync_tick` (`test_single_run_lock_refuses_overlap`); the Plan-04 handler shares it.

## Threat Flags
None — this plan adds a client-side outbound driver only; it introduces NO new server endpoint, auth path, or schema surface (it consumes the Phase-28 `/api/sync/` endpoints unchanged).

## Known Stubs
None — `run_sync_once` and `run_sync_tick` are fully wired against the real in-process server and merge engine; `pulled`/`pushed` counts are live.

## Issues Encountered
- A SYNC `httpx.Client` cannot use `httpx.ASGITransport` directly (it only implements `handle_async_request`). Resolved with `_SyncASGITransport`, a small sync transport that runs the async transport via an `anyio` blocking portal and buffers the response — the same in-process seam starlette's TestClient uses, but reusable for the driver's own sync client.
- The full suite (~5 min) surfaced the same 3 pre-existing `SAWarning`s in `test_receipts.py`/`test_returns.py` (identity-key conflicts on deliberate error-path flushes) — out of scope, unchanged, logged here only (already noted in Plan 02).

## User Setup Required
None — the driver stays a no-op (`not_configured`) until the operator sets `sync_server_url` + `sync_token` in `.env`; a fresh install runs fully offline (SRV-03).

## Next Phase Readiness
- Plan 04 (manual sync button) can wrap `run_sync_once` in `_run_lock.acquire(blocking=False)` + `build_sync_client()` and render the result via `format_sync_message`.
- Plan 05 (auto-sync loop) calls `run_sync_tick()` from a lifespan `asyncio` loop that reads the toggle/interval fresh per tick.
- Full suite: **1100 passed, 12 skipped, 0 failing** after this plan (was 1086; +14 new tests).

## Self-Check: PASSED

- FOUND: app/services/sync_client.py, tests/test_sync_client.py, tests/conftest.py
- FOUND commits: e7540c6, 53802ba, f749344
- `uv run pytest tests/test_sync_client.py -x -q`: 21 passed
- `uv run ruff check` on all three files: All checks passed
- Full suite: 1100 passed, 12 skipped, 0 failing

---
*Phase: 29-online-client-sync*
*Completed: 2026-07-20*
