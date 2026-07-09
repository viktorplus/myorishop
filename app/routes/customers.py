"""Customer pages (CST-01/02): thin routes, all writes in app/services/customers.py."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.routes import templates
from app.services.customers import (
    create_customer,
    customer_search_view,
    get_customer,
    purchase_history,
    update_customer,
)

router = APIRouter()

# Route order: literal paths (/customers/new, /customers/search) MUST stay
# declared before the parameterized /customers/{customer_id} routes below.


@router.get("/customers")
def customers_list(request: Request, session: Session = Depends(get_session)):
    context = customer_search_view(session, "")
    return templates.TemplateResponse(request, "pages/customers_list.html", context)


@router.get("/customers/search")
def customers_search(request: Request, q: str = "", session: Session = Depends(get_session)):
    context = customer_search_view(session, q)
    return templates.TemplateResponse(request, "partials/customer_rows.html", context)


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
