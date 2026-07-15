"""Финансы (FIN-03/04/05/06): balance display + manual cash entry.

Routes stay THIN — every cash write and ALL validation (amount parse, category
allow-list, mandatory comment, negative-balance gate, sign) live in
app.services.finance.record_manual_movement (D-00c). This module NEVER writes
cash directly; it only reads the balance and delegates writes to the service.
"""

import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.core import local_day_bounds_utc
from app.db import get_session
from app.models import CASH_BUCKETS
from app.routes import templates
from app.routes.reports import _resolve_period
from app.services.finance import (
    CATEGORY_ERROR,
    cash_history_view,
    compute_balance,
    record_manual_movement,
)
from app.services.finance_reports import cash_expense_total, stock_valuation
from app.services.pagination import page_window
from app.services.reports import sales_profit_report

router = APIRouter()
logger = logging.getLogger(__name__)

# Desktop surface prefix passed into the shared forms so hx-post resolves here;
# the mobile router (Plan 04) reuses the same partials with "/m/finance".
FINANCE_BASE = "/finance"

SAVE_FAILED_ERROR = "Не удалось сохранить. Попробуйте ещё раз."
# UI-SPEC §D: the deposit form calls the category «Основание», so a blank basis
# surfaces deposit-specific copy instead of the service's generic category error.
DEPOSIT_CATEGORY_ERROR = "Выберите основание."


def _history_context(session: Session, *, bucket: str = "", page: int = 0) -> dict:
    """Build the desktop cash-history render context (mirrors history.py): the
    numbered page_window bar + extra_qs that re-serializes the active bucket onto
    every pagination link so paging never drops the filter (T-16-07: the raw
    bucket string is passed to the service, never into SQL)."""
    result = cash_history_view(session, bucket=bucket or None, page=page)
    pw = page_window(result["page"], result["total_pages"])
    qs_parts = {k: v for k, v in {"bucket": result["bucket"]}.items() if v}
    extra_qs = ("&" + urlencode(qs_parts)) if qs_parts else ""
    return {
        "finance_base": FINANCE_BASE,
        "rows": result["rows"],
        "page": result["page"],
        "total": result["total"],
        "total_pages": result["total_pages"],
        "page_window": pw,
        "bucket": result["bucket"],
        "list_url": "/finance/history",
        "rows_target_id": "cash-history-rows",
        "extra_qs": extra_qs,
    }


def _metrics_context(session: Session, from_: str, to: str) -> dict:
    """Build the dashboard-tile render context (D-04/D-04b): gross + net profit
    follow the light period selector; stock_valuation is called UNCONDITIONALLY
    (point-in-time, period-independent — mirrors reports_products_page's
    unconditional stale_products call outside the period-error guard).
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


@router.get("/finance")
def finance_page(request: Request, session: Session = Depends(get_session)):
    context = {
        "finance_base": FINANCE_BASE,
        "balance_cents": compute_balance(session),
        "form": {},
        "errors": {},
        **_history_context(session),
        **_metrics_context(session, "", ""),
    }
    return templates.TemplateResponse(request, "pages/finance.html", context)


@router.get("/finance/metrics")
def finance_metrics(
    request: Request,
    from_: str = Query("", alias="from"),
    to: str = Query("", alias="to"),
    session: Session = Depends(get_session),
):
    """D-04b light period selector target: HX swap returns only the tiles
    partial into #finance-metrics; a plain GET (deep link / no-JS) returns
    the full /finance page with balance/forms/history intact."""
    context = _metrics_context(session, from_, to)
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "partials/finance_tiles.html", context)
    context = {
        "finance_base": FINANCE_BASE,
        "balance_cents": compute_balance(session),
        "form": {},
        "errors": {},
        **_history_context(session),
        **context,
    }
    return templates.TemplateResponse(request, "pages/finance.html", context)


@router.get("/finance/history")
def finance_history(
    request: Request,
    bucket: str = "",
    page: int = 0,
    session: Session = Depends(get_session),
):
    context = _history_context(session, bucket=bucket, page=page)
    # A genuine htmx request (filter change / paging) gets the chrome-less rows
    # partial; a plain GET gets the full «Финансы» page (mirrors history.py).
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(request, "partials/cash_history_rows.html", context)
    context = {
        **context,
        "balance_cents": compute_balance(session),
        "form": {},
        "errors": {},
    }
    return templates.TemplateResponse(request, "pages/finance.html", context)


def _movement_success(session: Session, form_template: str) -> HTMLResponse:
    """Compose a successful withdraw/deposit response: a fresh empty form plus
    out-of-band #cash-balance and #cash-history-rows refreshes (mirrors
    mobile_history's sibling-concat) so a movement updates both in place."""
    form_html = templates.get_template(form_template).render(
        finance_base=FINANCE_BASE, form={}, errors={}
    )
    balance_html = templates.get_template("partials/cash_balance.html").render(
        oob=True, balance_cents=compute_balance(session)
    )
    history_html = templates.get_template("partials/cash_history_rows.html").render(
        oob=True, **_history_context(session)
    )
    return HTMLResponse(form_html + balance_html + history_html)


@router.post("/finance/withdraw")
def finance_withdraw(
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
    # WR-01 defence-in-depth: this endpoint accepts ONLY withdrawal categories.
    # The service derives direction from the category (not the endpoint), so a
    # crafted deposit_* POST here would otherwise be recorded as a deposit via
    # the withdraw route. Reject the cross-direction category at the boundary.
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
        logger.exception("record_manual_movement (withdraw) failed")
        context = {
            "finance_base": FINANCE_BASE,
            "errors": {"form": SAVE_FAILED_ERROR},
            "form": form_echo,
        }
        return templates.TemplateResponse(
            request, "partials/withdraw_form.html", context, status_code=422
        )

    # D-05: negative-balance warn — ZERO writes, warn above the intact form
    # (confirm re-POSTs the same form via form="withdraw-form" + confirm=1).
    # HTTP 200 (not 422): htmx swaps 200; the 422-swap config covers true errors.
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


@router.post("/finance/deposit")
def finance_deposit(
    request: Request,
    amount: str = Form(""),
    category: str = Form(""),
    note: str = Form(""),
    session: Session = Depends(get_session),
):
    # D-05: deposits never warn (they only increase the balance) — confirm is
    # irrelevant, so this route has only the errors/success branches.
    form_echo = {"amount": amount, "category": category, "note": note}
    # WR-01 defence-in-depth: this endpoint accepts ONLY deposit categories. A
    # crafted withdrawal_* POST here would otherwise reach the withdrawal
    # direction (and the negative-balance gate) via the deposit route — a
    # deposit that silently records an expense (or a false "success"). Reject it.
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
        logger.exception("record_manual_movement (deposit) failed")
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
