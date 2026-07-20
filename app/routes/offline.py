"""Offline self-upload ingest (OFF-04/OFF-05/OFF-07): login + upload routes.

A THIN caller of the Phase 27 merge engine, mirroring app/routes/sync.py: it
re-implements NO merge, idempotency or conflict logic. `parse_exchange` validates
the payload before any DB touch and `apply_merge` owns all merge semantics (the
origin-UUID replay IS the idempotency mechanism). The route's ONLY additions over
sync_push are the SHA-256 integrity check (D-08) and the schema-version gate
(D-09), both at the route layer BEFORE apply_merge — never inside pure
`parse_exchange`.

Because the ingest routes bypass the session guard (security.OFFLINE_PATH_PREFIX,
D-05), they authenticate IN-BODY: a short-lived, upload-scoped token minted by
`app.services.offline`. No cookies means no CSRF surface (T-30-10), the same
reasoning as the Bearer-token sync tree.

Wired in app/main.py with `include_router(offline.router)` and NO `dependencies=`
(the app-level auth_guard already returns early for the /api/offline/ prefix).

CLAUDE.md safety: the token and the raw uploaded bytes are NEVER logged and NEVER
echoed back to the client. Parse/integrity failures land on a fixed RU result page
(T-28-07 / V7); only the two known schema-version strings are ever interpolated,
autoescaped.
"""

import json

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import JSONResponse
from itsdangerous import BadSignature, SignatureExpired
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import utcnow_iso
from app.db import get_session
from app.models import User
from app.routes import templates
from app.services import offline as offline_service
from app.services.auth import verify_password
from app.services.merge import apply_merge, parse_exchange, payload_digest
from app.services.rate_limit import check_rate_limit
from app.services.sync import current_schema_version

# Belt-and-braces body cap independent of any proxy config (clone of
# sync.MAX_PUSH_BYTES, T-30-09). Kept module-level so the oversized-body test can
# monkeypatch it to a tiny value.
MAX_OFFLINE_BYTES = 32 * 1024 * 1024

# Fixed RU error strings (UI-SPEC Copywriting Contract, T-28-07). HTML-free, no
# enumeration oracle — the same generic message for every login failure mode
# (unknown login / wrong password / deactivated), mirroring auth.py:31.
BAD_CREDENTIALS_ERROR = "Неверный логин или пароль."
RATE_LIMITED_ERROR = "Слишком много попыток. Подождите немного и попробуйте снова."

# The SINGLE narrow CORS header (D-05), scoped to THIS module's login responses
# only. The self-uploading file's `file://` origin is null, so its JS must be
# allowed to read the token. NO Access-Control-Allow-Credentials: the endpoint
# sends no cookies. NO app-wide CORSMiddleware — /api/sync/ stays untouched.
_ACAO = {"Access-Control-Allow-Origin": "*"}

router = APIRouter()


def _result(request: Request, state: str, *, status: int = 200, **ctx) -> Response:
    """Render the S2 no-session result page for `state` (D-01).

    Never renders raw uploaded bytes: only the two known schema-version strings
    (`file_ver`/`server_ver`) are ever passed through `ctx`, autoescaped by Jinja2.
    """
    return templates.TemplateResponse(
        request,
        "offline/result.html",
        {"state": state, **ctx},
        status_code=status,
    )


@router.post("/api/offline/login")
def offline_login(
    login: str = Form(""),
    password: str = Form(""),
    session: Session = Depends(get_session),
) -> Response:
    """Verify creds and mint a short-lived upload token (OFF-04 / D-04).

    Declaring ONLY `login` + `password` (no payload/data field) is what literally
    satisfies "no data sent on failure" — the business data never reaches this
    endpoint. Plain `def` (CLAUDE.md sync-session rule) → FastAPI threadpool.

    Every response carries the SINGLE narrow `_ACAO` header (D-05) and no cookies,
    so the self-uploading file's null-origin JS can read the token without opening
    the /api/sync/ CORS posture. The login body is `x-www-form-urlencoded`, a CORS
    simple request → no preflight.
    """
    login = login.strip()

    # (1) Rate-limit the login bucket FIRST (brute-force blunt, D-05 / T-30-07).
    if not check_rate_limit(f"offline-login:{login}"):
        return JSONResponse(
            {"error": RATE_LIMITED_ERROR}, status_code=429, headers=_ACAO
        )

    # (2) One generic failure for unknown login / wrong password / deactivated —
    # no enumeration oracle (V2 / T-25-04-05). NO token, NO data on failure (D-04).
    user = session.scalar(select(User).where(User.login == login))
    if (
        user is None
        or not verify_password(session, user, password)
        or user.is_active != 1
    ):
        return JSONResponse(
            {"error": BAD_CREDENTIALS_ERROR}, status_code=401, headers=_ACAO
        )

    # (3) Success: mint the upload-scoped token (D-03). Never logged (CLAUDE.md).
    token = offline_service.mint_offline_token(user.id)
    return JSONResponse({"token": token}, headers=_ACAO)


