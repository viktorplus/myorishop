"""Published catalog pages (CAT-04): list PDFs, serve them, show contents.

Read-only: no writes here. The PDF list is a folder scan (no DB table); the
per-catalog product list joins the Dictionary.catalogs membership column.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.catalogs import (
    catalog_file_path,
    get_catalog,
    list_catalogs,
    products_in_catalog,
)
from app.services.pricing import prices_for_catalog

router = APIRouter()

# Route order: the literal /catalogs stays before the parameterized
# /catalogs/{url_code} routes below.


@router.get("/catalogs")
def catalogs_page(request: Request, session: Session = Depends(get_session)):
    context = {"catalogs": list_catalogs(session)}
    return templates.TemplateResponse(request, "pages/catalogs.html", context)


@router.get("/catalogs/{url_code}/file")
def catalog_file(url_code: str):
    path = catalog_file_path(url_code)
    if path is None:
        raise HTTPException(status_code=404, detail="unknown catalog")
    # inline so the PDF opens in the browser tab instead of downloading.
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=path.name,
        content_disposition_type="inline",
    )


@router.get("/catalogs/{url_code}")
def catalog_detail(request: Request, url_code: str, session: Session = Depends(get_session)):
    catalog = get_catalog(url_code)
    if catalog is None:
        raise HTTPException(status_code=404, detail="unknown catalog")
    context = {
        "catalog": catalog,
        "products": products_in_catalog(session, url_code),
        # code -> price row for this issue; template shows ПЦ per product.
        "prices": prices_for_catalog(session, catalog["year"], catalog["number"]),
    }
    return templates.TemplateResponse(request, "pages/catalog_detail.html", context)
