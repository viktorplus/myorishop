"""Mobile expiry report (LOT-06 on mobile): reuses batches.expiring_batches unchanged."""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.routes import templates
from app.services.batches import expiring_batches

router = APIRouter()


@router.get("/m/reports/expiry")
def mobile_reports_expiry(request: Request, session: Session = Depends(get_session)):
    # Pitfall 5 (mirrors app/routes/reports.py::reports_expiry_page): local
    # date, not UTC, so batches near local midnight aren't mis-flagged.
    today = datetime.now(ZoneInfo(settings.display_tz)).date().isoformat()
    context = {"rows": expiring_batches(session), "today": today}
    return templates.TemplateResponse(request, "mobile_pages/reports_expiry.html", context)
