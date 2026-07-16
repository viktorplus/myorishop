"""Warehouse management page (WH-01): thin routes, all writes in app/services/warehouses.py.

Phase 14 (LIST-01..04): GET /warehouses gains name/address/status/sort/page
query params and an is_hx dual-response branch (mirrors app/routes/history.py).

Phase 20 plan 02 (WH-02, D-01/D-02): add/edit/delete moved off the list's
inline row rendering onto dedicated `GET /warehouses/new` /
`GET /warehouses/{id}/edit` pages, mirroring `app/routes/products.py`'s
`/new`/`/{id}/edit` shape — redirect-after-POST on success, 422-re-render on
the SAME form page on validation error. `partials/warehouse_rows.html` (this
page's list) is untouched by this plan; only its former inline
add/edit/delete controls moved away from it.
"""

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Warehouse
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


@router.get("/warehouses/new")
def warehouse_new(request: Request):
    context = {"warehouse": None, "errors": {}, "form": {}}
    return templates.TemplateResponse(request, "pages/warehouse_form.html", context)


@router.post("/warehouses")
def warehouse_add(
    request: Request,
    name: str = Form(""),
    address: str = Form(""),
    session: Session = Depends(get_session),
):
    _, errors = add_warehouse(session, name=name, address=address)
    if errors:
        context = {
            "warehouse": None,
            "errors": errors,
            "form": {"name": name, "address": address},
        }
        return templates.TemplateResponse(
            request, "pages/warehouse_form.html", context, status_code=422
        )
    return RedirectResponse("/warehouses", status_code=303)


@router.get("/warehouses/{warehouse_id}/edit")
def warehouse_edit(
    request: Request, warehouse_id: str, session: Session = Depends(get_session)
):
    warehouse = session.get(Warehouse, warehouse_id)
    # WR-02: a soft-deleted warehouse is not editable — treat its edit URL
    # (bookmark/history/typed) the same as an unknown id.
    if warehouse is None or warehouse.deleted_at is not None:
        raise HTTPException(status_code=404, detail="unknown warehouse")
    context = {"warehouse": warehouse, "errors": {}, "form": None}
    return templates.TemplateResponse(request, "pages/warehouse_form.html", context)


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
    if errors:
        existing = session.get(Warehouse, warehouse_id)
        context = {
            "warehouse": existing,
            "errors": errors,
            "form": {"name": name, "address": address},
        }
        return templates.TemplateResponse(
            request, "pages/warehouse_form.html", context, status_code=422
        )
    return RedirectResponse("/warehouses", status_code=303)


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
    warehouse = session.get(Warehouse, warehouse_id)
    if warehouse is None:
        raise HTTPException(status_code=404, detail="unknown warehouse")
    deleted, warning = soft_delete_warehouse(session, warehouse_id, confirm=confirm == "1")
    if deleted:
        # Terminal success — mirrors product_delete exactly.
        return Response(status_code=200, headers={"HX-Redirect": "/warehouses"})
    # Non-terminal warn states (stock-blocked or last-active-warning) swap
    # the delete wrap in place — status 200, these are warn states, not
    # validation errors.
    context = {
        "warehouse": warehouse,
        "stock_blocked": warning.get("stock"),
        "warning": warning.get("warehouse"),
    }
    return templates.TemplateResponse(request, "partials/warehouse_delete_wrap.html", context)


@router.post("/warehouses/{warehouse_id}/restore")
def warehouse_restore(
    request: Request, warehouse_id: str, session: Session = Depends(get_session)
):
    restore_warehouse(session, warehouse_id)
    context = _warehouses_context(session)
    return templates.TemplateResponse(request, "partials/warehouse_rows.html", context)
