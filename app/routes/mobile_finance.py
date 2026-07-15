"""Mobile Финансы (FIN-03/04/05/06/07/08/09/10/11/12): balance display +
manual cash entry + cash-movement history + dashboard tiles + period report +
CSV export, mirroring app/routes/finance.py at parity (D-06a/D-04c).

Routes stay THIN — every cash write and ALL validation live in
app.services.finance.record_manual_movement (D-00c). This module NEVER writes
cash directly; it delegates writes to the service and reuses the Plan 03 SHARED
form partials (parameterised by `finance_base`), plus (Plan 04) the SHARED
partials/finance_tiles.html and partials/cash_flow_report.html — no
mobile-specific tiles/report partial is created (D-04c). Only the history
PRESENTATION is mobile-specific: card stacks + a «Показать ещё» load-more
(UI-SPEC Q1), NOT the desktop numbered pagination bar (Pitfall 7).
"""

import logging

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.core import local_day_bounds_utc
from app.db import get_session
from app.models import CASH_BUCKETS
from app.routes import templates
from app.routes.reports import _resolve_period
from app.services import export as export_service
from app.services.finance import (
    CATEGORY_ERROR,
    cash_history_view,
    compute_balance,
    record_manual_movement,
)
from app.services.finance_reports import cash_expense_total, cash_flow_report, stock_valuation
from app.services.reports import sales_profit_report

router = APIRouter()
logger = logging.getLogger(__name__)

# Mobile surface prefix passed into the SHARED forms so hx-post resolves here
# (the desktop router uses "/finance"; UI-SPEC Q2 — one form, two prefixes).
FINANCE_BASE = "/m/finance"

SAVE_FAILED_ERROR = "Не удалось сохранить. Попробуйте ещё раз."
# UI-SPEC §D: the deposit form calls the category «Основание», so a blank basis
# surfaces deposit-specific copy instead of the service's generic category error.
DEPOSIT_CATEGORY_ERROR = "Выберите основание."


def _history_context(session: Session, *, bucket: str = "", page: int = 0) -> dict:
    """Build the mobile cash-history render context (mirrors mobile_history.py):
    a locally-derived `has_next` load-more sentinel instead of the desktop
    numbered page_window (UI-SPEC Q1 / Pitfall 7). The raw bucket string is
    passed to the service, never into SQL (T-16-07)."""
    result = cash_history_view(session, bucket=bucket or None, page=page)
    return {
        "finance_base": FINANCE_BASE,
        "rows": result["rows"],
        "has_next": result["page"] < result["total_pages"] - 1,
        "page": result["page"],
        "bucket": result["bucket"],
    }


def _metrics_context(session: Session, from_: str, to: str) -> dict:
    """Build the dashboard-tile render context (D-04/D-04b/D-04c): near-verbatim
    clone of app.routes.finance._metrics_context with finance_base=FINANCE_BASE
    (= "/m/finance"). Gross + net profit follow the light period selector;
    stock_valuation is called UNCONDITIONALLY (point-in-time, period-independent).
    Net profit is gross PLUS the already-negative cash_expense_total, a plain
    addition, never a subtraction (D-01a)."""
    period = _resolve_period(from_, to, settings.display_tz)
    metrics = None
    if not period["error"]:
        start_iso, end_iso = local_day_bounds_utc(
            period["from_date"], period["to_date"], settings.display_tz
        )
        gross = sales_profit_report(session, start_iso, end_iso)
        expense = cash_expense_total(session, start_iso, end_iso)
        metrics = {
            "gross_profit_cents": gross["totals"]["profit_cents"],
            "cost_unknown_count": gross["totals"]["cost_unknown_count"],
            "net_profit_cents": gross["totals"]["profit_cents"] + expense,
        }
    valuation = stock_valuation(session)
    return {
        "from_date": period["from_date"].isoformat(),
        "to_date": period["to_date"].isoformat(),
        "active_preset": period["active_preset"],
        "presets": period["presets"],
        "error": period["error"],
        "metrics": metrics,
        "valuation": valuation,
        "finance_base": FINANCE_BASE,
    }


