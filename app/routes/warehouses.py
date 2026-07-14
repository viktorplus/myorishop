"""Warehouse management page (WH-01): thin routes, all writes in app/services/warehouses.py.

D-08: this backs a single settings-style page (/warehouses) — every write
response re-renders `partials/warehouse_rows.html` in place, there is no
separate `/warehouses/new` or `/warehouses/{id}/edit` page, unlike Products.

Phase 14 (LIST-01..04): GET /warehouses gains name/address/status/sort/page
query params and an is_hx dual-response branch (mirrors app/routes/history.py).
No new route was added — POST /warehouses/{id}/delete stays the single
quick-delete endpoint, now carrying both the existing last-active warning
and the new D-11 stock-guard block in the same context.
"""

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.pagination import page_window
from app.services.warehouses import (
    add_warehouse,
    list_warehouses,
    restore_warehouse,
    soft_delete_warehouse,
    update_warehouse,
)

router = APIRouter()

# Route order: no literal /warehouses/* sub-path collides with the
# parameterized /warehouses/{warehouse_id} routes below, but the convention
# (literal paths declared before parameterized ones) is kept for consistency.


def _warehouses_context(
    session: Session,
    *,
    name: str = "",
    address: str = "",
    status: str = "",
    sort: str = "",
    page: int = 0,
    warning_id: str | None = None,
    stock_blocked_id: str | None = None,
    stock_blocked_qty: int | None = None,
    errors: dict | None = None,
    form: dict | None = None,
    error_entry_id: str | None = None,
    error_form: dict | None = None,
) -> dict:
    """Shared template context for every warehouse GET/POST response."""
    result = list_warehouses(
        session, name=name, address=address, status=status, sort=sort, page=page
    )
    pw = page_window(result["page"], result["total_pages"])
    qs_parts = {
        key: value
        for key, value in {
            "name": result["name"],
            "address": result["address"],
            "status": result["status"],
            "sort": result["sort"],
        }.items()
        if value
    }
    extra_qs = ("&" + urlencode(qs_parts)) if qs_parts else ""
    return {
        "warehouses": result["warehouses"],
        "page": result["page"],
        "total": result["total"],
        "total_pages": result["total_pages"],
        "page_window": pw,
        "name": result["name"],
        "address": result["address"],
        "status": result["status"],
        "sort": result["sort"],
        "list_url": "/warehouses",
        "rows_target_id": "warehouse-rows",
        "extra_qs": extra_qs,
        "errors": errors or {},
        "form": form or {},
        "warning_id": warning_id,
        "stock_blocked_id": stock_blocked_id,
        "stock_blocked_qty": stock_blocked_qty,
        "error_entry_id": error_entry_id,
        "error_form": error_form,
    }


@router.get("/warehouses")
def warehouses_page(
    request: Request,
    name: str = "",
    address: str = "",
    status: str = "",
    sort: str = "",
    page: int = 0,
    session: Session = Depends(get_session),
):
    context = _warehouses_context(
        session, name=name, address=address, status=status, sort=sort, page=page
    )
    is_hx = bool(request.headers.get("HX-Request"))
    if is_hx:
        return templates.TemplateResponse(request, "partials/warehouse_rows.html", context)
    return templates.TemplateResponse(request, "pages/warehouses.html", context)


@router.post("/warehouses")
def warehouse_add(
    request: Request,
    name: str = Form(""),
    address: str = Form(""),
    session: Session = Depends(get_session),
):
    _, errors = add_warehouse(session, name=name, address=address)
    context = _warehouses_context(
        session,
        errors=errors,
        form={"name": name, "address": address} if errors else {},
    )
    return templates.TemplateResponse(
        request,
        "partials/warehouse_rows.html",
        context,
        status_code=422 if errors else 200,
    )


@router.post("/warehouses/{warehouse_id}")
def warehouse_update(
    request: Request,
    warehouse_id: str,
    name: str = Form(""),
    address: str = Form(""),
    session: Session = Depends(get_session),
):
    _, errors = update_warehouse(session, warehouse_id, name=name, address=address)
    if "warehouse" in errors:
        raise HTTPException(status_code=404, detail="unknown warehouse")
    context = _warehouses_context(
        session,
        errors=errors,
        error_entry_id=warehouse_id if errors else None,
        error_form={"name": name, "address": address} if errors else None,
    )
    return templates.TemplateResponse(
        request,
        "partials/warehouse_rows.html",
        context,
        status_code=422 if errors else 200,
    )


@router.post("/warehouses/{warehouse_id}/delete")
def warehouse_delete(
    request: Request,
    warehouse_id: str,
    confirm: str = Form(""),
    session: Session = Depends(get_session),
):
    # D-11 stock guard runs first inside soft_delete_warehouse and is
    # non-overridable; the existing warn-but-allow last-active-warehouse
    # guard (D-06/D-07) is only reached once the stock guard has passed.
    # Both are plain 200 warn states, not validation errors or redirects.
    _, warning = soft_delete_warehouse(session, warehouse_id, confirm=confirm == "1")
    context = _warehouses_context(
        session,
        warning_id=warehouse_id if warning.get("warehouse") else None,
        stock_blocked_id=warehouse_id if warning.get("stock") else None,
        stock_blocked_qty=warning.get("stock"),
    )
    return templates.TemplateResponse(request, "partials/warehouse_rows.html", context)


@router.post("/warehouses/{warehouse_id}/restore")
def warehouse_restore(
    request: Request, warehouse_id: str, session: Session = Depends(get_session)
):
    restore_warehouse(session, warehouse_id)
    context = _warehouses_context(session)
    return templates.TemplateResponse(request, "partials/warehouse_rows.html", context)
