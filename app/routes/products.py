"""Product catalog pages (D-18): thin routes, all writes in app/services/catalog.py."""

from urllib.parse import urlencode

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
    list_products_view,
    price_history,
    quick_delete_product,
    restore_product,
    soft_delete_product,
    update_product,
)
from app.services.catalogs import catalogs_for_code
from app.services.pagination import page_window
from app.services.pricing import latest_price_for_code

router = APIRouter()

# Route order: literal paths (/products/new, /products/lookup-price) MUST stay
# declared before the parameterized /products/{product_id} routes below.


def _products_context(
    session: Session,
    *,
    code: str = "",
    name: str = "",
    category: str = "",
    sort: str = "",
    page: int = 0,
    blocked_id: str | None = None,
    blocked_qty: int | None = None,
) -> dict:
    """Shared context for the full list page AND the rows partial (D-18 pattern,
    reused from search_view for the new filter/sort/page shape)."""
    result = list_products_view(
        session, code=code, name=name, category=category, sort=sort, page=page
    )
    pw = page_window(result["page"], result["total_pages"])
    qs_parts = {
        k: v
        for k, v in {
            "code": result["code"],
            "name": result["name"],
            "category": result["category"],
            "sort": result["sort"],
        }.items()
        if v
    }
    extra_qs = ("&" + urlencode(qs_parts)) if qs_parts else ""
    return {
        "rows": result["rows"],
        "page": result["page"],
        "total": result["total"],
        "total_pages": result["total_pages"],
        "page_window": pw,
        "code": result["code"],
        "name": result["name"],
        "category": result["category"],
        "sort": result["sort"],
        "list_url": "/products",
        "rows_target_id": "product-rows",
        "extra_qs": extra_qs,
        "blocked_id": blocked_id,
        "blocked_qty": blocked_qty,
    }


@router.get("/products")
def products_list(
    request: Request,
    code: str = "",
    name: str = "",
    category: str = "",
    sort: str = "",
    page: int = 0,
    session: Session = Depends(get_session),
):
    context = _products_context(
        session, code=code, name=name, category=category, sort=sort, page=page
    )
    is_hx = bool(request.headers.get("HX-Request"))
    if is_hx:
        return templates.TemplateResponse(request, "partials/product_rows.html", context)
    return templates.TemplateResponse(request, "pages/products_list.html", context)


@router.post("/products/{product_id}/quick-delete")
def product_quick_delete(
    request: Request,
    product_id: str,
    code: str = "",
    name: str = "",
    category: str = "",
    sort: str = "",
    page: int = 0,
    session: Session = Depends(get_session),
):
    # CR-01 fix: the list state the operator was viewing is echoed back via
    # query params on the quick-delete POST (see product_rows.html), so the
    # blocked-delete row error stays visible even when the affected product
    # is off the default page-0/no-filter view.
    deleted, blocked = quick_delete_product(session, product_id)
    context = _products_context(
        session,
        code=code,
        name=name,
        category=category,
        sort=sort,
        page=page,
        blocked_id=product_id if not deleted and blocked else None,
        blocked_qty=blocked.get("blocked_qty"),
    )
    return templates.TemplateResponse(request, "partials/product_rows.html", context)


# Formalized under Phase 12 (PRICE-02) — shipped ad-hoc on feat/catalogs-pricing, now a permanent feature.
@router.get("/products/lookup-price")
def product_price_lookup(
    request: Request,
    code: str = "",
    cost: str = "",
    sale: str = "",
    session: Session = Depends(get_session),
):
    """CAT-05 autofill: fill the purchase/sale price from the latest catalog.

    Triggered by the code field on the product form. Fills a price ONLY when
    it is currently empty (the operator's own value is never overwritten) and
    the code has a known price; empty response (204) when there is nothing to
    fill. The two inputs are returned as out-of-band swaps (hx-swap-oob).

    D-01/Pitfall 6 (Phase 18 plan 02): the catalog reference price is no
    longer echoed into an editable field here — PROD-05 collapses product
    pricing to ДЦ/ПЦ only. The catalog's consumer price (ПЦ) is still this
    shop's default sale price, so it fills #sale when empty.
    """
    latest = latest_price_for_code(session, code)
    fill_cost = latest is not None and latest.consultant_cents is not None and not cost.strip()
    fill_sale = latest is not None and latest.consumer_cents is not None and not sale.strip()
    if not fill_cost and not fill_sale:
        return Response(status_code=204)
    context = {
        "fill_cost": fill_cost,
        "cost_cents": latest.consultant_cents if latest else None,
        "fill_sale": fill_sale,
        "sale_cents": latest.consumer_cents if latest else None,
    }
    return templates.TemplateResponse(request, "partials/product_price_autofill.html", context)


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
    min_sale: str = Form(""),
    low_stock_threshold: str = Form(""),
    stale_days: str = Form(""),
    session: Session = Depends(get_session),
):
    # Money fields arrive as strings on purpose: Pydantic v2 rejects ""
    # for int | None, and to_cents in the service gives the RU error.
    # D-01/Pitfall 4 (Phase 18 plan 02): create_product no longer accepts a
    # catalog_raw kwarg — the `catalog` Form field is still accepted here
    # (harmless, unused) since the form input is deleted from product_form.html.
    product, errors = create_product(
        session,
        code=code,
        name=name,
        category=category,
        cost_raw=cost,
        sale_raw=sale,
        min_sale_raw=min_sale,
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
                "min_sale": min_sale,
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
        "product_catalogs": catalogs_for_code(session, product.code or ""),
        "latest_price": latest_price_for_code(session, product.code or ""),
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
    min_sale: str = Form(""),
    low_stock_threshold: str = Form(""),
    stale_days: str = Form(""),
    session: Session = Depends(get_session),
):
    # D-01/Pitfall 4 (Phase 18 plan 02): update_product no longer accepts a
    # catalog_raw kwarg — see product_create's comment above.
    product, errors = update_product(
        session,
        product_id,
        code=code,
        name=name,
        category=category,
        cost_raw=cost,
        sale_raw=sale,
        min_sale_raw=min_sale,
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
                "min_sale": min_sale,
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
