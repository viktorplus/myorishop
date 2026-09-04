"""Return pages (OPS-02): thin routes, writes in app/services/returns.py."""

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
from app.services.sales import recent_sales

router = APIRouter()
logger = logging.getLogger(__name__)

SAVE_FAILED_ERROR = "Не удалось сохранить. Проверьте данные и попробуйте ещё раз."
ORIGIN_NOT_FOUND_ERROR = "Исходная продажа не найдена."


def _resolve_origin(
    session: Session, *, origin_op_id: str, sale_id: str, product_id: str
) -> Operation | None:
    """D-05: resolve the origin `sale` op.

    Prefers the explicit origin_op_id (the id the «Вернуть» link passes);
    falls back to the latest `sale` op matching sale_id+product_id when
    origin_op_id is blank or unresolvable (the entry point may only carry
    those two identifiers).
    """
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


def _origin_business_day(origin: Operation) -> str:
    """D-24: the day the «Возврат из продажи от …» label must name.

    The origin sale's BUSINESS date — the day the goods actually changed hands,
    not the day the row was typed in. A pre-0027 row (DATE-08) still carries
    business_date IS NULL, so it falls back to the UTC prefix of created_at,
    the same fallback business_date_expr uses in SQL. The result is a 10-char
    ISO date and MUST be rendered with `| ru_date`, never `| local_dt`:
    iso_to_local on a date-only string builds a naive datetime and prints a
    bogus time.
    """
    return origin.business_date or origin.created_at[:10]


def _empty_context(origin_op_id: str, errors: dict[str, str], op_date: str = "") -> dict:
    return {
        "origin_op_id": origin_op_id,
        "product": None,
        "sold": 0,
        "remaining": 0,
        "origin_business_day": None,
        "unit_price_cents": None,
        "origin_batch": None,
        "errors": errors,
        "op_date": op_date,
        "saved": None,
    }


def _origin_context(
    session: Session, origin: Operation, errors: dict[str, str], op_date: str = ""
) -> dict:
    return {
        "origin_op_id": origin.id,
        "product": session.get(Product, origin.product_id),
        "sold": sold_qty(session, origin.sale_id, origin.product_id),
        "remaining": returnable_qty(session, origin.sale_id, origin.product_id),
        "origin_business_day": _origin_business_day(origin),
        # D-07: the frozen origin price, display-only — never an editable input.
        "unit_price_cents": origin.unit_price_cents,
        # D-08: the batch this return restores to, read-only (None -> legacy label).
        "origin_batch": resolve_return_batch(session, origin),
        "errors": errors,
        # DATE-01: the flat echo key return_form.html reads, so a 422 redisplays
        # the date the operator typed instead of snapping back to today.
        "op_date": op_date,
        "saved": None,
    }


@router.get("/returns")
def return_form_page(
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
            request, "partials/return_form.html", context, status_code=422
        )
    context = _origin_context(session, origin, {})
    return templates.TemplateResponse(request, "partials/return_form.html", context)


@router.post("/returns")
def return_create(
    request: Request,
    origin_op_id: str = Form(""),
    qty: str = Form(""),
    op_date: str = Form(""),
    session: Session = Depends(get_session),
):
    origin = session.get(Operation, origin_op_id) if origin_op_id else None
    origin_valid = origin is not None and origin.type == "sale" and origin.sale_id is not None

    try:
        result, errors = register_return(
            session, origin_op_id=origin_op_id, qty_raw=qty, op_date=op_date
        )
    except Exception:  # noqa: BLE001 — UI-SPEC: block error, never a raw 500
        # CR-03: rollback FIRST — an unexpected failure may have left the
        # session needing rollback (e.g. a failed flush/commit); any further
        # query below (_origin_context/_empty_context) would otherwise raise
        # an unhandled PendingRollbackError instead of this graceful 422.
        session.rollback()
        # WR-02 analog: log so a real bug isn't silently reduced to a
        # generic user-facing message with no server-side trace.
        logger.exception("register_return failed")
        context = (
            _origin_context(session, origin, {"form": SAVE_FAILED_ERROR}, op_date)
            if origin_valid
            else _empty_context(origin_op_id, {"form": SAVE_FAILED_ERROR}, op_date)
        )
        return templates.TemplateResponse(
            request, "partials/return_form.html", context, status_code=422
        )

    if errors:
        context = (
            _origin_context(session, origin, errors, op_date)
            if origin_valid
            else _empty_context(origin_op_id, errors, op_date)
        )
        return templates.TemplateResponse(
            request, "partials/return_form.html", context, status_code=422
        )

    # D-06: success -> neutral saved line + oob refresh of recent-sales so
    # the remaining-returnable count updates.
    context = {
        "origin_op_id": origin_op_id,
        "product": result["product"],
        "sold": sold_qty(session, origin.sale_id, origin.product_id),
        "remaining": result["remaining"],
        "origin_business_day": _origin_business_day(origin),
        "unit_price_cents": origin.unit_price_cents,
        "origin_batch": resolve_return_batch(session, origin),
        "errors": {},
        # A saved return starts the next one from today, not from the date the
        # previous one used — the echo exists for the 422 path only.
        "op_date": "",
        "saved": {"name": result["product"].name, "qty": result["operation"].qty_delta},
        "sales": recent_sales(session),
        "include_oob_rows": True,
    }
    return templates.TemplateResponse(request, "partials/return_form.html", context)
