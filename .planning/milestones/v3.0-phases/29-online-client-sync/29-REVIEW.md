---
phase: 29-online-client-sync
reviewed: 2026-07-20T03:19:15Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - alembic/versions/0020_sync_state_and_unsynced_indexes.py
  - app/config.py
  - app/main.py
  - app/models.py
  - app/routes/__init__.py
  - app/routes/settings.py
  - app/routes/sync.py
  - app/services/settings.py
  - app/services/sync_client.py
  - app/templates/base.html
  - app/templates/pages/settings.html
  - app/templates/partials/sync_status.html
  - tests/conftest.py
  - tests/test_autosync.py
  - tests/test_ledger.py
  - tests/test_pg_parity.py
  - tests/test_sync_client.py
  - tests/test_sync_ui.py
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 29: Code Review Report

**Reviewed:** 2026-07-20T03:19:15Z
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

Reviewed the Phase 29 online client-sync feature: the pure state/presentation
layer (`sync_client.py`), the network driver (push FK-closure + server-wins
pull), the manual `/sync/run` trigger, the Settings auto-sync control, the
`sync_state` migration/model, the every-page header status surface, and the
lifespan interval loop.

Overall the security posture is solid: the `sync_token` is `.env`-only, never a
DB column, never rendered (verified by `test_web_settings_never_renders_token`),
never logged, and travels only in the `Authorization` header. Only fixed D-12
Russian strings + integer counts cross into HTML — no raw server bytes are
interpolated. CSRF, auth bypass scoping (`/api/sync/` vs `/sync/run`), the
stamp-after-2xx ordering, the composite pull cursor, and the server-wins upsert
that preserves local-derived `quantity` are all correct.

The findings below concern (1) a client-side htmx swap defect that erases the
manual-sync control after its first use, (2) the driver's offline-safety
contract leaking non-`httpx` exceptions out of the pull stage (breaking the D-10
"record every attempt" guarantee on the auto-sync tick), (3) a write performed
on the page-render read path, and minor coupling/dead-value issues.

## Critical Issues

### CR-01: Manual «Синхронизировать» trigger erases its own label after first click

**File:** `app/templates/base.html:61`
**Issue:** The trigger `<a hx-post="/sync/run" hx-indicator="#sync-inflight" ...>`
has neither `hx-target` nor `hx-swap`, so htmx uses the defaults: swap style
`innerHTML` into the triggering `<a>` itself. But `POST /sync/run` returns
`sync_status.html` rendered with `oob=True`, i.e. a response whose *only* two
elements (`#sync-status`, `#sync-badge`) both carry `hx-swap-oob="true"`. htmx
extracts and out-of-band-swaps both elements, leaving an empty (whitespace-only)
"main" fragment — which it then swaps into the `<a>`'s `innerHTML`, erasing the
"Синхронизировать" text. After one manual sync the header control becomes an
empty, effectively unusable clickable region until a full page reload.

This is the codebase's own established idiom failing: every other all-OOB
response is triggered by an element carrying `hx-swap="none"`
(`app/templates/pages/product_form.html:50`, and the `correction_lookup` /
`receipt_lookup` all-OOB responses). The sync trigger omits it. The TestClient
UI tests (`test_sync_run_returns_oob_partial`) cannot catch this because they do
not execute htmx — they only assert the OOB attribute and message are present in
the response text.

**Fix:**
```html
<a hx-post="/sync/run" hx-swap="none" hx-indicator="#sync-inflight"
   style="margin-left:auto;cursor:pointer">Синхронизировать</a>
```

## Warnings

### WR-01: `run_sync_once` leaks non-`httpx` exceptions from the pull stage — tick stops recording results (D-10)

**File:** `app/services/sync_client.py:390-397` (and `488-522`)
**Issue:** The docstring promises "It NEVER re-raises `httpx` errors to the
caller" and maps offline/error paths to a `SyncResult`. But the pull stage is
only guarded by `except httpx.HTTPError`:

```python
try:
    pulled = _pull_all(session, client)
except httpx.HTTPError:
    return SyncResult(status="partial", ...)
```

`_pull_all` → `_apply_pull_page` calls `recompute_derived` (which *raises
ValueError* on an invariant mismatch) inside `with session.begin()`, and any FK
`IntegrityError` from applying a server reference row propagates the same way.
Neither is an `httpx.HTTPError`, so both escape `run_sync_once`.

- In the **background tick** (`run_sync_tick`), `run_sync_once` is called outside
  any broad `except`, so such an error unwinds past `record_sync_result`. The
  loop survives only because `_auto_sync_iteration` swallows it — but the D-10
  "a failure is recorded as reliably as a success" contract is violated: no
  result is written and `last_status`/`last_sync_at` go stale/misleading.
