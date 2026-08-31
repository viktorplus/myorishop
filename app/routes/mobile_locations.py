"""Mobile Места хранения (D-10): reuses locations.list_locations_view unchanged.

Thin route mirroring mobile_history.py's shape: a genuine HX-Request (search
or place-picker change) gets the cards partial plus an oob-swapped pagination
bar — ALWAYS both together, never nested, so a filter swap can never destroy
the pagination control (CR-01 precedent); a plain GET gets full page chrome.

Place CARDS are plain full-page links, not htmx swaps: tapping a place is
navigation, and a full render is what keeps the place picker above the list
showing the place actually being viewed (the picker is a DOM sibling of the
cards, outside every swap — the mobile filter idiom).
"""

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.locations import list_locations_view
from app.services.pagination import page_window

router = APIRouter()


@router.get("/m/locations")
def mobile_locations(
    request: Request,
    q: str = "",
    place: str = "",
    page: int = 0,
    session: Session = Depends(get_session),
):
    context = list_locations_view(session, q=q, place=place, page=page)
    qs_parts = {k: v for k, v in {"q": context["q"], "place": context["place"]}.items() if v}
    context.update(
        {
            "page_window": page_window(context["page"], context["total_pages"]),
            "list_url": "/m/locations",
            "rows_target_id": "location-cards",
            "extra_qs": ("&" + urlencode(qs_parts)) if qs_parts else "",
        }
    )
    if request.headers.get("HX-Request"):
        cards = templates.get_template("mobile_partials/location_cards.html").render(**context)
        pagination = templates.get_template("mobile_partials/location_pagination.html").render(
            oob=True, **context
        )
        return HTMLResponse(cards + pagination)
    return templates.TemplateResponse(request, "mobile_pages/locations.html", context)
