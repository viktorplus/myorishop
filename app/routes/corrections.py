"""Stock-correction pages (OPS-03): thin routes, writes in app/services/corrections.py.

D-12: this is the SINGLE correction path — it replaces the walking-skeleton
POST /ops (deleted alongside this route's introduction).
"""

import logging

from fastapi import APIRouter, Depends, Form, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Batch, Product
from app.routes import templates
from app.services.batches import open_batches
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

    # LOT-05: an active product also gets its open batches so the shared picker
    # can be oob-swapped into the form. The current-qty hint is now batch-scoped
    # (Pitfall 7): no batch is picked yet at lookup time, so it resets to «—»
    # (the real remaining arrives on /corrections/batch-pick).
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
        "batch_qty": None,
        "show_empty": product is not None and not batches,
    }
    return templates.TemplateResponse(request, "partials/correction_lookup.html", context)


@router.get("/corrections/batch-pick")
def correction_batch_pick(
    request: Request,
    batch_id: str = "",
    code: str = "",
    session: Session = Depends(get_session),
):
    # T-09-08/T-09-12: re-query the open list (fresh remaining qty) and
    # re-validate the client id's ownership before echoing it back.
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
        # Pitfall 7: the batch-scoped current-qty hint is oob-refreshed to the
        # picked batch's remaining (or reset to «—» when the pick cleared).
        "batch_qty": picked.quantity if picked else None,
        "show_empty": product is not None and not batches,
    }
    return templates.TemplateResponse(request, "partials/correction_batch_pick.html", context)


@router.post("/corrections")
def correction_create(
    request: Request,
    code: str = Form(""),
    name: str = Form(""),
    mode: str = Form(""),
    value: str = Form(""),
    note: str = Form(""),
    batch_id: str = Form(""),
    confirm: str = Form(""),
    session: Session = Depends(get_session),
):
    # Mode/qty fields arrive as strings on purpose: parsing/validation
    # happens in the service, which returns RU errors.
    form_echo = {"code": code, "name": name, "value": value, "note": note}
    # LOT-05: resolve the picked batch (if any) so a 422/warn re-render re-echoes
    # the operator's selection and the batch-scoped current-qty hint survives.
    selected_batch = session.get(Batch, batch_id.strip()) if batch_id.strip() else None
    batch_qty = selected_batch.quantity if selected_batch is not None else None
    try:
        result, errors = register_correction(
            session,
            code=code,
            mode=mode,
            value_raw=value,
            note=note,
            batch_id=batch_id,
            confirm=confirm,
        )
    except Exception:  # noqa: BLE001 — UI-SPEC: block error, never a raw 500
        # WR-03: defensive rollback, mirroring the fix applied to
        # returns.py (CR-03) — this handler doesn't re-query the session
        # today, but a future edit easily could reintroduce that bug.
        session.rollback()
        logger.exception("register_correction failed")
        context = {
            "errors": {"form": SAVE_FAILED_ERROR},
            "form": form_echo,
            "mode": mode or "count",
            "current_qty": None,
            "focus_code": False,
            "selected_batch": selected_batch,
            "batch_qty": batch_qty,
        }
        return templates.TemplateResponse(
            request, "partials/correction_form.html", context, status_code=422
        )

    # D-09/criterion 4: over-removal — zero writes, warn above the still-intact
    # form (the confirm button re-POSTs the same form via form="correction-form"
    # + confirm=1).
    if result and result.get("oversell"):
        context = {
            "errors": {},
            "form": form_echo,
            "mode": mode or "count",
            "current_qty": None,
            "focus_code": False,
            "oversell": result["oversell"],
            "selected_batch": selected_batch,
            "batch_qty": batch_qty,
        }
        return templates.TemplateResponse(request, "partials/correction_form.html", context)

    if errors:
        context = {
            "errors": errors,
            "form": form_echo,
            "mode": mode or "count",
            "current_qty": None,
            "focus_code": False,
            "selected_batch": selected_batch,
            "batch_qty": batch_qty,
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
