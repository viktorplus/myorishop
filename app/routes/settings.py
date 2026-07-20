"""Settings hub page (D-06/D-08): thin route, all summary logic in the service.

Mirrors app/routes/backup.py's exact shape — one service call, one context
dict, one template. Zero query/form params accepted (V12).
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.routes import templates
from app.services.settings import save_autosync_config, settings_summary
from app.services.sync_client import DEFAULT_INTERVAL_SECONDS

router = APIRouter()


@router.get("/settings")
def settings_page(request: Request, session: Session = Depends(get_session)):
    context = settings_summary(session, Path(settings.backup_dir))
    return templates.TemplateResponse(request, "pages/settings.html", context)


@router.post("/settings/sync")
def settings_save_sync(
    request: Request,
    auto_enabled: str = Form(""),
    auto_interval_seconds: str = Form(""),
    session: Session = Depends(get_session),
):
    """Persist the D-15 auto-sync config (admin-gated via the settings router).

    The checkbox posts `auto_enabled=on` only when checked (absent = disabled).
    The interval is parsed leniently: an unparseable value falls back to the
    default and the service clamps it into 60..3600 — a bad input is never a
    5xx (D-15). CSRF is carried by the base body `hx-headers`; the token is
    NEVER shown (T-29-07).
    """
    enabled = auto_enabled.strip().lower() in ("on", "true", "1", "yes")
    try:
        interval = int(auto_interval_seconds)
    except (TypeError, ValueError):
        interval = DEFAULT_INTERVAL_SECONDS
    save_autosync_config(session, enabled=enabled, interval_seconds=interval)

    context = settings_summary(session, Path(settings.backup_dir))
    context["sync_saved"] = True
    return templates.TemplateResponse(request, "pages/settings.html", context)
