"""Customer pages (CST-01/02): thin routes, all writes in app/services/customers.py."""

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.customers import (
    create_customer,
    get_customer,
    list_customers_view,
    purchase_history,
    update_customer,
)
from app.services.pagination import page_window

router = APIRouter()

# Route order: literal paths (/customers/new) MUST stay declared before the
# parameterized /customers/{customer_id} routes below. /customers/search was
# retired (LIST-02/D-04, Pitfall 6) — its filtering folded into /customers'
# header-row filters; the sale-picker's own /sales/customer-search is separate.


def _customers_context(
    session: Session,
    *,
    name: str = "",
    surname: str = "",
    consultant_number: str = "",
    sort: str = "",
    page: int = 0,
) -> dict:
    """Shared context for the /customers full page AND its #customer-rows partial."""
    result = list_customers_view(
        session,
        name=name,
        surname=surname,
        consultant_number=consultant_number,
        sort=sort,
        page=page,
    )
    pw = page_window(result["page"], result["total_pages"])
    qs_parts = {
        key: value
        for key, value in {
            "name": result["name"],
            "surname": result["surname"],
            "consultant_number": result["consultant_number"],
            "sort": result["sort"],
        }.items()
        if value
    }
    extra_qs = ("&" + urlencode(qs_parts)) if qs_parts else ""
    return {
        "rows": result["rows"],
        "page": result["page"],
        "total": result["total"],
        "total_pages": result["total_pages"],
        "page_window": pw,
        "name": result["name"],
        "surname": result["surname"],
        "consultant_number": result["consultant_number"],
        "sort": result["sort"],
        "list_url": "/customers",
        "rows_target_id": "customer-rows",
        "extra_qs": extra_qs,
    }


@router.get("/customers")
def customers_list(
    request: Request,
    name: str = "",
    surname: str = "",
    consultant_number: str = "",
    sort: str = "",
    page: int = 0,
    session: Session = Depends(get_session),
):
    context = _customers_context(
        session,
        name=name,
        surname=surname,
        consultant_number=consultant_number,
        sort=sort,
        page=page,
    )
    is_hx = bool(request.headers.get("HX-Request"))
    if is_hx:
        return templates.TemplateResponse(request, "partials/customer_rows.html", context)
    return templates.TemplateResponse(request, "pages/customers_list.html", context)


@router.get("/customers/new")
def customer_new(request: Request):
    context = {"customer": None, "errors": {}, "form": {}}
    return templates.TemplateResponse(request, "pages/customer_form.html", context)


@router.post("/customers")
def customer_create(
    request: Request,
    name: str = Form(""),
    surname: str = Form(""),
    consultant_number: str = Form(""),
    session: Session = Depends(get_session),
):
    customer, errors = create_customer(
        session, name=name, surname=surname, consultant_number=consultant_number
    )
    if errors:
        context = {
            "customer": None,
            "errors": errors,
            "form": {"name": name, "surname": surname, "consultant_number": consultant_number},
        }
        return templates.TemplateResponse(
            request, "pages/customer_form.html", context, status_code=422
        )
    return RedirectResponse("/customers", status_code=303)


@router.get("/customers/{customer_id}")
def customer_detail(request: Request, customer_id: str, session: Session = Depends(get_session)):
    customer = get_customer(session, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="unknown customer")
    context = {"customer": customer, "history": purchase_history(session, customer_id)}
    return templates.TemplateResponse(request, "pages/customer_detail.html", context)


@router.get("/customers/{customer_id}/edit")
def customer_edit(request: Request, customer_id: str, session: Session = Depends(get_session)):
    customer = get_customer(session, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="unknown customer")
    context = {"customer": customer, "errors": {}, "form": None}
    return templates.TemplateResponse(request, "pages/customer_form.html", context)


@router.post("/customers/{customer_id}")
def customer_update(
    request: Request,
    customer_id: str,
    name: str = Form(""),
    surname: str = Form(""),
    consultant_number: str = Form(""),
    session: Session = Depends(get_session),
):
    customer, errors = update_customer(
        session,
        customer_id,
        name=name,
        surname=surname,
        consultant_number=consultant_number,
    )
    if errors:
        existing = get_customer(session, customer_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="unknown customer")
        context = {
            "customer": existing,
            "errors": errors,
            "form": {"name": name, "surname": surname, "consultant_number": consultant_number},
        }
        return templates.TemplateResponse(
            request, "pages/customer_form.html", context, status_code=422
        )
    return RedirectResponse("/customers", status_code=303)
