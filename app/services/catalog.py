"""Catalog service (CAT-01): create/list products, fat service (D-11).

Contract: Product-field writes live in app/services/*; Operation rows and
the cached stock projection are written ONLY in app/services/ledger.record_operation.
The catalog stages Product mutations WITHOUT committing and lets
record_operation's internal commit close the transaction atomically (D-30).
"""

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import new_id, to_cents, utcnow_iso
from app.models import Operation, Product
from app.services.ledger import record_operation
from app.services.pagination import paginate

PRICE_ERROR = "Неверный формат цены — введите число, например 12,50."
DUPLICATE_CODE_ERROR = "Код уже используется другим товаром — введите другой код."
THRESHOLD_ERROR = "Введите целое число 0 или больше."

# Phase 14 (LIST-03, D-06/D-07): allow-list of sort keys for list_products_view.
# Python-side `key=` callables (small cardinality per RESEARCH.md A1), never
# string-interpolated into a SQL ORDER BY (T-14-09).
_SORT_MAP = {
    "name_desc": lambda p: p.name_lc or "",
    "code": lambda p: (p.code or "").lower(),
}


def parse_optional_cents(raw: str, errors: dict, field: str) -> int | None:
    """Empty string -> NULL column; otherwise to_cents; RU error on garbage.

    WR-04: negative amounts have no domain meaning for a purchase/sale/
    catalog price, so they are rejected with the same PRICE_ERROR as
    unparsable input, not silently stored as a negative cents value.
    """
    raw = raw.strip()
    if not raw:
        return None
    try:
        cents = to_cents(raw)
    except ValueError:
        errors[field] = PRICE_ERROR
        return None
    if cents < 0:
        errors[field] = PRICE_ERROR
        return None
    return cents


def parse_optional_int(raw: str, errors: dict, field: str) -> int | None:
    """Empty string -> NULL (Pitfall 3: "use global default", NOT zero).

    T-06-01/T-06-02: WR-01-style ASCII-digit-only allow-list — mirrors the
    qty/price guard style used in sales.py/writeoffs.py/corrections.py. A
    genuine "0" is parsed and returned as the int 0, never coerced to None.
    """
    raw = raw.strip()
    if not raw:
        return None
    if raw.isascii() and raw.isdigit() and int(raw) <= 2_147_483_647:
        return int(raw)
    errors[field] = THRESHOLD_ERROR
    return None


def create_product(
    session: Session,
    *,
    code: str,
    name: str,
    category: str,
    cost_raw: str,
    sale_raw: str,
    min_sale_raw: str = "",
    low_stock_threshold_raw: str = "",
    stale_days_raw: str = "",
) -> tuple[Product | None, dict[str, str]]:
    """Create a product and its product_created audit op atomically (D-19/D-30).

    Returns (product, {}) on success or (None, errors) with RU messages —
    on errors NOTHING is written to the session.
    """
    errors: dict[str, str] = {}
    code = code.strip()  # PD-2: normalize codes at write time
    name = name.strip()
    category = category.strip()

    if not code:
        errors["code"] = "Укажите код товара."
    if not name:
        errors["name"] = "Укажите название."

    # D-19: code unique among NON-deleted products only.
    if code:
        duplicate = session.scalars(
            select(Product).where(Product.code == code, Product.deleted_at.is_(None))
        ).first()
        if duplicate is not None:
            errors["code"] = DUPLICATE_CODE_ERROR

    cost_cents = parse_optional_cents(cost_raw, errors, "cost")
    sale_cents = parse_optional_cents(sale_raw, errors, "sale")
    min_sale_cents = parse_optional_cents(min_sale_raw, errors, "min_sale")
    low_stock_threshold = parse_optional_int(
        low_stock_threshold_raw, errors, "low_stock_threshold"
    )
    stale_days = parse_optional_int(stale_days_raw, errors, "stale_days")

    if errors:
        return None, errors

    product = Product(
        id=new_id(),
        code=code,
        name=name,
        # D-27: unconditional Python lower — SQLite cannot fold Cyrillic.
        name_lc=name.lower(),
        category=category or None,
        cost_cents=cost_cents,
        sale_cents=sale_cents,
        # D-01/Pitfall 4 (Phase 18 plan 02): the third (catalog) price is no
        # longer parsed or written here — PROD-05 collapses pricing to ДЦ/ПЦ only.
        min_sale_cents=min_sale_cents,
        low_stock_threshold=low_stock_threshold,
        stale_days=stale_days,
        quantity=0,
    )
    # Stage-then-commit: record_operation's session.get autoflushes the
    # pending product, then its commit persists product + op atomically.
    # WR-04: uq_products_code_active is the DB backstop for the SELECT-based
    # duplicate check above — a double-submit race fires IntegrityError at
    # flush/commit and is translated into the same RU error shape.
    session.add(product)
    try:
        record_operation(
            session,
            type_="product_created",
            product_id=product.id,
            qty_delta=0,
            payload={"code": product.code, "name": product.name},
        )
    except IntegrityError:
        session.rollback()
        return None, {"code": DUPLICATE_CODE_ERROR}
    return product, errors


