"""GET / — main page: ledger table + correction form (thin route, D-11/D-12)."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.ledger import ledger_view

router = APIRouter()


@router.get("/")
def home(request: Request, session: Session = Depends(get_session)):
    context = ledger_view(session)
    return templates.TemplateResponse(request, "pages/home.html", context)
