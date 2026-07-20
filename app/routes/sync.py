"""Token-authenticated sync transport (SYNC-09): POST /api/sync/push.

This router is a THIN caller of the Phase 27 merge engine. It re-implements NO
merge, idempotency or conflict logic — `parse_exchange` validates the payload
before any DB touch and `apply_merge` owns all merge semantics (the origin-UUID
replay IS the idempotency mechanism, SYNC-02). The route's only jobs are:
authenticate the device (require_device), cap the body size (T-28-04), rate-limit
(T-28-12), and own the ONE transaction so a poisoned record rolls the whole batch
back (apply_merge never commits).

Wired in app/main.py with `include_router(sync.router)` and NO `dependencies=`:
`require_device` is declared per-route, so the app-level auth_guard bypass for the
/api/sync/ prefix does not leave this tree unguarded.

CLAUDE.md safety: the Bearer token is read ONLY from the Authorization header,
never from a query string (which lands in proxy logs / browser history), and is
never logged. Parse errors return a fixed RU constant and never echo the
submitted bytes back to the client (T-28-07 / V7).
"""

import dataclasses
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.core import utcnow_iso
from app.db import get_session
from app.models import DeviceToken
from app.routes import templates
from app.services import sync_client
from app.services.merge import apply_merge, parse_exchange, serialize_exchange
from app.services.rate_limit import check_rate_limit
from app.services.security import require_device
from app.services.sync import (
    DEFAULT_PULL_LIMIT,
    collect_reference_records,
    current_schema_version,
)
from app.services.sync_client import (
    SyncResult,
    format_sync_message,
    get_or_create_sync_state,
    record_sync_result,
    unsynced_count,
)

# RU error messages (UI-SPEC Copywriting Contract). HTML-free.
PAYLOAD_TOO_LARGE_ERROR = "Слишком большой объём данных."
RATE_LIMITED_ERROR = "Слишком много запросов. Попробуйте позже."
MALFORMED_BATCH_ERROR = "Некорректный формат данных."
INVALID_CURSOR_ERROR = "Некорректная метка синхронизации."

# NDJSON media type for the pull stream (matches the push Content-Type).
PULL_MEDIA_TYPE = "application/x-ndjson"

# Belt-and-braces body cap: the Caddy `request_body { max_size 32MB }` twin lands
# in Plan 06, but the app must be safe even if the proxy config is wrong or absent.
MAX_PUSH_BYTES = 32 * 1024 * 1024

router = APIRouter()


