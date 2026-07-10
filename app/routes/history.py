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
    # D-14/D-15/CR-01: only a genuine htmx request (a real HX-Request header,
    # i.e. a filter change or "Показать ещё") gets the chrome-less rows-only
    # partial with oob=True so the load-more control replaces itself in
    # place. Every other request — including a plain top-level GET that
    # happens to carry a type/product filter param (a browser reload, a
    # bookmark, or a shared URL after hx-push-url wrote the filter into the
    # address bar) — must always render the full pages/history.html chrome
    # (nav + filter bar + table), with the filter bar pre-selecting the
    # current type_filter/product_id via partials/history_filters.html's
    # existing `selected` logic. Filter presence alone must never route to
    # the chrome-less partial (that was the CR-01 bug: a real browser drops
    # a bare rows fragment per HTML5 parsing rules, rendering a blank page).
    is_hx = bool(request.headers.get("HX-Request"))
    context = {
        "rows": result["rows"],
        "has_next": result["has_next"],
        "page": result["page"],
        "type_filter": result["type_filter"],
        "product_id": result["product_id"],
        "oob": is_hx,
    }
    if is_hx:
        return templates.TemplateResponse(request, "partials/history_rows.html", context)
    context["products"] = filter_products(session)
    return templates.TemplateResponse(request, "pages/history.html", context)
