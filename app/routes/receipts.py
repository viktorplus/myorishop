"""Goods receipt pages (RCP-01/RCP-02): thin routes, writes in app/services/receipts.py."""

import logging

from fastapi import APIRouter, Depends, Form, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Product
from app.routes import templates
from app.services.batches import active_warehouses, open_batches
from app.services.receipts import lookup_prefill, recent_receipts, register_receipt

logger = logging.getLogger(__name__)

router = APIRouter()

# Route order: literal paths (/receipts/new, /receipts/lookup, /receipts/batches)
# MUST stay declared before any parameterized /receipts/{...} routes added later.

SAVE_FAILED_ERROR = "Не удалось сохранить. Проверьте данные и попробуйте ещё раз."
CARD_FILL_HINT = "Данные подставлены из карточки товара — новые цены обновят карточку."
# D-01/D-04 (Phase 12): unknown-to-Product code matched by Dictionary and/or
# CatalogPrice. Must stay non-empty — name_input.html's `hint | default(...)`
# filter falls back to the dictionary wording for an empty hint string.
CATALOG_FILL_HINT = "Цена и название подставлены из каталога — можно изменить."
# D-02 (RESEARCH Open Q2): the receipt form preselects the Phase 8 seeded
# default warehouse when it is still active. Re-declared, never imported from
# the migration (frozen 0007 D-03 contract).
DEFAULT_WAREHOUSE_ID = "00000000-0000-4000-8000-000000000010"


def _preselect_warehouse_id(actives: list, submitted: str = "") -> str:
    """Echo a submitted warehouse, else preselect the seeded default when active,
    else the first active warehouse alphabetically (RESEARCH Open Q2)."""
    submitted = submitted.strip()
    if submitted:
        return submitted
    ids = {w.id for w in actives}
    if DEFAULT_WAREHOUSE_ID in ids:
        return DEFAULT_WAREHOUSE_ID
    return actives[0].id if actives else ""


def _chooser_context(session: Session, code: str, warehouse_id: str, actives: list) -> dict:
    """Chooser render context (D-01/D-02). Zero active warehouses -> blocking
    hint; otherwise the product's open batches in that warehouse (empty for an
    unknown/new code -> the template shows the new-batch-only path)."""
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


def _form_extras(session: Session, *, code: str = "", warehouse_id: str = "") -> dict:
    """Shared receipt-form context: active warehouses, the preselected warehouse,
    and the chooser state — merged into every receipt_form.html render path."""
    actives = active_warehouses(session)
    selected = _preselect_warehouse_id(actives, warehouse_id)
    return {
        "active_warehouses": actives,
        "selected_warehouse_id": selected,
        **_chooser_context(session, code, selected, actives),
    }


@router.get("/receipts/new")
def receipt_new_page(request: Request, session: Session = Depends(get_session)):
    context = {
        "errors": {},
        "form": {},
        "focus_code": False,
        "receipts": recent_receipts(session),
        **_form_extras(session),
    }
    return templates.TemplateResponse(request, "pages/receipt_form.html", context)


@router.get("/receipts/batches")
def receipt_batches(
    request: Request,
    code: str = "",
    warehouse_id: str = "",
    session: Session = Depends(get_session),
):
    # D-01: the resolve-or-create chooser — refreshed on a warehouse change (and
    # oob on the code lookup). Server decides content; the browser only swaps.
    actives = active_warehouses(session)
    context = _chooser_context(session, code, warehouse_id.strip(), actives)
    return templates.TemplateResponse(
        request, "partials/receipt_batch_chooser.html", context
    )