- In the **manual path** the outer `except Exception` catches it, but the push
  already committed and stamped `synced_at`, so a successful push followed by a
  failed pull is reported as `status="error"` instead of `partial`.

**Fix:** Make the driver truly non-raising and preserve push credit — either
broaden the pull guard, or wrap the tick's driver call like the manual handler:
```python
try:
    pulled = _pull_all(session, client)
except httpx.HTTPError:
    return SyncResult(status="partial", pushed=pushed, pushed_total=pushed_total)
except Exception:
    # a poisoned pull page must not defeat the durable push nor the D-10 record
    return SyncResult(status="partial", pushed=pushed, pushed_total=pushed_total)
```
and/or add `except Exception: result = SyncResult(status="error")` around
`run_sync_once` inside `run_sync_tick` so every tick records a result.

### WR-02: Header context processor performs a write (INSERT + flush) on every page render

**File:** `app/routes/__init__.py:54-68` (via `sync_client.get_or_create_sync_state`, `app/services/sync_client.py:82-91`)
**Issue:** `_sync_status_context` runs on every `TemplateResponse` and calls
`get_or_create_sync_state(session)`, which on a DB with no `sync_state` row does
`session.add(row); session.flush()` — a write that acquires a SQLite
write/reserved lock. The context-processor session is never committed (the `with
SessionLocal()` block exits and rolls back), so on a fresh install the singleton
is INSERTed-then-rolled-back on *every* page load, never persisting through this
path, and each read-only page render takes a write lock. Under the background
auto-sync tick writing `sync_state` concurrently this is a needless
"database is locked" contention surface, and the flush cost is paid per render.

**Fix:** Use a read-only accessor on the render path — read the row with
`session.get(SyncState, 1)` and treat `None` as the never-synced default,
without inserting:
```python
row = session.get(SyncState, 1)
last = row.last_sync_at if row else None
message = (row.last_result if row else "") or ""
```
Reserve `get_or_create_sync_state` for the write paths (`/sync/run`,
`run_sync_tick`, `save_autosync_config`) that actually commit.

### WR-03: Offloaded sync thread can outlive lifespan cancellation

**File:** `app/main.py:84, 114-119`
**Issue:** The tick is offloaded with `await anyio.to_thread.run_sync(sync_client.run_sync_tick)`.
On shutdown the lifespan does `auto_sync_task.cancel()` then
`await auto_sync_task` (suppressing `CancelledError`). Cancellation makes the
awaiting coroutine raise `CancelledError` immediately, but the worker *thread*
cannot be cancelled — it keeps running `run_sync_tick`, which is mid-transaction
(`session.commit()` on `sync_state`). `await auto_sync_task` therefore returns
while a DB write is still in flight, and app/engine teardown can then race the
thread's commit, producing a stray unhandled exception in the detached thread
(and, at worst, a half-applied `record_sync_result`).

**Fix:** Bound the shutdown wait on the offloaded work, e.g. offload through a
cancel-scope / task group that is awaited to completion, or gate the tick's DB
work behind a shutdown flag checked before `session.commit()`. At minimum,
document that shutdown may leave one in-flight tick and ensure its commit failure
is swallowed inside `run_sync_tick` rather than surfacing on a dead loop.

## Info

### IN-01: `_apply_pull_page` return value is dead; pull count can diverge from applied rows

**File:** `app/services/sync_client.py:449, 477-479`
**Issue:** `_apply_pull_page` computes and returns `applied`, but `_pull_all`
discards it (`with session.begin(): _apply_pull_page(session, batch)`) and
instead accumulates `pulled += len(batch.records)`. Today the two are equal
because the server pull is reference-only, but `_apply_pull_page` silently drops
any record whose kind is not in `_REFERENCE_INSERT_ORDER` (e.g. a stray
`operation`) while `len(batch.records)` still counts it, so the reported
`pulled` would overcount. The returned `applied` is simply never used.

**Fix:** Use the returned value: `pulled += _apply_pull_page(session, batch)`
(after moving it to return from inside the `with` block), so the count reflects
rows actually applied.

### IN-02: `sync_client` couples to `merge`'s private names

**File:** `app/services/sync_client.py:250-252, 326, 407-439`
**Issue:** The driver reaches into merge internals: `merge._IN_CHUNK`,
`merge._partition_new`, `merge._reference_row`, `merge._REFERENCE_INSERT_ORDER`.
Depending on another module's underscore-private API is fragile — a refactor of
`merge` internals silently breaks the client. (This mirrors an existing pattern
in the codebase, so it is informational.)

**Fix:** Promote the shared primitives the client legitimately needs
(`REFERENCE_INSERT_ORDER`, `IN_CHUNK`, `partition_new`, `reference_row`) to
public names in `merge`, or expose a small public helper the client calls.

---

_Reviewed: 2026-07-20T03:19:15Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
