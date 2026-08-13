"""Batch edit page (quick-260813-i28): thin route, write in app/services/batches.py.

Mirrors app/routes/products.py's product_edit/product_update pair exactly.
Quantity/warehouse are read-only on this surface — no Form parameter for
either exists anywhere on this router.
"""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Batch, Product, Warehouse
from app.routes import templates
from app.services.batches import update_batch

router = APIRouter()


@router.get("/batches/{batch_id}/edit")
def batch_edit(request: Request, batch_id: str, session: Session = Depends(get_session)):
    batch = session.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="unknown batch")
    # Both FKs are guaranteed to resolve — mirrors transfers.py's unguarded
    # session.get(Warehouse, source.warehouse_id) precedent.
    product = session.get(Product, batch.product_id)
    warehouse = session.get(Warehouse, batch.warehouse_id)
    context = {
        "batch": batch,
        "product": product,
        "warehouse": warehouse,
        "errors": {},
        "form": None,
    }
    return templates.TemplateResponse(request, "pages/batch_form.html", context)


@router.post("/batches/{batch_id}")
def batch_update(
    request: Request,
    batch_id: str,
    name: str = Form(""),
    expiry: str = Form(""),
    location: str = Form(""),
    comment: str = Form(""),
    price: str = Form(""),
    cost: str = Form(""),
    session: Session = Depends(get_session),
):
    batch, errors = update_batch(
        session,
        batch_id,
        name_raw=name,
        expiry_raw=expiry,
        location_raw=location,
        comment_raw=comment,
        price_raw=price,
        cost_raw=cost,
    )
    if errors:
        existing = session.get(Batch, batch_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="unknown batch")
        product = session.get(Product, existing.product_id)
        warehouse = session.get(Warehouse, existing.warehouse_id)
        context = {
            "batch": existing,
            "product": product,
            "warehouse": warehouse,
            "errors": errors,
            "form": {
                "name": name,
                "expiry": expiry,
                "location": location,
                "comment": comment,
                "price": price,
                "cost": cost,
            },
        }
        return templates.TemplateResponse(
            request, "pages/batch_form.html", context, status_code=422
        )
    return RedirectResponse(f"/products/{batch.product_id}/edit", status_code=303)
