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
from app.services.sales import PRODUCT_NOT_FOUND_TMPL, lookup_prefill, register_sale

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
def mobile_sales_page(request: Request, code: str = ""):
    context = {
        "code": code,
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
            "name": result["name"],
            "batch_id": "",
            "fill_price_cents": None,
            "fill_price_hint": "",
            # 11-UAT.md Test 4 (Bug B): no batch step was ever shown for a
            # dictionary-only match, so this step's own "Назад" must return
            # straight to the product step, not to a batch step that never
            # existed.
            "from_batch_step": False,
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
        "name": result["name"],
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
        "name": product.name if product is not None else "",
        "batches": batches,
        "selected_batch_id": picked.id if picked else None,
        "batch_id": picked.id if picked else "",
        "auto_note": False,
        "show_empty": not batches,
        **acc,
    }
    return templates.TemplateResponse(request, "mobile_partials/sale_step_batch.html", context)


@router.post("/m/sales/step/qty-price")
def mobile_sale_step_qty_price(
    request: Request,
    code: str = Form(""),
    batch_id: str = Form(""),
    code_acc: list[str] = Form([], alias="code_acc[]"),
    qty_acc: list[str] = Form([], alias="qty_acc[]"),
    price_acc: list[str] = Form([], alias="price_acc[]"),
    batch_acc: list[str] = Form([], alias="batch_acc[]"),
    session: Session = Depends(get_session),
):
    acc = _acc_context(code_acc, qty_acc, price_acc, batch_acc)
    code_clean = code.strip()
    product = session.scalars(
        select(Product).where(Product.code == code_clean, Product.deleted_at.is_(None))
    ).first()

    # T-09-08/T-11-10 analog: re-validate ownership of the batch carried
    # forward from the batch step before using it as a price source.
    picked: Batch | None = None
    if batch_id and product is not None:
        candidate = session.get(Batch, batch_id)
        if candidate is not None and candidate.product_id == product.id:
            picked = candidate

    # Mirrors sale_batch_pick's fill rule exactly (app/routes/sales.py):
    # with a picked batch, the batch price is the SOLE source (Pitfall 4 —
    # no card fill when a batch was required), falling back to the card
    # sale_cents only when the batch itself has no price snapshot (D-14).
    fill_price_cents: int | None = None
    fill_price_hint = ""
    if picked is not None:
        if picked.price_cents is not None:
            fill_price_cents = picked.price_cents
            fill_price_hint = "Цена подставлена из партии — можно изменить."
        else:
            fill_price_cents = product.sale_cents if product is not None else None
            fill_price_hint = "Цена подставлена из карточки товара — можно изменить."

    context = {
        "code": code_clean,
        "name": product.name if product is not None else "",
        "batch_id": picked.id if picked else "",
        "qty": "",
        "price": "",
        "fill_price_cents": fill_price_cents,
        "fill_price_hint": fill_price_hint,
        # 11-UAT.md Test 4 (Bug B): this route's only caller is the batch
        # step's own "Далее" button, so a batch step was always shown for
        # this line — this step's own "Назад" must return to it (fresh
        # cards via GET /m/sales/step/batch), not skip past it.
        "from_batch_step": True,
        **acc,
    }
    return templates.TemplateResponse(request, "mobile_partials/sale_step_qty_price.html", context)


def _basket_lines(
    session: Session,
    code_acc: list[str],
    qty_acc: list[str],
    price_acc: list[str],
    batch_acc: list[str],
) -> list[dict]:
    """Display-only re-echo of the accumulated basket for the Корзина screen.

    Purely presentational (product name + batch summary lookups) — never a
    trust boundary. register_sale (called only from POST /m/sales) is the
    single source of truth for validation (T-11-11).
    """
    lines = []
    for code, qty, price, batch_id in zip(code_acc, qty_acc, price_acc, batch_acc, strict=False):
        code_clean = code.strip()
        product = session.scalars(
            select(Product).where(Product.code == code_clean, Product.deleted_at.is_(None))
        ).first()
        batch = session.get(Batch, batch_id) if batch_id else None
        if batch is not None and product is not None and batch.product_id != product.id:
            batch = None
        lines.append(
            {
                "code": code,
                "qty": qty,
                "price": price,
                "batch_id": batch_id,
                "product_name": product.name if product is not None else code_clean,
                "batch": batch,
            }
        )
    return lines


