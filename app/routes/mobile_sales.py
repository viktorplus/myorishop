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

# mobile_finance.py:26 (`from app.routes.reports import _resolve_period`) is
# the in-repo precedent for a mobile route module importing a private
# helper from a desktop route module — it licenses this import too.
from app.routes.sales import _CUSTOMER_MODES
from app.services.batches import active_warehouses, open_batches
from app.services.customers import create_customer, customer_search_view, get_customer
from app.services.pricing import reference_prices_for_code
from app.services.sales import (
    PRODUCT_NOT_FOUND_TMPL,
    SALE_BATCH_FILL_HINT,
    SALE_CARD_FILL_HINT,
    lookup_prefill,
    register_sale,
)

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


def _warehouse_names(session: Session) -> dict[str, str]:
    """id -> name map so a wizard step can show its own «Склад:» line."""
    return {w.id: w.name for w in active_warehouses(session)}


def _m_customer_context(
    session: Session, mode: str, customer_id: str, form: dict[str, str]
) -> dict:
    """Mobile twin of app.routes.sales._customer_context.

    Mirrors that builder's LOGIC only — allow-list `mode` against the
    imported `_CUSTOMER_MODES` (default "existing"), resolve `selected`
    via `get_customer` only when mode is "existing" and the id is
    non-empty, degrade an unresolvable id to "nothing selected" (mirrors
    `_build_lines`'/`_customer_context`'s batch/customer rule), and
    return `mode`, `customer_id`, `selected`, `form`.

    Deliberately NOT a direct import of `_customer_context` itself: that
    builder is bound to the desktop template's echo-field shape, and this
    partial's echo fields differ (D-04 is full parity, not a shared
    object). Do not "de-duplicate" the two into one shared helper — it
    would then have to serve two different templates and would break the
    moment either one's echo shape changes independently.

    Returns NO "errors" key on purpose (mirrors `_customer_context`):
    callers own their own errors dict; returning one here would clobber a
    caller's real errors on merge.
    """
    mode = mode if mode in _CUSTOMER_MODES else "existing"
    selected = None
    if mode == "existing" and customer_id:
        selected = get_customer(session, customer_id)
    return {
        "mode": mode,
        "customer_id": selected.id if selected else "",
        "selected": selected,
        "form": form,
    }


# Route order: the three literal /m/sales/customer* paths below are
# declared as literal paths (no {...} segment), matching the desktop
# module's convention that literal paths precede any parameterized route.


@router.get("/m/sales/customer-mode")
def mobile_sale_customer_mode(
    request: Request,
    customer_mode: str = "existing",
    customer_id: str = "",
    customer_id_keep: str = "",
    customer_q: str = "",
    name: str = "",
    surname: str = "",
    consultant_number: str = "",
    session: Session = Depends(get_session),
):
    # SALE-03/D-03: the mode radio's hx-get lands here on every switch.
    # Coalesce customer_id/customer_id_keep — whichever mode is LEAVING
    # supplies one of them (the visible hidden input, or the inactive
    # echo).
    raw_id = customer_id or customer_id_keep
    context = {
        **_m_customer_context(
            session,
            customer_mode,
            raw_id,
            {
                "customer_q": customer_q,
                "name": name,
                "surname": surname,
                "consultant_number": consultant_number,
            },
        ),
        "customer_id_keep": raw_id,
        "errors": {},
    }
    return templates.TemplateResponse(request, "mobile_partials/sale_customer.html", context)


@router.get("/m/sales/customer-search")
def mobile_sale_customer_search(
    request: Request, q: str = "", session: Session = Depends(get_session)
):
    # D-05: rows-only partial for the mobile selector's autocomplete
    # picker. The search backend needs ZERO changes — search_customers
    # already matches name, surname AND consultant number via the
    # search_lc shadow column, and Cyrillic folding cannot happen in
    # SQLite (customers.py:5-7), so it is never reimplemented in SQL here.
    context = customer_search_view(session, q)
    return templates.TemplateResponse(request, "mobile_partials/customer_picker.html", context)


