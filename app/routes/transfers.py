"""Transfer pages (WH-03): thin routes, writes in app/services/transfers.py."""

import logging

from fastapi import APIRouter, Depends, Form, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Batch, Product
from app.routes import templates
from app.services.batches import active_warehouses, open_batches
from app.services.receipts import lookup_prefill
from app.services.transfers import recent_transfers, register_transfer

router = APIRouter()
logger = logging.getLogger(__name__)

# Route order: the literal /transfers/lookup and /transfers/batch-pick paths
# MUST stay declared before any parameterized /transfers/{...} route added
# later.

SAVE_FAILED_ERROR = "Не удалось сохранить. Проверьте данные и попробуйте ещё раз."


def _dest_warehouses(session: Session, source: Batch | None) -> list:
    """Active warehouses, including the source batch's own warehouse (D-09)."""
    if source is None:
        return []
    return list(active_warehouses(session))


@router.get("/transfers")
def transfers_page(request: Request, session: Session = Depends(get_session)):
    context = {
        "errors": {},
        "form": {},
        "focus_code": False,
        "transfers": recent_transfers(session),
    }
    return templates.TemplateResponse(request, "pages/transfer_form.html", context)


@router.get("/transfers/lookup")
def transfers_lookup(
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

    # WH-03: an active product also gets its open batches (ALL warehouses —
    # a transfer's source may be any warehouse) so the shared picker can be
    # oob-swapped into the form (empty state when there are none).
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
    return templates.TemplateResponse(request, "partials/transfer_lookup.html", context)


@router.get("/transfers/batch-pick")
def transfers_batch_pick(
    request: Request,
    batch_id: str = "",
    code: str = "",
    session: Session = Depends(get_session),
):
    # T-10-06: re-query the open list on every pick (fresh remaining qty) and
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
        "show_empty": product is not None and not batches,
        # T-10-07/D-09: destination options = all active warehouses (including
        # the picked source's own warehouse, for same-warehouse splits); empty
        # (no select) until a source is picked.
        "warehouses": _dest_warehouses(session, picked),
    }
    return templates.TemplateResponse(request, "partials/transfer_batch_wrap.html", context)


@router.post("/transfers")
def transfers_create(
    request: Request,
    code: str = Form(""),
    name: str = Form(""),
    qty: str = Form(""),
    batch_id: str = Form(""),
    dest_warehouse_id: str = Form(""),
    new_expiry: str = Form(""),
    new_comment: str = Form(""),
    confirm: str = Form(""),
    session: Session = Depends(get_session),
):
    # Qty arrives as a string on purpose: parsing/validation happens in the
    # service, which returns RU errors.
    form_echo = {
        "code": code,
        "name": name,
        "qty": qty,
        "dest_warehouse_id": dest_warehouse_id,
        "new_expiry": new_expiry,
        "new_comment": new_comment,
    }
    # WH-03/D-10: resolve the picked batch (if any) for the re-echoed picker +
    # dest select on a 422/warn re-render — re-validate ownership the same
    # way transfers_batch_pick does, a client-submitted batch_id naming
    # another product's batch must never be echoed back.
    code_clean = code.strip()
    lookup_product = session.scalars(
        select(Product).where(Product.code == code_clean, Product.deleted_at.is_(None))
    ).first()
    selected_batch: Batch | None = None
    batch_id_clean = batch_id.strip()
    if batch_id_clean and lookup_product is not None:
        candidate = session.get(Batch, batch_id_clean)
        if candidate is not None and candidate.product_id == lookup_product.id:
            selected_batch = candidate
    try:
        result, errors = register_transfer(
            session,
            code=code,
            name=name,
            qty_raw=qty,
            batch_id=batch_id,
            dest_warehouse_id=dest_warehouse_id,
            new_expiry=new_expiry,
            new_comment=new_comment,
            confirm=confirm,
        )
    except Exception:  # noqa: BLE001 — block error, never a raw 500
        # T-10-09/Pitfall 7: defensive rollback before re-querying anything.
        session.rollback()
        logger.exception("register_transfer failed")
        context = {
            "errors": {"form": SAVE_FAILED_ERROR},
            "form": form_echo,
            "focus_code": False,
            "include_oob_rows": False,
            "selected_batch": selected_batch,
            "warehouses": _dest_warehouses(session, selected_batch),
        }
        return templates.TemplateResponse(
            request, "partials/transfer_form.html", context, status_code=422
        )

    # D-06: over-transfer — zero writes, warn above the still-intact form (the
    # confirm button re-POSTs the same form via form="transfer-form" + confirm=1).
    if result and result.get("oversell"):
        context = {
            "errors": {},
            "form": form_echo,
            "focus_code": False,
            "include_oob_rows": False,
            "oversell": result["oversell"],
            "selected_batch": selected_batch,
            "warehouses": _dest_warehouses(session, selected_batch),
        }
        return templates.TemplateResponse(request, "partials/transfer_form.html", context)

    if errors:
        context = {
            "errors": errors,
            "form": form_echo,
            "focus_code": False,
            "include_oob_rows": False,
            "selected_batch": selected_batch,
            "warehouses": _dest_warehouses(session, selected_batch),
        }
        return templates.TemplateResponse(
            request, "partials/transfer_form.html", context, status_code=422
        )

    # D-02 (mirrors write-off ergonomics): success -> fresh empty form +
    # neutral success line + focus back to «Код»; the refreshed recent list
    # rides along as an oob swap.
    context = {
        "errors": {},
        "form": {},
        "saved": {"name": result["product"].name, "qty": result["qty"]},
        "focus_code": True,
        "transfers": recent_transfers(session),
        "include_oob_rows": True,
    }
    return templates.TemplateResponse(request, "partials/transfer_form.html", context)