def _movement_success(session: Session, form_template: str) -> HTMLResponse:
    """Compose a successful withdraw/deposit response: a fresh empty shared form
    plus out-of-band #cash-balance, #cash-history-cards and #cash-history-load-more
    refreshes (mirrors mobile_history's sibling-concat) so a movement updates the
    balance and the card list in place."""
    hc = _history_context(session)
    form_html = templates.get_template(form_template).render(
        finance_base=FINANCE_BASE, form={}, errors={}
    )
    balance_html = templates.get_template("partials/cash_balance.html").render(
        oob=True, balance_cents=compute_balance(session)
    )
    cards_html = templates.get_template(
        "mobile_partials/cash_history_cards.html"
    ).render(oob=True, **hc)
    load_more_html = templates.get_template(
        "mobile_partials/cash_history_load_more.html"
    ).render(oob=True, **hc)
    return HTMLResponse(form_html + balance_html + cards_html + load_more_html)


@router.get("/m/finance")
def mobile_finance_page(
    request: Request,
    bucket: str = "",
    page: int = 0,
    session: Session = Depends(get_session),
):
    context = {
        "balance_cents": compute_balance(session),
        "form": {},
        "errors": {},
        **_history_context(session, bucket=bucket, page=page),
        **_metrics_context(session, "", ""),
    }
    return templates.TemplateResponse(request, "mobile_pages/finance.html", context)


@router.get("/m/finance/metrics")
def mobile_finance_metrics(
    request: Request,
    from_: str = Query("", alias="from"),
    to: str = Query("", alias="to"),
    session: Session = Depends(get_session),
):
    """D-04b light period selector target: HX swap returns only the SHARED
    tiles partial into #finance-metrics; a plain GET (deep link / no-JS)
    returns the full /m/finance page with balance/forms/history intact."""
    context = _metrics_context(session, from_, to)
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "partials/finance_tiles.html", context)
    context = {
        "balance_cents": compute_balance(session),
        "form": {},
        "errors": {},
        **_history_context(session),
        **context,
    }
    return templates.TemplateResponse(request, "mobile_pages/finance.html", context)


@router.get("/m/finance/history")
def mobile_finance_history(
    request: Request,
    bucket: str = "",
    page: int = 0,
    session: Session = Depends(get_session),
):
    context = _history_context(session, bucket=bucket, page=page)
    # A genuine htmx request (filter change / «Показать ещё») gets the chrome-less
    # cards partial plus an oob-swapped load-more control (mirrors mobile_history.py);
    # a plain GET gets the full «Финансы» page.
    if request.headers.get("HX-Request"):
        cards_html = templates.get_template(
            "mobile_partials/cash_history_cards.html"
        ).render(**context)
        load_more_html = templates.get_template(
            "mobile_partials/cash_history_load_more.html"
        ).render(oob=True, **context)
        return HTMLResponse(cards_html + load_more_html)
    context = {
        **context,
        "balance_cents": compute_balance(session),
        "form": {},
        "errors": {},
        **_metrics_context(session, "", ""),
    }
    return templates.TemplateResponse(request, "mobile_pages/finance.html", context)


@router.post("/m/finance/withdraw")
def mobile_finance_withdraw(
    request: Request,
    amount: str = Form(""),
    category: str = Form(""),
    note: str = Form(""),
    confirm: str = Form(""),
    session: Session = Depends(get_session),
):
    # String fields on purpose: parsing/validation happens in the service, which
    # returns RU errors. The route never writes cash (D-00c).
    form_echo = {"amount": amount, "category": category, "note": note}
    # WR-01 defence-in-depth: this endpoint accepts ONLY withdrawal categories
    # (mirror of the desktop guard). A crafted deposit_* POST here would
    # otherwise be recorded as a deposit via the withdraw route.
    if category in CASH_BUCKETS["deposit"]:
        context = {
            "finance_base": FINANCE_BASE,
            "errors": {"category": CATEGORY_ERROR},
            "form": form_echo,
        }
        return templates.TemplateResponse(
            request, "partials/withdraw_form.html", context, status_code=422
        )
    try:
        result, errors = record_manual_movement(
            session, category=category, amount_raw=amount, note=note, confirm=confirm
        )
    except Exception:  # noqa: BLE001 — UI-SPEC: block error, never a raw 500
        session.rollback()
        logger.exception("record_manual_movement (mobile withdraw) failed")
        context = {
            "finance_base": FINANCE_BASE,
            "errors": {"form": SAVE_FAILED_ERROR},
            "form": form_echo,
        }
        return templates.TemplateResponse(
            request, "partials/withdraw_form.html", context, status_code=422
        )

    # D-05: negative-balance warn — ZERO writes, warn above the intact form. HTTP
    # 200 (not 422): htmx swaps 200; the 422-swap config covers true errors.
    if result and result.get("negative_balance"):
        context = {
            "finance_base": FINANCE_BASE,
            "errors": {},
            "form": form_echo,
            "negative_balance": result["negative_balance"],
        }
        return templates.TemplateResponse(request, "partials/withdraw_form.html", context)

    if errors:
        context = {
            "finance_base": FINANCE_BASE,
            "errors": errors,
            "form": form_echo,
        }
        return templates.TemplateResponse(
            request, "partials/withdraw_form.html", context, status_code=422
        )

    return _movement_success(session, "partials/withdraw_form.html")


