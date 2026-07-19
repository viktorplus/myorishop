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

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core import utcnow_iso
from app.db import get_session
from app.models import DeviceToken
from app.services.merge import apply_merge, parse_exchange
from app.services.rate_limit import check_rate_limit
from app.services.security import require_device

# RU error messages (UI-SPEC Copywriting Contract). HTML-free.
PAYLOAD_TOO_LARGE_ERROR = "Слишком большой объём данных."
RATE_LIMITED_ERROR = "Слишком много запросов. Попробуйте позже."
MALFORMED_BATCH_ERROR = "Некорректный формат данных."

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
    # (1) Rate limit on the NON-SECRET token prefix (T-28-12).
    if not check_rate_limit(device.token_prefix):
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
    # mid-batch failure rolls the WHOLE batch back (all-or-nothing).
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
