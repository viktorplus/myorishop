---
phase: 29-online-client-sync
plan: 02
subsystem: sync-client
tags: [sync, sqlalchemy, dataclass, i18n, timezone, tdd]

# Dependency graph
requires:
  - phase: 29-online-client-sync
    plan: 01
    provides: SyncState model (id=1 singleton, D-10 result + D-15 config columns), synced_at partial indexes, migration 0020
provides:
  - SyncResult dataclass (status + pushed/pushed_total/pulled) — the value object the Plan-03 driver returns
  - get_or_create_sync_state / record_sync_result — portable single-row sync_state (id=1) persistence (D-10)
  - read_autosync_config — fresh + clamped (60..3600) auto-sync toggle/interval read (D-08/D-15)
  - unsynced_count — the D-11 badge (ops+cash where synced_at IS NULL)
  - format_sync_message — the LOCKED D-12 Russian result strings + Moscow last-sync line
affects: [29-03, online-client-sync driver, unsynced badge, auto-sync loop, header sync-status partial]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure state+presentation layer (no network) unit-tested BEFORE the Plan-03 network driver that consumes it"
    - "record_sync_result never commits — the driver owns the transaction around its single D-10 exit point"
    - "Only fixed D-12 strings + integer counts cross the rendered-status boundary (T-29-07)"

key-files:
  created:
    - app/services/sync_client.py
    - tests/test_sync_client.py
  modified: []

key-decisions:
  - "record_sync_result truncates last_result defensively to 300 chars (SyncState.last_result column width) and only accepts a fixed RU string — never raw exception text (T-29-07)"
  - "format_sync_message collapses `error` and any unexpected status to the generic D-12 error string, so no unknown status can leak an untranslated value"
  - "The whole module was written cohesively in Task 1's GREEN step; Task 2 added the badge + formatter tests against the already-present functions (test commit, no separate feat needed)"

patterns-established:
  - "Interval clamp helper (_clamp_interval) falls back to DEFAULT_INTERVAL_SECONDS on None/invalid, then forces into MIN..MAX"

requirements-completed: [SYNC-06, SYNC-07, SYNC-08]

# Metrics
duration: ~15min (plus 7min full-suite gate)
completed: 2026-07-20
---

# Phase 29 Plan 02: Sync Client State + Presentation Layer Summary

**A pure, network-free `app/services/sync_client.py` — the SyncResult value object, the portable single-row `sync_state` (id=1) persistence written from one exit point (D-10), the fresh+clamped auto-sync config read (D-08/D-15), the `synced_at IS NULL` badge count (D-11), and every LOCKED D-12 Russian result string rendered in Europe/Moscow — unit-tested ahead of the Plan-03 network driver.**

## Performance

- **Duration:** ~15 min (implementation) + ~7 min full-suite gate
- **Completed:** 2026-07-20
- **Tasks:** 2 (both `tdd="true"`)
- **Files:** 2 created (1 service, 1 test module)

## Accomplishments
- `SyncResult` frozen dataclass with `status` (`ok`|`partial`|`offline`|`error`|`locked`|`not_configured`) + `pushed`/`pushed_total`/`pulled` int counts (default 0) — the value the Plan-03 driver returns and the formatter renders.
- `get_or_create_sync_state(session)` — portable SELECT-then-INSERT of the id=1 singleton with ORM defaults (`auto_enabled=0`, `auto_interval_seconds=300`); idempotent, flushes (never commits).
- `record_sync_result(session, *, status, last_result, last_sync_at)` — upserts the D-10 result columns from ONE exit point so a failure is recorded as reliably as a success (T-29-08); does NOT commit (the Plan-03 driver owns the transaction); defensively truncates `last_result` to the 300-char column width and only ever stores a fixed RU string (T-29-07).
- `read_autosync_config(session)` — reads the D-15 toggle+interval FRESH each call (so flipping the toggle takes effect next tick, D-08) and clamps the interval into 60..3600, falling back to 300 on a None/invalid value.
- `unsynced_count(session)` — the D-11 badge: two `COUNT(*) WHERE synced_at IS NULL` scalars (Operation + CashMovement) summed, backed by the Plan-01 partial indexes (T-29-09).
- `format_sync_message(result, sync_state, tz)` — returns `(status_message, last_sync_line)` using the LOCKED D-12 strings VERBATIM plus the two UI-SPEC secondary states (`Синхронизация уже выполняется`, `Синхронизация не настроена`); last-sync line via `iso_to_local` in Europe/Moscow, or `Ещё не синхронизировано` when never synced.

