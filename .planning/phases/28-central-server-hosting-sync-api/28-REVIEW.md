---
phase: 28-central-server-hosting-sync-api
reviewed: 2026-07-19T00:00:00Z
depth: standard
files_reviewed: 22
files_reviewed_list:
  - alembic/versions/0018_sync_cursor_trigger_relaxation.py
  - alembic/versions/0019_device_tokens.py
  - app/config.py
  - app/db.py
  - app/main.py
  - app/models.py
  - app/routes/devices.py
  - app/routes/sync.py
  - app/services/backup.py
  - app/services/devices.py
  - app/services/rate_limit.py
  - app/services/security.py
  - app/services/sync.py
  - app/templates/pages/devices.html
  - app/templates/pages/settings.html
  - app/templates/partials/device_rows.html
  - tests/conftest.py
  - tests/test_append_only_cursor.py
  - tests/test_backup.py
  - tests/test_devices.py
  - tests/test_devices_ui.py
  - tests/test_pg_parity.py
  - tests/test_sync_api.py
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
resolved:
  - CR-01 (fixed: 5a90e1c code, 75ad4e8 regression test)
  - WR-03 (fixed: f093268)
deferred:
  - WR-01 (unauth flood relies on upstream Caddy rate limit — proxy ships in Plan 06)
  - WR-02 (in-memory body cap relies on Caddy max_size — proxy ships in Plan 06)
  - IN-01 (session_https_only default — documented deploy step)
  - IN-02 (cosmetic size label for 0-byte file)
---

# Phase 28: Code Review Report

**Reviewed:** 2026-07-19
**Depth:** standard
**Files Reviewed:** 22
**Status:** issues_found

## Summary

Phase 28 opens the token-authenticated sync API. The auth-bypass prefix scoping,
per-device Bearer gate, token storage (SHA-256 hex + constant-time
`compare_token`), append-only trigger relaxation (SQLite `IS NOT` / PG
`IS DISTINCT FROM` with the `payload::text` cast), the dialect-guarded backup, and
the environment-driven cookie `Secure` flag are all implemented carefully and
well tested. The auth surface (Bearer-only sync tree vs session-only HTML tree)
is cross-tested in both directions and holds.

However, the **pull cursor query silently drops reference rows** during multi-kind
pagination — a data-loss defect that directly contradicts the project's Core
Value ("without losing any data") and the module's own docstring. This is the
headline finding. Two further hardening gaps weaken the stated DoS protection.

The single BLOCKER below must be fixed before this ships as the sync foundation
that Phase 29 clients depend on.

## Critical Issues

### CR-01: Paginated `/api/sync/pull` silently omits reference rows across kinds (data loss)

**File:** `app/services/sync.py:195-207` (the `elif since is not None:` branch)
**Issue:**
`collect_reference_records` walks the six PULL_KINDS in FK order with a single
composite `(since, after_id)` cursor. On a **paging-continuation** request (both
`since` and `after_id` present, so `resume_kind` is resolved), the code applies
`where(column >= since)` to every kind *after* the resume kind:

```python
if not passed_resume:
    if kind != resume_kind:
        continue
    stmt = stmt.where(or_(column > since, and_(column == since, model.id > after_id)))
    passed_resume = True
elif since is not None:            # <-- fires for kinds AFTER resume_kind too
    stmt = stmt.where(column >= since)
```

But `since` on a continuation is the **advanced** cursor value carried over from
the *previous* kind's timeline (`next_since` = the last delivered row's
`updated_at`/`created_at`), not the client's original watermark. Kinds after the
resume kind have an **independent** timeline, so filtering them by that unrelated
advanced `since` drops every row whose cursor value is earlier — and those rows
are never re-offered on any later page, so the client never receives them.

This contradicts the function's own docstring, which states kinds after the
resume kind get a **"full scan (no lower bound)"** (`app/services/sync.py:160`).
The code implements a lower bound instead.

Worked example (incremental sync from `T=2026-01-01`, `limit=2`):
- warehouses w1..w3 (updated 2026-06-01/02/03), products p1 (2026-03-01), p2 (2026-07-01)
- Page 1 (`since=T`, `after_id=None`) → `[w1, w2]`, cursor → `(2026-06-02, w2)`
- Page 2 (`since=2026-06-02`, `after_id=w2`) → resume_kind=warehouse → `w3`, then
  products filtered by `updated_at >= 2026-06-02` → **only p2**; **p1 is dropped**.
- Page 3 resumes at product past p2 → empty → client stops.

Net: **p1 is never delivered.** Any reference row (product, customer, dictionary,
batch, sale) in a kind after the resume kind whose cursor predates the advanced
`since` is silently lost. The existing tests only paginate within a *single* kind
(`test_pull_paginates_past_identical_timestamps`, `test_pull_limit_and_next_since`
seed only products), so the multi-kind omission is uncaught.

**Fix:** Only the *first* incremental page (`resume_kind is None`, `since` set,
`after_id` None) may lower-bound every kind by `>= since`. On a paging
continuation, kinds after the resume kind must be full-scanned (matching the
docstring). Over-delivery of older rows is safe because the Phase 27 reference
upsert is idempotent ("a small overlap is free", per this module).

