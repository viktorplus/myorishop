"""Reference dictionary pages (CAT-02): thin routes, writes in the service.

PD-5: the autofill lookup lives HERE at GET /dictionary/lookup (not under
/products) — the dictionary router owns all dictionary reads, keeping
wave-3 file ownership conflict-free.
"""

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Product
from app.routes import templates
from app.services.dictionary import (
    add_entry,
    add_entry_from_product,
    list_entries,
    list_missing_products,
    lookup,
    update_entry,
)
from app.services.pagination import page_window
from app.services.pricing import latest_prices_for_codes
from app.services.rubrics import RUBRICS

router = APIRouter()

# Route order: the literal /dictionary/lookup MUST stay declared before the
# parameterized /dictionary/{entry_id} route below.


def _dictionary_context(
    session: Session,
    *,
    code: str = "",
    name: str = "",
    category: str = "",
    sort: str = "",
    page: int = 0,
) -> dict:
    """Shared filter/sort/page context for GET and the two POST handlers."""
    result = list_entries(session, code=code, name=name, category=category, sort=sort, page=page)
    pw = page_window(result["page"], result["total_pages"])
    # CAT-05 display: the dictionary is code->name only, but the operator wants
    # ПЦ/ДЦ visible without opening each card. Pull the latest catalog price for
    # just this page's codes (one query) as read-only reference values; codes
    # with no catalog row render "—". Helper data only — never a Product write.
    prices = latest_prices_for_codes(session, [e.code for e in result["entries"]])
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
        "entries": result["entries"],
        "prices": prices,
        "page": result["page"],
        "total": result["total"],
        "total_pages": result["total_pages"],
        "page_window": pw,
        "code": result["code"],
        "name": result["name"],
        "category": result["category"],
        "rubrics": RUBRICS,
        "sort": result["sort"],
        "list_url": "/dictionary",
        "rows_target_id": "dictionary-rows",
        "extra_qs": extra_qs,
        "errors": {},
        "form": {},
    }


def _dictionary_missing_context(session: Session, *, page: int = 0) -> dict:
    """Shared context for GET /dictionary/missing and its POST re-render.

    Quick task 260814-je0. No filters on this list, so extra_qs stays the
    empty string the shared pagination partial expects.
    """
    result = list_missing_products(session, page=page)
    pw = page_window(result["page"], result["total_pages"])
    return {
        "products": result["products"],
        "total": result["total"],
        "total_pages": result["total_pages"],
        "page": result["page"],
        "page_window": pw,
        "list_url": "/dictionary/missing",
        "rows_target_id": "dictionary-missing-rows",
        "extra_qs": "",
    }


@router.get("/dictionary")
def dictionary_page(
    request: Request,
    code: str = "",
    name: str = "",
    category: str = "",
    sort: str = "",
    page: int = 0,
    session: Session = Depends(get_session),
):
    context = _dictionary_context(
        session, code=code, name=name, category=category, sort=sort, page=page
    )
    is_hx = bool(request.headers.get("HX-Request"))
    if is_hx:
        return templates.TemplateResponse(request, "partials/dictionary_rows.html", context)
    return templates.TemplateResponse(request, "pages/dictionary.html", context)


# Formalized under Phase 12 (PRICE-03) — shipped ad-hoc on feat/catalogs-pricing, now a permanent feature.
@router.get("/dictionary/lookup")
def dictionary_lookup(
    request: Request,
    code: str = "",
    name: str = "",
    category: str = "",
    session: Session = Depends(get_session),
):
    # Pattern 2 (D-23): the SERVER decides fill vs no-op; htmx ignores 204.
    # Pitfall 5: a non-empty operator value is never overwritten — applied
    # independently per field (CAT-06 quick task 260720-wqc).
    entry = lookup(session, code)
    if entry is None:
        return Response(status_code=204)
    fill_name = not name.strip()
    fill_category = bool(entry.rubric) and not category.strip()
    if not fill_name and not fill_category:
        return Response(status_code=204)
    context = {
        "name": entry.name if fill_name else name,
        "autofilled": fill_name,
        "fill_category": fill_category,
        "category": entry.rubric if fill_category else category,
    }
    return templates.TemplateResponse(request, "partials/dictionary_lookup.html", context)


