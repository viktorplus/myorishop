"""Customer pages (CST-01/02): thin routes, all writes in app/services/customers.py."""

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import CONTACT_KINDS
from app.routes import templates
from app.services.customers import (
    contacts_by_kind,
    create_customer,
    get_customer,
    list_customers_view,
    purchase_history,
    update_customer,
)
from app.services.pagination import page_window

router = APIRouter()

# Route order: literal paths (/customers/new, /customers/contact-row) MUST
# stay declared before the parameterized /customers/{customer_id} routes
# below. /customers/search was retired (LIST-02/D-04, Pitfall 6) — its
# filtering folded into /customers' header-row filters; the sale-picker's
# own /sales/customer-search is separate.


def _contact_rows(raw: dict[str, list[str]]) -> dict[str, list[str]]:
    """Pad a raw contacts dict so every CONTACT_KINDS key holds >=1 row.

    UI-SPEC Interaction 6: /customers/new and an edit page for a kind with
    zero stored/submitted values both render exactly ONE blank .contact-row
    — a blank input IS the empty state, so customer_form.html never has to
    special-case a missing/empty key. Shared by customer_new, customer_edit
    and both POST handlers' 422 re-echo branches (the padding rule must be
    identical everywhere a `contacts` context key is built).
    """
    return {kind: (raw.get(kind) or [""]) for kind in CONTACT_KINDS}


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
    context = {
        "customer": None,
        "errors": {},
        "form": {},
        "contacts": _contact_rows({}),
    }
    return templates.TemplateResponse(request, "pages/customer_form.html", context)


@router.get("/customers/contact-row")
def contact_row(request: Request, kind: str = ""):
    # T-21-02 (CR-01 rule /sales/row already follows with _ROW_ID_RE):
    # `kind` is interpolated into the rendered input's `name` attribute, so
    # it is untrusted input and must be validated against the CONTACT_KINDS
    # allow-list BEFORE rendering. Unlike sale_row's fallback-to-a-fresh-id,
    # `kind` has no sensible fallback, so an unknown kind is a 404 — nothing
    # is rendered, matching this file's own unknown-resource convention.
    if kind not in CONTACT_KINDS:
        raise HTTPException(status_code=404, detail="unknown contact kind")
    context = {"kind": kind, "value": ""}
    return templates.TemplateResponse(request, "partials/contact_row.html", context)


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
    raw = {
        kind: [row.value for row in rows]
        for kind, rows in contacts_by_kind(session, customer_id).items()
    }
    context = {
        "customer": customer,
        "errors": {},
        "form": None,
        "contacts": _contact_rows(raw),
    }
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
