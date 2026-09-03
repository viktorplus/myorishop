---
phase: 29-online-client-sync
plan: 04
subsystem: sync-ui
tags: [sync, htmx, oob-swap, jinja2, context-processor, ui]

# Dependency graph
requires:
  - phase: 29-online-client-sync
    plan: 02
    provides: format_sync_message, unsynced_count, get_or_create_sync_state, record_sync_result, SyncResult
  - phase: 29-online-client-sync
    plan: 03
    provides: run_sync_once, build_sync_client, _run_lock (D-09 single-run guard)
provides:
  - POST /sync/run — always-200 manual sync handler returning the OOB status/badge partial (SYNC-01/06)
  - partials/sync_status.html — #sync-status + #sync-badge OOB partial (first paint + refresh)
  - _sync_status_context — every-page Jinja context processor (sync_message/last_sync_line/unsynced)
  - base.html «Синхронизировать» nav trigger + status/badge cluster (D-01)
affects: [29-05 auto-sync loop shares the _run_lock and the same partial contract]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "The manual sync handler mirrors finance.py _movement_success: templates.get_template(...).render(oob=True, ...) → HTMLResponse"
    - "A second context processor on the shared templates env injects the sync surface into EVERY render (mirrors _auth_context) — no route re-passes it"
    - "The handler ALWAYS returns 200: a broad guard + the offline-safe driver ensure no network failure becomes a non-swappable 5xx (SYNC-06)"
    - "htmx built-in .htmx-indicator opacity rule reveals the «Синхронизация…» text — no spinner graphic, no new CSS (UI-SPEC)"

key-files:
  created:
    - app/templates/partials/sync_status.html
    - tests/test_sync_ui.py
  modified:
    - app/routes/sync.py
    - app/routes/__init__.py
    - app/templates/base.html

key-decisions:
  - "The unsynced-count badge is styled inline (amber #b45309 on #fef9e7 tint, padding 4px 8px, radius 4px, 14px/600) rather than adding a CSS class — style.css is not in the plan's files_modified and base.html already sets inline styles (logout link); the values are the LOCKED price-cue token values, no new token (UI-SPEC hard rule)"
  - "The #sync-badge container is ALWAYS emitted (empty at 0) so an OOB swap can clear a stale badge; the visible .sync-badge-count span is present only when unsynced > 0"
  - "The context processor opens its OWN short-lived SessionLocal (the established run_sync_tick precedent) and swallows ANY error to a neutral never-synced default so a sync-state hiccup can never break page rendering (SRV-03)"
  - "First paint shows the stored last_result string (already a fixed D-12 message) directly; the last-sync line is derived from the row via format_sync_message (its dummy status does not affect that line)"

patterns-established:
  - "OOB header-surface partial served by BOTH a context processor (first paint, oob unset) and a POST handler (oob=True refresh) — the cash_balance.html idiom generalised to a two-element status+badge cluster"

requirements-completed: [SYNC-01, SYNC-06, SYNC-07]

# Metrics
duration: ~35min (plus ~5min full-suite gate)
completed: 2026-07-20
---

# Phase 29 Plan 04: Online Client Sync — Manual Button & Header Surface Summary

**The sync surface the operator actually sees: a «Синхронизировать» nav trigger plus a live status line and unsynced-count badge rendered in `base.html` on every desktop page (D-01), refreshed in place by an always-200 `POST /sync/run` OOB swap (D-02) that surfaces any failure as a plain Russian D-12 partial — never a 5xx that would break the page (SYNC-06) — with the badge showing the count when > 0 and hidden at 0 (SYNC-07).**

## Performance
- **Duration:** ~35 min (implementation) + ~5 min full-suite gate
- **Completed:** 2026-07-20
- **Tasks:** 2 (both `type="auto"`)
- **Files:** 2 created, 3 modified

