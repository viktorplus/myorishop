"""Mobile history page (Phase 11 Plan 08; extended Phase 23 Plan 05 for
HIST-01..04 parity with desktop's app/routes/history.py — D-10): thin route,
reuses app.services.operations.history_view unchanged — no new ledger query.

Full filter set (Тип + product deep-link + category/customer/date-range) and
numbered page_window/paginate pagination, replacing the legacy load-more
mechanism (closes the Phase-14 mobile-pagination generation gap, D-10/HIST-04).
Mirrors app/routes/history.py's CR-01 HX-Request branching: a genuine htmx
request (filter change or a pagination click) gets the chrome-less cards
partial plus an oob-swapped pagination bar — ALWAYS both together, so a
pagination click also refreshes the filter state and a filter change also
refreshes the page count; a plain GET gets the full mobile_pages/history.html
chrome.
"""

from datetime import date, datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.core import local_day_bounds_utc
from app.db import get_session
from app.routes import templates
from app.services.operations import history_view
from app.services.pagination import page_window

router = APIRouter()

INVALID_DATE_ERROR = "Некорректная дата."
INVERTED_RANGE_ERROR = "Проверьте даты: «с» должно быть раньше или равно «по»."


def _resolve_history_period(from_raw: str, to_raw: str, tz_name: str) -> dict:
    """Local date-range resolver — duplicated from app/routes/history.py's
    `_resolve_history_period` (same reasoning: `_metrics_context` is already
    independently duplicated between finance.py and mobile_finance.py, this
    codebase has no shared route-helper module).

    Differs from app/routes/reports.py::_resolve_period in exactly one
    respect: when BOTH from_raw and to_raw are blank, returns
    `from_date=None, to_date=None, error=None` (no date filter at all — the
    generic default view stays fully unfiltered, D-04). A malformed or
    inverted range falls back to TODAY with an inline RU error, matching
    `_resolve_period`'s convention (never a raw 500, ASVS V5). Mobile has no
    preset bar (D-10's "own simpler layout" — no preset-bar reuse), so unlike
    history.py's version this omits the presets/active_preset computation
    entirely — only from_date/to_date/error are needed here.
    """
    tz = ZoneInfo(tz_name)
    today = datetime.now(tz).date()

    if not from_raw.strip() and not to_raw.strip():
        return {"from_date": None, "to_date": None, "error": None}
    try:
        from_date = date.fromisoformat(from_raw)
        to_date = date.fromisoformat(to_raw)
    except ValueError:
        return {"from_date": today, "to_date": today, "error": INVALID_DATE_ERROR}
    if from_date > to_date:
        return {"from_date": today, "to_date": today, "error": INVERTED_RANGE_ERROR}
    return {"from_date": from_date, "to_date": to_date, "error": None}


@router.get("/m/history")
def mobile_history_page(
    request: Request,
    type: str = "",
    product: str = "",
    category: str = "",
    customer: str = "",
    from_: str = Query("", alias="from"),
    to: str = Query("", alias="to"),
    page: int = 0,
    session: Session = Depends(get_session),
):
    # D-10: `product` is reinstated (the Phase-11 CONTEXT discretion that
    # dropped it is superseded this phase) — the dashboard feed's deep link
    # (/m/history?type=X&product=Y) narrows results even though mobile has
    # no visible Товар filter control (per 23-UI-SPEC.md's Copywriting
    # Contract, the param exists for the deep-link only).
    period = _resolve_history_period(from_, to, settings.display_tz)
    start_iso = end_iso = None
    if period["from_date"] is not None:
        start_iso, end_iso = local_day_bounds_utc(
            period["from_date"], period["to_date"], settings.display_tz
        )

    result = history_view(
        session,
        type_filter=type or None,
        product_id=product or None,
        page=page,
        customer=customer or None,
        category=category or None,
        start_iso=start_iso,
        end_iso=end_iso,
    )

    # D-02/HIST-04: page-number pagination replaces the has_next sentinel —
    # mirrors history.py's Task 1 shape exactly. extra_qs re-serializes every
    # active filter dimension so a pagination click never loses the active
    # filter view, and a filter change never loses the current page's peers.
    pw = page_window(result["page"], result["total_pages"])
    from_out = period["from_date"].isoformat() if period["from_date"] else ""
    to_out = period["to_date"].isoformat() if period["to_date"] else ""
    qs_parts = {
        k: v
        for k, v in {
            "type": result["type_filter"],
            "product": result["product_id"],
            "category": category,
            "customer": customer,
            "from": from_out,
            "to": to_out,
        }.items()
        if v
    }
    extra_qs = ("&" + urlencode(qs_parts)) if qs_parts else ""

    context = {
        "rows": result["rows"],
        "columns": result["columns"],
        "page": result["page"],
        "total": result["total"],
        "total_pages": result["total_pages"],
        "page_window": pw,
        "type_filter": result["type_filter"],
        "product_id": result["product_id"],
        "category": category,
        "customer": customer,
        "from_date": from_out,
        "to_date": to_out,
        "error": period["error"],
        "list_url": "/m/history",
        "rows_target_id": "history-cards",
        "extra_qs": extra_qs,
    }
    is_hx = bool(request.headers.get("HX-Request"))
    if is_hx:
        # CR-01-precedent: two structural siblings in one response — the
        # cards (main-swap payload) and an oob-swapped pagination bar —
        # never nested, so a filter-change outerHTML swap can never destroy
        # the pagination control.
        cards_html = templates.get_template("mobile_partials/history_cards.html").render(**context)
        pagination_html = templates.get_template("mobile_partials/history_pagination.html").render(
            oob=True, **context
        )
        return HTMLResponse(cards_html + pagination_html)
    return templates.TemplateResponse(request, "mobile_pages/history.html", context)