@router.post("/api/sync/push")
def sync_push(
    request: Request,
    payload: bytes = Body(..., media_type="application/x-ndjson"),
    device: DeviceToken = Depends(require_device),
    session: Session = Depends(get_session),
) -> dict:
    """Merge a pushed NDJSON batch (SYNC-09): thin caller of the Phase 27 engine.

    Plain `def` (NOT async): CLAUDE.md's locked sync-session rule means FastAPI
    runs this in the threadpool. Reading the body via a `Body(...)` parameter
    rather than `await request.body()` is what keeps the handler synchronous.
    """
    # (1) Rate limit on the NON-SECRET token prefix (T-28-12). require_device
    # already committed the last_used_at stamp; with SQLAlchemy's default
    # expire_on_commit that commit EXPIRED `device`, so reading token_prefix here
    # reloads it and autobegins a read-only transaction (step 5 clears it before
    # the merge opens the single owned write transaction).
    rate_key = device.token_prefix
    if not check_rate_limit(rate_key):
        raise HTTPException(status_code=429, detail=RATE_LIMITED_ERROR)

    # (2) Size cap (T-28-04) — check the declared Content-Length first (reject
    # before buffering where possible), then the ACTUAL body length so a missing
    # or lying Content-Length cannot defeat the cap.
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_PUSH_BYTES:
                raise HTTPException(status_code=413, detail=PAYLOAD_TOO_LARGE_ERROR)
        except ValueError:
            pass  # unpar. a garbage header falls through to the len() check below
    if len(payload) > MAX_PUSH_BYTES:
        raise HTTPException(status_code=413, detail=PAYLOAD_TOO_LARGE_ERROR)

    # (3) Decode strictly; a non-UTF-8 body is malformed input.
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail=MALFORMED_BATCH_ERROR) from exc
    lines = text.splitlines()

    # (4) Parse OUTSIDE the transaction — parse_exchange validates before any DB
    # touch by design. Never echo the raw exception text (it can quote attacker
    # input) back to the client (V7).
    try:
        batch = parse_exchange(lines)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=MALFORMED_BATCH_ERROR) from exc

    # (5) The route owns the ONE transaction: apply_merge never commits, so a
    # mid-batch failure rolls the WHOLE batch back (all-or-nothing). Discard the
    # stray read-only transaction the step-1 attribute reload may have autobegun
    # (a no-op if none is open) so this begin() opens the single owned write txn.
    session.rollback()
    with session.begin():
        report = apply_merge(session, batch, server_now=utcnow_iso())

    # (6) Plain-dict MergeReport projection.
    return {
        "operations_inserted": report.operations_inserted,
        "operations_skipped": report.operations_skipped,
        "cash_inserted": report.cash_inserted,
        "cash_skipped": report.cash_skipped,
        "reference_inserted": report.reference_inserted,
        "reference_server_wins": report.reference_server_wins,
        "conflicts": [dataclasses.asdict(c) for c in report.conflicts],
    }


@router.get("/api/sync/pull")
def sync_pull(
    since: str | None = None,
    after_id: str | None = None,
    limit: int = DEFAULT_PULL_LIMIT,
    device: DeviceToken = Depends(require_device),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """Stream one cursor-paged page of REFERENCE records as NDJSON (SYNC-09).

    Plain `def` (NOT async): CLAUDE.md's locked sync-session rule runs this in the
    threadpool. Read-only — it opens NO write transaction and never commits; the
    server never stamps `synced_at` (locked semantic, see app/services/sync.py).
    `require_device` already stamped `last_used_at`.

    The cursor is COMPOSITE `(since, after_id)`: the client MUST echo BOTH the
    `X-Sync-Next-Since` and `X-Sync-Next-After-Id` response headers back as the
    `since` and `after_id` query parameters, or pagination will not terminate
    across a run of identical timestamps. A lone `after_id` with no `since` is
    meaningless and is ignored by `collect_reference_records`.
    """
    # (0) Normalize a blank `?since=` to absent: an empty query value is a common
    # client artifact (templating a blank cursor on the first pull), so treat it as
    # "no cursor" — a first-page pull — rather than failing fromisoformat("") with a
    # 400 (WR-03). `after_id` needs no such guard: a lone/blank after_id with no
    # `since` is already ignored, and it is only ever an indexed PK equality probe.
    since = since or None

    # (1) Rate limit on the NON-SECRET token prefix (T-28-12), exactly as push.
    if not check_rate_limit(device.token_prefix):
        raise HTTPException(status_code=429, detail=RATE_LIMITED_ERROR)

    # (2) Validate `since` early: a non-empty ISO-8601 string. It is only ever a
    # bound parameter in a select() (never interpolated into SQL), but rejecting
    # garbage keeps the contract honest and the error RU (T-28-21).
    if since is not None:
        try:
            datetime.fromisoformat(since)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail=INVALID_CURSOR_ERROR) from exc

    # (3) Pure query — `collect_reference_records` clamps `limit` itself.
    page = collect_reference_records(
        session, since=since, after_id=after_id, limit=limit
    )

    # (4) Serialize through the UNMODIFIED Phase 27 writer, one NDJSON line each.
    lines = serialize_exchange(
        page.records,
        schema_version=current_schema_version(session),
        source_device_id=settings.device_id,
        generated_at=utcnow_iso(),
    )

    # (5) The two cursor halves travel as HTTP headers, NOT in the fixed NDJSON
    # envelope (the Phase 27 engine is untouched). BOTH are emitted together (each
    # omitted only when None): a client with only `since` cannot advance past a
    # run of identical timestamps. StreamingResponse avoids materialising the page
    # as one big string (T-28-12).
    headers: dict[str, str] = {}
    if page.next_since is not None:
        headers["X-Sync-Next-Since"] = page.next_since
    if page.next_after_id is not None:
        headers["X-Sync-Next-After-Id"] = page.next_after_id

    return StreamingResponse(
        (f"{line}\n" for line in lines),
        media_type=PULL_MEDIA_TYPE,
        headers=headers,
    )