@router.get("/dictionary/missing")
def dictionary_missing_page(
    request: Request,
    page: int = 0,
    session: Session = Depends(get_session),
):
    """Quick task 260814-je0: active products whose code is missing from the
    dictionary — one-click backfill entry point (CAT-02 D-24 helper only)."""
    context = _dictionary_missing_context(session, page=page)
    is_hx = bool(request.headers.get("HX-Request"))
    if is_hx:
        return templates.TemplateResponse(
            request, "partials/dictionary_missing_rows.html", context
        )
    return templates.TemplateResponse(request, "pages/dictionary_missing.html", context)


@router.post("/dictionary/missing/{product_id}/add")
def dictionary_missing_add(
    request: Request,
    product_id: str,
    page: int = 0,
    session: Session = Depends(get_session),
):
    """Quick task 260814-je0: whole-list re-render — the added product no
    longer matches the LEFT JOIN query, so it is simply absent afterwards."""
    entry, errors = add_entry_from_product(session, product_id)
    if "product" in errors:
        raise HTTPException(status_code=404, detail="unknown product")
    context = _dictionary_missing_context(session, page=page)
    return templates.TemplateResponse(
        request, "partials/dictionary_missing_rows.html", context
    )


@router.post("/dictionary/from-product/{product_id}")
def dictionary_from_product(
    request: Request,
    product_id: str,
    session: Session = Depends(get_session),
):
    """Quick task 260814-je0: shared CTA on the product detail cards
    (desktop /products/{id}/edit, mobile /m/search/product/{id})."""
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="unknown product")
    _, errors = add_entry_from_product(session, product_id)
    context = {
        "product": product,
        "dictionary_entry": lookup(session, product.code) if product.code else None,
        "error": next(iter(errors.values()), None) if errors else None,
    }
    return templates.TemplateResponse(
        request,
        "partials/dictionary_quick_add.html",
        context,
        status_code=422 if errors else 200,
    )


@router.post("/dictionary")
def dictionary_add(
    request: Request,
    code: str = Form(""),
    name: str = Form(""),
    session: Session = Depends(get_session),
):
    entry, errors = add_entry(session, code=code, name=name)
    context = {
        **_dictionary_context(session),
        "errors": errors,
        "form": {"code": code, "name": name} if errors else {},
    }
    return templates.TemplateResponse(
        request,
        "partials/dictionary_rows.html",
        context,
        status_code=422 if errors else 200,
    )


@router.post("/dictionary/{entry_id}")
def dictionary_update(
    request: Request,
    entry_id: str,
    code: str = Form(""),
    name: str = Form(""),
    # CR-01 fix: echo back the list state the operator was viewing (query
    # params, populated from the current row's edit form action — see
    # dictionary_rows.html) so a validation error stays visible even when
    # the edited row is off the default page-0/no-filter view. Prefixed
    # with list_ to avoid colliding with the code/name Form fields above.
    list_code: str = "",
    list_name: str = "",
    list_category: str = "",
    list_sort: str = "",
    list_page: int = 0,
    session: Session = Depends(get_session),
):
    entry, errors = update_entry(session, entry_id, code=code, name=name)
    if "entry" in errors:
        raise HTTPException(status_code=404, detail="unknown dictionary entry")
    context = {
        **_dictionary_context(
            session,
            code=list_code,
            name=list_name,
            category=list_category,
            sort=list_sort,
            page=list_page,
        ),
        "errors": errors,
        "form": {},
        "error_entry_id": entry_id if errors else None,
        "error_form": {"code": code, "name": name} if errors else None,
    }
    return templates.TemplateResponse(
        request,
        "partials/dictionary_rows.html",
        context,
        status_code=422 if errors else 200,
    )
