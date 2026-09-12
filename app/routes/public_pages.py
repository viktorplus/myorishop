"""Публичная страница отчёта о добавлении товара с рукописных листов.

Открыта БЕЗ авторизации по просьбе владельца: отчёт нужно показывать людям,
у которых нет учётной записи в программе.

До 12.09.2026 здесь жили пять отдельных страниц — опись, отчёт по её импорту,
список неопознанных кодов и два отчёта по приходам. Они заменены одной сводной:
разделы по датам, внутри каждого — что добавлено, что не добавлено, что осталось
без названия и что нужно перепроверить.

Как снять с публикации: удалить этот модуль, его строку в app/main.py, путь из
security.PUBLIC_PATHS и сам HTML. Пока страница живёт, она read-only: отдаётся
статический файл, никаких запросов к базе, никаких параметров запроса.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

# Адрес читаемый, а не UUID: его диктуют вслух. Он же перечислен в
# security.PUBLIC_PATHS — точным совпадением, иначе auth_guard увёл бы
# анонима на /login.
RECEIPTS_PATH = "/otchet-prihodov"
RECEIPTS_FILE = Path("app/static/public/report-receipts.html")


@router.get(RECEIPTS_PATH, include_in_schema=False)
def public_receipts_report():
    if not RECEIPTS_FILE.is_file():
        raise HTTPException(status_code=404, detail="page not found")
    return FileResponse(RECEIPTS_FILE, media_type="text/html; charset=utf-8")