@router.post("/m/finance/deposit")
def mobile_finance_deposit(
    request: Request,
    amount: str = Form(""),
    category: str = Form(""),
    note: str = Form(""),
    session: Session = Depends(get_session),
):
    # D-05: deposits never warn (they only increase the balance) — confirm is
    # irrelevant, so this route has only the errors/success branches.
    form_echo = {"amount": amount, "category": category, "note": note}
    # WR-01 defence-in-depth: this endpoint accepts ONLY deposit categories
    # (mirror of the desktop guard). A crafted withdrawal_* POST here would
    # otherwise reach the withdrawal direction via the deposit route.
    if category in CASH_BUCKETS["withdrawal"]:
        context = {
            "finance_base": FINANCE_BASE,
            "errors": {"category": DEPOSIT_CATEGORY_ERROR},
            "form": form_echo,
        }
        return templates.TemplateResponse(
            request, "partials/deposit_form.html", context, status_code=422
        )
    try:
        result, errors = record_manual_movement(
            session, category=category, amount_raw=amount, note=note
        )
    except Exception:  # noqa: BLE001 — UI-SPEC: block error, never a raw 500
        session.rollback()
        logger.exception("record_manual_movement (mobile deposit) failed")
        context = {
            "finance_base": FINANCE_BASE,
            "errors": {"form": SAVE_FAILED_ERROR},
            "form": form_echo,
        }
        return templates.TemplateResponse(
            request, "partials/deposit_form.html", context, status_code=422
        )

    if errors:
        # UI-SPEC §D: relabel the generic category error for the «Основание» field.
        if "category" in errors:
            errors = {**errors, "category": DEPOSIT_CATEGORY_ERROR}
        context = {
            "finance_base": FINANCE_BASE,
            "errors": errors,
            "form": form_echo,
        }
        return templates.TemplateResponse(
            request, "partials/deposit_form.html", context, status_code=422
        )

    return _movement_success(session, "partials/deposit_form.html")


@router.get("/m/finance/report")
def mobile_finance_report(
    request: Request,
    from_: str = Query("", alias="from"),
    to: str = Query("", alias="to"),
    session: Session = Depends(get_session),
):
    """FIN-08/D-04c: period cash-flow report — near-verbatim clone of
    finance_report_page (app/routes/finance.py) with finance_base=FINANCE_BASE.
    Reuses the SHARED partials/cash_flow_report.html; no mobile-specific
    report partial is created."""
    period = _resolve_period(from_, to, settings.display_tz)
    report = None
    if not period["error"]:
        start_iso, end_iso = local_day_bounds_utc(
            period["from_date"], period["to_date"], settings.display_tz
        )
        report = cash_flow_report(session, start_iso, end_iso)

    context = {
        "from_date": period["from_date"].isoformat(),
        "to_date": period["to_date"].isoformat(),
        "active_preset": period["active_preset"],
        "presets": period["presets"],
        "error": period["error"],
        "report": report,
        "finance_base": FINANCE_BASE,
    }
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "partials/cash_flow_report.html", context)
    return templates.TemplateResponse(request, "mobile_pages/finance_report.html", context)


@router.get("/m/finance/report.csv")
def mobile_finance_report_csv(
    from_: str = Query("", alias="from"),
    to: str = Query("", alias="to"),
    session: Session = Depends(get_session),
):
    """FIN-09/D-03b: period-scoped cash-movement CSV, delegating to the same
    export_service.stream_cash_movements_csv used by the desktop route (from/to
    only, no filename/path param — plain download route, no Request/template)."""
    period = _resolve_period(from_, to, settings.display_tz)
    start_iso, end_iso = local_day_bounds_utc(
        period["from_date"], period["to_date"], settings.display_tz
    )
    return export_service.stream_cash_movements_csv(session, start_iso, end_iso)
