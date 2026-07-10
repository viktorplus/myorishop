"""Write-off pages (OPS-01): thin routes, writes in app/services/writeoffs.py."""

import logging

from fastapi import APIRouter, Depends, Form, Request, Response
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.receipts import lookup_prefill
from app.services.writeoffs import recent_writeoffs, register_writeoff

router = APIRouter()
logger = logging.getLogger(__name__)

# Route order: the literal /writeoff/lookup path MUST stay declared before
# any parameterized /writeoff/{...} route added later.

SAVE_FAILED_ERROR = "Не удалось сохранить. Проверьте данные и попробуйте ещё раз."


@router.get("/writeoff")
def writeoff_page(request: Request, session: Session = Depends(get_session)):
    context = {
        "errors": {},
        "form": {},
        "focus_code": False,
        "writeoffs": recent_writeoffs(session),
    }
    return templates.TemplateResponse(request, "pages/writeoff_form.html", context)


@router.get("/writeoff/lookup")
def writeoff_lookup(
    request: Request,
    code: str = "",
    name: str = "",
    session: Session = Depends(get_session),
):
    # D-04: reuses the receipt lookup — name only, no price fields. The
    # SERVER decides fill vs 204; a non-empty typed name is never overwritten.
    if name.strip():
        return Response(status_code=204)
    result = lookup_prefill(session, code)
    if result is None:
        return Response(status_code=204)
    context = {"name": result["name"]}
    return templates.TemplateResponse(request, "partials/writeoff_lookup.html", context)


@router.post("/writeoff")
def writeoff_create(
    request: Request,
    code: str = Form(""),
    name: str = Form(""),
    qty: str = Form(""),
    reason_code: str = Form(""),
    note: str = Form(""),
    confirm: str = Form(""),
    session: Session = Depends(get_session),
):
    # Money/qty/reason fields arrive as strings on purpose: Pydantic v2
    # rejects "" for int | None, and parsing/validation happens in the
    # service, which returns RU errors.
    form_echo = {
        "code": code,
        "name": name,
        "qty": qty,
        "reason_code": reason_code,
        "note": note,
    }
    try:
        result, errors = register_writeoff(
            session,
            code=code,
            name=name,
            qty_raw=qty,
            reason_code=reason_code,
            note=note,
            confirm=confirm,
        )
    except Exception:  # noqa: BLE001 — UI-SPEC: block error, never a raw 500
        # WR-03: defensive rollback, mirroring the fix applied to
        # returns.py (CR-03) — this handler doesn't re-query the session
        # today, but a future edit easily could reintroduce that bug.
        session.rollback()
        logger.exception("register_writeoff failed")
        context = {
            "errors": {"form": SAVE_FAILED_ERROR},
            "form": form_echo,
            "focus_code": False,
            "include_oob_rows": False,
        }
        return templates.TemplateResponse(
            request, "partials/writeoff_form.html", context, status_code=422
        )

    # D-04/T-05-03: oversell — zero writes, warn above the still-intact form
    # (the confirm button re-POSTs the same form via form="writeoff-form" +
    # confirm=1).
    if result and result.get("oversell"):
        context = {
            "errors": {},
            "form": form_echo,
            "focus_code": False,
            "include_oob_rows": False,
            "oversell": result["oversell"],
        }
        return templates.TemplateResponse(request, "partials/writeoff_form.html", context)

    if errors:
        context = {
            "errors": errors,
            "form": form_echo,
            "focus_code": False,
            "include_oob_rows": False,
        }
        return templates.TemplateResponse(
            request, "partials/writeoff_form.html", context, status_code=422
        )

    # D-02 (mirrors receipt/sale ergonomics): success -> fresh empty form +
    # neutral success line + focus back to «Код»; the refreshed recent list
    # rides along as an oob swap.
    context = {
        "errors": {},
        "form": {},
        "saved": {"name": result["product"].name, "qty": -result["operation"].qty_delta},
        "focus_code": True,
        "writeoffs": recent_writeoffs(session),
        "include_oob_rows": True,
    }
    return templates.TemplateResponse(request, "partials/writeoff_form.html", context)
