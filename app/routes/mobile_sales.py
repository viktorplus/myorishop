"""Mobile sale wizard (UI-01/D-05): Товар -> Партия (conditional) ->
Количество и цена -> Корзина -> Оформить продажу, one line at a time via
hidden-field carry-forward (RESEARCH.md Pattern 1). The final write is the
exact same array-shaped register_sale() call the desktop basket already
uses (app/routes/sales.py::sale_create) — zero changes to the write path.
"""

import logging

from fastapi import APIRouter, Depends, Form, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Batch, Product
from app.routes import templates
from app.services.batches import open_batches
from app.services.sales import PRODUCT_NOT_FOUND_TMPL, lookup_prefill

router = APIRouter()
logger = logging.getLogger(__name__)

SAVE_FAILED_ERROR = "Не удалось сохранить. Проверьте данные и попробуйте ещё раз."


def _acc_context(
    code_acc: list[str], qty_acc: list[str], price_acc: list[str], batch_acc: list[str]
) -> dict:
    """The 4 accumulated-basket arrays, re-echoed as hidden fields by every step."""
    return {
        "code_acc": code_acc,
        "qty_acc": qty_acc,
        "price_acc": price_acc,
        "batch_acc": batch_acc,
    }


@router.get("/m/sales")
def mobile_sales_page(request: Request):
    context = {
        "code": "",
        "error": None,
        "saved": None,
        **_acc_context([], [], [], []),
    }
    return templates.TemplateResponse(request, "mobile_pages/sales.html", context)


@router.post("/m/sales/step/product")
def mobile_sale_step_product(
    request: Request,
    code: str = Form(""),
    back: str = Form(""),
    code_acc: list[str] = Form([], alias="code_acc[]"),
    qty_acc: list[str] = Form([], alias="qty_acc[]"),
    price_acc: list[str] = Form([], alias="price_acc[]"),
    batch_acc: list[str] = Form([], alias="batch_acc[]"),
    session: Session = Depends(get_session),
):
    acc = _acc_context(code_acc, qty_acc, price_acc, batch_acc)
    code_clean = code.strip()

    # D-05 step-back control ("Назад" from step 2/3): re-show step 1 as-is,
    # no lookup re-run, no auto-forward. Also the natural landing state for
    # a blank/cleared code input.
    if back == "1" or not code_clean:
        context = {"code": code, "error": None, "saved": None, **acc}
        return templates.TemplateResponse(
            request, "mobile_partials/sale_step_product.html", context
        )

    result = lookup_prefill(session, code_clean)
    if result is None:
        context = {
            "code": code,
            "error": PRODUCT_NOT_FOUND_TMPL.format(code=code_clean),
            "saved": None,
            **acc,
        }
        return templates.TemplateResponse(
            request, "mobile_partials/sale_step_product.html", context, status_code=422
        )

    if result["source"] == "dictionary":
        # Dictionary-only match (no product row, desktop's dictionary-only
        # path): skip straight to step 3 — no batch to pick, price pre-fill
        # left empty (no product card to fill the price from).
        context = {
            "code": code_clean,
            "batch_id": "",
            "fill_price_cents": None,
            "fill_price_hint": "",
            **acc,
        }
        return templates.TemplateResponse(
            request, "mobile_partials/sale_step_qty_price.html", context
        )

    product = session.scalars(
        select(Product).where(Product.code == code_clean, Product.deleted_at.is_(None))
    ).first()
    batches = open_batches(session, product.id) if product is not None else []
    selected_batch: Batch | None = None
    auto_note = False
    # D-06: exactly one open batch auto-selects (pre-checked + highlighted +
    # hidden set) but the step is still shown with its forward control
    # enabled — never silently skipped (Pitfall 6 boundary distinction from
    # the zero-batch case below).
    if len(batches) == 1:
        selected_batch = batches[0]
        auto_note = True

    context = {
        "code": code_clean,
        "batches": batches,
        "selected_batch_id": selected_batch.id if selected_batch else None,
        "batch_id": selected_batch.id if selected_batch else "",
        "auto_note": auto_note,
        # Pitfall 6/D-12: zero open batches blocks forward wizard progress —
        # sale_step_batch.html omits its "Далее" control when this is True.
        "show_empty": not batches,
        **acc,
    }
    return templates.TemplateResponse(request, "mobile_partials/sale_step_batch.html", context)


@router.get("/m/sales/step/batch")
def mobile_sale_step_batch(
    request: Request,
    batch_id: str = "",
    code: str = "",
    code_acc: list[str] = Query([], alias="code_acc[]"),
    qty_acc: list[str] = Query([], alias="qty_acc[]"),
    price_acc: list[str] = Query([], alias="price_acc[]"),
    batch_acc: list[str] = Query([], alias="batch_acc[]"),
    session: Session = Depends(get_session),
):
    acc = _acc_context(code_acc, qty_acc, price_acc, batch_acc)
    code_clean = code.strip()
    product = session.scalars(
        select(Product).where(Product.code == code_clean, Product.deleted_at.is_(None))
    ).first()
    # T-09-10 analog: re-query the open list fresh on every pick (defuses
    # stale picker drift — a batch may have emptied since the step first
    # rendered).
    batches = open_batches(session, product.id) if product is not None else []
    # T-09-08/T-11-10: the client-supplied batch_id is untrusted — ownership
    # is re-validated before the pick is ever trusted.
    picked: Batch | None = None
    if batch_id and product is not None:
        candidate = session.get(Batch, batch_id)
        if candidate is not None and candidate.product_id == product.id:
            picked = candidate

    context = {
        "code": code_clean,
        "batches": batches,
        "selected_batch_id": picked.id if picked else None,
        "batch_id": picked.id if picked else "",
        "auto_note": False,
        "show_empty": not batches,
        **acc,
    }
    return templates.TemplateResponse(request, "mobile_partials/sale_step_batch.html", context)