@router.post("/m/sales/customer")
def mobile_sale_customer_create(
    request: Request,
    name: str = Form(""),
    surname: str = Form(""),
    consultant_number: str = Form(""),
    customer_q: str = Form(""),
    session: Session = Depends(get_session),
):
    # D-05 mirror: inline quick-create from the mobile selector. Reuses
    # the same create_customer service call as desktop's /sales/customer
    # — never a raw ORM insert built by hand here, which would skip the
    # search_lc maintenance and make the new customer permanently
    # invisible to the autocomplete.
    try:
        customer, errors = create_customer(
            session, name=name, surname=surname, consultant_number=consultant_number
        )
    except Exception:  # noqa: BLE001 — UI-SPEC: block error, never a raw 500
        # WR-01 (mobile-specific): rollback FIRST — an unexpected failure
        # may have left the session needing rollback (e.g. a failed
        # flush/commit); a following query would otherwise raise an
        # unhandled PendingRollbackError instead of this graceful 422.
        session.rollback()
        logger.exception("create_customer failed")
        context = {
            **_m_customer_context(
                session,
                "new",
                "",
                {
                    "name": name,
                    "surname": surname,
                    "consultant_number": consultant_number,
                    "customer_q": customer_q,
                },
            ),
            "errors": {"quick_create": SAVE_FAILED_ERROR},
        }
        return templates.TemplateResponse(
            request, "mobile_partials/sale_customer.html", context, status_code=422
        )

    if errors:
        context = {
            **_m_customer_context(
                session,
                "new",
                "",
                {
                    "name": name,
                    "surname": surname,
                    "consultant_number": consultant_number,
                    "customer_q": customer_q,
                },
            ),
            "errors": errors,
        }
        return templates.TemplateResponse(
            request, "mobile_partials/sale_customer.html", context, status_code=422
        )

    context = {**_m_customer_context(session, "existing", customer.id, {}), "errors": {}}
    return templates.TemplateResponse(request, "mobile_partials/sale_customer.html", context)


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
        # PROD-06 (Phase 18 plan 08): ref_pc_cents is the code's CATALOG ПЦ
        # reference (D-05/D-08/D-22) — independent of the dictionary/product
        # match, a code can still carry a CatalogPrice row.
        _, ref_pc_cents = reference_prices_for_code(session, code_clean)
        context = {
            "code": code_clean,
            "name": result["name"],
            "batch_id": "",
            "fill_price_cents": None,
            "fill_price_hint": "",
            "ref_pc_cents": ref_pc_cents,
            # 11-UAT.md Test 4 (Bug B): no batch step was ever shown for a
            # dictionary-only match, so this step's own "Назад" must return
            # straight to the product step, not to a batch step that never
            # existed.
            "from_batch_step": False,
            # No batch exists at this branch, so warehouse is never knowable
            # (explicit None, never "" — mirrors corrections' convention).
            "warehouse_name": None,
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
        "warehouse_names": _warehouse_names(session),
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
        "warehouse_names": _warehouse_names(session),
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

    # T-13-11: warehouse_name resolved ONLY from the already ownership-
    # validated `picked` batch above, never from a raw client-supplied field.
    # Line wrapped (Phase 18 plan 08): pre-existing ruff E501, deferred at
    # 18-06, now fixed since this plan touches mobile_sales.py anyway.
    warehouse_name = (
        _warehouse_names(session).get(picked.warehouse_id) if picked is not None else None
    )

    # Mirrors sale_batch_pick's fill rule exactly (app/routes/sales.py):
    # with a picked batch, the batch price is the SOLE source (Pitfall 4 —
    # no card fill when a batch was required), falling back to the card
    # sale_cents only when the batch itself has no price snapshot (D-14).
    fill_price_cents: int | None = None
    fill_price_hint = ""
    if picked is not None:
        if picked.price_cents is not None:
            fill_price_cents = picked.price_cents
            fill_price_hint = SALE_BATCH_FILL_HINT
        else:
            fill_price_cents = product.sale_cents if product is not None else None
            fill_price_hint = SALE_CARD_FILL_HINT

    # PROD-06 (Phase 18 plan 08): ref_pc_cents is the code's CATALOG ПЦ
    # reference (D-05/D-08/D-22), resolved independently of fill_price_cents
    # — the batch/card fill value is not the same thing as the catalog
    # reference the cue compares against.
    _, ref_pc_cents = reference_prices_for_code(session, code_clean)

    context = {
        "code": code_clean,
        "name": product.name if product is not None else "",
        "batch_id": picked.id if picked else "",
        "qty": "",
        "price": "",
        "fill_price_cents": fill_price_cents,
        "fill_price_hint": fill_price_hint,
        "ref_pc_cents": ref_pc_cents,
        # 11-UAT.md Test 4 (Bug B): this route's only caller is the batch
        # step's own "Далее" button, so a batch step was always shown for
        # this line — this step's own "Назад" must return to it (fresh
        # cards via GET /m/sales/step/batch), not skip past it.
        "from_batch_step": True,
        "warehouse_name": warehouse_name,
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
    warehouse_names = _warehouse_names(session)
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
                # Line wrapped (Phase 18 plan 08): pre-existing ruff E501,
                # deferred at 18-06, now fixed since this plan touches
                # mobile_sales.py anyway.
                "warehouse_name": (
                    warehouse_names.get(batch.warehouse_id) if batch is not None else None
                ),
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
    customer_id: str = Form(""),
    confirm: str = Form(""),
    session: Session = Depends(get_session),
):
    try:
        result, errors = register_sale(
            session,
            customer_id=customer_id,
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
