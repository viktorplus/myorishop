"""Product catalog pages (D-18): thin routes, all writes in app/services/catalog.py."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.routes import templates
from app.services.catalog import (
    category_options,
    create_product,
    get_product,
    price_history,
    restore_product,
    search_view,
    soft_delete_product,
    update_product,
)

router = APIRouter()

# Route order: literal paths (/products/new, later /products/search) MUST stay
# declared before the parameterized /products/{product_id} routes below.


@router.get("/products")
def products_list(request: Request, session: Session = Depends(get_session)):
    # D-18: list page and search partial share the same search_view context
    # (empty query = first 20 active products by name).
    context = search_view(session, "")
    return templates.TemplateResponse(request, "pages/products_list.html", context)


@router.get("/products/search")
def products_search(request: Request, q: str = "", session: Session = Depends(get_session)):
    # D-25: HTMX active search — returns ONLY the rows partial (Phase 1 rule).
    context = search_view(session, q)
    return templates.TemplateResponse(request, "partials/product_rows.html", context)


@router.get("/products/new")
def product_new(request: Request, session: Session = Depends(get_session)):
    context = {
        "product": None,
        "categories": category_options(session),
        "errors": {},
        "form": {},
        "low_stock_default": settings.low_stock_threshold,
        "stale_days_default": settings.stale_days,
    }
    return templates.TemplateResponse(request, "pages/product_form.html", context)


@router.post("/products")
def product_create(
    request: Request,
    code: str = Form(""),
    name: str = Form(""),
    category: str = Form(""),
    cost: str = Form(""),
    sale: str = Form(""),
    catalog: str = Form(""),
    low_stock_threshold: str = Form(""),
    stale_days: str = Form(""),
    session: Session = Depends(get_session),
):
    # Money fields arrive as strings on purpose: Pydantic v2 rejects ""
    # for int | None, and to_cents in the service gives the RU error.
    product, errors = create_product(
        session,
        code=code,
        name=name,
        category=category,
        cost_raw=cost,
        sale_raw=sale,
        catalog_raw=catalog,
        low_stock_threshold_raw=low_stock_threshold,
        stale_days_raw=stale_days,
    )
    if errors:
        context = {
            "product": None,
            "categories": category_options(session),
            "errors": errors,
            "form": {
                "code": code,
                "name": name,
                "category": category,
                "cost": cost,
                "sale": sale,
                "catalog": catalog,
                "low_stock_threshold": low_stock_threshold,
                "stale_days": stale_days,
            },
            "low_stock_default": settings.low_stock_threshold,
            "stale_days_default": settings.stale_days,
        }
        return templates.TemplateResponse(
            request, "pages/product_form.html", context, status_code=422
        )
    return RedirectResponse("/products", status_code=303)


@router.get("/products/{product_id}/edit")
def product_edit(request: Request, product_id: str, session: Session = Depends(get_session)):
    product = get_product(session, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="unknown product")
    context = {
        "product": product,
        "categories": category_options(session),
        "errors": {},
        "history": price_history(session, product_id),
        "form": None,
        "low_stock_default": settings.low_stock_threshold,
        "stale_days_default": settings.stale_days,
    }
    return templates.TemplateResponse(request, "pages/product_form.html", context)


@router.post("/products/{product_id}")
def product_update(
    request: Request,
    product_id: str,
    code: str = Form(""),
    name: str = Form(""),
    category: str = Form(""),
    cost: str = Form(""),
    sale: str = Form(""),
    catalog: str = Form(""),
    low_stock_threshold: str = Form(""),
    stale_days: str = Form(""),
    session: Session = Depends(get_session),
):
    product, errors = update_product(
        session,
        product_id,
        code=code,
        name=name,
        category=category,
        cost_raw=cost,
        sale_raw=sale,
        catalog_raw=catalog,
        low_stock_threshold_raw=low_stock_threshold,
        stale_days_raw=stale_days,
    )
    if errors:
        existing = get_product(session, product_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="unknown product")
        context = {
            "product": existing,
            "categories": category_options(session),
            "errors": errors,
            "history": price_history(session, product_id),
            "form": {
                "code": code,
                "name": name,
                "category": category,
                "cost": cost,
                "sale": sale,
                "catalog": catalog,
                "low_stock_threshold": low_stock_threshold,
                "stale_days": stale_days,
            },
            "low_stock_default": settings.low_stock_threshold,
            "stale_days_default": settings.stale_days,
        }
        return templates.TemplateResponse(
            request, "pages/product_form.html", context, status_code=422
        )
    return RedirectResponse("/products", status_code=303)


@router.post("/products/{product_id}/delete")
def product_delete(product_id: str, session: Session = Depends(get_session)):
    # PD-4: htmx POST answered with 200 + HX-Redirect so the browser navigates
    # after the native hx-confirm dialog.
    soft_delete_product(session, product_id)
    return Response(status_code=200, headers={"HX-Redirect": "/products"})


@router.post("/products/{product_id}/restore")
def product_restore(product_id: str, session: Session = Depends(get_session)):
    restore_product(session, product_id)
    return Response(status_code=200, headers={"HX-Redirect": f"/products/{product_id}/edit"})