## Accomplishments
- `POST /sync/run` (`app/routes/sync.py`) — a plain `def` handler (threadpool, D-04) on the app-level `auth_guard` (NOT under the `/api/sync/` token-bypass prefix, so a logged-in operator — not just an admin — can trigger it, T-29-13; CSRF via the base.html body `hx-headers`). Acquires the shared `sync_client._run_lock` non-blocking (D-09 → `locked` partial on a double-click), short-circuits `not_configured` on a blank URL/token (SRV-03 no-op, no network), else runs `run_sync_once`, records the D-10 result, commits, and renders the OOB partial. A broad guard around the driver plus the driver's own offline-safety mean it ALWAYS returns 200 (SYNC-06).
- `partials/sync_status.html` (NEW) — mirrors `cash_balance.html`: `#sync-status` (message + last-sync line, `.muted`) and `#sync-badge` (the amber count), each carrying `hx-swap-oob="true"` only when `oob=True`, so the SAME template serves first paint and the refresh. Only fixed D-12 strings + the integer count reach the DOM (T-29-07).
- `_sync_status_context` (`app/routes/__init__.py`) — a second context processor on the shared `templates` env that opens its own short-lived `SessionLocal`, injects `sync_message`/`last_sync_line`/`unsynced` into EVERY render (mirrors `_auth_context`), and swallows any error to a neutral never-synced default (SRV-03).
- `base.html` `<nav>` — the «Синхронизировать» `hx-post="/sync/run"` trigger + `hx-indicator` «Синхронизация…» text (htmx's built-in opacity rule, no spinner, no new CSS) + `{% include "partials/sync_status.html" %}`, right-aligned via the existing `margin-left:auto` idiom, visible on every desktop page for both roles (D-01).
- `tests/test_sync_ui.py` (NEW) — 8 tests: header trigger+status present, badge hidden at 0 / visible with count when > 0, OOB success refresh, offline 200 + «Нет связи с сервером», not-configured no-op, lock-hit partial, and context-processor resilience when `SessionLocal` raises.

## Task Commits
1. **Task 1 — POST /sync/run OOB handler + sync_status partial** — `22c7eea` (feat)
2. **Task 2 — every-page context processor + header nav wiring + UI tests** — `14daed2` (feat)

## Files Created/Modified
- `app/routes/sync.py` (modified) — added `_render_sync_status` helper + the `POST /sync/run` handler; new imports (`HTMLResponse`, `templates`, `sync_client`, and the Plan-02 helpers).
- `app/templates/partials/sync_status.html` (created) — the OOB `#sync-status` + `#sync-badge` partial.
- `app/routes/__init__.py` (modified) — `_sync_status_context` context processor registered on the shared `templates` env; imports `SessionLocal` + the Plan-02 sync helpers.
- `app/templates/base.html` (modified) — the sync nav cluster (trigger + indicator + partial) inside `<nav>`; the logout link kept, its `margin-left:auto` moved to the sync trigger.
- `tests/test_sync_ui.py` (created) — 8 UI-wiring tests.

## Decisions Made
- **Inline-styled badge, no CSS class:** `style.css` is not in the plan's `files_modified` and `base.html` already sets inline styles; the badge reuses the LOCKED price-cue token values (`#b45309`/`#fef9e7`, 4px 8px, radius 4px, 14px/600) inline — no new CSS token (UI-SPEC hard rule). A `.sync-badge-count` class name is used only as a render/test hook (no CSS rule attached).
- **Always-present `#sync-badge` container:** the outer span is always emitted (empty at 0) so an OOB swap can clear a stale badge; the visible count span is conditional (`unsynced > 0`), satisfying "hide at 0" while keeping the OOB target swappable.
- **Context processor owns its own session (SRV-03):** it opens a short-lived `SessionLocal` (the `run_sync_tick` precedent) and swallows any error to a neutral default, so a missing/locked DB or sync-state hiccup can never break a page render.

## Deviations from Plan
None — plan executed as written. The only judgment call (inline badge styling vs. a new CSS class, since `style.css` is outside `files_modified`) is documented under Decisions Made; it changes styling mechanism, not the visual (the exact UI-SPEC values are reused) or scope.

## Threat Model Compliance
- **T-29-07 (Information Disclosure):** the partial renders ONLY `format_sync_message`'s fixed D-12 strings + the integer `unsynced` count; the token and raw exception text are never interpolated (the handler's broad guard maps any exception to the generic D-12 `error`). The context processor never reads the token.
- **T-29-13 (Spoofing / Access Control):** `/sync/run` is NOT under `SYNC_PATH_PREFIX`, so it stays behind the app-level `auth_guard`; CSRF is carried by the existing body `hx-headers` line.
- **T-29-10 (DoS / availability):** the handler always returns 200 with the OOB partial; the Plan-03 `SYNC_TIMEOUT` bounds the request; the page stays interactive.
- **T-29-12 (Concurrency):** a fast double-click hits `_run_lock.acquire(blocking=False)` → the `locked` partial (`Синхронизация уже выполняется`), never a second overlapping run (covered by `test_lock_hit_returns_locked_partial`).

## Threat Flags
None — this plan adds one session-guarded, CSRF-protected operator route plus template wiring; it introduces no new network endpoint, external auth path, or schema surface (it consumes the Plan-03 driver and the Plan-02 helpers unchanged).

## Known Stubs
None — the handler drives the real Plan-03 `run_sync_once` and renders live `unsynced_count` + `format_sync_message` output; the badge and status are backed by real data.

## Issues Encountered
- Full suite surfaced the same 3 pre-existing `SAWarning`s in `test_receipts.py` / `test_returns.py` (identity-key conflicts on deliberate error-path flushes) — out of scope, unchanged, logged here only (already noted in Plans 02/03).

## User Setup Required
None — the surface renders on every page immediately; «Синхронизировать» is a no-op (`Синхронизация не настроена`) until the operator sets `sync_server_url` + `sync_token` in `.env` (SRV-03).

## Next Phase Readiness
- Plan 05 (auto-sync loop) shares the same `_run_lock` and can reuse `_sync_status_context` / `partials/sync_status.html` unchanged — a background tick that records a D-10 result will be reflected on the next page render.
- Full suite: **1108 passed, 12 skipped, 0 failing** after this plan (was 1100; +8 new UI tests).

## Self-Check: PASSED
- FOUND: app/templates/partials/sync_status.html, tests/test_sync_ui.py, app/routes/sync.py, app/routes/__init__.py, app/templates/base.html
- FOUND commits: 22c7eea, 14daed2
- `uv run pytest tests/test_sync_ui.py -q`: 8 passed
- `uv run ruff check` on the changed .py files: All checks passed
- Full suite: 1108 passed, 12 skipped, 0 failing

---
*Phase: 29-online-client-sync*
*Completed: 2026-07-20*
