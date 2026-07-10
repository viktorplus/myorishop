"""Reports routes (RPT-01): thin routes, read-only via app/services/reports.py."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.core import local_day_bounds_utc
from app.db import get_session
from app.routes import templates
from app.services.reports import sales_profit_report, writeoff_report
from app.services.stock import (
    all_active_products,
    effective_low_stock_threshold,
    low_stock_products,
)

router = APIRouter()

INVALID_DATE_ERROR = "Некорректная дата."
INVERTED_RANGE_ERROR = "Проверьте даты: «с» должно быть раньше или равно «по»."


def _resolve_period(from_raw: str, to_raw: str, tz_name: str) -> dict:
    """Parse from/to query params into a validated period + preset metadata (D-01).

    One code path: presets are just precomputed (from, to) pairs — a preset
    click and hand-typed dates both end up here. Malformed or inverted
    ranges never reach the query layer (Security V5): they fall back to
    today with a RU error shown inline instead of raising.
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
        # D-01: no query params at all = today's preset, not an error.
        from_date = to_date = today
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


@router.get("/reports")
def reports_landing(request: Request):
    return templates.TemplateResponse(request, "pages/reports_landing.html", {})


@router.get("/reports/sales")
def reports_sales_page(
    request: Request,
    from_: str = Query("", alias="from"),
    to: str = Query("", alias="to"),
    session: Session = Depends(get_session),
):
    period = _resolve_period(from_, to, settings.display_tz)
    report = None
    if not period["error"]:
        start_iso, end_iso = local_day_bounds_utc(
            period["from_date"], period["to_date"], settings.display_tz
        )
        report = sales_profit_report(session, start_iso, end_iso)

    context = {
        "from_date": period["from_date"].isoformat(),
        "to_date": period["to_date"].isoformat(),
        "active_preset": period["active_preset"],
        "presets": period["presets"],
        "error": period["error"],
        "report": report,
    }
    # CR-01 precedent (history.py): only a genuine HX-Request header gets
    # the chrome-less results partial; a filtered top-level GET still
    # renders full chrome (nav + period filter + results).
    if bool(request.headers.get("HX-Request")):
        return templates.TemplateResponse(request, "partials/sales_report_results.html", context)
    return templates.TemplateResponse(request, "pages/reports_sales.html", context)


@router.get("/reports/writeoffs")
def reports_writeoffs_page(
    request: Request,
    from_: str = Query("", alias="from"),
    to: str = Query("", alias="to"),
    session: Session = Depends(get_session),
):
    period = _resolve_period(from_, to, settings.display_tz)
    report = None
    if not period["error"]:
        start_iso, end_iso = local_day_bounds_utc(
            period["from_date"], period["to_date"], settings.display_tz
        )
        report = writeoff_report(session, start_iso, end_iso)

    context = {
        "from_date": period["from_date"].isoformat(),
        "to_date": period["to_date"].isoformat(),
        "active_preset": period["active_preset"],
        "presets": period["presets"],
        "error": period["error"],
        "report": report,
    }
    # CR-01 precedent (history.py / reports_sales_page): only a genuine
    # HX-Request header gets the chrome-less results partial.
    if bool(request.headers.get("HX-Request")):
        return templates.TemplateResponse(
            request, "partials/writeoffs_report_rows.html", context
        )
    return templates.TemplateResponse(request, "pages/reports_writeoffs.html", context)


@router.get("/reports/stock")
def reports_stock_page(request: Request, session: Session = Depends(get_session)):
    """RPT-02/D-03: "as of now" stock view — no period filter, always the full page."""
    low_stock_rows = [
        {"product": p, "threshold": effective_low_stock_threshold(p)}
        for p in low_stock_products(session)
    ]
    context = {
        "low_stock_rows": low_stock_rows,
        "all_products": all_active_products(session),
        "low_stock_ids": {row["product"].id for row in low_stock_rows},
    }
    return templates.TemplateResponse(request, "pages/reports_stock.html", context)
