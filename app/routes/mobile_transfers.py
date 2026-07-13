"""Mobile Перемещение (transfer) wizard (WH-03/UI-01): thin routes, same
write as desktop's app/routes/transfers.py -> app.services.transfers.

3 mobile steps: Товар -> Партия (source warehouse shown) -> Куда и
количество, ending in the exact same register_transfer() call as desktop.
This is the last of Phase 11's four "single scalar batch_id" wizards; the
batch-selection step renders its OWN card markup (not batch_card_picker.html
verbatim) because a transfer card also needs to show the source warehouse,
a field the shared partial doesn't display by default.

Every step-2/step-3 partial's root element carries id="wizard-step" so an
hx-swap="outerHTML" targeting that id can move the wizard forward OR
backward between steps without touching the surrounding mobile_base.html
chrome (back link stays put).
"""

import logging

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Batch, Product, Warehouse
from app.routes import templates
from app.services.batches import active_warehouses, open_batches
from app.services.receipts import lookup_prefill
from app.services.transfers import register_transfer

router = APIRouter()
logger = logging.getLogger(__name__)

SAVE_FAILED_ERROR = "Не удалось сохранить. Проверьте данные и попробуйте ещё раз."


def _dest_warehouses(session: Session, source: Batch | None) -> list[Warehouse]:
    """Active warehouses minus the source batch's own warehouse (D-02, mirrors desktop)."""
    if source is None:
        return []
    return [w for w in active_warehouses(session) if w.id != source.warehouse_id]


def _warehouse_names(session: Session) -> dict[str, str]:
    """id -> name map so the batch-step card can show its own «Склад:» line."""
    return {w.id: w.name for w in active_warehouses(session)}


def _find_product(session: Session, code: str) -> Product | None:
    code_clean = code.strip()
    if not code_clean:
        return None
    # Active-only lookup — a transfer never auto-creates a product.
    return session.scalars(
        select(Product).where(Product.code == code_clean, Product.deleted_at.is_(None))
    ).first()


def _render_batch_step(request: Request, session: Session, code: str, name: str = ""):
    code_clean = code.strip()
    product = _find_product(session, code_clean)
    batches = open_batches(session, product.id) if product is not None else []
    context = {
        "step_label": "Шаг 2 из 3",
        "code": code_clean,
        "name": name,
        "batches": batches,
        "warehouse_names": _warehouse_names(session),
        "show_empty": product is not None and not batches,
        "product_missing": code_clean != "" and product is None,
    }
    return templates.TemplateResponse(request, "mobile_partials/transfers_step_batch.html", context)


def _pick_batch(session: Session, product: Product | None, batch_id: str) -> Batch | None:
    # T-11-19/T-09-08: the client-supplied batch id is untrusted — re-query +
    # re-validate ownership before trusting it as the transfer's source.
    batch_id = batch_id.strip()
    if not batch_id or product is None:
        return None
    candidate = session.get(Batch, batch_id)
    if candidate is not None and candidate.product_id == product.id:
        return candidate
    return None


def _render_dest_step(
    request: Request,
    session: Session,
    *,
    code: str,
    picked: Batch | None,
    name: str = "",
    qty: str = "",
    errors: dict | None = None,
    oversell: dict | None = None,
    saved: dict | None = None,
    status_code: int = 200,
):
    context = {
        "step_label": "Шаг 3 из 3",
        "code": code,
        "name": name,
        "batch_id": picked.id if picked else "",
        "warehouses": _dest_warehouses(session, picked),
        "qty": qty,
        "errors": errors or {},
        "oversell": oversell,
        "saved": saved,
    }
    return templates.TemplateResponse(
        request,
        "mobile_partials/transfers_step_dest.html",
        context,
        status_code=status_code,
    )


@router.get("/m/transfers")
def transfers_step_product(request: Request):
    context = {"step_label": "Шаг 1 из 3", "code": "", "errors": {}}
    return templates.TemplateResponse(request, "mobile_pages/transfers.html", context)


@router.post("/m/transfers/step/batch")
def transfers_step_batch(
    request: Request,
    code: str = Form(""),
    session: Session = Depends(get_session),
):
    # D-04/D-14: reuses the receipt lookup (transfer has no price fields of
    # its own to fill) — the result is now captured and threaded through as
    # the visible readout name, instead of being discarded.
    code_clean = code.strip()
    result = lookup_prefill(session, code_clean) if code_clean else None
    return _render_batch_step(
        request, session, code, name=(result["name"] or "") if result else ""
    )


@router.get("/m/transfers/step/batch-pick")
def transfers_step_batch_pick(
    request: Request,
    batch_id: str = "",
    code: str = "",
    name: str = "",
    session: Session = Depends(get_session),
):
    code_clean = code.strip()
    product = _find_product(session, code_clean)
    picked = _pick_batch(session, product, batch_id)
    if picked is None:
        # Invalid/foreign/unknown id -> safe fallback: re-render step
        # "Партия" instead of advancing with no source batch.
        return _render_batch_step(request, session, code_clean, name=name)
    # D-07: tapping a batch card advances the wizard straight to "Куда и
    # количество" — no separate confirm sub-step.
    return _render_dest_step(request, session, code=code_clean, picked=picked, name=name)


@router.post("/m/transfers/step/dest")
def transfers_step_dest(
    request: Request,
    code: str = Form(""),
    batch_id: str = Form(""),
    name: str = Form(""),
    session: Session = Depends(get_session),
):
    code_clean = code.strip()
    product = _find_product(session, code_clean)
    picked = _pick_batch(session, product, batch_id)
    if picked is None:
        return _render_batch_step(request, session, code_clean, name=name)
    return _render_dest_step(request, session, code=code_clean, picked=picked, name=name)


@router.post("/m/transfers")
def transfers_create(
    request: Request,
    code: str = Form(""),
    name: str = Form(""),
    qty: str = Form(""),
    batch_id: str = Form(""),
    dest_warehouse_id: str = Form(""),
    confirm: str = Form(""),
    session: Session = Depends(get_session),
):
    code_clean = code.strip()
    product = _find_product(session, code_clean)
    picked = _pick_batch(session, product, batch_id)
    try:
        result, errors = register_transfer(
            session,
            code=code,
            name=name,
            qty_raw=qty,
            batch_id=batch_id,
            dest_warehouse_id=dest_warehouse_id,
            confirm=confirm,
        )
    except Exception:  # noqa: BLE001 — block error, never a raw 500
        # T-10-09/Pitfall 7 precedent: defensive rollback before re-rendering.
        session.rollback()
        logger.exception("register_transfer failed")
        return _render_dest_step(
            request,
            session,
            code=code_clean,
            picked=picked,
            name=name,
            qty=qty,
            errors={"form": SAVE_FAILED_ERROR},
            status_code=422,
        )

    # D-06/T-11-21: over-transfer — zero writes, warn above the still-intact
    # step. Scalar truthiness — result.get("oversell") is a dict or absent.
    if result and result.get("oversell"):
        return _render_dest_step(
            request,
            session,
            code=code_clean,
            picked=picked,
            name=name,
            qty=qty,
            oversell=result["oversell"],
        )

    if errors:
        return _render_dest_step(
            request,
            session,
            code=code_clean,
            picked=picked,
            name=name,
            qty=qty,
            errors=errors,
            status_code=422,
        )

    # D-05: mobile adds an explicit post-success confirmation screen instead
    # of desktop's silent form reset.
    return _render_dest_step(
        request,
        session,
        code=code_clean,
        picked=picked,
        name=name,
        qty=qty,
        saved={"name": result["product"].name, "qty": qty},
    )
