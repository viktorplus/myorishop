"""Admin device-token routes (SYNC-09): thin over app/services/devices.py.

Registered in app/main.py behind `require_role("administrator")`, so these
handlers never re-check the role — the include_router dependency is the
server-side boundary. Every validation / mint / revoke rule stays in the fat
device service (app/services/devices.py); these routes only wire HTTP →
service → template swap (users.py precedent).

Paths: GET /settings/devices (page + HX rows), POST /settings/devices (mint),
POST /settings/devices/{token_id}/revoke.

CLAUDE.md safety — the INVERSE of the users.py password line: the minted token
plaintext IS rendered exactly once into the response fragment that follows a
successful mint. It is NEVER stored, NEVER re-fetchable on any later request,
and NEVER logged. Only its SHA-256 digest lives at rest (app/services/devices).

Note: app/routes/devices.py and app/services/devices.py share a basename — the
service functions are imported explicitly below and never shadowed.
"""

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.devices import list_device_tokens, mint_token, revoke_token

router = APIRouter()

# Neutral notice lines (UI-SPEC Copywriting Contract). No green success styling.
DEVICE_CREATED_NOTICE = "Токен устройства создан."
DEVICE_REVOKED_NOTICE = "Токен устройства отозван."
TOKEN_SHOWN_ONCE_WARNING = "Скопируйте токен сейчас — он больше не будет показан."


def _rows_context(session: Session, **extra) -> dict:
    """Shared context for the device-rows partial (all tokens + optional flags)."""
    return {"tokens": list_device_tokens(session), **extra}


@router.get("/settings/devices")
def devices_page(request: Request, session: Session = Depends(get_session)):
    context = _rows_context(session)
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "partials/device_rows.html", context)
    return templates.TemplateResponse(request, "pages/devices.html", context)


@router.post("/settings/devices")
def device_create(
    request: Request,
    label: str = Form(""),
    device_id: str = Form(""),
    session: Session = Depends(get_session),
):
    result, errors = mint_token(session, device_id=device_id, label=label)
    if errors:
        # The create form lives in pages/devices.html OUTSIDE #devices-table and
        # is not swapped, so the operator's typed values survive naturally; the
        # inline errors render at the top of the refreshed table region.
        context = _rows_context(session, errors=errors)
        return templates.TemplateResponse(
            request, "partials/device_rows.html", context, status_code=422
        )
    _, plaintext = result
    # The plaintext travels ONLY in this single response context — never into the
    # session, a redirect target, a query string, or a log line. After this
    # render it is unrecoverable (only its SHA-256 digest is stored).
    context = _rows_context(
        session,
        notice=DEVICE_CREATED_NOTICE,
        new_token_plaintext=plaintext,
        token_warning=TOKEN_SHOWN_ONCE_WARNING,
    )
    return templates.TemplateResponse(request, "partials/device_rows.html", context)


@router.post("/settings/devices/{token_id}/revoke")
def device_revoke(
    request: Request, token_id: str, session: Session = Depends(get_session)
):
    # Revocation is the ONLY mitigation for a stolen token (no expiry, by
    # decision), so this control is load-bearing security — it must actually
    # soft-disable the row (never delete it; the audit trail must survive).
    _, errors = revoke_token(session, token_id)
    if errors:
        context = _rows_context(session, errors=errors)
        return templates.TemplateResponse(
            request, "partials/device_rows.html", context, status_code=422
        )
    context = _rows_context(session, notice=DEVICE_REVOKED_NOTICE)
    return templates.TemplateResponse(request, "partials/device_rows.html", context)
