"""Category browsing (CAT-01): thin route, read-only, no writes here."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.catalog import products_by_category

router = APIRouter()


@router.get("/categories")
def categories_page(request: Request, session: Session = Depends(get_session)):
    """D-01: plain full-page GET — no HX-Request branching, no filter/search."""
    context = {"groups": products_by_category(session)}
    return templates.TemplateResponse(request, "pages/categories.html", context)
