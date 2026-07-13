"""Mobile write-off wizard (UI-01/LOT-05): 4 screens ending in the SAME
`register_writeoff()` write as desktop (app/routes/writeoffs.py).

Steps: Товар -> Партия (conditional on open batches) -> Количество -> Причина
-> post-success screen. Every step re-echoes prior fields as HIDDEN inputs in
a plain (non-htmx) `<form>` — there is no server-side wizard session; each
POST is a normal full-page navigation, matching the phase's "single-purpose
screen" shape (D-05). HTMX is used ONLY for two small in-step affordances:
the debounced code->name lookup on step 1, and the batch-card tap echo on
step 2 (both partial swaps of a small `<div>`, never the whole page).

Registered into app.main in Plan 09 — this router is tested standalone via
mobile_client_factory until then (mirrors every other Phase 11 feature plan).
"""

import logging

from fastapi import APIRouter, Depends, Form, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Batch, Product
from app.routes import templates
from app.services.batches import active_warehouses, open_batches
from app.services.receipts import lookup_prefill
from app.services.writeoffs import register_writeoff

router = APIRouter()
logger = logging.getLogger(__name__)

SAVE_FAILED_ERROR = "Не удалось сохранить. Проверьте данные и попробуйте ещё раз."
PRODUCT_NOT_FOUND_TMPL = "Товар с кодом „{code}“ не найден. Сначала оприходуйте товар."


def _find_product(session: Session, code: str) -> Product | None:
    # Active-only lookup (mirrors desktop's writeoffs.py) — write-off never
    # auto-creates a card, so a soft-deleted product's code is unknown.
    code = code.strip()
    if not code:
        return None
    return session.scalars(
        select(Product).where(Product.code == code, Product.deleted_at.is_(None))
    ).first()


def _warehouse_names(session: Session) -> dict[str, str]:
    """id -> name map so a wizard step can show its own «Склад:» line."""
    return {w.id: w.name for w in active_warehouses(session)}


def _carried_warehouse_name(session: Session, code_clean: str, batch_id_clean: str) -> str | None:
    """T-13-05: re-validate the carried batch_id's ownership against the
    resolved product before trusting its warehouse_id for display — never
    trust batch_id blindly."""
    if not batch_id_clean:
        return None
    product = _find_product(session, code_clean)
    if product is None:
        return None
    candidate = session.get(Batch, batch_id_clean)
    if candidate is not None and candidate.product_id == product.id:
        return _warehouse_names(session).get(candidate.warehouse_id)
    return None


@router.get("/m/writeoff")
def mobile_writeoff_start(request: Request):
    context = {"errors": {}, "code": "", "name": "", "saved": None}
    if bool(request.headers.get("HX-Request")):
        return templates.TemplateResponse(
            request, "mobile_partials/writeoff_step_product.html", context
        )
    return templates.TemplateResponse(request, "mobile_pages/writeoff.html", context)


@router.get("/m/writeoff/lookup")
def mobile_writeoff_lookup(
    request: Request, code: str = "", session: Session = Depends(get_session)
):
    # D-04: same receipt lookup as desktop's writeoff_lookup — write-off
    # never creates/edits a product, this is display-only feedback while
    # typing the code (204 leaves the prior #name-fill content untouched,
    # per the shared htmx-config 204->no-swap rule).
    result = lookup_prefill(session, code)
    if result is None:
        return Response(status_code=204)
    context = {"name": result["name"]}
    return templates.TemplateResponse(request, "mobile_partials/writeoff_name_fill.html", context)


@router.post("/m/writeoff/step/batch")
def mobile_writeoff_step_batch(
    request: Request, code: str = Form(""), session: Session = Depends(get_session)
):
    code_clean = code.strip()
    product = _find_product(session, code_clean)
    if product is None:
        context = {
            "errors": {"code": PRODUCT_NOT_FOUND_TMPL.format(code=code_clean)},
            "code": code_clean,
            "name": "",
            "saved": None,
        }
        return templates.TemplateResponse(
            request, "mobile_partials/writeoff_step_product.html", context, status_code=422
        )
    batches = open_batches(session, product.id)
    context = {
        "errors": {},
        "code": code_clean,
        "name": product.name,
        "warehouse_name": None,
        "batches": batches,
        "batch_id": None,
        "selected_batch_id": None,
        "show_empty": not batches,
        "pick_url": "/m/writeoff/step/batch-pick",
    }
    return templates.TemplateResponse(request, "mobile_partials/writeoff_step_batch.html", context)


