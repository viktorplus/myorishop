"""History page (OPS-04): thin route, read-only via app/services/operations.py."""

from datetime import date, datetime, timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.core import local_day_bounds_utc
from app.db import get_session
from app.routes import templates
from app.services.operations import filter_products, history_view
from app.services.pagination import page_window

router = APIRouter()

INVALID_DATE_ERROR = "Некорректная дата."
INVERTED_RANGE_ERROR = "Проверьте даты: «с» должно быть раньше или равно «по»."


def _resolve_history_period(from_raw: str, to_raw: str, tz_name: str) -> dict:
    """Parse от/по query params for /history's universal date-range filter (HIST-02).

    Deliberately NOT `reports.py::_resolve_period` (not imported, not
    shared) — differs in exactly one respect: when BOTH params are blank,
    this returns `from_date=None, to_date=None, error=None` (no date filter
    at all), instead of `_resolve_period`'s "blank = today" default, which
    would silently restrict /history's unfiltered default view to today's
    operations (breaking D-04 — the generic default view must stay the full,
    unfiltered ledger). Every other path — preset detection, malformed/
    inverted-range fallback to today with an inline RU error — mirrors
    `_resolve_period` exactly (ASVS V5: never a raw 500).
    """
    tz = ZoneInfo(tz_name)
    today = datetime.now(tz).date()
    week_start = today - timedelta(days=today.weekday())  # Monday-start (RU convention)
    week_end = week_start + timedelta(days=6)
    month_start = today.replace(day=1)
    month_end = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    presets = {
        "today": (today, today),
        "week": (week_start, week_end),
        "month": (month_start, month_end),
    }

    error: str | None = None
    if not from_raw.strip() and not to_raw.strip():
        # D-04: no query params at all = no date filter, not "today".
        from_date = to_date = None
    else:
        try:
            from_date = date.fromisoformat(from_raw)
            to_date = date.fromisoformat(to_raw)
        except ValueError:
            error = INVALID_DATE_ERROR
            from_date = to_date = today
        else:
            if from_date > to_date:
                error = INVERTED_RANGE_ERROR
                from_date = to_date = today

    active_preset = None
    if from_date is not None:
        for key, (preset_start, preset_end) in presets.items():
            if (from_date, to_date) == (preset_start, preset_end):
                active_preset = key
                break

    return {
        "from_date": from_date,
        "to_date": to_date,
        "active_preset": active_preset,
        "error": error,
        "presets": {
            key: {"from": bounds[0].isoformat(), "to": bounds[1].isoformat()}
            for key, bounds in presets.items()
        },
    }


@router.get("/history")
def history_page(
    request: Request,
    type: str = "",
    product: str = "",
    sort: str = "",
    page: int = 0,
    category: str = "",
    customer: str = "",
    from_: str = Query("", alias="from"),
    to: str = Query("", alias="to"),
    session: Session = Depends(get_session),
):
    period = _resolve_history_period(from_, to, settings.display_tz)
    from_date = period["from_date"]
    to_date = period["to_date"]
    start_iso = end_iso = None
    if from_date is not None and to_date is not None:
        start_iso, end_iso = local_day_bounds_utc(from_date, to_date, settings.display_tz)

    result = history_view(
        session,
        type_filter=type or None,
        product_id=product or None,
        sort=sort,
        page=page,
        customer=customer or None,
        category=category or None,
        start_iso=start_iso,
        end_iso=end_iso,
    )
    # D-02/D-03: page-number pagination retires the old "Показать ещё"
    # load-more mechanism — both the is_hx and full-page branches now render
    # the same single swappable partials/history_rows.html block (top
    # filter-bar + period filter + header-row filters + type-narrowed table
    # + pagination), consistent with every other list page. `extra_qs`
    # re-serializes the active filter/sort state onto every pagination link
    # so paging never loses the active view — dates are re-serialized from
    # the RESOLVED from_date/to_date, never the raw (possibly malformed)
    # query input (HIST-02).
    is_hx = bool(request.headers.get("HX-Request"))
    pw = page_window(result["page"], result["total_pages"])
    qs_parts = {
        k: v
        for k, v in {
            "type": result["type_filter"],
            "product": result["product_id"],
            "sort": result["sort"],
            "category": category,
            "customer": customer,
            "from": from_date.isoformat() if from_date else "",
            "to": to_date.isoformat() if to_date else "",
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
        "columns": result["columns"],
        "category": category,
        "customer": customer,
        "from_date": from_date.isoformat() if from_date else "",
        "to_date": to_date.isoformat() if to_date else "",
        "active_preset": period["active_preset"],
        "presets": period["presets"],
        "error": period["error"],
    }
    if is_hx:
        return templates.TemplateResponse(request, "partials/history_rows.html", context)
    return templates.TemplateResponse(request, "pages/history.html", context)
