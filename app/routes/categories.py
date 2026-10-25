"""Category browsing (CAT-01): thin route, read-only, no writes here."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.batches import scoped_quantities
from app.services.catalog import products_by_category

router = APIRouter()


@router.get("/categories")
def categories_page(request: Request, session: Session = Depends(get_session)):
    """D-01: plain full-page GET — no HX-Request branching, no filter/search."""
    # Quick 261026-wha: an operator sees the stock of their own warehouses.
    context = {"groups": products_by_category(session), "scoped_qty": scoped_quantities(session)}
    return templates.TemplateResponse(request, "pages/categories.html", context)
