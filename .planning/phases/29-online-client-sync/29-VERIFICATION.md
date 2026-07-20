---
phase: 29-online-client-sync
verified: 2026-07-20T06:10:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: none
  note: initial goal-backward verification (code review 29-REVIEW.md ran separately; its 1 blocker + 3 warnings confirmed fixed here)
---

# Phase 29: Online Client Sync Verification Report

**Phase Goal:** Wire the local desktop client to the server's sync API — a manual «Синхронизировать» action pushes operations and cash movements up and pulls server-authoritative reference data down, with clear status, an unsynced-count badge, an optional interval-based background sync, and offline-safe failure that never blocks local work.
**Verified:** 2026-07-20T06:10:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | Online: «Синхронизировать» pushes ops+cash up, pulls server-authoritative reference down, stock/figures correct afterward (SYNC-01) | ✓ VERIFIED | `run_sync_once` (sync_client.py:334) collects unsynced Operation+CashMovement, builds D-13 FK closure (`_collect_push_records`), POSTs `/api/sync/push` with Bearer, stamps `synced_at` ONLY after `raise_for_status()` (line 369-386), then `_pull_all` applies D-14 server-wins upsert + `recompute_derived` (line 458) rebuilding stock from LOCAL ledger. Route `/sync/run` registered (openapi confirms). Tests pass: `test_push_marks_synced_and_pulls`, `test_second_sync_is_noop`, `test_pull_applies_server_update`, `test_pull_does_not_clobber_local_quantity` |
| 2 | Sync UI shows status, last-sync time, plain-language RU result; failure surfaces clearly, never blocks local work (SYNC-06) | ✓ VERIFIED | `format_sync_message` (sync_client.py:165) renders LOCKED D-12 RU strings + last-sync line in Europe/Moscow; `sync_status.html` shows `#sync-status` (message + last_sync_line) on every page via `_sync_status_context` processor (routes/__init__.py:40); `POST /sync/run` ALWAYS returns 200 (routes/sync.py:236, broad except → error partial). `test_offline_returns_offline_not_raise`, `test_push_ok_pull_fail_is_partial`, `test_sync_run_returns_oob_partial` pass |
| 3 | Badge shows count of local operations not yet synced (SYNC-07) | ✓ VERIFIED | `unsynced_count` (sync_client.py:139) = COUNT(*) WHERE synced_at IS NULL across Operation+CashMovement, backed by partial indexes; `sync_status.html:16` renders `#sync-badge` only when `unsynced > 0` (hidden at 0). `test_badge_visibility` in test_sync_ui.py passes |
| 4 | Optional interval auto-sync; silently stops while offline; disabled = only manual button (SYNC-08) | ✓ VERIFIED | `_auto_sync_loop`/`_auto_sync_iteration` (main.py:64-108) started in lifespan, reads config FRESH each tick, offloads `run_sync_tick` via `anyio.to_thread.run_sync`, broad except swallows offline errors; `run_sync_tick` returns early when `enabled` is False (sync_client.py:512). Settings toggle+interval form (`/settings/sync`) clamps 60..3600. `test_iteration_auto_off_does_not_call_run_sync_tick`, `test_iteration_swallows_tick_exception`, `test_lifespan_starts_and_cancels_loop_cleanly`, save/clamp tests pass |
| 5 | Client keeps working fully offline on local SQLite; server needed only for sync (SRV-03) | ✓ VERIFIED | Blank `sync_server_url`/`sync_token` short-circuit to `not_configured` no-op (sync_client.py:348, routes/sync.py:255); config defaults blank (verified at runtime). No local write-path service imports `sync_client` (grep: only settings.py imports it, for config). `test_local_work_unaffected_when_unconfigured`, `test_run_sync_once_not_configured` pass |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `app/config.py` | sync_server_url + sync_token fields, blank default | ✓ VERIFIED | Lines 56-57; both default `""`, token `.env`-only (never a DB column) |
| `app/models.py` SyncState + indexes | 6-col singleton + 2 partial indexes | ✓ VERIFIED | `SyncState` at line 602 (id, last_sync_at, last_status, last_result, auto_enabled, auto_interval_seconds); `ix_operations_unsynced` (line 346) + `ix_cash_movements_unsynced` (line 496), both sqlite_where+postgresql_where |
| `alembic/versions/0020_*.py` | sync_state table + 2 unsynced indexes, portable | ✓ VERIFIED | revision="0020", down_revision="0019", String/Integer only, no app imports, both partial indexes present |
| `app/services/sync_client.py` | state+presentation+driver | ✓ VERIFIED | 552 lines; SyncResult, get_or_create_sync_state, record_sync_result, read_autosync_config, unsynced_count, format_sync_message, run_sync_once, _collect_push_records, _apply_pull_page, _pull_all, run_sync_tick, build_sync_client |
| `app/routes/sync.py` | POST /sync/run always-200 OOB | ✓ VERIFIED | `sync_run` at line 236, lock-guarded, `_render_sync_status` renders oob=True partial, HTMLResponse 200 |
| `app/routes/__init__.py` | every-page context processor | ✓ VERIFIED | `_sync_status_context` registered on templates env; read-only (WR-02 fix) |
| `app/templates/partials/sync_status.html` | OOB status + badge partial | ✓ VERIFIED | `#sync-status` + `#sync-badge`, hx-swap-oob when oob, badge hidden at 0 |
| `app/templates/base.html` | «Синхронизировать» trigger on every page | ✓ VERIFIED | Line 67 nav link with hx-post + hx-swap="none" (CR-01 fix), include partial |
| `app/main.py` | lifespan auto-sync loop | ✓ VERIFIED | `_auto_sync_loop` created in lifespan, cancelled cleanly; startup_backup preserved |
| `app/routes/settings.py` + service | /settings/sync toggle/interval | ✓ VERIFIED | POST persists clamped config; summary exposes non-secret sync_server_url only |
| `app/templates/pages/settings.html` | Синхронизация section | ✓ VERIFIED | Checkbox + interval (min60/max3600) + save + confirmation; token never rendered |

