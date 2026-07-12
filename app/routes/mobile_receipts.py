"""Mobile Приход (goods receipt) wizard (UI-01, Phase 11 Plan 03).

Four single-purpose screens — Товар -> Партия -> Количество/Цены ->
Подтверждение — that together produce the exact same register_receipt()
call as the desktop /receipts/new form (app/routes/receipts.py). State is
carried step-to-step via hidden fields inside one persistent <form>
(RESEARCH Pattern 1) — no server-side wizard session.

_preselect_warehouse_id/_chooser_context mirror the module-private helpers
in app/routes/receipts.py (same logic, re-declared here — not imported,
since they are underscore-prefixed private helpers of another route file).
"""

import logging

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Product
from app.routes import templates
from app.services.batches import active_warehouses, open_batches
from app.services.receipts import lookup_prefill, register_receipt

logger = logging.getLogger(__name__)

router = APIRouter()

# D-02 (RESEARCH Open Q2): re-declared, never imported from the migration —
# same frozen contract app/routes/receipts.py documents for this constant.
DEFAULT_WAREHOUSE_ID = "00000000-0000-4000-8000-000000000010"
# Mirrors app/routes/receipts.py::SAVE_FAILED_ERROR verbatim — re-declared
# rather than cross-imported, matching this codebase's convention of never
# importing one route module from another.
SAVE_FAILED_ERROR = "Не удалось сохранить. Проверьте данные и попробуйте ещё раз."


def _preselect_warehouse_id(actives: list, submitted: str = "") -> str:
    """Echo a submitted warehouse, else preselect the seeded default when active,
    else the first active warehouse alphabetically (mirrors receipts.py)."""
    submitted = submitted.strip()
    if submitted:
        return submitted
    ids = {w.id for w in actives}
    if DEFAULT_WAREHOUSE_ID in ids:
        return DEFAULT_WAREHOUSE_ID
    return actives[0].id if actives else ""


def _chooser_context(session: Session, code: str, warehouse_id: str, actives: list) -> dict:
    """Chooser render context (mirrors receipts.py). Zero active warehouses ->
    blocking hint; otherwise the product's open batches in that warehouse
    (empty for an unknown/new code -> the template shows the new-batch-only
    path)."""
    code = code.strip()
    if not actives:
        return {"zero_warehouses": True, "batches": [], "code_entered": bool(code)}
    product = None
    if code:
        product = session.scalars(
            select(Product).where(Product.code == code, Product.deleted_at.is_(None))
        ).first()
    batches = (
        open_batches(session, product.id, warehouse_id)
        if product is not None and warehouse_id
        else []
    )
    return {"zero_warehouses": False, "batches": batches, "code_entered": bool(code)}


def _lookup_name(session: Session, code: str) -> str:
    """Resolve the product/dictionary name for a code (mirrors desktop's
    /receipts/lookup, RCP-02), or "" when the code is unknown everywhere —
    the operator must then type a name to create a brand-new product
    (register_receipt's D-05 auto-create path requires a non-empty name)."""
    code = code.strip()
    if not code:
        return ""
    result = lookup_prefill(session, code)
    return result["name"] if result else ""


@router.get("/m/receipts")
def mobile_receipt_new(request: Request, session: Session = Depends(get_session)):
    actives = active_warehouses(session)
    context = {
        "zero_warehouses": not actives,
        "active_warehouses": actives,
        "selected_warehouse_id": _preselect_warehouse_id(actives),
        "code": "",
    }
    return templates.TemplateResponse(request, "mobile_pages/receipts.html", context)


@router.post("/m/receipts/step/batch")
def mobile_receipt_step_batch(
    request: Request,
    code: str = Form(""),
    warehouse_id: str = Form(""),
    name: str = Form(""),
    session: Session = Depends(get_session),
):
    actives = active_warehouses(session)
    selected = _preselect_warehouse_id(actives, warehouse_id)
    chooser = _chooser_context(session, code, selected, actives)
    resolved_name = _lookup_name(session, code)
    # A fresh lookup wins over a stale typed name (code changed to a now-known
    # product); otherwise preserve whatever the operator already typed (e.g.
    # tapping "Назад" from step 3 must not lose a manually-typed new-product
    # name for a code that still resolves to nothing).
    final_name = resolved_name or name.strip()
    context = {
        "code": code.strip(),
        "warehouse_id": selected,
        "name": final_name,
        "name_known": bool(resolved_name),
        **chooser,
    }
    return templates.TemplateResponse(
        request, "mobile_partials/receipts_step_batch.html", context
    )


