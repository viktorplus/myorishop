"""Mobile batch edit screen (quick-260813-i28): mirrors app/routes/batches.py
exactly, but at /m/batches/{id}/edit (GET) and /m/batches/{id} (POST), and
redirects a successful save to /m/search/product/{id} — the closest mobile
analog to "back to the product".
"""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Batch, Product, Warehouse
from app.routes import templates
from app.services.batches import update_batch

router = APIRouter()


@router.get("/m/batches/{batch_id}/edit")
def mobile_batch_edit(request: Request, batch_id: str, session: Session = Depends(get_session)):
    batch = session.get(Batch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="unknown batch")
    product = session.get(Product, batch.product_id)
    warehouse = session.get(Warehouse, batch.warehouse_id)
    context = {
        "batch": batch,
        "product": product,
        "warehouse": warehouse,
        "errors": {},
        "form": None,
    }
    return templates.TemplateResponse(request, "mobile_pages/batch_edit.html", context)


@router.post("/m/batches/{batch_id}")
def mobile_batch_update(
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
            request, "mobile_pages/batch_edit.html", context, status_code=422
        )
    return RedirectResponse(f"/m/search/product/{batch.product_id}", status_code=303)
