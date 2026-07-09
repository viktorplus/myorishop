"""Sale pages (SAL-01/02/05): thin routes, writes in app/services/sales.py."""

from fastapi import APIRouter, Depends, Form, Request, Response
from sqlalchemy.orm import Session

from app.core import new_id
from app.db import get_session
from app.routes import templates
from app.services.sales import lookup_prefill, recent_sales, register_sale

router = APIRouter()

# Route order: literal paths (/sales/new, /sales/lookup, /sales/row) MUST
# stay declared before any parameterized /sales/{...} route added later
# (04-05 customer picker endpoints are also literal paths, so this holds).

SAVE_FAILED_ERROR = "Не удалось сохранить. Проверьте данные и попробуйте ещё раз."


def _build_lines(codes: list[str], qtys: list[str], prices: list[str], errors: dict[str, str]):
    """Rebuild the echoed basket rows from submitted arrays + service errors.

    Mirrors register_sale's own non-blank-line filtering so error keys
    (f"qty-{i}"/"price-{i}"/"code-{i}") line up with the right row. The
    first row keeps a bare row_id ("") so its input ids match the
    sale-form-wrap focus hook (id="code") exactly like a fresh basket;
    later rows get a generated id to avoid DOM collisions.
    """
    non_blank = [
        (code, qty, price)
        for code, qty, price in zip(codes, qtys, prices, strict=False)
        if code.strip() or qty.strip() or price.strip()
    ]
    lines = []
    for i, (code, qty, price) in enumerate(non_blank):
        lines.append(
            {
                "row_id": "" if i == 0 else new_id(),
                "code": code,
                "name": "",
                "qty": qty,
                "price": price,
                "error_code": errors.get(f"code-{i}"),
                "error_qty": errors.get(f"qty-{i}"),
                "error_price": errors.get(f"price-{i}"),
            }
        )
    return lines


@router.get("/sales/new")
def sale_new_page(request: Request, session: Session = Depends(get_session)):
    context = {
        "errors": {},
        "lines": [],
        "customer_id": "",
        "focus_code": False,
        "sales": recent_sales(session),
    }
    return templates.TemplateResponse(request, "pages/sale_form.html", context)


@router.get("/sales/lookup")
def sale_lookup(
    request: Request,
    code: str = "",
    name: str = "",
    price: str = "",
    row: str = "",
    session: Session = Depends(get_session),
):
    # D-10/RCP-02 analog: the SERVER decides fill vs no-op; htmx ignores 204.
    # A non-empty typed name is never overwritten.
    if name.strip():
        return Response(status_code=204)
    result = lookup_prefill(session, code)
    if result is None:
        return Response(status_code=204)
    context = {
        "row": row,
        "name": result["name"],
        "source": result["source"],
        # PD-10 analog: only fill Цена продажи when it arrived empty and the
        # match is an active product (dictionary matches carry no prices).
        "fill_price": result["source"] == "product" and not price.strip(),
        "prices": result["prices"],
    }
    return templates.TemplateResponse(request, "partials/sale_lookup.html", context)


@router.get("/sales/row")
def sale_row(request: Request, row: str = ""):
    # A fresh row is always appended alongside existing rows (hx-swap
    # "beforeend"), so it needs a unique, never-blank row id.
    row_id = row.strip() or new_id()
    context = {
        "row_id": row_id,
        "code": "",
        "name": "",
        "qty": "",
        "price": "",
        "error_code": None,
        "error_qty": None,
        "error_price": None,
        "autofocus": False,
        "focus_new": True,
    }
    return templates.TemplateResponse(request, "partials/sale_row.html", context)


@router.post("/sales")
def sale_create(
    request: Request,
    code: list[str] = Form([], alias="code[]"),
    qty: list[str] = Form([], alias="qty[]"),
    price: list[str] = Form([], alias="price[]"),
    customer_id: str = Form(""),
    confirm: str = Form(""),
    session: Session = Depends(get_session),
):
    try:
        result, errors = register_sale(
            session,
            customer_id=customer_id,
            codes=code,
            qtys=qty,
            prices=price,
            confirm=confirm,
        )
    except Exception:  # noqa: BLE001 — UI-SPEC: block error, never a raw 500
        context = {
            "errors": {"form": SAVE_FAILED_ERROR},
            "lines": _build_lines(code, qty, price, {}),
            "customer_id": customer_id,
            "focus_code": False,
            "include_oob_rows": False,
        }
        return templates.TemplateResponse(
            request, "partials/sale_form.html", context, status_code=422
        )

    # SAL-04/D-08: oversell — zero writes, warn above the still-intact
    # basket (lines re-rendered from the submitted arrays; the confirm
    # button re-POSTs the same basket via form="sale-form" + confirm=1).
    if result and result.get("oversell"):
        context = {
            "errors": {},
            "lines": _build_lines(code, qty, price, {}),
            "customer_id": customer_id,
            "focus_code": False,
            "include_oob_rows": False,
            "oversell": result["oversell"],
        }
        return templates.TemplateResponse(request, "partials/sale_form.html", context)

    if errors:
        context = {
            "errors": errors,
            "lines": _build_lines(code, qty, price, errors),
            "customer_id": customer_id,
            "focus_code": False,
            "include_oob_rows": False,
        }
        return templates.TemplateResponse(
            request, "partials/sale_form.html", context, status_code=422
        )

    # D-02: success -> fresh empty basket + neutral success line + focus
    # back to «Код»; the refreshed recent-sales list rides along as oob.
    context = {
        "errors": {},
        "lines": [],
        "customer_id": "",
        "saved": result,
        "focus_code": True,
        "sales": recent_sales(session),
        "include_oob_rows": True,
    }
    return templates.TemplateResponse(request, "partials/sale_form.html", context)
