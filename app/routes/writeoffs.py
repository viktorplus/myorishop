"""Write-off pages (OPS-01): thin routes, writes in app/services/writeoffs.py."""

import logging

from fastapi import APIRouter, Depends, Form, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Batch, Product
from app.routes import templates
from app.services.batches import open_batches
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

    # LOT-05: an active product also gets its open batches so the shared picker
    # can be oob-swapped into the form (empty state «Нет партий с остатком.»
    # when there are none). Dictionary-only matches have no product row.
    code_clean = code.strip()
    product = session.scalars(
        select(Product).where(Product.code == code_clean, Product.deleted_at.is_(None))
    ).first()
    batches = open_batches(session, product.id) if product is not None else []
    context = {
        "name": result["name"],
        "code": code_clean,
        "batches": batches,
        "selected_batch_id": None,
        "batch_id_value": "",
        "show_empty": product is not None and not batches,
    }
    return templates.TemplateResponse(request, "partials/writeoff_lookup.html", context)


@router.get("/writeoff/batch-pick")
def writeoff_batch_pick(
    request: Request,
    batch_id: str = "",
    code: str = "",
    session: Session = Depends(get_session),
):
    # T-09-08/T-09-12: re-query the open list on every pick (fresh remaining
    # qty) and re-validate the client id's ownership before echoing it back.
    code_clean = code.strip()
    product = session.scalars(
        select(Product).where(Product.code == code_clean, Product.deleted_at.is_(None))
    ).first()
    batches = open_batches(session, product.id) if product is not None else []
    picked: Batch | None = None
    if batch_id and product is not None:
        candidate = session.get(Batch, batch_id)
        if candidate is not None and candidate.product_id == product.id:
            picked = candidate
    context = {
        "code": code_clean,
        "batches": batches,
        "selected_batch_id": picked.id if picked else None,
        "batch_id_value": picked.id if picked else "",
        "show_empty": product is not None and not batches,
    }
    return templates.TemplateResponse(request, "partials/writeoff_batch_wrap.html", context)


@router.post("/writeoff")
def writeoff_create(
    request: Request,
    code: str = Form(""),
    name: str = Form(""),
    qty: str = Form(""),
    reason_code: str = Form(""),
    note: str = Form(""),
    batch_id: str = Form(""),
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
    # LOT-05: resolve the picked batch (if any) for the re-echoed picker on a
    # 422/warn re-render so the operator's selection survives.
    selected_batch = session.get(Batch, batch_id.strip()) if batch_id.strip() else None
    try:
        result, errors = register_writeoff(
            session,
            code=code,
            name=name,
            qty_raw=qty,
            reason_code=reason_code,
            note=note,
            batch_id=batch_id,
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
            "selected_batch": selected_batch,
        }
        return templates.TemplateResponse(
            request, "partials/writeoff_form.html", context, status_code=422
        )

    # D-04/D-09/criterion 4: over-removal — zero writes, warn above the
    # still-intact form (the confirm button re-POSTs the same form via
    # form="writeoff-form" + confirm=1).
    if result and result.get("oversell"):
        context = {
            "errors": {},
            "form": form_echo,
            "focus_code": False,
            "include_oob_rows": False,
            "oversell": result["oversell"],
            "selected_batch": selected_batch,
        }
        return templates.TemplateResponse(request, "partials/writeoff_form.html", context)

    if errors:
        context = {
            "errors": errors,
            "form": form_echo,
            "focus_code": False,
            "include_oob_rows": False,
            "selected_batch": selected_batch,
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