# ---------------------------------------------------------------------------
# Manual sync trigger (Phase 29, Plan 04). Unlike the /api/sync/* routes above,
# `/sync/run` is NOT under the SYNC_PATH_PREFIX bypass, so it stays behind the
# app-level auth_guard: a normal logged-in operator (not just an admin) may
# trigger sync (D-01), and the CSRF token is carried by the base.html body
# hx-headers line (T-29-13). It renders the sync_status.html OOB partial.
# ---------------------------------------------------------------------------


def _render_sync_status(
    result: SyncResult, session: Session, *, oob: bool = True
) -> HTMLResponse:
    """Render the OOB sync-status partial for `result` off the CURRENT state.

    Reads the sync_state row + the live unsynced count FRESH from `session`, so
    a post-commit render reflects the just-stamped rows. Only the LOCKED D-12
    strings + the integer count cross into the HTML (T-29-07)."""
    row = get_or_create_sync_state(session)
    message, last_sync_line = format_sync_message(result, row, settings.display_tz)
    html = templates.get_template("partials/sync_status.html").render(
        oob=oob,
        sync_message=message,
        last_sync_line=last_sync_line,
        unsynced=unsynced_count(session),
    )
    return HTMLResponse(html)


@router.post("/sync/run")
def sync_run(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Run one manual push+pull sync and return the OOB status/badge partial.

    Plain `def` (D-04): FastAPI runs it in the threadpool (CLAUDE.md sync-session
    rule). ALWAYS returns 200 — a network failure surfaces as a plain RU D-12
    partial, never a 5xx that base.html's htmx-config would refuse to swap
    (SYNC-06). D-09: the shared `_run_lock` is acquired non-blocking, so a fast
    double-click / an overlapping tick yields the `locked` partial instead of a
    second run. The token and raw exception text are never rendered (T-29-07)."""
    # D-09: single-run guard. A second concurrent caller gets the locked partial.
    if not sync_client._run_lock.acquire(blocking=False):
        return _render_sync_status(SyncResult(status="locked"), session)
    try:
        # SRV-03 no-op: a fresh install with no server configured never hits the
        # network — render the not-configured state without building a client.
        if not settings.sync_server_url or not settings.sync_token:
            return _render_sync_status(SyncResult(status="not_configured"), session)

        client = sync_client.build_sync_client()
        try:
            # The driver is offline-safe (never raises httpx); the broad guard is
            # belt-and-braces so NOTHING can turn into a 5xx (SYNC-06).
            result = sync_client.run_sync_once(session, client=client)
        except Exception:
            result = SyncResult(status="error")
        finally:
            client.close()

        row = get_or_create_sync_state(session)
        last_sync_at = (
            utcnow_iso()
            if result.status in ("ok", "partial")
            else row.last_sync_at
        )
        message, _ = format_sync_message(result, row, settings.display_tz)
        record_sync_result(
            session,
            status=result.status,
            last_result=message,
            last_sync_at=last_sync_at,
        )
        session.commit()
        return _render_sync_status(result, session)
    finally:
        sync_client._run_lock.release()