@router.post("/api/offline/upload")
def offline_upload(
    request: Request,
    token: str = Form(...),
    payload: str = Form(...),
    session: Session = Depends(get_session),
) -> Response:
    """Ingest a self-uploaded NDJSON bundle (OFF-05 / OFF-07).

    A near-verbatim mirror of sync_push: the ONLY additions are the SHA-256
    integrity check (gate 4, D-08) and the schema-version gate (gate 5, D-09), both
    BEFORE parse_exchange/apply_merge — never inside the pure engine. Plain `def`
    (CLAUDE.md sync-session rule) → FastAPI threadpool. Every rejection lands on a
    fixed RU result page; raw uploaded bytes are NEVER rendered (T-28-07 / V7).
    """
    # (1) Token gate (T-30-04): expired / tampered / wrong-scope → expired page.
    try:
        offline_service.verify_offline_token(token)
    except (SignatureExpired, BadSignature):
        return _result(request, "expired", status=401)

    # (2) Size cap (T-30-09): belt-and-braces DoS guard, independent of any proxy.
    if len(payload.encode("utf-8")) > MAX_OFFLINE_BYTES:
        return _result(request, "corrupted", status=413)

    # (3) Canonicalize newlines: splitlines() strips CRLF and LF alike, so a form
    # navigation's CRLF normalization yields the SAME record bytes the digest was
    # computed over (Pitfall 1). An empty body is malformed input.
    lines = payload.splitlines()
    if not lines:
        return _result(request, "corrupted", status=400)

    # (4) Integrity (D-08): the digest is over the RECORD lines only (header
    # excluded), so it must match header.payload_sha256 before any DB touch. Never
    # echo the raw bytes — a malformed header or a mismatch both land on «повреждён».
    try:
        header = json.loads(lines[0])
    except json.JSONDecodeError:
        return _result(request, "corrupted", status=400)
    if not isinstance(header, dict):
        return _result(request, "corrupted", status=400)
    record_lines = lines[1:]
    if payload_digest(record_lines) != header.get("payload_sha256"):
        return _result(request, "corrupted", status=400)

    # (5) Schema gate (D-09): exact-match at the route layer, naming BOTH versions;
    # an empty server schema (create_all fixture) skips the gate (Pitfall 7).
    server_schema = current_schema_version(session)
    file_schema = header.get("schema_version", "")
    if not offline_service.schema_version_ok(file_schema, server_schema):
        return _result(
            request,
            "incompatible",
            status=409,
            file_ver=file_schema,
            server_ver=server_schema,
        )

    # (6) Structural validation (BEFORE any DB touch): parse_exchange enforces
    # format_version + record shape. A bad format_version raises ValueError here.
    try:
        batch = parse_exchange(lines)
    except ValueError:
        return _result(request, "corrupted", status=400)

    # (7) All-or-nothing merge (OFF-05, verbatim sync_push idiom): apply_merge
    # never commits, so the route owns the ONE transaction and a poisoned record
    # (e.g. a missing FK parent) rolls the WHOLE batch back. The IntegrityError is
    # deliberately NOT swallowed — the tests assert zero rows persist. The
    # origin-UUID replay IS the idempotency: re-uploading inserts nothing.
    session.rollback()
    with session.begin():
        report = apply_merge(session, batch, server_now=utcnow_iso())

    # reference_inserted is a dict[str, int] (per-kind counts) → sum the values.
    total = (
        report.operations_inserted
        + report.cash_inserted
        + sum(report.reference_inserted.values())
    )
    return _result(
        request,
        "success",
        total=total,
        ops=report.operations_inserted,
        cash=report.cash_inserted,
    )
