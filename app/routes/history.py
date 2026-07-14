"""History page (OPS-04): thin route, read-only via app/services/operations.py."""

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.operations import filter_products, history_view
from app.services.pagination import page_window

router = APIRouter()


@router.get("/history")
def history_page(
    request: Request,
    type: str = "",
    product: str = "",
    sort: str = "",
    page: int = 0,
    session: Session = Depends(get_session),
):
    result = history_view(
        session, type_filter=type or None, product_id=product or None, sort=sort, page=page
    )
    # D-02/D-03: page-number pagination retires the old "Показать ещё"
    # load-more mechanism — both the is_hx and full-page branches now render
    # the same single swappable partials/history_rows.html block (sort
    # dropdown + header-row filters + table + pagination), consistent with
    # every other list page. `extra_qs` re-serializes the active filter/sort
    # state onto every pagination link so paging never loses the active view.
    is_hx = bool(request.headers.get("HX-Request"))
    pw = page_window(result["page"], result["total_pages"])
    qs_parts = {
        k: v
        for k, v in {
            "type": result["type_filter"],
            "product": result["product_id"],
            "sort": result["sort"],
        }.items()
        if v
    }
    extra_qs = ("&" + urlencode(qs_parts)) if qs_parts else ""
    context = {
        "rows": result["rows"],
        "page": result["page"],
        "total": result["total"],
        "total_pages": result["total_pages"],
        "page_window": pw,
        "type_filter": result["type_filter"],
        "product_id": result["product_id"],
        "sort": result["sort"],
        "list_url": "/history",
        "rows_target_id": "history-rows",
        "extra_qs": extra_qs,
        "products": filter_products(session),
    }
    if is_hx:
        return templates.TemplateResponse(request, "partials/history_rows.html", context)
    return templates.TemplateResponse(request, "pages/history.html", context)