@router.post("/m/sales/step/basket-add")
def mobile_sale_step_basket_add(
    request: Request,
    code: str = Form(""),
    qty: str = Form(""),
    price: str = Form(""),
    batch_id: str = Form(""),
    code_acc: list[str] = Form([], alias="code_acc[]"),
    qty_acc: list[str] = Form([], alias="qty_acc[]"),
    price_acc: list[str] = Form([], alias="price_acc[]"),
    batch_acc: list[str] = Form([], alias="batch_acc[]"),
    session: Session = Depends(get_session),
):
    code_acc = [*code_acc, code]
    qty_acc = [*qty_acc, qty]
    price_acc = [*price_acc, price]
    batch_acc = [*batch_acc, batch_id]
    context = {"lines": _basket_lines(session, code_acc, qty_acc, price_acc, batch_acc)}
    return templates.TemplateResponse(request, "mobile_partials/sale_basket.html", context)


@router.post("/m/sales")
def mobile_sale_create(
    request: Request,
    code_acc: list[str] = Form([], alias="code_acc[]"),
    qty_acc: list[str] = Form([], alias="qty_acc[]"),
    price_acc: list[str] = Form([], alias="price_acc[]"),
    batch_acc: list[str] = Form([], alias="batch_acc[]"),
    confirm: str = Form(""),
    session: Session = Depends(get_session),
):
    try:
        result, errors = register_sale(
            session,
            customer_id="",  # D-04: no mobile customer picker this phase
            codes=code_acc,
            qtys=qty_acc,
            prices=price_acc,
            batch_ids=batch_acc,
            confirm=confirm,
        )
    except Exception:  # noqa: BLE001 — UI-SPEC: block error, never a raw 500
        # WR-01: rollback FIRST — an unexpected failure may have left the
        # session needing rollback (e.g. a failed flush/commit); the
        # _basket_lines query below would otherwise raise an unhandled
        # PendingRollbackError instead of this graceful 422.
        session.rollback()
        logger.exception("register_sale failed")
        context = {
            "errors": {"form": SAVE_FAILED_ERROR},
            "lines": _basket_lines(session, code_acc, qty_acc, price_acc, batch_acc),
        }
        return templates.TemplateResponse(
            request, "mobile_partials/sale_basket.html", context, status_code=422
        )

    # PRICE-01/SAL-04/D-08/D-09/T-11-12: both keys are checked (not just
    # "oversell") so a basket tripping ONLY below_minimum still warns —
    # zero writes until the danger button re-POSTs with confirm=1.
    if result and (result.get("oversell") or result.get("below_minimum")):
        context = {
            "oversell": result.get("oversell"),
            "below_minimum": result.get("below_minimum"),
            "lines": _basket_lines(session, code_acc, qty_acc, price_acc, batch_acc),
        }
        return templates.TemplateResponse(request, "mobile_partials/sale_warning.html", context)

    if errors:
        context = {
            "errors": errors,
            "lines": _basket_lines(session, code_acc, qty_acc, price_acc, batch_acc),
        }
        return templates.TemplateResponse(
            request, "mobile_partials/sale_basket.html", context, status_code=422
        )

    # D-05: success -> post-success confirmation screen (sale_step_product.html
    # doubles as this screen when `saved` is set); "Добавить ещё" restarts the
    # wizard at step 1 via a fresh GET /m/sales.
    context = {"saved": result}
    return templates.TemplateResponse(request, "mobile_partials/sale_step_product.html", context)
