"""GET / — Главная dashboard (DASH-01..05, thin route, Phase 23 Plan 06).

The walking-skeleton "oldest active product + correction form" concept is
fully retired here; app.services.ledger.ledger_view is no longer read from
any route (it stays in app/services/ledger.py, still used by tests). All
composition happens in app.services.dashboard.dashboard_context — this
route only calls it and renders the result.
"""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.core import CURRENCIES, DEFAULT_CURRENCY
from app.db import get_session
from app.routes import templates
from app.services.dashboard import dashboard_context

router = APIRouter()


def _clean_query_currency(raw: str) -> str:
    """CUR-02/T-quick-260810-02: an untrusted `?currency=` value never reaches
    a WHERE clause unvalidated — anything outside CURRENCIES falls back to RUB."""
    return raw if raw in CURRENCIES else DEFAULT_CURRENCY


@router.get("/")
def home(request: Request, currency: str = Query(""), session: Session = Depends(get_session)):
    currency = _clean_query_currency(currency)
    context = dashboard_context(session, settings.display_tz, currency)
    return templates.TemplateResponse(request, "pages/home.html", context)
