---
phase: 29-online-client-sync
plan: 05
subsystem: sync-autoloop
tags: [sync, asyncio, lifespan, anyio, settings, htmx, jinja2]

# Dependency graph
requires:
  - phase: 29-online-client-sync
    plan: 02
    provides: read_autosync_config, get_or_create_sync_state, _clamp_interval, MIN/MAX/DEFAULT_INTERVAL_SECONDS
  - phase: 29-online-client-sync
    plan: 03
    provides: run_sync_tick (lock + fresh Session + record result), _run_lock (D-09 single-run guard)
  - phase: 29-online-client-sync
    plan: 04
    provides: partials/sync_status.html + _sync_status_context (a background tick's D-10 result is reflected on next page render)
provides:
  - _auto_sync_loop / _auto_sync_iteration — lifespan-started interval auto-sync (D-06/D-07/D-08)
  - lifespan wiring — asyncio.create_task after startup_backup + clean cancel on shutdown
  - save_autosync_config — clamp + persist auto_enabled/auto_interval_seconds to sync_state (D-15)
  - POST /settings/sync — admin-gated auto-sync config form handler
  - Settings «Синхронизация» section — checkbox + interval + save
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Zero-dependency asyncio background loop started in the FastAPI lifespan (D-06) — no APScheduler/Celery/Redis"
    - "The blocking sync driver is offloaded OFF the event loop via anyio.to_thread.run_sync with its own fresh Session (D-07); the sync Session never runs on the loop"
    - "The WHOLE iteration (config read + tick) is wrapped in one broad guard so any error is swallowed and the loop never dies (D-08)"
    - "task.cancel() + contextlib.suppress(asyncio.CancelledError) on lifespan shutdown — clean, no hang, no raise"
    - "_auto_sync_iteration factored out of _auto_sync_loop so the per-tick decision is unit-testable without spinning the infinite loop"

key-files:
  created:
    - tests/test_autosync.py
  modified:
    - app/main.py
    - app/routes/settings.py
    - app/services/settings.py
    - app/templates/pages/settings.html

key-decisions:
  - "The config read was moved INSIDE the broad try/except (not just the tick): a transient DB hiccup — e.g. the dev DB lacking sync_state during test lifespans — must also be swallowed, or the background task dies and the stored exception surfaces at shutdown, violating the D-08 'loop never dies' truth"
  - "_auto_sync_iteration returns the interval; _auto_sync_loop is the thin while-loop over it — the iteration is the pure, testable unit (config read → offload if enabled → return interval), the loop only adds asyncio.sleep"
  - "The checkbox posts auto_enabled=on only when checked (absent = disabled); the route parses it leniently (on/true/1/yes) and parses the interval in a try/except that falls back to DEFAULT_INTERVAL_SECONDS, so a bad input is clamped/defaulted — never a 5xx (D-15)"
  - "settings_summary surfaces the read-only sync_server_url but NEVER the sync_token (T-29-07); the token is not returned from the service at all"

patterns-established:
  - "Lifespan asyncio background loop + anyio.to_thread.run_sync offload + broad-guard-the-whole-tick — the zero-dependency 'runs with the tab closed' pattern for optional background work"

requirements-completed: [SYNC-08]

# Metrics
duration: ~45min (incl. ~6min full-suite gate)
completed: 2026-07-20
---

# Phase 29 Plan 05: Online Client Sync — Interval Auto-Sync & Settings Control Summary

**The optional interval auto-sync: a zero-dependency asyncio loop started in the FastAPI lifespan (D-06) that reads its on/off toggle + interval fresh each tick (D-08), offloads the blocking sync driver off the event loop via `anyio.to_thread.run_sync` with a fresh Session (D-07), swallows offline/DB errors so the loop never dies, and cancels cleanly on shutdown — driven by a new «Синхронизация» section on the admin Settings page where the operator enables auto-sync and sets a clamped 60..3600 s interval (D-03/D-15).**

## Performance
- **Duration:** ~45 min (implementation) + ~6 min full-suite gate
- **Completed:** 2026-07-20
- **Tasks:** 2 (both `type="auto"`)
- **Files:** 1 created, 4 modified

## Accomplishments
- `app/main.py` — `_auto_sync_iteration()` (reads `read_autosync_config` fresh, offloads `sync_client.run_sync_tick` via `anyio.to_thread.run_sync` when enabled, and swallows any error) + `_auto_sync_loop()` (the thin `while True:` over the iteration + `asyncio.sleep(interval)`). The existing `lifespan` now does `asyncio.create_task(_auto_sync_loop())` AFTER `backup_service.startup_backup()` (unchanged) and, in a `finally`, `task.cancel()` + `contextlib.suppress(asyncio.CancelledError)` for a clean, non-hanging shutdown (D-06/D-07/D-08). New imports: `asyncio`, `contextlib`, `anyio`, `SessionLocal`, `sync_client`, `DEFAULT_INTERVAL_SECONDS`.
- `app/services/settings.py` — `save_autosync_config(session, *, enabled, interval_seconds)` get-or-creates the single `sync_state` row, sets `auto_enabled` 1/0 and `auto_interval_seconds` clamped into 60..3600 via the reused Plan-02 `_clamp_interval` (D-15), commits. `settings_summary` extended to also return `auto_enabled` + `auto_interval_seconds` (fresh read, D-08) + the read-only `sync_server_url` — the `sync_token` is NEVER returned (T-29-07).
- `app/routes/settings.py` — `POST /settings/sync` (a `def` handler on the admin-gated settings router, so it inherits `require_role("administrator")`, T-29-13). Parses the checkbox leniently and the interval in a `try/except` that falls back to `DEFAULT_INTERVAL_SECONDS`, calls `save_autosync_config`, then re-renders `pages/settings.html` with `sync_saved=True`. A bad/unparseable interval is clamped/defaulted, never a 5xx (D-15).
- `app/templates/pages/settings.html` — a «Синхронизация» `<h2>` section with a `form.stacked-form`: the `Автоматическая синхронизация` checkbox (checked when `auto_enabled`, default OFF), the `Интервал синхронизации (секунды)` number input (`min=60 max=3600 step=60`, default 300), an optional read-only `Адрес сервера синхронизации` line (only when a server URL is configured), the CSRF hidden field, a `Сохранить` button, and the `Настройки сохранены` `.muted` confirmation after a save. Reuses existing classes only (UI-SPEC hard rule).
- `tests/test_autosync.py` (NEW) — 14 tests: auto OFF skips `run_sync_tick` / auto ON offloads it / a tick exception is swallowed / the lifespan starts + cancels the loop cleanly (Task 1); `save_autosync_config` persist + low/high clamp + disable, the web POST persist + clamp + unparseable-default + unchecked-disable, and the token-never-rendered check (Task 2).

## Task Commits
1. **Task 1 — lifespan interval auto-sync loop (D-06/D-07/D-08)** — `39fea87` (feat)
2. **Task 2 — Settings auto-sync control + guard whole tick (D-03/D-15)** — `67c2662` (feat)

## Files Created/Modified
- `app/main.py` (modified) — `_auto_sync_iteration` + `_auto_sync_loop` + lifespan task start/clean-cancel; imports.
- `app/services/settings.py` (modified) — `save_autosync_config` + extended `settings_summary`.
- `app/routes/settings.py` (modified) — `POST /settings/sync`.
- `app/templates/pages/settings.html` (modified) — «Синхронизация» section.
- `tests/test_autosync.py` (created) — 14 tests.

## Decisions Made
- **Guard the WHOLE iteration, not just the tick:** the first draft read the config OUTSIDE the `try/except`; a transient DB error there (e.g. the dev DB lacking `sync_state` while a `client`-fixture test runs the real lifespan) propagated out of the task, and the stored exception then surfaced at lifespan shutdown as a teardown error. Moving the config read inside the broad guard (returning `DEFAULT_INTERVAL_SECONDS` on failure) makes the loop honour the D-08 "loop never dies" truth for ANY error, not just httpx transport errors. (See Deviations — Rule 1.)
- **`_auto_sync_iteration` is the testable unit:** it returns the interval so the loop is a thin `while` over it — the per-tick decision (read → offload if enabled → return interval) is unit-tested with `asyncio.run` without spinning the infinite loop.
- **Lenient parse, never a 5xx:** the route parses the checkbox (`on/true/1/yes`) and the interval (`try int()` → default), and the service clamps — a malformed form value is defaulted/clamped, matching the SRV-03/SYNC-06 "failure never blocks work" stance.
- **Read-only server URL, never the token:** `settings_summary` surfaces `sync_server_url` for display but does not return `sync_token`; the template has no token field (T-29-07).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Background config read could kill the auto-sync loop**
- **Found during:** Task 2 (full-file test run — the Task-1 `client`-fixture tests errored at lifespan teardown with `no such table: sync_state`)
- **Issue:** In the Task-1 draft the `read_autosync_config` call sat OUTSIDE the broad `try/except`, so a transient DB error (the dev DB lacking `sync_state`, or a momentary lock) raised out of `_auto_sync_iteration` → `_auto_sync_loop`, killing the task; the stored exception then surfaced when the lifespan awaited the cancelled task at shutdown. This violates the D-08 "loop never dies" truth.
- **Fix:** Moved the config read inside the same broad guard and default the interval to `DEFAULT_INTERVAL_SECONDS` on failure, so ANY error (offline / transport / transient DB) is swallowed and the loop retries next interval.
- **Files modified:** `app/main.py`
- **Commit:** `67c2662` (folded into the Task 2 commit, which is where the full-suite run surfaced it)

## Threat Model Compliance
- **T-29-10 (DoS / availability):** the blocking driver is offloaded via `anyio.to_thread.run_sync` (D-07) so it never stalls the event loop; the driver is bounded by the Plan-03 `SYNC_TIMEOUT` (D-05); every tick error is swallowed so the loop never dies (D-08).
- **T-29-14 (DoS / too-frequent sync):** the interval is clamped 60..3600 s in `save_autosync_config` (D-15), default 300 s — the operator cannot set a sub-minute hammer.
- **T-29-13 (Access control):** `POST /settings/sync` sits on the settings router, which is mounted with `require_role("administrator")`; CSRF is carried by the base body `hx-headers` + the hidden field.
- **T-29-07 (Information disclosure):** only the non-secret `sync_server_url` is displayed read-only; `sync_token` is never returned by `settings_summary` nor rendered (covered by `test_web_settings_never_renders_token`).
- **T-29-12 (Concurrency):** the background tick calls `run_sync_tick`, which acquires the shared `_run_lock` non-blocking (D-09) — a tick overlapping a manual click silently skips.

## Threat Flags
None — this plan adds one admin-gated, CSRF-protected settings route plus a background loop that reuses the Plan-03 driver and Plan-02 helpers unchanged; it introduces no new network endpoint, external auth path, or schema surface.

## Known Stubs
None — the loop drives the real `run_sync_tick`, and the Settings control reads/writes the live `sync_state` row via `read_autosync_config` / `save_autosync_config`.

## Issues Encountered
- Full suite surfaced the same 3 pre-existing warnings noted in Plans 02/03/04 (2 `SAWarning` identity-key conflicts on deliberate error-path flushes in `test_receipts.py`/`test_returns.py`, 1 Starlette TestClient deprecation) — out of scope, unchanged, logged here only.

## User Setup Required
None — auto-sync defaults OFF; an admin enables it and sets the interval from Settings. Sync only actually transmits once `sync_server_url` + `sync_token` are set in `.env` (SRV-03); until then a tick is a silent no-op (`not_configured`).

## Next Phase Readiness
- SYNC-08 complete: the optional interval auto-sync runs, reads config fresh, offloads off the loop, stops silently while offline, cancels cleanly, and is controlled from Settings. With auto-sync disabled, only the Plan-04 manual button syncs.
- Full suite: **1122 passed, 12 skipped, 0 failing** after this plan (was 1108; +14 new tests).
- Manual UAT still recommended (29-VALIDATION.md): with auto-sync ON + a short interval, close the tab, make a server-side reference change, reopen after one interval, confirm the client pulled it.

## Self-Check: PASSED
- FOUND: app/main.py, app/routes/settings.py, app/services/settings.py, app/templates/pages/settings.html, tests/test_autosync.py
- FOUND commits: 39fea87, 67c2662
- `uv run pytest tests/test_autosync.py -q`: 14 passed
- `uv run ruff check` on the changed .py files: All checks passed
- Full suite: 1122 passed, 12 skipped, 0 failing

---
*Phase: 29-online-client-sync*
*Completed: 2026-07-20*
