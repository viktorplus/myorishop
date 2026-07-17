"""Settings hub page (D-06/D-08): thin route, all summary logic in the service.

Mirrors app/routes/backup.py's exact shape — one service call, one context
dict, one template. Zero query/form params accepted (V12).
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.routes import templates
from app.services.settings import settings_summary

router = APIRouter()


@router.get("/settings")
def settings_page(request: Request, session: Session = Depends(get_session)):
    context = settings_summary(session, Path(settings.backup_dir))
    return templates.TemplateResponse(request, "pages/settings.html", context)