def get_product(session: Session, product_id: str) -> Product | None:
    """Plain lookup; returns soft-deleted products too (edit page shows a banner)."""
    return session.get(Product, product_id)


# D-01/Pitfall 4 (Phase 18 plan 02): the third (catalog) price field was
# dropped from this tuple — it drives the price-change audit getattr loop
# below, so leaving a removed field here would AttributeError once plan
# 18-04 drops the model attribute it names.
_PRICE_FIELDS = ("cost_cents", "sale_cents", "min_sale_cents")


def update_product(
    session: Session,
    product_id: str,
    *,
    code: str,
    name: str,
    category: str,
    cost_raw: str,
    sale_raw: str,
    min_sale_raw: str = "",
    low_stock_threshold_raw: str = "",
    stale_days_raw: str = "",
) -> tuple[Product | None, dict[str, str]]:
    """Update a product; audit every change through the single write path.

    D-28: one price_change op per changed price field (old snapshotted
    BEFORE mutation — Pitfall 7). D-30: one product_edited op listing the
    changed non-price fields. Returns (product, {}) on success (also when
    nothing changed — then zero ops are written) or (None, errors).
    """
    errors: dict[str, str] = {}
    product = session.get(Product, product_id)
    if product is None:
        return None, {"product": "Товар не найден."}
    # D-20: editing a soft-deleted product is rejected up front.
    if product.deleted_at is not None:
        return None, {"product": "Товар удалён — восстановите его перед редактированием."}

    code = code.strip()  # PD-2: normalize codes at write time
    name = name.strip()
    category = category.strip()

    if not code:
        errors["code"] = "Укажите код товара."
    if not name:
        errors["name"] = "Укажите название."

    # D-19: code unique among NON-deleted products, excluding the product itself.
    if code:
        duplicate = session.scalars(
            select(Product).where(
                Product.code == code,
                Product.deleted_at.is_(None),
                Product.id != product_id,
            )
        ).first()
        if duplicate is not None:
            errors["code"] = DUPLICATE_CODE_ERROR

    cost_cents = parse_optional_cents(cost_raw, errors, "cost")
    sale_cents = parse_optional_cents(sale_raw, errors, "sale")
    min_sale_cents = parse_optional_cents(min_sale_raw, errors, "min_sale")
    low_stock_threshold = parse_optional_int(
        low_stock_threshold_raw, errors, "low_stock_threshold"
    )
    stale_days = parse_optional_int(stale_days_raw, errors, "stale_days")

    if errors:
        return None, errors

    # Pitfall 7: snapshot old values BEFORE any mutation.
    old_prices = {field: getattr(product, field) for field in _PRICE_FIELDS}
    # D-04/D-05: low_stock_threshold/stale_days are plain integer fields (not
    # money), so they follow the product_edited audit path alongside
    # code/name/category, NOT the per-field price_change path.
    old_fields = {
        "code": product.code,
        "name": product.name,
        "category": product.category,
        "low_stock_threshold": product.low_stock_threshold,
        "stale_days": product.stale_days,
    }
    new_prices = {
        "cost_cents": cost_cents,
        "sale_cents": sale_cents,
        "min_sale_cents": min_sale_cents,
    }
    new_fields = {
        "code": code,
        "name": name,
        "category": category or None,
        "low_stock_threshold": low_stock_threshold,
        "stale_days": stale_days,
    }

    changed_prices = [f for f in _PRICE_FIELDS if old_prices[f] != new_prices[f]]
    changed_non_price = sorted(f for f in old_fields if old_fields[f] != new_fields[f])

    # No-op save: nothing changed -> zero operations, no commit.
    if not changed_prices and not changed_non_price:
        return product, {}

    product.code = code
    product.name = name
    # D-27: unconditional Python lower — SQLite cannot fold Cyrillic.
    product.name_lc = name.lower()
    product.category = category or None
    product.cost_cents = cost_cents
    product.sale_cents = sale_cents
    product.min_sale_cents = min_sale_cents
    product.low_stock_threshold = low_stock_threshold
    product.stale_days = stale_days

    # PD-3: one op per changed price field. WR-03: ALL ops are staged with
    # commit=False and persisted by the SINGLE commit below, so the product
    # mutation and every audit row land in one transaction — a crash between
    # ops can no longer strand a partial price history.
    # WR-04: the staged code UPDATE flushes inside record_operation (autoflush
    # before next_seq's SELECT) or at the final commit — either can raise
    # IntegrityError from uq_products_code_active on a duplicate-code race.
    try:
        for field in changed_prices:
            payload = {
                "field": field,
                "old_cents": old_prices[field],
                "new_cents": new_prices[field],
            }
            record_operation(
                session,
                type_="price_change",
                product_id=product.id,
                qty_delta=0,
                payload=payload,
                commit=False,
            )
        if changed_non_price:
            record_operation(
                session,
                type_="product_edited",
                product_id=product.id,
                qty_delta=0,
                payload={"fields": changed_non_price},
                commit=False,
            )
        session.commit()
    except IntegrityError:
        session.rollback()
        return None, {"code": DUPLICATE_CODE_ERROR}
    return product, {}


