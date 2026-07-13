"""Mobile Корректировка (stock correction) wizard (OPS-03/UI-01).

Four steps (Товар -> Партия -> Режим -> Значение) ending in the SAME
register_correction() write as the desktop form
(app/routes/corrections.py::correction_create). Built and tested in
isolation via mobile_client_factory (Plan 01) — real registration into
app.main happens once, in Plan 09.

Route order: the literal /m/corrections/lookup and /m/corrections/step/*
paths are declared before any parameterized route (mirrors
app/routes/corrections.py's convention; no parameterized route exists here).
"""

import logging

from fastapi import APIRouter, Depends, Form, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Batch, Product
from app.routes import templates
from app.services.batches import active_warehouses, open_batches
from app.services.corrections import lookup_prefill, register_correction

router = APIRouter()
logger = logging.getLogger(__name__)

SAVE_FAILED_ERROR = "Не удалось сохранить. Попробуйте ещё раз."


def _warehouse_names(session: Session) -> dict[str, str]:
    """id -> name map so a wizard step can show its own «Склад:» line."""
    return {w.id: w.name for w in active_warehouses(session)}


@router.get("/m/corrections")
def mobile_correction_start(request: Request, code: str = ""):
    context = {"code": code.strip(), "not_found": False}
    if bool(request.headers.get("HX-Request")):
        return templates.TemplateResponse(
            request, "mobile_partials/corrections_step_product.html", context
        )
    return templates.TemplateResponse(request, "mobile_pages/corrections.html", context)


@router.get("/m/corrections/lookup")
def mobile_correction_lookup(
    request: Request,
    code: str = "",
    session: Session = Depends(get_session),
):
    # D-11 mirrored: corrections has its OWN lookup_prefill, distinct from
    # the receipts one used by write-off/transfer.
    result = lookup_prefill(session, code)
    if result is None:
        return Response(status_code=204)
    context = {"name": result["name"]}
    return templates.TemplateResponse(
        request, "mobile_partials/corrections_name_echo.html", context
    )


@router.post("/m/corrections/step/batch")
def mobile_correction_step_batch(
    request: Request,
    code: str = Form(""),
    session: Session = Depends(get_session),
):
    code_clean = code.strip()
    product = session.scalars(
        select(Product).where(Product.code == code_clean, Product.deleted_at.is_(None))
    ).first()
    if product is None:
        # CR-01: this request is an htmx outerHTML swap targeting
        # #corrections-step-wrap — must return a bare fragment, not the
        # full mobile_pages/corrections.html document.
        context = {"code": code_clean, "not_found": True}
        return templates.TemplateResponse(
            request, "mobile_partials/corrections_not_found.html", context, status_code=422
        )

    batches = open_batches(session, product.id)
    context = {
        "code": code_clean,
        "name": product.name,
        "warehouse_name": None,
        "batches": batches,
        "batch_id": "",
        "selected_batch_id": None,
        "batch_qty": None,
        "show_empty": not batches,
    }
    return templates.TemplateResponse(
        request, "mobile_partials/corrections_step_batch.html", context
    )


@router.get("/m/corrections/step/batch-pick")
def mobile_correction_batch_pick(
    request: Request,
    batch_id: str = "",
    code: str = "",
    session: Session = Depends(get_session),
):
    # T-11-16/T-09-08 precedent: re-query the open list (fresh remaining
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
        "name": product.name if product is not None else "",
        "warehouse_name": _warehouse_names(session).get(picked.warehouse_id) if picked else None,
        "batches": batches,
        "batch_id": picked.id if picked else "",
        "selected_batch_id": picked.id if picked else None,
        "batch_qty": picked.quantity if picked else None,
        "show_empty": product is not None and not batches,
    }
    return templates.TemplateResponse(
        request, "mobile_partials/corrections_step_batch.html", context
    )


def _carried_warehouse_name(session: Session, code_clean: str, batch_id_clean: str) -> str | None:
    """T-13-02: re-validate the carried batch_id's ownership before trusting
    its warehouse_id for display — never trust batch_id blindly."""
    if not batch_id_clean:
        return None
    product = session.scalars(
        select(Product).where(Product.code == code_clean, Product.deleted_at.is_(None))
    ).first()
    if product is None:
        return None
    candidate = session.get(Batch, batch_id_clean)
    if candidate is not None and candidate.product_id == product.id:
        return _warehouse_names(session).get(candidate.warehouse_id)
    return None


