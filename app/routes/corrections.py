"""Stock-correction pages (OPS-03): thin routes, writes in app/services/corrections.py.

D-12: this is the SINGLE correction path — it replaces the walking-skeleton
POST /ops (deleted alongside this route's introduction).
"""

import logging

from fastapi import APIRouter, Depends, Form, Request, Response
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.corrections import lookup_prefill, register_correction

router = APIRouter()
logger = logging.getLogger(__name__)

# Route order: the literal /corrections/lookup path MUST stay declared before
# any parameterized /corrections/{...} route added later.

SAVE_FAILED_ERROR = "Не удалось сохранить. Попробуйте ещё раз."


@router.get("/corrections")
def correction_page(request: Request):
    context = {
        "errors": {},
        "form": {},
        "mode": "count",
        "current_qty": None,
        "focus_code": False,
    }
    return templates.TemplateResponse(request, "pages/correction_form.html", context)


@router.get("/corrections/lookup")
def correction_lookup(
    request: Request,
    code: str = "",
    name: str = "",
    session: Session = Depends(get_session),
):
    # D-11: the SERVER decides fill vs 204; a non-empty typed name is never
    # overwritten (Pitfall 7).
    if name.strip():
        return Response(status_code=204)
    result = lookup_prefill(session, code)
    if result is None:
        return Response(status_code=204)
    context = {"name": result["name"], "quantity": result["quantity"]}
    return templates.TemplateResponse(request, "partials/correction_lookup.html", context)


@router.post("/corrections")
def correction_create(
    request: Request,
    code: str = Form(""),
    name: str = Form(""),
    mode: str = Form(""),
    value: str = Form(""),
    note: str = Form(""),
    session: Session = Depends(get_session),
):
    # Mode/qty fields arrive as strings on purpose: parsing/validation
    # happens in the service, which returns RU errors.
    form_echo = {"code": code, "name": name, "value": value, "note": note}
    try:
        result, errors = register_correction(
            session,
            code=code,
            mode=mode,
            value_raw=value,
            note=note,
        )
    except Exception:  # noqa: BLE001 — UI-SPEC: block error, never a raw 500
        logger.exception("register_correction failed")
        context = {
            "errors": {"form": SAVE_FAILED_ERROR},
            "form": form_echo,
            "mode": mode or "count",
            "current_qty": None,
            "focus_code": False,
        }
        return templates.TemplateResponse(
            request, "partials/correction_form.html", context, status_code=422
        )

    if errors:
        context = {
            "errors": errors,
            "form": form_echo,
            "mode": mode or "count",
            "current_qty": None,
            "focus_code": False,
        }
        return templates.TemplateResponse(
            request, "partials/correction_form.html", context, status_code=422
        )

    # D-02 ergonomics: success -> fresh empty form (mode reset to "count") +
    # neutral success line + focus back to «Код».
    context = {
        "errors": {},
        "form": {},
        "mode": "count",
        "current_qty": None,
        "saved": {"name": result["product"].name, "new_qty": result["new_qty"]},
        "focus_code": True,
    }
    return templates.TemplateResponse(request, "partials/correction_form.html", context)