def soft_delete_product(session: Session, product_id: str) -> None:
    """D-20 / PD-4: plain product-row write, no ledger op. Idempotent."""
    product = session.get(Product, product_id)
    if product is None or product.deleted_at is not None:
        return
    product.deleted_at = utcnow_iso()
    session.commit()


def quick_delete_product(session: Session, product_id: str) -> tuple[bool, dict]:
    """List-row quick delete (LIST-05, D-08): hard-blocked while stock > 0.

    Mirrors soft_delete_warehouse's (deleted, info) shape:
      (True, {})              -> deleted (quantity == 0)
      (False, {})              -> unknown id or already deleted (no-op)
      (False, {"blocked_qty"}) -> blocked, ZERO writes staged (no override, T-14-11)

    D-09: Product.quantity is already a cached projection of
    SUM(operations.qty_delta) — no extra query is needed for the guard.
    """
    product = session.get(Product, product_id)
    if product is None or product.deleted_at is not None:
        return False, {}
    if product.quantity > 0:
        return False, {"blocked_qty": product.quantity}
    product.deleted_at = utcnow_iso()
    session.commit()
    return True, {}


def restore_product(session: Session, product_id: str) -> None:
    """Clear deleted_at; the product reappears in lists and search (D-20)."""
    product = session.get(Product, product_id)
    if product is None or product.deleted_at is None:
        return
    product.deleted_at = None
    session.commit()


def price_history(session: Session, product_id: str) -> list[Operation]:
    """price_change ops for one product, newest first (D-29, Pitfall 8 tie-break)."""
    return list(
        session.scalars(
            select(Operation)
            .where(
                Operation.product_id == product_id,
                Operation.type == "price_change",
            )
            .order_by(Operation.created_at.desc(), Operation.seq.desc())
        )
    )


def list_products(session: Session) -> list[Product]:
    """Active products ordered by name, capped at 20 (D-26 shape for 02-03)."""
    return list(
        session.scalars(
            select(Product)
            .where(Product.deleted_at.is_(None))
            .order_by(Product.name)
            .limit(20)
        )
    )


