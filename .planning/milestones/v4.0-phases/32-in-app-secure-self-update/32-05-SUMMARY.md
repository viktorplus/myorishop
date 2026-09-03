---
phase: 32-in-app-secure-self-update
plan: 05
subsystem: self-update
tags: [update, htmx, settings, autoescape, lifespan, offline-safe]
requires: [32-03, 32-04]
provides:
  - "app/templates/partials/update_panel.html: #update-panel fragment for every update state"
  - "app/routes/settings.py: POST /settings/update/{check,apply,dismiss} thin routes (always 200)"
  - "app/services/settings.py: settings_summary exposes cached update_status for first paint"
  - "app/templates/pages/settings.html: sqlite-only «Обновление приложения» section"
  - "app/main.py: one-shot non-blocking startup update check in lifespan"
affects: []
tech-stack:
  added: []
  patterns:
    - "thin route -> service -> #update-panel partial (mirrors POST /settings/sync)"
    - "outerHTML self-contained partial (root <div id> survives every swap)"
    - "autoescaped untrusted GitHub notes (never |safe)"
    - "one-shot lifespan background task offloaded via anyio.to_thread.run_sync (never awaited before yield)"
key-files:
  created:
    - app/templates/partials/update_panel.html
  modified:
    - app/routes/settings.py
    - app/services/settings.py
    - app/templates/pages/settings.html
    - app/main.py
decisions:
  - "#update-panel is a self-contained <div id=update-panel> swapped with hx-swap=outerHTML (not the plan's innerHTML sketch) so the target id survives every swap and the manual-check response literally contains 'update-panel' (test_manual_check contract)"
  - "apply route echoes the release notes via the CACHED status (get_cached_status), so the autoescaped notes render deterministically regardless of update.apply()'s network outcome — an offline/no-op apply re-shows the notice (outcome=None) so the admin can retry; only a verify-gate raise shows the .error-block"
  - "dismiss renders the empty panel (notice gone from the DOM); a later check re-populates it — no server-side session-dismiss flag added (single-user local app)"
  - "__version__ left at 1.15 (app/__init__.py outside this plan's files): test_check_detects_newer pins 1.16 as the newer release, so bumping would flip that assertion to up_to_date"
metrics:
  duration: "~20m"
  completed: 2026-07-22
---

# Phase 32 Plan 05: Operator-Facing Update Surface + Startup Check Summary

Wired the verified update core (Waves 03/04) to the operator: an admin-only, sqlite-only «Обновление приложения» section inside Настройки with a notify-and-confirm notice (autoescaped release notes, «Обновить и перезапустить» / «Позже»), three thin always-200 routes, and a one-shot offline-safe startup check that populates the first-paint cache without ever blocking launch. This is the last wave of Phase 32 (UPD-01/03/05/06/07).

## What Was Built

**Task 1 — Settings update section + #update-panel partial + thin routes (UPD-03/07)** — commit `fc4a5ca`
- `app/templates/partials/update_panel.html` (new): a self-contained `<div id="update-panel">` fragment rendering every state — up-to-date muted caption, the S1 amber attention notice (inline `#fef9e7`/`#b45309` price-below token pair, no new CSS, no spinner), offline caption (manual only), applying caption, and the `.error-block` verification-failed / rollback messages. Release notes are rendered `{{ update_status.notes }}` (autoescaped, never `|safe`, T-32-01).
- `app/routes/settings.py`: `POST /settings/update/check` (calls `update.check_for_update`, manual offline caption), `/settings/update/apply` (calls `update.apply`, maps a `UpdateVerificationError` raise -> verification-failed, a staged result -> applying, any other post-verify failure -> rollback, echoing cached notes), `/settings/update/dismiss` (empty panel). A shared `_render_update_panel` helper keeps them thin; all return 200 (T-32-03).
- `app/services/settings.py`: `settings_summary` now exposes `update_status = update.get_cached_status()` for the first-paint notice.
- `app/templates/pages/settings.html`: a `{% if not is_server_db %}` section (UPD-06) with the «Проверить обновления» form (`hx-target="#update-panel" hx-swap="outerHTML"`, `hx-indicator="#update-inflight"`) and the included partial.

