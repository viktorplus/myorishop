"""GET / — Главная dashboard (DASH-01..05, thin route, Phase 23 Plan 06).

The walking-skeleton "oldest active product + correction form" concept is
fully retired here; app.services.ledger.ledger_view is no longer read from
any route (it stays in app/services/ledger.py, still used by tests). All
composition happens in app.services.dashboard.dashboard_context — this
route only calls it and renders the result.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.routes import templates
from app.services.dashboard import dashboard_context

router = APIRouter()


@router.get("/")
def home(request: Request, session: Session = Depends(get_session)):
    context = dashboard_context(session, settings.display_tz)
    return templates.TemplateResponse(request, "pages/home.html", context)
