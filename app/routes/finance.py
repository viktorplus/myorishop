"""Финансы (FIN-06): read-only balance display. Routes NEVER write cash
(D-00c) — this module imports compute_balance ONLY, never
record_cash_movement.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.finance import compute_balance

router = APIRouter()


@router.get("/finance")
def finance_page(request: Request, session: Session = Depends(get_session)):
    context = {"balance_cents": compute_balance(session)}
    return templates.TemplateResponse(request, "pages/finance.html", context)
