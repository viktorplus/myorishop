"""Storage-place page (D-18): thin route, all logic in app/services/locations.py.

Read-only sibling of the other Товары reference pages (/categories,
/dictionary, /catalogs) — same top-level URL shape, same HX-partial idiom as
/products: a genuine HX-Request gets the rows fragment, a bookmarked or
reloaded ?place=... URL still gets full page chrome.
"""

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.locations import list_locations_view
from app.services.pagination import page_window

router = APIRouter()


@router.get("/locations")
def locations_list(
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
            "list_url": "/locations",
            "rows_target_id": "location-rows",
            "extra_qs": ("&" + urlencode(qs_parts)) if qs_parts else "",
        }
    )
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "partials/location_rows.html", context)
    return templates.TemplateResponse(request, "pages/locations.html", context)