**Task 2 — One-shot non-blocking startup update check (UPD-01) + UPD-05 chip proof** — commit `7a58f50`
- `app/main.py`: `_startup_update_check()` offloads the blocking `update.check_for_update` via `anyio.to_thread.run_sync(..., abandon_on_cancel=False)` inside a broad guard; fired as `asyncio.create_task` in `lifespan` after the startup backup, NOT awaited before `yield`, and cancelled cleanly on shutdown. Confirmed the header `.app-version muted` chip already renders `APP_VERSION` (base.html:40) — UPD-05 needs no markup change.

## Verification

- `uv run pytest tests/test_update.py -x` — 7 passed (2 flipped RED->GREEN this wave: `test_manual_check`, `test_confirm_and_defer`; minisign round-trip GREEN, binary present).
- `uv run pytest tests/test_launcher.py -q` — 8 passed, 1 skipped.
- `uv run pytest -q` — 1196 passed, 13 skipped, **4 failed** = the known pre-existing `tests/test_sync_ui.py` failures ONLY (MEMORY `preexisting-sync-ui-test-failures`, held `_run_lock` from the lifespan auto-sync thread — NOT this wave's regression). No other regression.
- `uv run ruff check app/main.py app/routes/settings.py app/services/settings.py` — all checks passed (one import-sort auto-fix applied to main.py).
- Acceptance greps: no `|safe` filter in the partial (only a doc-comment mention); `is_server_db` gates the section; `Обновить и перезапустить` verbatim from 32-UI-SPEC; `check_for_update` present in main.py and NOT awaited before `yield`; `APP_VERSION` chip present in base.html.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Import-sort on app/main.py**
- **Found during:** Task 2 verification (`ruff check`).
- **Issue:** Adding `from app.services import update` left the import block un-sorted (I001).
- **Fix:** `ruff check --fix app/main.py` merged it into `from app.services import sync_client, update`. `update` still imported; behaviour unchanged.
- **Files modified:** app/main.py
- **Commit:** 7a58f50

### Design choice (planner discretion, within UI-SPEC)

- The plan sketch used `hx-swap="innerHTML"` into a wrapping `<div id="update-panel">`. I made the partial ITSELF the `<div id="update-panel">` root and swap with `hx-swap="outerHTML"` so (a) the target id survives every swap and (b) the manual-check response literally contains `update-panel` (the `test_manual_check` contract). Both satisfy the plan's `#update-panel` key-link.
- The apply partial shows the version + autoescaped notes header for the applying state (what is being installed), consistent with the `test_confirm_and_defer` contract that the apply response carries the escaped notes; the locked applying caption is appended below.

## Known Stubs

None — every state renders real data from the update service; no placeholder/mock data paths.

## Threat Flags

None — no new network endpoint, auth path, or schema surface beyond the plan's `<threat_model>` (the three routes are session-admin-gated via the existing settings router include; the startup check reuses the shipped dialect-gated `check_for_update`).

## Post-Phase UAT (for /gsd-verify-work 32)

These need two real signed releases and cannot be automated:
1. Install release N on a bare Windows box, publish a signed release N+1, launch → the Настройки notice appears; click «Обновить и перезапустить» → app restarts and the header chip shows N+1, ledger intact (UPD-01/03/04/05).
2. Confirm a downgrade offer and a checksum-tampered asset are both refused with nothing installed (UPD-02).

Phase completion is gated on this UAT **and** `/gsd-secure-phase 32` (plans carry threat_models T-32-01..10 + T-32-SC).

## Self-Check: PASSED

All created/modified files exist on disk; both task commits (`fc4a5ca`, `7a58f50`) are in the git log.