@router.post("/m/receipts/step/details")
def mobile_receipt_step_details(
    request: Request,
    code: str = Form(""),
    warehouse_id: str = Form(""),
    name: str = Form(""),
    batch_choice: str = Form(""),
    qty: str = Form(""),
    cost: str = Form(""),
    sale: str = Form(""),
    catalog: str = Form(""),
    expiry: str = Form(""),
    location: str = Form(""),
    comment: str = Form(""),
):
    # Also serves as the "Назад" target from step 4 — re-rendering step 3
    # with whatever qty/cost/sale/... the operator already typed, instead of
    # discarding them (RESEARCH Pattern 1: the server just re-renders from
    # posted state, no separate "back" endpoint needed).
    context = {
        "code": code,
        "warehouse_id": warehouse_id,
        "name": name,
        "batch_choice": batch_choice,
        "is_new_batch": batch_choice == "new",
        "qty": qty,
        "cost": cost,
        "sale": sale,
        "catalog": catalog,
        "expiry": expiry,
        "location": location,
        "comment": comment,
    }
    return templates.TemplateResponse(
        request, "mobile_partials/receipts_step_details.html", context
    )


@router.post("/m/receipts/step/confirm")
def mobile_receipt_step_confirm(
    request: Request,
    code: str = Form(""),
    warehouse_id: str = Form(""),
    name: str = Form(""),
    batch_choice: str = Form(""),
    qty: str = Form(""),
    cost: str = Form(""),
    sale: str = Form(""),
    catalog: str = Form(""),
    expiry: str = Form(""),
    location: str = Form(""),
    comment: str = Form(""),
):
    context = {
        "code": code,
        "warehouse_id": warehouse_id,
        "name": name,
        "batch_choice": batch_choice,
        "is_new_batch": batch_choice == "new",
        "qty": qty,
        "cost": cost,
        "sale": sale,
        "catalog": catalog,
        "expiry": expiry,
        "location": location,
        "comment": comment,
        "errors": {},
    }
    return templates.TemplateResponse(
        request, "mobile_partials/receipts_step_confirm.html", context
    )


@router.post("/m/receipts")
def mobile_receipt_create(
    request: Request,
    code: str = Form(""),
    name: str = Form(""),
    qty: str = Form(""),
    cost: str = Form(""),
    sale: str = Form(""),
    catalog: str = Form(""),
    warehouse_id: str = Form(""),
    batch_choice: str = Form(""),
    expiry: str = Form(""),
    location: str = Form(""),
    comment: str = Form(""),
    session: Session = Depends(get_session),
):
    form_echo = {
        "code": code,
        "name": name,
        "qty": qty,
        "cost": cost,
        "sale": sale,
        "catalog": catalog,
        "warehouse_id": warehouse_id,
        "batch_choice": batch_choice,
        "is_new_batch": batch_choice == "new",
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
        # CR-01: defensive rollback before re-rendering, mirroring
        # app/routes/receipts.py::receipt_create.
        session.rollback()
        logger.exception("register_receipt failed")
        context = {"errors": {"form": SAVE_FAILED_ERROR}, **form_echo}
        return templates.TemplateResponse(
            request, "mobile_partials/receipts_step_confirm.html", context, status_code=422
        )
    if errors:
        context = {"errors": errors, **form_echo}
        return templates.TemplateResponse(
            request, "mobile_partials/receipts_step_confirm.html", context, status_code=422
        )
    context = {
        "saved": {"name": result["product"].name, "qty": result["operation"].qty_delta},
    }
    return templates.TemplateResponse(
        request, "mobile_partials/receipts_step_confirm.html", context
    )
