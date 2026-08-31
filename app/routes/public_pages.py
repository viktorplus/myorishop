"""ВРЕМЕННАЯ публичная страница: зеркало артефакта описи склада «Офис».

Открыта БЕЗ авторизации по просьбе владельца — тот же документ уже отдаётся
по ссылке с claude.ai, здесь он лежит на своём домене.

Как снять с публикации: удалить этот модуль, его строку в app/main.py, путь из
security.PUBLIC_PATHS и сам HTML — один `git revert` коммита, которым всё это
пришло. Пока страница живёт, она read-only: отдаётся статический файл, никаких
запросов к базе, никаких параметров запроса.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

# Путь совпадает с адресом артефакта на claude.ai, чтобы ссылка читалась
# одинаково. Он же перечислен в security.PUBLIC_PATHS — точным совпадением,
# иначе auth_guard увёл бы анонима на /login.
ARTIFACT_PATH = "/code/artifact/0ac2f0bf-4df3-4de0-864a-b87d09e87305"
ARTIFACT_FILE = Path("app/static/public/artifact-0ac2f0bf-4df3-4de0-864a-b87d09e87305.html")


@router.get(ARTIFACT_PATH, include_in_schema=False)
def public_artifact():
    if not ARTIFACT_FILE.is_file():
        raise HTTPException(status_code=404, detail="page not found")
    return FileResponse(ARTIFACT_FILE, media_type="text/html; charset=utf-8")
