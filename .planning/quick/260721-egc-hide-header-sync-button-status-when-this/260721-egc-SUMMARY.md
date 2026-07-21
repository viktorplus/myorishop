---
quick_id: 260721-egc
subsystem: ui
tags: [jinja2, htmx, sync, nav]

provides:
  - "sync_configured / is_server_db booleans in _sync_status_context (app/routes/__init__.py), available on every template render"
  - "Header «Синхронизировать» trigger/status/badge only rendered when sync_server_url is set (paired client)"
  - "nav.server-mode dark style, applied only when database_url resolves to PostgreSQL (deployed central server)"
affects: [ui, sync]

tech-stack:
  added: []
  patterns:
    - "Config-derived booleans exposed via the existing _sync_status_context context processor, gated with plain {% if %} in base.html — no new context processor needed"

key-files:
  created: []
  modified:
    - app/routes/__init__.py
    - app/templates/base.html
    - app/static/style.css
    - tests/test_sync_ui.py

key-decisions:
  - "is_server_db is computed once at the top of _sync_status_context (pure string check on settings.database_url, never touches the DB) and reused identically in both the success and except-Exception return dicts, so it can never be skipped by a DB hiccup"
  - "sync_configured gate nested INSIDE the existing {% if current_user %} block in base.html, so the widget stays both 'logged-in only' and 'configured client only'"

requirements-completed: []

duration: ~20min
completed: 2026-07-21
---

# Quick Task 260721-egc: Hide header sync widget on unconfigured instances + dark server-mode nav Summary

**Header «Синхронизировать» widget now hidden when sync_server_url is unset (e.g. the central server itself); the top nav gets a dark server-mode style only on the PostgreSQL-backed deployed server, so operators can never confuse the server dashboard with a local SQLite client.**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-07-21
- **Tasks:** 2
- **Files modified:** 4 (app/routes/__init__.py, app/templates/base.html, app/static/style.css, tests/test_sync_ui.py)

## Accomplishments

- `_sync_status_context` now exposes `sync_configured` (`bool(sync_server_url)`) and `is_server_db` (`database_url.startswith("postgresql")`) to every template render, in both the success path and the exception fallback.
- `base.html`'s header sync trigger/inflight-indicator/status-partial block is wrapped in `{% if sync_configured %}` (nested inside the existing `{% if current_user %}`) — on the central server (never a sync client, SRV-03) the widget no longer renders its perpetual "Синхронизация не настроена" message.
- `<nav>` carries `class="server-mode"` when `is_server_db` is true; `style.css` adds a `nav.server-mode` rule (dark `#1e293b` background, light link text) as an additive override — the default `nav`/`nav a`/`nav a.active` rules are untouched, so every SQLite-backed local client renders exactly as before.

## Task Commits

Each task was committed atomically:

1. **Task 1: Hide the header sync widget when sync_server_url is not configured** - `4e123e6` (feat)
2. **Task 2: Visually distinguish the PostgreSQL-backed server instance's nav** - `be59323` (feat)

## Files Created/Modified

- `app/routes/__init__.py` - `_sync_status_context` now returns `sync_configured` + `is_server_db` in both branches
- `app/templates/base.html` - sync widget wrapped in `{% if sync_configured %}`; `<nav>` gets conditional `class="server-mode"`
- `app/static/style.css` - new additive `nav.server-mode` / `nav.server-mode a` / `nav.server-mode a.active` rules
- `tests/test_sync_ui.py` - 2 new tests (`test_header_hides_sync_trigger_when_not_configured`, `test_nav_server_mode_on_postgres_db_url`) + a companion default-mode test (`test_nav_default_mode_on_sqlite_db_url`); 4 existing tests updated to explicitly set `sync_server_url` since the widget's visibility is now conditional and the test-suite default is `""`

## Decisions Made

- `is_server_db` is computed once at the top of the function (outside the `try`) since it's a pure string check on already-loaded settings that can never itself raise — this keeps the success and exception-fallback branches trivially in sync, per the plan's explicit instruction.
- Chose to update the 4 pre-existing tests that implicitly relied on the sync widget always being visible (`test_header_shows_sync_trigger_and_status`, `test_badge_hidden_when_zero`, `test_badge_visible_when_unsynced`, `test_context_processor_never_breaks_page`) rather than leave them broken — this was a direct, in-scope consequence of Task 1's behavior change (Rule 3: fix blocking issue to complete the task; the plan's own `<done>` criterion requires "zero regressions").

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed 3 pre-existing tests broken by Task 1's conditional widget visibility, beyond the one test the plan explicitly named**
- **Found during:** Task 1 (verification run of `tests/test_sync_ui.py`)
- **Issue:** The plan explicitly called out updating `test_header_shows_sync_trigger_and_status` to set a non-empty `sync_server_url`, but three other tests also render the header via `client.get("/history")` without setting `sync_server_url` and assert on content now living inside the `{% if sync_configured %}` block: `test_badge_hidden_when_zero`, `test_badge_visible_when_unsynced` (assert on `#sync-badge`/badge count, which live inside `partials/sync_status.html`), and `test_context_processor_never_breaks_page` (asserts on "Ещё не синхронизировано", also inside that partial — and the exception-path `sync_configured` also defaults to `False` in the test suite, so the widget would have stayed hidden even during the SessionLocal-raises scenario).
- **Fix:** Added `monkeypatch.setattr(settings, "sync_server_url", "http://sync")` to all three, matching the pattern the plan specified for the one test it did name.
- **Files modified:** tests/test_sync_ui.py
- **Verification:** `uv run pytest tests/test_sync_ui.py -q` — 11 passed (was 9 before this quick task, +2 new tests), zero regressions.
- **Committed in:** 4e123e6 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 3 — blocking test fixes beyond the plan's single named example)
**Impact on plan:** Necessary to satisfy the plan's own done-criterion ("existing tests/test_sync_ui.py suite has zero regressions"). No scope creep — same file, same fixture pattern the plan already specified.

## Issues Encountered

None beyond the deviation above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Full test suite run after both tasks: `1161 passed, 12 skipped` (no regressions outside `tests/test_sync_ui.py`).
- Manual spot check from `<verification>` (local client shows sync widget + default nav; deployed PostgreSQL server hides widget + dark nav) not performed live in this session — deferred to the operator's next visit to ori.viktorplus.com per the quick task's scope (server-side logic is covered by the new automated tests: `test_nav_server_mode_on_postgres_db_url` proves the class renders when `database_url` starts with `postgresql`, which is exactly the deployed server's configuration).

---
*Quick task: 260721-egc-hide-header-sync-button-status-when-this*
*Completed: 2026-07-21*

## Self-Check: PASSED

All modified files and both task commits (`4e123e6`, `be59323`) verified present on disk / in git log.
