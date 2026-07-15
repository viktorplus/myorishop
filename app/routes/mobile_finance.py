"""Mobile Финансы (FIN-03/04/05/06): balance display + manual cash entry,
mirroring app/routes/finance.py at parity (D-06a).

Routes stay THIN — every cash write and ALL validation live in
app.services.finance.record_manual_movement (D-00c). This module NEVER writes
cash directly; it delegates writes to the service and reuses the Plan 03 SHARED
form partials (parameterised by `finance_base`).
"""

import logging

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.finance import compute_balance, record_manual_movement

router = APIRouter()
logger = logging.getLogger(__name__)

# Mobile surface prefix passed into the SHARED forms so hx-post resolves here
# (the desktop router uses "/finance"; UI-SPEC Q2 — one form, two prefixes).
FINANCE_BASE = "/m/finance"

SAVE_FAILED_ERROR = "Не удалось сохранить. Попробуйте ещё раз."
# UI-SPEC §D: the deposit form calls the category «Основание», so a blank basis
# surfaces deposit-specific copy instead of the service's generic category error.
DEPOSIT_CATEGORY_ERROR = "Выберите основание."


def _movement_success(session: Session, form_template: str) -> HTMLResponse:
    """Compose a successful withdraw/deposit response: a fresh empty shared form
    plus an out-of-band #cash-balance refresh so a movement updates the balance
    in place (the mobile history oob is added in Task 2)."""
    form_html = templates.get_template(form_template).render(
        finance_base=FINANCE_BASE, form={}, errors={}
    )
    balance_html = templates.get_template("partials/cash_balance.html").render(
        oob=True, balance_cents=compute_balance(session)
    )
    return HTMLResponse(form_html + balance_html)


@router.get("/m/finance")
def mobile_finance_page(request: Request, session: Session = Depends(get_session)):
    context = {
        "finance_base": FINANCE_BASE,
        "balance_cents": compute_balance(session),
        "form": {},
        "errors": {},
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
