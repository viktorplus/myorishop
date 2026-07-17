"""Mobile home (D-03/D-10): existing 10-tile nav grid, UNCHANGED, plus the
same dashboard content as desktop (DASH-01..05) appended below it.

Calls the identical app.services.dashboard.dashboard_context(session,
tz_name) as app/routes/home.py — same data, mobile's own card/2-column
layout in the template (D-10: "own layout", not shared markup).
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.routes import templates
from app.services.dashboard import dashboard_context

router = APIRouter()


@router.get("/m/")
def mobile_home(request: Request, session: Session = Depends(get_session)):
    context = dashboard_context(session, settings.display_tz)
    return templates.TemplateResponse(request, "mobile_pages/home.html", context)