```python
    limit = _clamp_limit(limit)

    resume_kind: str | None = None
    if since is not None and after_id is not None:
        resume_kind = _resume_kind(session, after_id)
    is_paging = resume_kind is not None   # continuation, not a first page

    ...
        if not passed_resume:
            if kind != resume_kind:
                continue
            stmt = stmt.where(
                or_(column > since, and_(column == since, model.id > after_id))
            )
            passed_resume = True
        elif since is not None and not is_paging:
            # FIRST incremental page only: lower-bound every kind by `since`.
            # On a continuation, kinds after the resume kind have not started
            # and must be scanned in full (idempotent upsert makes overlap free).
            stmt = stmt.where(column >= since)
```

Add a regression test that paginates across a kind boundary with a later kind
holding rows whose cursor value is *earlier* than the resume `since`, and assert
the full seeded set is collected with no omissions.

## Warnings

### WR-01: Rate limiter runs after authentication, so the primary DoS vector is unthrottled

**File:** `app/routes/sync.py:70-77` and `app/routes/sync.py:148-150`; gate in
`app/services/security.py:206-237`
**Issue:**
`check_rate_limit` is called *inside* the handler body, but `require_device` is a
route dependency that runs *first*. Two consequences that undercut the stated
purpose ("DoS protection ... caps request volume on a small VPS",
`app/services/rate_limit.py:1-7`):

1. **Unauthenticated floods are never rate-limited.** A request with a missing or
   bogus token is rejected by `require_device` before `check_rate_limit` is ever
   reached. Each such request still performs an indexed `SELECT` in
   `lookup_active_token` (`app/services/devices.py:102-107`). The cheap,
   high-volume attack path — hammering with garbage tokens — bypasses the limiter
   entirely.
2. **Authenticated requests that will be 429'd still write to the DB first.**
   `require_device` calls `touch_last_used`, which issues an `UPDATE ... COMMIT`
   (`app/services/devices.py:113-120`) on *every* verified request — including
   ones the limiter is about to reject. The limiter therefore does not protect the
   DB write it is supposed to shield.

**Fix:** Move the volume cap ahead of the expensive auth/DB work. A lightweight
option: rate-limit on a stable client key (e.g. the Bearer prefix parsed from the
header, or the peer IP behind the proxy) in a small dependency ordered *before*
`require_device`, or gate `touch_last_used` behind the limiter. At minimum,
document that the in-process limiter is effective only for authenticated volume
and that unauthenticated flood protection relies entirely on the upstream Caddy
proxy.

### WR-02: Body-size cap cannot prevent full in-memory buffering

**File:** `app/routes/sync.py:57-90`
**Issue:**
`payload: bytes = Body(...)` makes Starlette read the **entire** request body into
memory before the handler runs. The `len(payload) > MAX_PUSH_BYTES` check
(line 89) therefore fires only *after* the full body is already buffered. The
Content-Length pre-check (lines 82-88) helps only when the header is honest; the
docstring's claim that "a missing or lying Content-Length cannot defeat the cap"
is true for *rejection* but false for *memory consumption* — an attacker sending a
large body with no/short Content-Length still forces the server to buffer it all
before the 413. In-app memory is thus bounded only by the upstream proxy
(`request_body { max_size 32MB }`, noted as landing in Plan 06), not by this code.

**Fix:** Stream and cap incrementally instead of binding the whole body, e.g. read
`request.stream()` in chunks and abort past `MAX_PUSH_BYTES` before accumulating
more — or explicitly document that this cap is a post-buffer belt-and-braces
check and that the real memory bound is the Caddy `max_size`, so the app must
never be exposed without that proxy.

### WR-03: `sync_pull` accepts an empty `since` only to reject it with a 400

**File:** `app/routes/sync.py:127-159`
**Issue:**
With `since: str | None = None`, a request of `?since=` binds `since` to the empty
string (not `None`). `datetime.fromisoformat("")` raises, so the client gets a 400
`INVALID_CURSOR_ERROR`. That is defensible, but an empty query value is a common
client artifact (e.g. templating a blank cursor on the first pull), and turning it
into a hard error rather than treating it as "no cursor" is a foot-gun for the
Phase 29 client author.

**Fix:** Normalize blank to absent before validation, e.g.
`since = since or None` at the top of the handler, so `?since=` behaves like a
first-page pull instead of a 400.

## Info

### IN-01: `session_https_only` defaults to False on a public-facing app

**File:** `app/config.py:36-42`, `app/main.py:81-86`
**Issue:** The session cookie `Secure` flag defaults off and must be turned on via
`SESSION_HTTPS_ONLY=true` in the server env. The rationale (localhost/run.bat and
the test suite are plain HTTP) is sound and documented, but it makes cookie
security an easily-forgotten deploy step on the very phase that first exposes the
app to the internet. Consider failing loudly (or warning at startup) when a
PostgreSQL/`database_url`-driven production config is detected with
`session_https_only=False`, so a missed env var is caught rather than silently
shipping non-Secure cookies.

### IN-02: `_size_label` reports "1 КБ" for a 0-byte file

**File:** `app/services/backup.py:81-86`
**Issue:** `max(1, size // 1024)` renders a 0-byte backup as "1 КБ". Harmless
cosmetically, but a genuinely empty/failed snapshot would be mislabelled as
non-empty in the backup list. Low priority; consider a distinct "0 КБ" / "пусто"
rendering if empty snapshots are ever surfaced to the operator.

---

_Reviewed: 2026-07-19_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
