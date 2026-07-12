"""Mobile history page (Phase 11 Plan 08): thin route, reuses
app.services.operations.history_view unchanged — no new ledger query.

Single simplified filter (Тип операции only — no product filter, per
UI-SPEC's CONTEXT discretion). Mirrors app/routes/history.py's CR-01
HX-Request branching: a genuine htmx request (filter change or "Показать
ещё") gets the chrome-less cards partial plus an oob-swapped load-more
control; a plain GET gets the full mobile_pages/history.html chrome.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.operations import history_view

router = APIRouter()


@router.get("/m/history")
def mobile_history_page(
    request: Request,
    type: str = "",
    page: int = 0,
    session: Session = Depends(get_session),
):
    result = history_view(session, type_filter=type or None, product_id=None, page=page)
    context = {
        "rows": result["rows"],
        "has_next": result["has_next"],
        "page": result["page"],
        "type_filter": result["type_filter"],
    }
    is_hx = bool(request.headers.get("HX-Request"))
    if is_hx:
        # CR-01-precedent: two structural siblings in one response — the
        # cards (main-swap payload) and an oob-swapped load-more control —
        # never nested, so a filter-change innerHTML swap can never destroy
        # the load-more control.
        cards_html = templates.get_template("mobile_partials/history_cards.html").render(
            **context
        )
        load_more_html = templates.get_template(
            "mobile_partials/history_load_more.html"
        ).render(oob=True, **context)
        return HTMLResponse(cards_html + load_more_html)
    return templates.TemplateResponse(request, "mobile_pages/history.html", context)
