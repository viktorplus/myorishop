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

# Спутник описи: отчёт по её импорту (что уже было, что добавляется, откуда
# взяты названия, товары без цены, где перепроверить). Тот же режим: статический
# файл, никаких запросов к базе и никаких параметров запроса.
REPORT_PATH = "/code/report/office-import-2026-09-02"
REPORT_FILE = Path("app/static/public/report-office-import-2026-09-02.html")


@router.get(ARTIFACT_PATH, include_in_schema=False)
def public_artifact():
    if not ARTIFACT_FILE.is_file():
        raise HTTPException(status_code=404, detail="page not found")
    return FileResponse(ARTIFACT_FILE, media_type="text/html; charset=utf-8")


@router.get(REPORT_PATH, include_in_schema=False)
def public_import_report():
    if not REPORT_FILE.is_file():
        raise HTTPException(status_code=404, detail="page not found")
    return FileResponse(REPORT_FILE, media_type="text/html; charset=utf-8")


# Рабочий список для обхода склада: коды, которые нельзя закрыть по документам.
UNKNOWN_PATH = "/code/report/unknown-codes-2026-09-02"
UNKNOWN_FILE = Path("app/static/public/report-unknown-codes-2026-09-02.html")


@router.get(UNKNOWN_PATH, include_in_schema=False)
def public_unknown_codes_report():
    if not UNKNOWN_FILE.is_file():
        raise HTTPException(status_code=404, detail="page not found")
    return FileResponse(UNKNOWN_FILE, media_type="text/html; charset=utf-8")


# Отчёт по приходу 1355 шт на склад «Офис» 03.09.2026. Режим тот же: статический
# файл, никаких запросов к базе и никаких параметров запроса.
RECEIPT_PATH = "/code/artifact/143c5a2c-d93f-4361-ae44-0059c828962a"
RECEIPT_FILE = Path("app/static/public/artifact-143c5a2c-d93f-4361-ae44-0059c828962a.html")


@router.get(RECEIPT_PATH, include_in_schema=False)
def public_office_receipt_report():
    if not RECEIPT_FILE.is_file():
        raise HTTPException(status_code=404, detail="page not found")
    return FileResponse(RECEIPT_FILE, media_type="text/html; charset=utf-8")
