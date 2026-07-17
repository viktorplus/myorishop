"""Mobile Товары page (MOB-01, D-11): reuses catalog.list_products_view unchanged.

Thin route mirroring mobile_search.py's shape: one plain full-page GET, no
HX-partial branch (matches the project's all-navigation-is-full-page-GETs
convention). Also hosts the D-11 toolbar mirror of the desktop Товары toolbar.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.catalog import list_products_view

router = APIRouter()


@router.get("/m/products")
def mobile_products(
    request: Request,
    code: str = "",
    name: str = "",
    page: int = 0,
    session: Session = Depends(get_session),
):
    context = list_products_view(session, code=code, name=name, page=page)
    return templates.TemplateResponse(request, "mobile_pages/products.html", context)
