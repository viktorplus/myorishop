"""Goods receipt pages (RCP-01): thin routes, writes in app/services/receipts.py."""

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.receipts import recent_receipts, register_receipt

router = APIRouter()

# Route order: literal paths (/receipts/new, later /receipts/lookup) MUST stay
# declared before any parameterized /receipts/{...} routes added later.

SAVE_FAILED_ERROR = "Не удалось сохранить. Проверьте данные и попробуйте ещё раз."


@router.get("/receipts/new")
def receipt_new_page(request: Request, session: Session = Depends(get_session)):
    context = {
        "errors": {},
        "form": {},
        "focus_code": False,
        "receipts": recent_receipts(session),
    }
    return templates.TemplateResponse(request, "pages/receipt_form.html", context)


@router.post("/receipts")
def receipt_create(
    request: Request,
    code: str = Form(""),
    name: str = Form(""),
    qty: str = Form(""),
    cost: str = Form(""),
    sale: str = Form(""),
    catalog: str = Form(""),
    session: Session = Depends(get_session),
):
    # Money/qty fields arrive as strings on purpose: Pydantic v2 rejects ""
    # for int | None, and parsing in the service gives the RU errors.
    form_echo = {
        "code": code,
        "name": name,
        "qty": qty,
        "cost": cost,
        "sale": sale,
        "catalog": catalog,
    }
    try:
        result, errors = register_receipt(
            session,
            code=code,
            name=name,
            qty_raw=qty,
            cost_raw=cost,
            sale_raw=sale,
            catalog_raw=catalog,
        )
    except Exception:  # noqa: BLE001 — UI-SPEC: block error, never a raw 500
        context = {
            "errors": {"form": SAVE_FAILED_ERROR},
            "form": form_echo,
            "focus_code": False,
            "include_oob_rows": False,
        }
        return templates.TemplateResponse(
            request, "partials/receipt_form.html", context, status_code=422
        )
    if errors:
        context = {
            "errors": errors,
            "form": form_echo,
            "focus_code": False,
            "include_oob_rows": False,
        }
        return templates.TemplateResponse(
            request, "partials/receipt_form.html", context, status_code=422
        )
    # D-02: success -> fresh empty form + success line + focus back to «Код»;
    # D-04: the refreshed recent list rides along as an oob swap.
    context = {
        "errors": {},
        "form": {},
        "saved": {"name": result["product"].name, "qty": result["operation"].qty_delta},
        "focus_code": True,
        "receipts": recent_receipts(session),
        "include_oob_rows": True,
    }
    return templates.TemplateResponse(request, "partials/receipt_form.html", context)
