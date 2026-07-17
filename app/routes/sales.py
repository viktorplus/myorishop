"""Sale pages (SAL-01/02/05): thin routes, writes in app/services/sales.py."""

import logging
import re

from fastapi import APIRouter, Depends, Form, Query, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import new_id
from app.db import get_session
from app.models import Batch, Product
from app.routes import templates
from app.services.batches import open_batches
from app.services.catalog import search_products, split_match
from app.services.customers import create_customer, customer_search_view, get_customer
from app.services.pricing import reference_prices_for_code
from app.services.sales import (
    SALE_BATCH_FILL_HINT,
    SALE_CARD_FILL_HINT,
    lookup_prefill,
    non_blank_lines,
    recent_sales,
    register_sale,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Route order: literal paths (/sales/new, /sales/lookup, /sales/row) MUST
# stay declared before any parameterized /sales/{...} route added later
# (04-05 customer picker endpoints are also literal paths, so this holds).

SAVE_FAILED_ERROR = "Не удалось сохранить. Проверьте данные и попробуйте ещё раз."

# CR-01: row_id is echoed unescaped into an hx-on::load JS-evaluated
# attribute (sale_row.html), so it must be constrained to the exact shape
# new_id() produces (a UUID4 string) before it is ever trusted. Anything
# that doesn't match is discarded in favor of a freshly generated id.
_ROW_ID_RE = re.compile(r"[0-9a-fA-F-]{1,36}")

# T-22-01: customer_mode reaches only {% if mode == "..." %} comparisons in
# sale_customer.html, never a JS-evaluated attribute (unlike row_id above,
# which needs the heavier _ROW_ID_RE regex) — so a plain allow-list tuple,
# membership-checked with a default on miss (mirrors customers.py:262's
# _SORT_MAP), is the proportionate guard. Compare, NEVER interpolate.
_CUSTOMER_MODES = ("new", "existing", "anon")


def _customer_context(session: Session, mode: str, customer_id: str, form: dict[str, str]) -> dict:
    """Single shared builder for every render of partials/sale_customer.html.

    D-03 contract: `form` carries ALL modes' values — the active mode's typed
    fields plus the other two (inactive) modes' echoed values — so a mode
    switch round-trips indefinitely without ever losing anything.

    D-12 contract (a verified defect, 22-RESEARCH.md Pitfall 7): this is the
    fix for the silent chip-loss bug. Every one of sale_create's five render
    paths must go through this builder and resolve `selected` server-side,
    instead of hand-writing a bare "customer_id": customer_id (or "") literal
    with no `selected`/`mode`/`form`.

    Returns NO "errors" key on purpose: callers own their own `errors` dict
    (e.g. sale_create's basket/oversell/validation errors) and merge this
    builder's keys into it. 22-RESEARCH.md's Pattern-1 sketch returns
    "errors": {}, which would CLOBBER a caller's real errors on merge — this
    is a deliberate deviation from that sketch, done here on purpose.
    """
    mode = mode if mode in _CUSTOMER_MODES else "existing"
    selected = None
    if mode == "existing" and customer_id:
        # An id that no longer resolves degrades to "nothing selected"
        # rather than rendering a chip for a deleted customer (mirrors
        # _build_lines' batch rule above).
        selected = get_customer(session, customer_id)
    return {
        "mode": mode,
        "customer_id": selected.id if selected else "",
        "selected": selected,
        "form": form,
    }


def _build_lines(
    session: Session,
    codes: list[str],
    qtys: list[str],
    prices: list[str],
    batch_ids: list[str],
    errors: dict[str, str],
):
    """Rebuild the echoed basket rows from submitted arrays + service errors.

    WR-04: uses the shared non_blank_lines helper (app/services/sales.py)
    so this filter always matches register_sale's own filtering — error
    keys (f"qty-{i}"/"price-{i}"/"code-{i}"/f"batch-{i}") line up with the
    right row. The first row keeps a bare row_id ("") so its input ids match
    the sale-form-wrap focus hook (id="code") exactly like a fresh basket;
    later rows get a generated id to avoid DOM collisions.

    D-04/Pitfall 3: each line carries its picked `batch_id` (padded by
    non_blank_lines) and the resolved `selected_batch` so the wrapper row
    re-renders the hidden batch_id[] + selected-only picker on a 422/warn
    re-render — the operator's pick survives. An id that no longer resolves
    renders as "no batch picked" (empty hidden), the service guard is the
    backstop.
    """
    non_blank = non_blank_lines(codes, qtys, prices, batch_ids)
    lines = []
    for i, (code, qty, price, batch_id) in enumerate(non_blank):
        picked = batch_id.strip()
        batch = session.get(Batch, picked) if picked else None
        # PROD-06 (Phase 18 plan 08): ref_pc_cents is the code's ПЦ
        # (consumer_cents) reference (reference_prices_for_code, 18-01),
        # resolved per basket row independently of the fill/error values —
        # a 422/warn re-render must not lose the colour cue on the echoed
        # basket (D-08/D-22).
        _, ref_pc_cents = reference_prices_for_code(session, code)
        lines.append(
            {
                "row_id": "" if i == 0 else new_id(),
                "code": code,
                "name": "",
                "qty": qty,
                "price": price,
                "batch_id": batch.id if batch is not None else "",
                "selected_batch": batch,
                "ref_pc_cents": ref_pc_cents,
                "error_code": errors.get(f"code-{i}"),
                "error_qty": errors.get(f"qty-{i}"),
                "error_price": errors.get(f"price-{i}"),
                "error_batch": errors.get(f"batch-{i}"),
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
    code: str = Query("", alias="code[]"),
    name: str = Query("", alias="name[]"),
    price: str = Query("", alias="price[]"),
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

    # WR-03: mirrors sale_search_name's/sale_batch_pick's row guard — a
    # malformed row value collapses to "" instead of being echoed into the
    # rendered hx-vals JSON (sale_name_field.html).
    row = row.strip()
    if row and not _ROW_ID_RE.fullmatch(row):
        row = ""

    code_clean = code.strip()
    batches: list[Batch] = []
    selected_batch: Batch | None = None
    auto_note = False
    show_empty = False
    # PD-10 analog: default is the card sale_cents fill when the price arrived
    # empty and the match is an active product (dictionary matches carry no
    # prices). The batch rules below may override this.
    fill_price = result["source"] == "product" and not price.strip()
    fill_price_cents = result["prices"]["sale"] if result["prices"] else None
    fill_price_hint = SALE_CARD_FILL_HINT
    # PROD-06 (Phase 18 plan 08): ref_pc_cents is the code's CATALOG ПЦ
    # reference (D-05/D-08/D-22), resolved independently of `source`/
    # fill_price_cents — a "product" match's own card price is NOT the same
    # thing as the catalog reference the cue compares against.
    # 18-REVIEW WR-02 (accepted limitation): sale_lookup.html only renders the
    # OOB price <td> (which carries data-ref-cents) when fill_price is True.
    # If the operator typed a price BEFORE the code lookup resolved, this
    # live-typing (AJAX) path never stamps data-ref-cents for that field —
    # the colour cue simply doesn't activate. The full basket row render
    # (sale_row.html) and the mobile wizard step are unaffected. Purely
    # advisory/cosmetic — not fixed to avoid touching the oob-before-swap
    # race guard (sale_form.html) that protects operator-typed money values.
    _, ref_pc_cents = reference_prices_for_code(session, code_clean)

    if result["source"] == "product":
        product = session.scalars(
            select(Product).where(Product.code == code_clean, Product.deleted_at.is_(None))
        ).first()
        if product is not None:
            batches = open_batches(session, product.id)
            show_empty = not batches
            if batches:
                # Pitfall 4: with open batches the batch pick is the SOLE price
                # source — skip the card fill so it can't occupy the input and
                # block the batch oob fill via the typed-value guard (D-05).
                fill_price = False
                if len(batches) == 1:
                    # D-06: exactly one open batch auto-selects (pre-checked,
                    # highlighted, hidden set) and fills the price by batch
                    # rules — batch price, card sale_cents fallback (D-14).
                    selected_batch = batches[0]
                    auto_note = True
                    if not price.strip():
                        fill_price = True
                        if selected_batch.price_cents is not None:
                            fill_price_cents = selected_batch.price_cents
                            fill_price_hint = SALE_BATCH_FILL_HINT
                        else:
                            fill_price_cents = product.sale_cents

    context = {
        "row": row,
        "name": result["name"],
        "source": result["source"],
        "fill_price": fill_price,
        "fill_price_cents": fill_price_cents,
        "fill_price_hint": fill_price_hint,
        "ref_pc_cents": ref_pc_cents,
        "batches": batches,
        "selected_batch_id": selected_batch.id if selected_batch else None,
        "batch_id_value": selected_batch.id if selected_batch else "",
        "auto_note": auto_note,
        "show_empty": show_empty,
        "code": code_clean,
    }
    return templates.TemplateResponse(request, "partials/sale_lookup.html", context)


@router.get("/sales/search-name")
def sale_search_name(
    request: Request,
    q: str = "",
    row: str = "",
    session: Session = Depends(get_session),
):
    # T-12-07: mirrors sale_batch_pick's row guard — a malformed row value
    # collapses to "" instead of being echoed into rendered ids/hx-on:click.
    row = row.strip()
    if row and not _ROW_ID_RE.fullmatch(row):
        row = ""

    q_stripped = q.strip()
    # D-10/RESEARCH Pitfall 5: the 3-character guard lives HERE, not inside
    # search_products() — that function's own empty-query "first 20 by name"
    # fallback is correct for /products/search but is noise for live typing.
    if len(q_stripped) < 3:
        return Response(status_code=204)

    q_lc = q_stripped.lower()
    products = search_products(session, q_stripped)
    rows = [
        {
            "product": product,
            "code_seg": split_match(product.code or "", q_lc),
            "name_seg": split_match(product.name, q_lc),
        }
        for product in products
    ]
    context = {
        "rows": rows,
        "code_input_id": "code" if not row else f"code-{row}",
        "name_input_id": "name-input" if not row else f"name-input-{row}",
        "dropdown_id": "name-dropdown" if not row else f"name-dropdown-{row}",
    }
    return templates.TemplateResponse(request, "partials/sale_name_search.html", context)


@router.get("/sales/batch-pick")
def sale_batch_pick(
    request: Request,
    row: str = "",
    batch_id: str = "",
    code: str = "",
    session: Session = Depends(get_session),
):
    # T-09-10: `row` is echoed into the re-rendered picker's hx attributes, so
    # a non-empty value must match the id shape new_id() produces (CR-01
    # precedent); anything malformed collapses to the first-row semantics.
    row = row.strip()
    if row and not _ROW_ID_RE.fullmatch(row):
        row = ""

    code_clean = code.strip()
    product = session.scalars(
        select(Product).where(Product.code == code_clean, Product.deleted_at.is_(None))
    ).first()
    # Re-query the open list on every pick (fresh remaining qty — defuses stale
    # picker drift). T-09-08: the client batch_id is untrusted, so re-validate
    # ownership before echoing it as the selection.
    batches = open_batches(session, product.id) if product is not None else []
    picked: Batch | None = None
    if batch_id and product is not None:
        candidate = session.get(Batch, batch_id)
        if candidate is not None and candidate.product_id == product.id:
            picked = candidate

    fill_price = picked is not None
    fill_price_cents: int | None = None
    fill_price_hint = ""
    if picked is not None:
        if picked.price_cents is not None:
            fill_price_cents = picked.price_cents
            fill_price_hint = SALE_BATCH_FILL_HINT
        else:
            # D-14: a legacy NULL-price batch falls back to the card sale_cents.
            fill_price_cents = product.sale_cents
            fill_price_hint = SALE_CARD_FILL_HINT

    # PROD-06 (Phase 18 plan 08): ref_pc_cents is the code's CATALOG ПЦ
    # reference (D-05/D-08/D-22), resolved independently of fill_price_cents
    # — the batch/card fill value is not the same thing as the catalog
    # reference the cue compares against.
    # 18-REVIEW WR-02 (accepted limitation): unlike sale_lookup, fill_price
    # here is gated on a batch being picked, not on the price field being
    # empty — but sale_form.html's oob-before-swap guard still blocks the
    # whole OOB <td> swap (value + data-ref-cents together) whenever the
    # operator has already typed a price. So if a price was typed before the
    # batch pick resolves, that field never gets the colour cue on this
    # AJAX path either. Purely advisory/cosmetic — not fixed to avoid
    # touching the race guard that protects operator-typed money values.
    _, ref_pc_cents = reference_prices_for_code(session, code_clean)

    context = {
        "row": row,
        "code": code_clean,
        "batches": batches,
        "selected_batch_id": picked.id if picked else None,
        "batch_id_value": picked.id if picked else "",
        "fill_price": fill_price,
        "fill_price_cents": fill_price_cents,
        "fill_price_hint": fill_price_hint,
        "ref_pc_cents": ref_pc_cents,
    }
    return templates.TemplateResponse(request, "partials/sale_batch_pick.html", context)


@router.get("/sales/row")
def sale_row(request: Request, row: str = ""):
    # A fresh row is always appended alongside existing rows (hx-swap
    # "beforeend"), so it needs a unique, never-blank row id.
    # CR-01: row_id is later interpolated into an hx-on::load JS attribute
    # (sale_row.html), so client input must be format-validated before use
    # instead of trusted as-is.
    row = row.strip()
    row_id = row if _ROW_ID_RE.fullmatch(row) else new_id()
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


@router.get("/sales/customer-search")
def sale_customer_search(request: Request, q: str = "", session: Session = Depends(get_session)):
    # D-05: rows-only partial for the sale-form header's autocomplete picker.
    context = customer_search_view(session, q)
    return templates.TemplateResponse(request, "partials/customer_picker.html", context)


@router.post("/sales/customer")
def sale_customer_create(
    request: Request,
    name: str = Form(""),
    surname: str = Form(""),
    consultant_number: str = Form(""),
    session: Session = Depends(get_session),
):
    # D-05: inline quick-create from the sale header. Reuses the same
    # create_customer as /customers/new; the difference is purely the
    # response shape (a selected-chip fragment, not a redirect).
    try:
        customer, errors = create_customer(
            session, name=name, surname=surname, consultant_number=consultant_number
        )
    except Exception:  # noqa: BLE001 — UI-SPEC: block error, never a raw 500
        # WR-02: log so a real bug isn't silently reduced to a generic
        # user-facing message with no server-side trace.
        logger.exception("create_customer failed")
        # "quick_create" (not "form") — sale_customer.html is included inside
        # sale_form.html on the normal basket routes, which already renders
        # its OWN errors.form; a shared "form" key would double-render the
        # same error block when both are present. mode stays "new" — the
        # operator is still mid-quick-create and must see their typed values.
        context = {
            **_customer_context(
                session,
                "new",
                "",
                {"name": name, "surname": surname, "consultant_number": consultant_number},
            ),
            "errors": {"quick_create": SAVE_FAILED_ERROR},
        }
        return templates.TemplateResponse(
            request, "partials/sale_customer.html", context, status_code=422
        )

    if errors:
        context = {
            **_customer_context(
                session,
                "new",
                "",
                {"name": name, "surname": surname, "consultant_number": consultant_number},
            ),
            "errors": errors,
        }
        return templates.TemplateResponse(
            request, "partials/sale_customer.html", context, status_code=422
        )

    context = {**_customer_context(session, "existing", customer.id, {}), "errors": {}}
    return templates.TemplateResponse(request, "partials/sale_customer.html", context)


@router.get("/sales/customer-mode")
def sale_customer_mode(
    request: Request,
    customer_mode: str = "existing",
    customer_id: str = "",
    customer_id_keep: str = "",
    customer_q: str = "",
    name: str = "",
    surname: str = "",
    consultant_number: str = "",
    session: Session = Depends(get_session),
):
    # SALE-03/D-03: the mode radio's hx-get lands here on every switch.
    # Coalesce customer_id/customer_id_keep — do NOT pick one: whichever
    # mode is LEAVING supplies one of them (the visible hidden input, or the
    # inactive echo).
    try:
        context = {
            **_customer_context(
                session,
                customer_mode,
                customer_id or customer_id_keep,
                {
                    "customer_q": customer_q,
                    "name": name,
                    "surname": surname,
                    "consultant_number": consultant_number,
                },
            ),
            "errors": {},
        }
    except Exception:  # noqa: BLE001 — UI-SPEC: block error, never a raw 500
        # WR-02: log so a real bug isn't silently reduced to a generic
        # user-facing message with no server-side trace.
        logger.exception("customer mode render failed")
        context = {
            "mode": "existing",
            "customer_id": "",
            "selected": None,
            "form": {},
            "errors": {"quick_create": SAVE_FAILED_ERROR},
        }
        return templates.TemplateResponse(
            request, "partials/sale_customer.html", context, status_code=422
        )
    return templates.TemplateResponse(request, "partials/sale_customer.html", context)


@router.post("/sales")
def sale_create(
    request: Request,
    code: list[str] = Form([], alias="code[]"),
    qty: list[str] = Form([], alias="qty[]"),
    price: list[str] = Form([], alias="price[]"),
    batch_id: list[str] = Form([], alias="batch_id[]"),
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
            batch_ids=batch_id,
            confirm=confirm,
        )
    except Exception:  # noqa: BLE001 — UI-SPEC: block error, never a raw 500
        # WR-02: log so a real bug isn't silently reduced to a generic
        # user-facing message with no server-side trace.
        logger.exception("register_sale failed")
        context = {
            "errors": {"form": SAVE_FAILED_ERROR},
            "lines": _build_lines(session, code, qty, price, batch_id, {}),
            "customer_id": customer_id,
            "focus_code": False,
            "include_oob_rows": False,
        }
        return templates.TemplateResponse(
            request, "partials/sale_form.html", context, status_code=422
        )

    # SAL-04/D-08/PRICE-01/D-11: oversell and/or below-minimum — zero
    # writes, warn above the still-intact basket (lines re-rendered from
    # the submitted arrays; the confirm button re-POSTs the same basket
    # via form="sale-form" + confirm=1). Both keys are checked here (not
    # just "oversell") so a basket tripping ONLY below_minimum doesn't
    # fall through this guard and reach the success-write branch below.
    if result and (result.get("oversell") or result.get("below_minimum")):
        context = {
            "errors": {},
            "lines": _build_lines(session, code, qty, price, batch_id, {}),
            "customer_id": customer_id,
            "focus_code": False,
            "include_oob_rows": False,
            "oversell": result.get("oversell"),
            "below_minimum": result.get("below_minimum"),
        }
        return templates.TemplateResponse(request, "partials/sale_form.html", context)

    if errors:
        context = {
            "errors": errors,
            "lines": _build_lines(session, code, qty, price, batch_id, errors),
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
