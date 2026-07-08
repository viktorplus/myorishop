"""Product catalog pages (D-18): thin routes, all writes in app/services/catalog.py."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.catalog import category_options, create_product, list_products

router = APIRouter()


@router.get("/products")
def products_list(request: Request, session: Session = Depends(get_session)):
    context = {"products": list_products(session)}
    return templates.TemplateResponse(request, "pages/products_list.html", context)


@router.get("/products/new")
def product_new(request: Request, session: Session = Depends(get_session)):
    context = {
        "product": None,
        "categories": category_options(session),
        "errors": {},
        "form": {},
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
            },
        }
        return templates.TemplateResponse(
            request, "pages/product_form.html", context, status_code=422
        )
    return RedirectResponse("/products", status_code=303)
