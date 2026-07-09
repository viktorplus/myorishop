"""Backup pages (BCK-01): thin routes, all file/VACUUM work in the service.

Security V12 / T-3-09: NEITHER endpoint accepts a filename, path, Form or
Query parameter — the list is a server-side glob of settings.backup_dir
only, and restore deliberately stays an OFFLINE script (restore.bat),
never a web endpoint (D-11).
"""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.routes import templates
from app.services import backup as backup_service

router = APIRouter()

BACKUP_ERROR = (
    "Не удалось создать резервную копию. "
    "Закройте другие программы, использующие базу, и попробуйте ещё раз."
)


@router.get("/backup")
def backup_page(request: Request):
    context = {
        "backups": backup_service.list_backups(Path(settings.backup_dir)),
        "message": None,
        "error": None,
    }
    return templates.TemplateResponse(request, "pages/backup.html", context)


@router.post("/backup")
def backup_now(request: Request, session: Session = Depends(get_session)):
    # PD-12: engine from the request session — the tmp-path test engine
    # under TestClient, the real app engine in production. NO client
    # parameters of any kind (V12).
    engine = session.get_bind()
    message = None
    error = None
    try:
        path = backup_service.create_backup(engine, Path(settings.backup_dir))
        backup_service.prune_backups(Path(settings.backup_dir), keep=settings.backup_keep)
        message = f"Резервная копия создана: {path.name}."
    except Exception:
        # htmx swaps 2xx only — render the RU error block at 200 with the
        # list unchanged (UI-SPEC backup failure copy).
        error = BACKUP_ERROR
    context = {
        "backups": backup_service.list_backups(Path(settings.backup_dir)),
        "message": message,
        "error": error,
    }
    return templates.TemplateResponse(request, "partials/backup_list.html", context)
