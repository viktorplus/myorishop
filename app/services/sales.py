"""Sales service (SAL-01/02/05): the multi-line basket write built on the ledger.

D-01/D-02/D-03: one sale = a BASKET of N product lines, grouped by a `sales`
header (id UUID, optional customer_id) and written as N `sale` operations
(qty_delta < 0) linked back to the header via `Operation.sale_id`. The whole
basket is ONE transaction — an empty basket cannot be finalized, and an
unknown code on any line aborts the entire basket (all-or-nothing).

D-10: the entered per-line price is REQUIRED and becomes unit_price_cents
(overrides the card sale_cents — a pre-fill only). D-11/D-12: unit_cost_cents
is frozen from Product.cost_cents at write time and may be NULL (a NULL card
cost never blocks the sale; an empty/invalid PRICE does).

SAL-04/D-08/D-09: after per-line validation and before any write, requested
quantity is aggregated per PICKED BATCH across the whole basket (Pitfall 8)
and compared to the cached Batch.quantity — a different batch's stock is
irrelevant (criterion 4). An oversold basket with confirm != "1" returns
{"oversell": [...]} with ZERO writes; confirm == "1" skips the check and the
sale writes (stock may go negative).

LOT-02/D-04: every line REQUIRES a picked batch owned by the line's product;
a missing/foreign batch is rejected with «Выберите партию.» before any write.

Single-write-path contract: Operation rows and products.quantity are
written ONLY through app.services.ledger.record_operation — every line is
staged with commit=False and ONE commit closes the transaction (WR-03).
"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.core import new_id, to_cents, utcnow_iso
from app.models import Batch, Customer, Operation, Product, Sale
from app.services import catalog, finance
from app.services.dictionary import lookup as dictionary_lookup
from app.services.ledger import record_operation

PRICE_REQUIRED_ERROR = "Укажите цену продажи."
EMPTY_BASKET_ERROR = "Добавьте хотя бы одну строку, чтобы оформить продажу."
PRODUCT_NOT_FOUND_TMPL = "Товар с кодом „{code}“ не найден. Сначала оприходуйте товар."
QTY_ERROR = "Укажите количество — целое число больше нуля."
SAVE_ROLLBACK = "Не удалось сохранить продажу. Попробуйте ещё раз."
# PROD-07/D-17/D-23: both sale prefill-hint families (card-sourced and
# batch-sourced) must state the sale-only scope — a sale is a negotiation
# with one customer, so an edited ПЦ/batch price here is saved to THIS sale
# only. D-15/D-16 reject any sale->card write-back (it would erode PRICE-01's
# below-minimum guardrail via the shared confirm=1 bypass), so a silent hint
# would wrongly imply the price persists. Mirrors receipts.py:23's
# CARD_FILL_HINT precedent; imported by both app/routes/sales.py and
# app/routes/mobile_sales.py (the sanctioned public-constant cross-import).
SALE_CARD_FILL_HINT = (
    "Цена подставлена из карточки товара — можно изменить; "
    "изменение сохранится только в этой продаже."
)
SALE_BATCH_FILL_HINT = (
    "Цена подставлена из партии — можно изменить; изменение сохранится только в этой продаже."
)
# LOT-02/D-04: service-level enforcement that every line has a picked, owned
# batch. This is the primary guard (the record_operation D-12 guard is only a
# Plan 05 backstop).
BATCH_REQUIRED_ERROR = "Выберите партию."


def non_blank_lines(
    codes: list[str],
    qtys: list[str],
    prices: list[str],
    batch_ids: list[str] | None = None,
) -> list[tuple[str, str, str, str]]:
    """Filter basket lines to those with any non-blank code/qty/price field.

    WR-04: single source of truth for "a line counts only if code/qty/price
    is non-blank after strip", shared by register_sale (below) and the
    route's _build_lines (app/routes/sales.py) so error keys
    (f"qty-{i}"/"price-{i}"/"code-{i}"/f"batch-{i}") stay in sync between them.

    D-04/Pitfall 2: a 4th strictly-aligned batch_ids array rides along. Its
    blankness NEVER affects the line filter (a stray batch_id must not
    resurrect an otherwise-blank row); it is padded with "" up to len(codes)
    BEFORE zipping so a short/missing array degrades to "no batch picked"
    (which register_sale then rejects loudly) rather than shifting attribution
    onto the wrong line.
    """
    batch_ids = list(batch_ids or [])
    if len(batch_ids) < len(codes):
        batch_ids = batch_ids + [""] * (len(codes) - len(batch_ids))
    return [
        (code, qty, price, batch_ids[i])
        for i, (code, qty, price) in enumerate(zip(codes, qtys, prices, strict=False))
        if code.strip() or qty.strip() or price.strip()
    ]


def register_sale(
    session: Session,
    *,
    customer_id: str | None,
    codes: list[str],
    qtys: list[str],
    prices: list[str],
    batch_ids: list[str] | None = None,
    confirm: str = "",
) -> tuple[dict | None, dict[str, str]]:
    """Register one walk-in/customer sale atomically; returns (result, errors).

    Success: ({"header": ..., "line_count": ..., "total_cents": ...}, {}).
    Failure: (None, errors) with RU messages — NOTHING is staged or written
    on any validation error (D-03: the whole basket is one transaction).

    LOT-02/D-04: `batch_ids` is the per-line picked-batch array, kept
    index-aligned with codes/qtys/prices (padded in non_blank_lines). Every
    line MUST resolve to a batch owned by that line's product; an empty,
    unknown, or foreign batch id is rejected with «Выберите партию.» here at
    the service level (the record_operation guard is Plan 05's backstop).
    """
    errors: dict[str, str] = {}

    # D-03: a line counts only if any of code/qty/price is non-blank after
    # strip; a fully blank basket cannot be finalized.
    non_blank = non_blank_lines(codes, qtys, prices, batch_ids)
    if not non_blank:
        return None, {"basket": EMPTY_BASKET_ERROR}

    resolved: list[dict] = []
    for i, (code_raw, qty_raw, price_raw, batch_id_raw) in enumerate(non_blank):
        code = code_raw.strip()

        # D-01: qty_delta strictly positive integer; corrections are Phase 5.
        # WR-01: isdigit() alone accepts non-ASCII "digit" characters (e.g.
        # superscript '²') that int() cannot parse and raises on; guard
        # with isascii() first so an unparsable value falls through to the
        # QTY_ERROR path instead of an uncaught ValueError.
        qty_text = qty_raw.strip()
        qty = int(qty_text) if qty_text.isascii() and qty_text.isdigit() else 0
        if qty <= 0:
            errors[f"qty-{i}"] = QTY_ERROR

        # D-12 divergence from receipts: sale price is REQUIRED per line —
        # empty is rejected (unlike receipts, where empty price = NULL).
        price_text = price_raw.strip()
        price_cents: int | None = None
        if not price_text:
            errors[f"price-{i}"] = PRICE_REQUIRED_ERROR
        else:
            try:
                price_cents = to_cents(price_text)
            except ValueError:
                errors[f"price-{i}"] = catalog.PRICE_ERROR
            else:
                # WR-04 (mirrors catalog.parse_optional_cents): a negative
                # sale price has no domain meaning regardless of whether
                # min_sale_cents is configured — reject with the same
                # PRICE_ERROR convention used for every other money field.
                if price_cents < 0:
                    errors[f"price-{i}"] = catalog.PRICE_ERROR
                    price_cents = None

        # Active-only lookup — a soft-deleted product's code is unknown.
        product = session.scalars(
            select(Product).where(Product.code == code, Product.deleted_at.is_(None))
        ).first()
        if product is None:
            errors[f"code-{i}"] = PRODUCT_NOT_FOUND_TMPL.format(code=code)

        # LOT-02/D-04: resolve+validate the picked batch. Empty, unknown, or
        # foreign (belongs to another product) -> «Выберите партию.» and the
        # whole basket aborts (D-03). T-09-08: the client batch_id is
        # untrusted, so ownership is re-checked server-side.
        batch_id = batch_id_raw.strip()
        batch: Batch | None = None
        if not batch_id:
            errors[f"batch-{i}"] = BATCH_REQUIRED_ERROR
        else:
            batch = session.get(Batch, batch_id)
            if batch is None or (product is not None and batch.product_id != product.id):
                errors[f"batch-{i}"] = BATCH_REQUIRED_ERROR
                batch = None

        resolved.append(
            {"product": product, "qty": qty, "price_cents": price_cents, "batch": batch}
        )

    # D-03: any invalid line aborts the WHOLE basket — nothing staged yet.
    if errors:
        return None, errors

    # SAL-04/D-08/D-09: aggregate oversell check — sum requested qty per
    # product_id across ALL resolved lines (Pitfall 6: the SAME product on
    # two lines must be summed before comparing, not checked line-by-line),
    # compare to the cached Product.quantity (authoritative projection —
    # RESEARCH A4, do NOT recompute via compute_stock here). If any product
    # oversells and confirm != "1", warn with ZERO writes. confirm == "1"
    # skips the block entirely (D-09: stock may go negative).
    if confirm != "1":
        # D-09/criterion 4: oversell is scoped to the PICKED BATCH's remaining
        # quantity, not the product total. The SAME batch on two lines is
        # summed before the check (Pitfall 8); a different batch's stock is
        # irrelevant. Every line has a validated batch here (errors is empty).
        requested_by_batch: dict[str, int] = {}
        batches_by_id: dict[str, Batch] = {}
        products_by_batch: dict[str, Product] = {}
        for line in resolved:
            batch = line["batch"]
            requested_by_batch[batch.id] = requested_by_batch.get(batch.id, 0) + line["qty"]
            batches_by_id[batch.id] = batch
            products_by_batch[batch.id] = line["product"]

        oversold = [
            {
                "product": products_by_batch[batch_id],
                "batch": batches_by_id[batch_id],
                "available": batches_by_id[batch_id].quantity,
                "requested": requested,
            }
            for batch_id, requested in requested_by_batch.items()
            if requested > batches_by_id[batch_id].quantity
        ]

        # PRICE-01/D-08/D-09/D-10: per-LINE minimum-price check (NOT
        # aggregated like the oversell qty sum above — the same product on
        # two lines is checked independently on each). is not None (D-06)
        # so an unset minimum never blocks, and strict < (D-10) so a price
        # exactly at the minimum passes silently.
        below_minimum = [
            {
                "product": line["product"],
                "entered": line["price_cents"],
                "minimum": line["product"].min_sale_cents,
            }
            for line in resolved
            if line["product"].min_sale_cents is not None
            and line["price_cents"] < line["product"].min_sale_cents
        ]

        # Pitfall 2: both checks are computed above BEFORE any return, so a
        # basket tripping both surfaces both warnings in the SAME response
        # instead of the price-floor check being silently skipped by an
        # early oversell-only return.
        if oversold or below_minimum:
            result: dict = {}
            if oversold:
                oversold.sort(key=lambda entry: entry["product"].name)
                result["oversell"] = oversold
            if below_minimum:
                below_minimum.sort(key=lambda entry: entry["product"].name)
                result["below_minimum"] = below_minimum
            return result, {}

    header = Sale(
        id=new_id(),
        customer_id=customer_id or None,
        created_at=utcnow_iso(),
        created_by=settings.operator_name,
        device_id=settings.device_id,
    )
    session.add(header)

    total_cents = 0
    # WR-03: the write loop itself is inside the try so a non-IntegrityError
    # raised by record_operation's own guards (e.g. a TOCTOU soft-delete
    # race -> ValueError) rolls back explicitly instead of leaving the
    # session holding uncommitted pending inserts.
    try:
        for line in resolved:
            product = line["product"]
            qty = line["qty"]
            price_cents = line["price_cents"]
            record_operation(
                session,
                type_="sale",
                product_id=product.id,
                qty_delta=-qty,
                unit_cost_cents=product.cost_cents,  # D-11 freeze (may be None)
                unit_price_cents=price_cents,  # D-10 entered price
                sale_id=header.id,
                batch_id=line["batch"].id,  # LOT-02/D-11 per-line picked batch
                commit=False,
            )
            total_cents += qty * price_cents

        # FIN-01/D-00c: stage ONE aggregated credit for the whole basket,
        # linked by header.id, in the SAME transaction as the Sale + N
        # Operation rows — closed by the single session.commit() below.
        finance.record_cash_movement(
            session,
            category="sale",
            amount_cents=total_cents,
            sale_id=header.id,
            commit=False,
        )

        # WR-03/WR-04: single transaction close.
        session.commit()
    except (IntegrityError, ValueError):
        session.rollback()
        return None, {"basket": SAVE_ROLLBACK}

    return {
        "header": header,
        "line_count": len(resolved),
        "total_cents": total_cents,
    }, {}


def lookup_prefill(session: Session, code: str) -> dict | None:
    """Pre-fill data for a basket line's lookup. Read-only.

    Active product first: its name plus the card `sale_cents` (D-10 — only
    the sale price pre-fills, not cost/catalog). Dictionary fallback: name
    only. Unknown code -> None (the route answers 204).
    """
    code = code.strip()
    if not code:
        return None
    product = session.scalars(
        select(Product).where(Product.code == code, Product.deleted_at.is_(None))
    ).first()
    if product is not None:
        return {
            "source": "product",
            "name": product.name,
            "prices": {"sale": product.sale_cents},
        }
    entry = dictionary_lookup(session, code)
    if entry is not None:
        return {"source": "dictionary", "name": entry.name, "prices": None}
    return None


def recent_sales(session: Session, limit: int = 10) -> list[dict]:
    """Last N sale ops joined to their products, newest first (mirrors D-04).

    SALE-07/D-06: also joins the buyer via a DOUBLE outerjoin (Operation ->
    Sale -> Customer, mirroring export.py:117-125's shipped shape) so every
    row carries a `customer` key — `None` for a walk-in sale. Both hops MUST
    stay outerjoin: an inner join on Sale or Customer would silently DROP a
    walk-in row from this newest-first UI listing instead of labelling it
    «Розница» (D-06), and Operation.sale_id/Sale.customer_id are both
    nullable by design (models.py:318/409). Do not "simplify" to `.join`.
    """
    rows = session.execute(
        select(Operation, Product, Customer)
        .join(Product, Operation.product_id == Product.id)
        .outerjoin(Sale, Operation.sale_id == Sale.id)
        .outerjoin(Customer, Sale.customer_id == Customer.id)
        .where(Operation.type == "sale")
        .order_by(Operation.created_at.desc(), Operation.seq.desc())
        .limit(limit)
    ).all()
    return [{"op": op, "product": product, "customer": customer} for op, product, customer in rows]