def list_products_view(
    session: Session,
    *,
    code: str = "",
    name: str = "",
    category: str = "",
    sort: str = "",
    page: int = 0,
) -> dict:
    """Filter/sort/page the `/products` list (LIST-01/02/03, D-04..D-07).

    Small cardinality (RESEARCH.md A1) -> Python-side filter/sort after one
    fetch, then the shared pagination.paginate slicer. Deleted products never
    appear, regardless of filter/sort/page.
    """
    rows = list(session.scalars(select(Product).where(Product.deleted_at.is_(None))))

    code_q = code.strip().lower()
    if code_q:
        rows = [p for p in rows if code_q in (p.code or "").lower()]
    name_q = name.strip().lower()
    if name_q:
        rows = [p for p in rows if name_q in (p.name_lc or "")]
    category_q = category.strip().lower()
    if category_q:
        rows = [p for p in rows if category_q in (p.category or "").lower()]

    if sort in _SORT_MAP:
        rows.sort(key=_SORT_MAP[sort], reverse=(sort == "name_desc"))
    else:
        rows.sort(key=lambda p: p.name_lc or "")  # D-07: unchanged default order

    page_rows, total, total_pages = paginate(rows, page)
    return {
        "rows": page_rows,
        "total": total,
        "total_pages": total_pages,
        "page": page,
        "code": code,
        "name": name,
        "category": category,
        "sort": sort,
    }


# --- Instant search (CAT-03, D-25/D-26/D-27) ---


def _escape_like(q: str) -> str:
    """Escape \\, % and _ so they match LITERALLY in the manual prefix LIKE."""
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search_products(session: Session, q: str) -> list[Product]:
    """Ranked, capped, Cyrillic-safe product search (D-25/D-26).

    D-27: the query string is lowered in PYTHON and compared against the
    name_lc shadow column — SQLite lower()/LIKE fold ASCII only, so
    func.lower is permitted ONLY on Product.code (ASCII codes, A1).
    """
    base = select(Product).where(Product.deleted_at.is_(None))
    q_lc = q.strip().lower()  # Python folds Cyrillic; SQL lower() cannot
    if not q_lc:
        # Pitfall 6: empty query -> first 20 active products by name.
        return list(session.scalars(base.order_by(Product.name).limit(20)))
    code_prefix = func.lower(Product.code).like(_escape_like(q_lc) + "%", escape="\\")
    # D-26 ranking: exact code (0) > code prefix (1) > name substring (2).
    rank = case(
        (func.lower(Product.code) == q_lc, 0),
        (code_prefix, 1),
        else_=2,
    )
    stmt = (
        base.where(code_prefix | Product.name_lc.contains(q_lc, autoescape=True))
        .order_by(rank, Product.name_lc)
        .limit(20)  # locked cap
    )
    return list(session.scalars(stmt))


def split_match(text: str, q_lc: str) -> tuple[str, str, str]:
    """Return (pre, match, post) segments; match == '' when q empty/not found.

    Pattern 5: no HTML is built in Python — the template renders each
    segment autoescaped with a literal <mark> around the match.
    """
    idx = text.lower().find(q_lc) if q_lc else -1
    if idx < 0:
        return text, "", ""
    return text[:idx], text[idx : idx + len(q_lc)], text[idx + len(q_lc) :]


def search_view(session: Session, q: str) -> dict:
    """Shared context for the full list page AND the search partial (D-18)."""
    q_lc = q.strip().lower()
    rows = [
        {
            "product": product,
            "code_seg": split_match(product.code or "", q_lc),
            "name_seg": split_match(product.name, q_lc),
        }
        for product in search_products(session, q)
    ]
    return {"q": q, "rows": rows}


def category_options(session: Session) -> list[str]:
    """Distinct non-empty categories of active products, sorted (datalist)."""
    return list(
        session.scalars(
            select(Product.category)
            .where(
                Product.deleted_at.is_(None),
                Product.category.is_not(None),
                Product.category != "",
            )
            .distinct()
            .order_by(Product.category)
        )
    )


def products_by_category(session: Session) -> list[dict]:
    """Active products grouped by category, alphabetical, "Без категории" last (D-03/D-04).

    Python-side grouping (not a SQL NULL-ordering trick, per RESEARCH.md Open
    Question #2) guarantees the uncategorized bucket sorts last regardless of
    dict iteration order.
    """
    products = list(
        session.scalars(
            select(Product).where(Product.deleted_at.is_(None)).order_by(Product.name_lc)
        )
    )
    by_category: dict[str, list[Product]] = {}
    for p in products:
        by_category.setdefault(p.category or "", []).append(p)
    named = sorted(k for k in by_category if k)
    groups = [{"label": k, "products": by_category[k]} for k in named]
    if "" in by_category:
        groups.append({"label": "Без категории", "products": by_category[""]})
    return groups
