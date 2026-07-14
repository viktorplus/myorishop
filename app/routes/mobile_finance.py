"""Mobile Финансы (FIN-06): read-only balance display, mirrors
app/routes/finance.py. Routes NEVER write cash (D-00c).
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.finance import compute_balance

router = APIRouter()


@router.get("/m/finance")
def mobile_finance_page(request: Request, session: Session = Depends(get_session)):
    context = {"balance_cents": compute_balance(session)}
    return templates.TemplateResponse(request, "mobile_pages/finance.html", context)