@router.get("/m/writeoff/step/batch-pick")
def mobile_writeoff_step_batch_pick(
    request: Request,
    batch_id: str = "",
    code: str = "",
    session: Session = Depends(get_session),
):
    # T-09-08/T-11-13: re-query the open list fresh (current remaining qty)
    # and re-validate the client-supplied batch_id's product ownership
    # BEFORE echoing it back — the id is untrusted.
    code_clean = code.strip()
    product = _find_product(session, code_clean)
    batches = open_batches(session, product.id) if product is not None else []
    picked: Batch | None = None
    if batch_id and product is not None:
        candidate = session.get(Batch, batch_id)
        if candidate is not None and candidate.product_id == product.id:
            picked = candidate
    context = {
        "code": code_clean,
        "batches": batches,
        "batch_id": picked.id if picked else None,
        "selected_batch_id": picked.id if picked else None,
        "show_empty": product is not None and not batches,
        "pick_url": "/m/writeoff/step/batch-pick",
    }
    return templates.TemplateResponse(request, "mobile_partials/writeoff_batch_wrap.html", context)


@router.post("/m/writeoff/step/qty")
def mobile_writeoff_step_qty(
    request: Request,
    code: str = Form(""),
    batch_id: str = Form(""),
    name: str = Form(""),
    session: Session = Depends(get_session),
):
    code_clean = code.strip()
    batch_id_clean = batch_id.strip()
    context = {
        "errors": {},
        "code": code_clean,
        "batch_id": batch_id_clean,
        "name": name.strip(),
        "warehouse_name": _carried_warehouse_name(session, code_clean, batch_id_clean),
        "qty": "",
    }
    return templates.TemplateResponse(request, "mobile_partials/writeoff_step_qty.html", context)


@router.post("/m/writeoff/step/reason")
def mobile_writeoff_step_reason(
    request: Request,
    code: str = Form(""),
    batch_id: str = Form(""),
    qty: str = Form(""),
    name: str = Form(""),
    session: Session = Depends(get_session),
):
    code_clean = code.strip()
    batch_id_clean = batch_id.strip()
    context = {
        "errors": {},
        "code": code_clean,
        "batch_id": batch_id_clean,
        "name": name.strip(),
        "warehouse_name": _carried_warehouse_name(session, code_clean, batch_id_clean),
        "qty": qty.strip(),
        "form_reason_code": "",
        "note": "",
        "oversell": None,
    }
    return templates.TemplateResponse(request, "mobile_partials/writeoff_step_reason.html", context)


@router.post("/m/writeoff")
def mobile_writeoff_submit(
    request: Request,
    code: str = Form(""),
    batch_id: str = Form(""),
    qty: str = Form(""),
    reason_code: str = Form(""),
    note: str = Form(""),
    name: str = Form(""),
    confirm: str = Form(""),
    session: Session = Depends(get_session),
):
    code_clean = code.strip()
    batch_id_clean = batch_id.strip()
    warehouse_name = _carried_warehouse_name(session, code_clean, batch_id_clean)
    # Money/qty/reason fields arrive as strings on purpose — the service
    # returns RU errors rather than a Pydantic parse failure (mirrors
    # app/routes/writeoffs.py::writeoff_create verbatim).
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
        session.rollback()
        logger.exception("register_writeoff failed")
        context = {
            "errors": {"form": SAVE_FAILED_ERROR},
            "code": code,
            "batch_id": batch_id,
            "qty": qty,
            "form_reason_code": reason_code,
            "note": note,
            "name": name,
            "warehouse_name": warehouse_name,
            "oversell": None,
        }
        return templates.TemplateResponse(
            request, "mobile_partials/writeoff_step_reason.html", context, status_code=422
        )

    # D-04/D-09/T-11-15: over-removal — zero writes, warn above the still-intact
    # reason form (the danger button re-posts the same ambient #writeoff-form
    # via htmx, adding confirm=1 through hx-vals).
    if result and result.get("oversell"):
        context = {
            "errors": {},
            "code": code,
            "batch_id": batch_id,
            "qty": qty,
            "form_reason_code": reason_code,
            "note": note,
            "name": name,
            "warehouse_name": warehouse_name,
            "oversell": result["oversell"],
        }
        return templates.TemplateResponse(
            request, "mobile_partials/writeoff_step_reason.html", context
        )

    if errors:
        context = {
            "errors": errors,
            "code": code,
            "batch_id": batch_id,
            "qty": qty,
            "form_reason_code": reason_code,
            "note": note,
            "name": name,
            "warehouse_name": warehouse_name,
            "oversell": None,
        }
        return templates.TemplateResponse(
            request, "mobile_partials/writeoff_step_reason.html", context, status_code=422
        )

    context = {
        "errors": {},
        "code": "",
        "name": "",
        "saved": {"name": result["product"].name, "qty": -result["operation"].qty_delta},
    }
    return templates.TemplateResponse(request, "mobile_pages/writeoff.html", context)
