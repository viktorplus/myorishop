"""Mobile return flow (Phase 11 Plan 08): thin route, writes through the
SAME app.services.returns.register_return as desktop.

Entry point: a history card's «Вернуть» action carries sale_id/product_id/
origin_op_id (see mobile_partials/history_cards.html). No standalone tile
(UI-SPEC). `_resolve_origin` below replicates app/routes/returns.py's
module-private helper logic inline — deliberately NOT imported, since it is
`_`-prefixed (module-private, per the plan's read_first note).
"""

import logging

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Operation, Product
from app.routes import templates
from app.services.returns import (
    register_return,
    resolve_return_batch,
    returnable_qty,
    sold_qty,
)

router = APIRouter()
logger = logging.getLogger(__name__)

SAVE_FAILED_ERROR = "Не удалось сохранить. Проверьте данные и попробуйте ещё раз."
ORIGIN_NOT_FOUND_ERROR = "Исходная продажа не найдена."


def _resolve_origin(
    session: Session, *, origin_op_id: str, sale_id: str, product_id: str
) -> Operation | None:
    """T-11-22: only a genuine `sale`-typed Operation with a non-null
    sale_id is ever treated as a valid return origin — identical guard to
    desktop's app.routes.returns._resolve_origin, replicated verbatim so a
    tampered id pointing at a non-sale Operation (e.g. a writeoff) is
    rejected."""
    if origin_op_id:
        origin = session.get(Operation, origin_op_id)
        if origin is not None and origin.type == "sale" and origin.sale_id is not None:
            return origin
    if sale_id and product_id:
        return session.scalars(
            select(Operation)
            .where(
                Operation.sale_id == sale_id,
                Operation.product_id == product_id,
                Operation.type == "sale",
            )
            .order_by(Operation.created_at.desc(), Operation.seq.desc())
            .limit(1)
        ).first()
    return None


def _empty_context(origin_op_id: str, errors: dict[str, str]) -> dict:
    return {
        "origin_op_id": origin_op_id,
        "product": None,
        "sold": 0,
        "remaining": 0,
        "origin_created_at": None,
        "unit_price_cents": None,
        "origin_batch": None,
        "errors": errors,
        "saved": None,
    }


def _origin_context(session: Session, origin: Operation, errors: dict[str, str]) -> dict:
    return {
        "origin_op_id": origin.id,
        "product": session.get(Product, origin.product_id),
        "sold": sold_qty(session, origin.sale_id, origin.product_id),
        "remaining": returnable_qty(session, origin.sale_id, origin.product_id),
        "origin_created_at": origin.created_at,
        # D-07: the frozen origin price, display-only — never an editable input.
        "unit_price_cents": origin.unit_price_cents,
        # D-08: the batch this return restores to, read-only (None -> legacy label).
        "origin_batch": resolve_return_batch(session, origin),
        "errors": errors,
        "saved": None,
    }


@router.get("/m/returns")
def mobile_return_form(
    request: Request,
    sale_id: str = "",
    product_id: str = "",
    origin_op_id: str = "",
    session: Session = Depends(get_session),
):
    origin = _resolve_origin(
        session, origin_op_id=origin_op_id, sale_id=sale_id, product_id=product_id
    )
    if origin is None:
        context = _empty_context(origin_op_id, {"form": ORIGIN_NOT_FOUND_ERROR})
        return templates.TemplateResponse(
            request, "mobile_partials/return_confirm.html", context, status_code=422
        )
    context = _origin_context(session, origin, {})
    return templates.TemplateResponse(request, "mobile_partials/return_confirm.html", context)


@router.post("/m/returns")
def mobile_return_create(
    request: Request,
    origin_op_id: str = Form(""),
    qty: str = Form(""),
    session: Session = Depends(get_session),
):
    origin = session.get(Operation, origin_op_id) if origin_op_id else None
    origin_valid = origin is not None and origin.type == "sale" and origin.sale_id is not None

    try:
        result, errors = register_return(session, origin_op_id=origin_op_id, qty_raw=qty)
    except Exception:  # noqa: BLE001 — UI-SPEC: block error, never a raw 500
        # CR-03: rollback FIRST — an unexpected failure may have left the
        # session needing rollback (e.g. a failed flush/commit); any further
        # query below (_origin_context/_empty_context) would otherwise raise
        # an unhandled PendingRollbackError instead of this graceful 422.
        session.rollback()
        logger.exception("register_return failed")
        context = (
            _origin_context(session, origin, {"form": SAVE_FAILED_ERROR})
            if origin_valid
            else _empty_context(origin_op_id, {"form": SAVE_FAILED_ERROR})
        )
        return templates.TemplateResponse(
            request, "mobile_partials/return_confirm.html", context, status_code=422
        )

    if errors:
        context = (
            _origin_context(session, origin, errors)
            if origin_valid
            else _empty_context(origin_op_id, errors)
        )
        return templates.TemplateResponse(
            request, "mobile_partials/return_confirm.html", context, status_code=422
        )

    # Success -> neutral saved line + explicit "Готово" exit (mobile-specific
    # addition — desktop stays inline in the table, so it has no equivalent
    # button; mobile's return-slot needs an explicit way to leave it).
    context = {
        "origin_op_id": origin_op_id,
        "product": result["product"],
        "sold": sold_qty(session, origin.sale_id, origin.product_id),
        "remaining": result["remaining"],
        "origin_created_at": origin.created_at,
        "unit_price_cents": origin.unit_price_cents,
        "origin_batch": resolve_return_batch(session, origin),
        "errors": {},
        "saved": {"name": result["product"].name, "qty": result["operation"].qty_delta},
    }
    return templates.TemplateResponse(request, "mobile_partials/return_confirm.html", context)
