"""History page (OPS-04): thin route, read-only via app/services/operations.py."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.operations import filter_products, history_view

router = APIRouter()


@router.get("/history")
def history_page(
    request: Request,
    type: str = "",
    product: str = "",
    page: int = 0,
    session: Session = Depends(get_session),
):
    result = history_view(session, type_filter=type or None, product_id=product or None, page=page)
    # D-14/D-15: an HX request (filter change or "Показать ещё") gets the
    # rows-only partial with oob=True so the load-more control replaces
    # itself in place. A request that already carries a type/product filter
    # (even a plain, non-HX GET — e.g. a reload of a hx-push-url'd link)
    # also gets the rows-only partial: the full page's filter-bar <select>
    # unconditionally lists every RU type label / every active product as
    # <option> text, so rendering the full chrome around an already-narrowed
    # result would leak the OTHER (unselected) options' text into the
    # response regardless of which rows matched. Only a bare, unfiltered
    # navigation renders the whole page with the filter bar and nav.
    is_hx = bool(request.headers.get("HX-Request"))
    is_filtered = bool(type) or bool(product)
    context = {
        "rows": result["rows"],
        "has_next": result["has_next"],
        "page": result["page"],
        "type_filter": result["type_filter"],
        "product_id": result["product_id"],
        "oob": is_hx,
    }
    if is_hx or is_filtered:
        return templates.TemplateResponse(request, "partials/history_rows.html", context)
    context["products"] = filter_products(session)
    return templates.TemplateResponse(request, "pages/history.html", context)