@router.post("/m/corrections/step/mode")
def mobile_correction_step_mode(
    request: Request,
    code: str = Form(""),
    name: str = Form(""),
    batch_id: str = Form(""),
    batch_qty: str = Form(""),
    session: Session = Depends(get_session),
):
    code_clean = code.strip()
    batch_id_clean = batch_id.strip()
    context = {
        "code": code_clean,
        "name": name.strip(),
        "warehouse_name": _carried_warehouse_name(session, code_clean, batch_id_clean),
        "batch_id": batch_id_clean,
        "batch_qty": batch_qty,
        "mode": "",
    }
    return templates.TemplateResponse(
        request, "mobile_partials/corrections_step_mode.html", context
    )


@router.post("/m/corrections/step/value")
def mobile_correction_step_value(
    request: Request,
    code: str = Form(""),
    name: str = Form(""),
    batch_id: str = Form(""),
    batch_qty: str = Form(""),
    mode: str = Form(""),
    session: Session = Depends(get_session),
):
    code_clean = code.strip()
    batch_id_clean = batch_id.strip()
    context = {
        "code": code_clean,
        "name": name.strip(),
        "warehouse_name": _carried_warehouse_name(session, code_clean, batch_id_clean),
        "batch_id": batch_id_clean,
        "batch_qty": batch_qty,
        "mode": mode,
    }
    return templates.TemplateResponse(
        request, "mobile_partials/corrections_step_value.html", context
    )


@router.post("/m/corrections")
def mobile_correction_create(
    request: Request,
    code: str = Form(""),
    name: str = Form(""),
    mode: str = Form(""),
    value: str = Form(""),
    note: str = Form(""),
    batch_id: str = Form(""),
    batch_qty: str = Form(""),
    confirm: str = Form(""),
    session: Session = Depends(get_session),
):
    # Mode/qty fields arrive as strings on purpose: parsing/validation
    # happens in the service, which returns RU errors.
    form_echo = {"value": value, "note": note}
    code_clean = code.strip()
    batch_id_clean = batch_id.strip()
    name_clean = name.strip()
    warehouse_name = _carried_warehouse_name(session, code_clean, batch_id_clean)
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
    except Exception:  # noqa: BLE001 -- UI-SPEC: block error, never a raw 500
        # WR-03: defensive rollback, mirroring correction_create.
        session.rollback()
        logger.exception("register_correction failed")
        context = {
            "errors": {"form": SAVE_FAILED_ERROR},
            "form": form_echo,
            "code": code_clean,
            "name": name_clean,
            "warehouse_name": warehouse_name,
            "batch_id": batch_id_clean,
            "mode": mode or "count",
            "batch_qty": batch_qty,
        }
        return templates.TemplateResponse(
            request, "mobile_partials/corrections_step_value.html", context, status_code=422
        )

    # T-11-18/D-09 criterion 4: over-removal -- zero writes, warn ABOVE the
    # still-editable step 4 form (CR-02 fix: re-render the real step-4
    # template with `oversell` set, mirroring writeoff_step_reason.html /
    # transfers_step_dest.html, instead of a hand-rolled hidden-field copy).
    # The danger button re-POSTs the same visible #corrections-value-form
    # plus confirm=1 via form association (see corrections_warning.html).
    if result and result.get("oversell"):
        context = {
            "oversell": result["oversell"],
            "form": form_echo,
            "code": code_clean,
            "name": name_clean,
            "warehouse_name": warehouse_name,
            "batch_id": batch_id_clean,
            "mode": mode or "count",
            "batch_qty": batch_qty,
        }
        return templates.TemplateResponse(
            request, "mobile_partials/corrections_step_value.html", context
        )

    if errors:
        context = {
            "errors": errors,
            "form": form_echo,
            "code": code_clean,
            "name": name_clean,
            "warehouse_name": warehouse_name,
            "batch_id": batch_id_clean,
            "mode": mode or "count",
            "batch_qty": batch_qty,
        }
        return templates.TemplateResponse(
            request, "mobile_partials/corrections_step_value.html", context, status_code=422
        )

    # D-05: success -> mobile confirmation screen, not desktop's silent form
    # reset. CR-01: this request is an htmx outerHTML swap targeting
    # #corrections-step-wrap, so it must return a bare fragment, not the
    # full mobile_pages/corrections.html document.
    context = {
        "saved": {"name": result["product"].name, "new_qty": result["new_qty"]},
    }
    return templates.TemplateResponse(request, "mobile_partials/corrections_success.html", context)
