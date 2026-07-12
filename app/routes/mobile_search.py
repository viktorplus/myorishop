"""Mobile stock search (T-11-04/T-11-06): reuses catalog.search_view unchanged.

Read-only: GET /m/search (ranked/capped/Cyrillic-safe results, unchanged
service call) and GET /m/search/product/{product_id} (read-only per-warehouse
stock summary). No edit/POST route on mobile this phase.
"""

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Product
from app.routes import templates
from app.services.batches import active_warehouses, open_batches
from app.services.catalog import search_view

router = APIRouter()


@router.get("/m/search")
def mobile_search(request: Request, q: str = "", session: Session = Depends(get_session)):
    context = search_view(session, q)
    # CR-01-precedent (history.py): only a genuine HX-Request gets the
    # rows-only fragment; a bookmarked/reloaded ?q=... URL still gets chrome.
    if bool(request.headers.get("HX-Request")):
        return templates.TemplateResponse(
            request, "mobile_partials/search_results.html", context
        )
    return templates.TemplateResponse(request, "mobile_pages/search.html", context)


@router.get("/m/search/product/{product_id}")
def mobile_search_product_detail(
    request: Request, product_id: str, session: Session = Depends(get_session)
):
    # T-11-06: session.get returns None for a nonexistent id -> plain 404,
    # never a different product's data or a stack trace.
    product = session.get(Product, product_id)
    if product is None or product.deleted_at is not None:
        return Response(status_code=404)

    warehouse_names = {w.id: w.name for w in active_warehouses(session)}
    totals: dict[str, int] = {}
    for b in open_batches(session, product.id):
        totals[b.warehouse_id] = totals.get(b.warehouse_id, 0) + b.quantity

    stock_rows = sorted(
        (
            {"warehouse_name": warehouse_names.get(warehouse_id, ""), "total_qty": qty}
            for warehouse_id, qty in totals.items()
        ),
        key=lambda row: row["warehouse_name"],
    )

    context = {"product": product, "stock_rows": stock_rows}
    return templates.TemplateResponse(
        request, "mobile_partials/search_product_detail.html", context
    )