@router.get("/receipts/lookup")
def receipt_lookup(
    request: Request,
    code: str = "",
    name: str = "",
    cost: str = "",
    sale: str = "",
    warehouse_id: str = "",
    session: Session = Depends(get_session),
):
    # Phase 2 D-23 contract: the SERVER decides fill vs no-op, htmx ignores
    # 204. Pitfall 7: a non-empty operator name is never overwritten; PD-10:
    # typed price fields are excluded from the fill (empty-after-strip only).
    if name.strip():
        return Response(status_code=204)
    result = lookup_prefill(session, code)
    if result is None:
        return Response(status_code=204)
    if result["source"] == "product":
        # Pitfall 1 / D-01: catalog field removed from the receipt slice —
        # only cost/sale are ever fillable now.
        typed = {"cost": cost, "sale": sale}
        fill_fields = [f for f in ("cost", "sale") if not typed[f].strip()]
        hint = CARD_FILL_HINT
        # D-01: an existing product has open batches to top up — oob-refresh the
        # chooser so the operator sees them without touching the warehouse select.
        actives = active_warehouses(session)
        chooser = _chooser_context(session, code, warehouse_id.strip(), actives)
        include_chooser = True
    else:
        # WR-02: lookup_prefill only ever returns source == "product",
        # source == "catalog", or None (handled above) — the old
        # "dictionary" source was removed by this phase's diff, so this is
        # the only remaining branch.
        # D-01/D-04 (Phase 12/PRICE-04): unknown-to-Product code matched by
        # Dictionary and/or CatalogPrice. Pitfall 1: reuse the exact same
        # "still empty after strip" computation as the product branch above.
        # D-02 superseded: the catalog consumer price (ПЦ) is this shop's
        # default sale price, so "sale" fills the same as cost. Catalog field
        # removed from the receipt slice — only cost/sale are ever fillable.
        typed = {"cost": cost, "sale": sale}
        fill_fields = [f for f in ("cost", "sale") if not typed[f].strip()]
        hint = CATALOG_FILL_HINT
        # D-05: the batch chooser is untouched by this branch — same empty
        # state as the dictionary-only fallback used previously.
        chooser = {"zero_warehouses": False, "batches": [], "code_entered": False}
        include_chooser = False
    context = {
        # None-guard: result["name"] can be None when only a CatalogPrice
        # match exists (no Dictionary entry) — name_input.html's
        # value="{{ name }}" has no `or ''` guard of its own.
        "name": result["name"] or "",
        "hint": hint,
        "source": result["source"],
        "fill_fields": fill_fields,
        "prices": result["prices"],
        "include_chooser": include_chooser,
        **chooser,
    }
    return templates.TemplateResponse(request, "partials/receipt_lookup.html", context)


@router.post("/receipts")
def receipt_create(
    request: Request,
    code: str = Form(""),
    name: str = Form(""),
    qty: str = Form(""),
    cost: str = Form(""),
    sale: str = Form(""),
    warehouse_id: str = Form(""),
    batch_choice: str = Form("new"),
    expiry: str = Form(""),
    location: str = Form(""),
    comment: str = Form(""),
    session: Session = Depends(get_session),
):
    # Money/qty fields arrive as strings on purpose: Pydantic v2 rejects ""
    # for int | None, and parsing in the service gives the RU errors.
    form_echo = {
        "code": code,
        "name": name,
        "qty": qty,
        "cost": cost,
        "sale": sale,
        "warehouse_id": warehouse_id,
        "batch_choice": batch_choice,
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
            warehouse_id=warehouse_id,
            batch_choice=batch_choice,
            expiry_raw=expiry,
            location_raw=location,
            comment_raw=comment,
        )
    except Exception:  # noqa: BLE001 — UI-SPEC: block error, never a raw 500
        # CR-01: defensive rollback before re-querying the session, mirroring
        # writeoffs.py (WR-03) / returns.py (CR-03). Without it a commit-time
        # OperationalError (e.g. SQLite "database is locked") leaves the session
        # in a pending-rollback state, so the _form_extras() SELECTs below raise
        # PendingRollbackError → raw 500, violating the "never a raw 500" contract.
        session.rollback()
        logger.exception("register_receipt failed")
        context = {
            "errors": {"form": SAVE_FAILED_ERROR},
            "form": form_echo,
            "focus_code": False,
            "include_oob_rows": False,
            **_form_extras(session, code=code, warehouse_id=warehouse_id),
        }
        return templates.TemplateResponse(
            request, "partials/receipt_form.html", context, status_code=422
        )
    if errors:
        context = {
            "errors": errors,
            "form": form_echo,
            "focus_code": False,
            "include_oob_rows": False,
            **_form_extras(session, code=code, warehouse_id=warehouse_id),
        }
        return templates.TemplateResponse(
            request, "partials/receipt_form.html", context, status_code=422
        )
    # D-02: success -> fresh empty form + success line + focus back to «Код»;
    # D-04: the refreshed recent list rides along as an oob swap.
    context = {
        "errors": {},
        "form": {},
        "saved": {"name": result["product"].name, "qty": result["operation"].qty_delta},
        "focus_code": True,
        "receipts": recent_receipts(session),
        "include_oob_rows": True,
        **_form_extras(session),
    }
    return templates.TemplateResponse(request, "partials/receipt_form.html", context)
