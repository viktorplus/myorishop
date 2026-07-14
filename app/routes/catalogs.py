"""Published catalog pages (CAT-04): list PDFs, serve them, show contents.

Read-only: no writes here. The PDF list is a folder scan (no DB table); the
per-catalog product list joins the Dictionary.catalogs membership column.
"""

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.catalogs import (
    catalog_file_path,
    catalog_year_options,
    get_catalog,
    list_catalogs,
    products_in_catalog,
)
from app.services.pagination import page_window
from app.services.pricing import prices_for_catalog

router = APIRouter()

# Route order: the literal /catalogs stays before the parameterized
# /catalogs/{url_code} routes below.


def _catalogs_context(session: Session, *, year: str = "", sort: str = "", page: int = 0) -> dict:
    """Shared context builder for both the full-page and HTMX-partial responses."""
    result = list_catalogs(session, year=year, sort=sort, page=page)
    pw = page_window(result["page"], result["total_pages"])
    qs_parts = {k: v for k, v in {"year": result["year"], "sort": result["sort"]}.items() if v}
    extra_qs = ("&" + urlencode(qs_parts)) if qs_parts else ""
    return {
        "catalogs": result["catalogs"],
        "page": result["page"],
        "total": result["total"],
        "total_pages": result["total_pages"],
        "page_window": pw,
        "year": result["year"],
        "sort": result["sort"],
        "year_options": catalog_year_options(session),
        "list_url": "/catalogs",
        "rows_target_id": "catalog-rows",
        "extra_qs": extra_qs,
    }


@router.get("/catalogs")
def catalogs_page(
    request: Request,
    year: str = "",
    sort: str = "",
    page: int = 0,
    session: Session = Depends(get_session),
):
    context = _catalogs_context(session, year=year, sort=sort, page=page)
    is_hx = bool(request.headers.get("HX-Request"))
    template = "partials/catalog_rows.html" if is_hx else "pages/catalogs.html"
    return templates.TemplateResponse(request, template, context)


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