## Task Commits

TDD (RED → GREEN) commits, atomic per gate:

1. **Task 1 RED — failing state-layer tests** - `9b4c84a` (test)
2. **Task 1 GREEN — sync_state persistence + fresh clamped config** - `eac93ec` (feat)
3. **Task 2 — unsynced badge + D-12 formatter tests** - `1c934fa` (test)

## Files Created/Modified
- `app/services/sync_client.py` (created) - `SyncResult`, `get_or_create_sync_state`, `record_sync_result`, `_clamp_interval`, `read_autosync_config`, `unsynced_count`, `format_sync_message`; module constants `MIN_INTERVAL_SECONDS=60`, `MAX_INTERVAL_SECONDS=3600`, `DEFAULT_INTERVAL_SECONDS=300`.
- `tests/test_sync_client.py` (created) - state-layer half (idempotency, cross-restart persistence, error-path persistence, fresh/clamped config) + badge count + all D-12 messages + Moscow last-sync line.

## Decisions Made
- **Cohesive module write:** the entire `sync_client.py` (both the Task-1 state helpers and the Task-2 badge/formatter) was written in Task 1's GREEN step because the functions share a module and imports. Task 2 therefore contributes its tests as a `test(...)` commit against the already-present, already-green functions rather than a separate `feat(...)` — both `test` and `feat` gate commits exist for the plan.
- `format_sync_message` treats `error` **and any unexpected/unknown status** identically (generic D-12 error string), so a future status value can never leak an untranslated token to the UI.
- `record_sync_result` deliberately does not commit — Plan 03's driver wraps push/pull/record in a single transaction with the result written in a `finally` (D-10).

## Deviations from Plan
None — plan executed as written. The only judgment call (writing the whole module in Task 1's GREEN rather than splitting the formatter into Task 2) is documented under Decisions Made; it changes commit shape, not behavior or scope.

## Threat Model Compliance
- **T-29-07 (Information Disclosure):** `format_sync_message` renders ONLY the fixed D-12 strings + integer counts; `record_sync_result` truncates and only accepts a fixed RU string — no raw server error bytes or token can cross. Covered by `test_result_messages`.
- **T-29-08 (Tampering/integrity):** `record_sync_result` is the single exit point and persists `status="error"` as reliably as success. Covered by `test_record_sync_result_writes_on_error`.
- **T-29-09 (DoS):** `unsynced_count` is backed by the Plan-01 `synced_at IS NULL` partial indexes.

## Issues Encountered
- Ruff initially flagged Task-2-only imports (`Operation`, `CashMovement`, `SyncResult`, `new_id`) as unused while only Task-1 tests existed; trimmed them for the Task-1 commit and reintroduced them with the Task-2 tests. No production impact.
- Full suite surfaced 3 pre-existing `SAWarning`s in `test_receipts.py` / `test_returns.py` (identity-key conflicts on deliberate error-path flushes) — out of scope for this plan, unchanged, logged here only.

## User Setup Required
None — this layer is pure Python over a `Session`; no external service, config, or migration is introduced (the `sync_state` table + indexes already shipped in Plan 01).

## Next Phase Readiness
- Plan 03's network driver can now `record_sync_result` from its `finally`, `read_autosync_config` per tick, render results via `format_sync_message`, and drive the header badge via `unsynced_count` — every deterministic piece is isolated and unit-tested.
- Full suite: **1086 passed, 12 skipped, 0 failing** after this plan (was 1079 passed; +7 new tests).

## Self-Check: PASSED

- FOUND: app/services/sync_client.py, tests/test_sync_client.py
- FOUND commits: 9b4c84a, eac93ec, 1c934fa
- `uv run pytest tests/test_sync_client.py -q`: 7 passed
- `uv run ruff check` on both files: All checks passed
- Full suite: 1086 passed, 12 skipped, 0 failing

---
*Phase: 29-online-client-sync*
*Completed: 2026-07-20*
