"""Warehouse management page (WH-01): thin routes, all writes in app/services/warehouses.py.

D-08: this backs a single settings-style page (/warehouses) — every write
response re-renders `partials/warehouse_rows.html` in place, there is no
separate `/warehouses/new` or `/warehouses/{id}/edit` page, unlike Products.
"""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
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


@router.get("/warehouses")
def warehouses_page(request: Request, session: Session = Depends(get_session)):
    context = {"warehouses": list_warehouses(session), "errors": {}, "form": {}}
    return templates.TemplateResponse(request, "pages/warehouses.html", context)


@router.post("/warehouses")
def warehouse_add(
    request: Request,
    name: str = Form(""),
    address: str = Form(""),
    session: Session = Depends(get_session),
):
    _, errors = add_warehouse(session, name=name, address=address)
    context = {
        "warehouses": list_warehouses(session),
        "errors": errors,
        "form": {"name": name, "address": address} if errors else {},
    }
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
    context = {
        "warehouses": list_warehouses(session),
        "errors": errors,
        "form": {},
        "error_entry_id": warehouse_id if errors else None,
        "error_form": {"name": name, "address": address} if errors else None,
    }
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
    # Warn-but-allow last-active-warehouse guard (D-06/D-07): this is a
    # 200 warn state, not a validation error, so it never uses 422/HX-Redirect.
    _, warning = soft_delete_warehouse(session, warehouse_id, confirm=confirm == "1")
    context = {
        "warehouses": list_warehouses(session),
        "errors": {},
        "form": {},
        "warning_id": warehouse_id if warning else None,
    }
    return templates.TemplateResponse(request, "partials/warehouse_rows.html", context)


@router.post("/warehouses/{warehouse_id}/restore")
def warehouse_restore(
    request: Request, warehouse_id: str, session: Session = Depends(get_session)
):
    restore_warehouse(session, warehouse_id)
    context = {
        "warehouses": list_warehouses(session),
        "errors": {},
        "form": {},
        "warning_id": None,
    }
    return templates.TemplateResponse(request, "partials/warehouse_rows.html", context)
