"""Goods receipt pages (RCP-01/RCP-02): thin routes, writes in app/services/receipts.py."""

from fastapi import APIRouter, Depends, Form, Request, Response
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.receipts import lookup_prefill, recent_receipts, register_receipt

router = APIRouter()

# Route order: literal paths (/receipts/new, /receipts/lookup) MUST stay
# declared before any parameterized /receipts/{...} routes added later.

SAVE_FAILED_ERROR = "Не удалось сохранить. Проверьте данные и попробуйте ещё раз."
CARD_FILL_HINT = "Данные подставлены из карточки товара — новые цены обновят карточку."


@router.get("/receipts/new")
def receipt_new_page(request: Request, session: Session = Depends(get_session)):
    context = {
        "errors": {},
        "form": {},
        "focus_code": False,
        "receipts": recent_receipts(session),
    }
    return templates.TemplateResponse(request, "pages/receipt_form.html", context)


@router.get("/receipts/lookup")
def receipt_lookup(
    request: Request,
    code: str = "",
    name: str = "",
    cost: str = "",
    sale: str = "",
    catalog: str = "",
    session: Session = Depends(get_session),
):
    # Phase 2 D-23 contract: the SERVER decides fill vs no-op, htmx ignores
    # 204. Pitfall 7: a non-empty operator name is never overwritten; PD-10:
    # typed price fields are excluded from the fill (empty-after-strip only).
    if name.strip():
        return Response(status_code=204)
    result = lookup_prefill(session, code)
    if result is None:
        return Response(status_code=204)
    if result["source"] == "product":
        typed = {"cost": cost, "sale": sale, "catalog": catalog}
        fill_fields = [f for f in ("cost", "sale", "catalog") if not typed[f].strip()]
        hint = CARD_FILL_HINT
    else:
        fill_fields = []
        hint = ""  # name_input.html falls back to the dictionary wording
    context = {
        "name": result["name"],
        "hint": hint,
        "source": result["source"],
        "fill_fields": fill_fields,
        "prices": result["prices"],
    }
    return templates.TemplateResponse(request, "partials/receipt_lookup.html", context)


@router.post("/receipts")
def receipt_create(
    request: Request,
    code: str = Form(""),
    name: str = Form(""),
    qty: str = Form(""),
    cost: str = Form(""),
    sale: str = Form(""),
    catalog: str = Form(""),
    warehouse_id: str = Form(""),
    batch_choice: str = Form("new"),
    expiry: str = Form(""),
    location: str = Form(""),
    comment: str = Form(""),
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
        "warehouse_id": warehouse_id,
        "batch_choice": batch_choice,
        "expiry": expiry,
        "location": location,
        "comment": comment,
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
            warehouse_id=warehouse_id,
            batch_choice=batch_choice,
            expiry_raw=expiry,
            location_raw=location,
            comment_raw=comment,
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