### Key Link Verification

| From | To | Via | Status |
| ---- | -- | --- | ------ |
| run_sync_once push | POST /api/sync/push | httpx.Client + Bearer + serialize_exchange | ✓ WIRED (sync_client.py:364) |
| _pull_all | GET /api/sync/pull | echoes X-Sync-Next-Since + X-Sync-Next-After-Id | ✓ WIRED (sync_client.py:482,490-494) |
| D-14 client upsert | recompute_derived | server-wins update then rebuild local qty | ✓ WIRED (sync_client.py:458) |
| base.html nav | /sync/run | hx-post trigger + include partial | ✓ WIRED (base.html:67,69) |
| _auto_sync_loop | run_sync_tick | anyio.to_thread.run_sync, fresh Session | ✓ WIRED (main.py:90) |
| POST /settings/sync | sync_state.auto_enabled/interval | save_autosync_config clamp+persist | ✓ WIRED (settings.py service:54-57) |

### Code Review Fixes (29-REVIEW.md: 1 blocker + 3 warnings)

| ID | Issue | Fix Present | Evidence |
| -- | ----- | ----------- | -------- |
| CR-01 (blocker) | Manual button erases its own label after first click | ✓ FIXED | base.html:67 `hx-swap="none"` added; commit e0eae5a |
| WR-01 | run_sync_once leaks non-httpx errors from pull stage | ✓ FIXED | sync_client.py:394-403 `except Exception → partial` + rollback; run_sync_tick:517-524 `except Exception → error` records result; commit 8b807d0 |
| WR-02 | Context processor performs write on every render | ✓ FIXED | routes/__init__.py:62 read-only `session.get(SyncState, 1)`; commit b01c957 |
| WR-03 | Offloaded thread can outlive lifespan cancel | ✓ FIXED | main.py:90-92 `abandon_on_cancel=False` + sync_client.py:538-549 commit-failure swallow; commit bcc640b |
| IN-01 (info) | `_apply_pull_page` return value dead; count uses len(batch.records) | ○ NOT FIXED (info-only, not required) | Reference-only pull keeps counts equal today; no goal impact |
| IN-02 (info) | Couples to merge private names | ○ NOT FIXED (info-only, matches existing codebase pattern) | No goal impact |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| httpx importable at runtime | `python -c "import httpx"` | 0.28.1 | ✓ PASS |
| Sync routes registered | openapi paths | /sync/run, /settings/sync, /api/sync/push, /api/sync/pull all present | ✓ PASS |
| Config defaults blank (offline-first) | runtime check | sync_server_url=='', sync_token=='' | ✓ PASS |
| Phase test suites | `pytest test_sync_client.py test_sync_ui.py test_autosync.py` | 43 passed | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Status | Evidence |
| ----------- | ----------- | ------ | -------- |
| SYNC-01 | 29-03, 29-04 | ✓ SATISFIED | Truth 1; push+pull driver + manual button |
| SYNC-06 | 29-01, 29-02, 29-03, 29-04 | ✓ SATISFIED | Truth 2; status UI + offline-safe always-200 |
| SYNC-07 | 29-01, 29-02, 29-04 | ✓ SATISFIED | Truth 3; unsynced_count badge |
| SYNC-08 | 29-05 | ✓ SATISFIED | Truth 4; lifespan loop + Settings toggle |
| SRV-03 | 29-01, 29-03 | ✓ SATISFIED | Truth 5; blank-config no-op, no network in local write path |

All 5 declared requirement IDs traced to REQUIREMENTS.md (lines 40,45,50-52) and marked Complete in the traceability table (lines 144-148). No orphaned requirements for Phase 29.

### Anti-Patterns Found

None. No TODO/FIXME/XXX/TBD/HACK/PLACEHOLDER markers in any of the 9 phase implementation files. Only fixed D-12 RU strings + integer counts cross into HTML; sync_token never a DB column, never rendered, never logged, travels only in the Authorization header.

### Human Verification Required

None required for goal achievement — all five success criteria are verifiable in the codebase and are covered by passing automated tests against the real in-process server (ASGITransport) plus MockTransport for offline/error paths. The optional end-to-end "close tab, change server data, reopen after one interval" flow (29-VALIDATION.md manual note) is a nice-to-have real-network check, but the interval loop, fresh-config read, offload, and offline-swallow behaviors are all unit-verified, so it is not a blocking gap.

### Gaps Summary

No gaps. The phase goal is achieved: the desktop client is wired to the server sync API with a manual «Синхронизировать» push+pull, D-13 FK-closure push, D-14 server-wins pull with local-ledger stock recompute, a plain-language RU status surface with last-sync time on every page, an unsynced-count badge hidden at zero, an optional clamped interval background auto-sync that silently stops while offline, and a fully offline-safe contract where a blank config or a network failure never blocks local SQLite work. All four code-review fixes (CR-01, WR-01, WR-02, WR-03) are present and correct in the committed code; the two info-only items (IN-01, IN-02) were not required and have no goal impact.

---

_Verified: 2026-07-20T06:10:00Z_
_Verifier: Claude (gsd-verifier)_
