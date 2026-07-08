"""Catalog service (CAT-01): create/list products, fat service (D-11).

Contract: Product-field writes live in app/services/*; Operation rows and
the cached stock projection are written ONLY in app/services/ledger.record_operation.
The catalog stages Product mutations WITHOUT committing and lets
record_operation's internal commit close the transaction atomically (D-30).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import new_id, to_cents, utcnow_iso
from app.models import Operation, Product
from app.services.ledger import record_operation

PRICE_ERROR = "Неверный формат цены — введите число, например 12,50."


def parse_optional_cents(raw: str, errors: dict, field: str) -> int | None:
    """Empty string -> NULL column; otherwise to_cents; RU error on garbage."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        return to_cents(raw)
    except ValueError:
        errors[field] = PRICE_ERROR
        return None


def create_product(
    session: Session,
    *,
    code: str,
    name: str,
    category: str,
    cost_raw: str,
    sale_raw: str,
    catalog_raw: str,
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
            errors["code"] = "Код уже используется другим товаром — введите другой код."

    cost_cents = parse_optional_cents(cost_raw, errors, "cost")
    sale_cents = parse_optional_cents(sale_raw, errors, "sale")
    catalog_cents = parse_optional_cents(catalog_raw, errors, "catalog")

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
        catalog_cents=catalog_cents,
        quantity=0,
    )
    # Stage-then-commit: record_operation's session.get autoflushes the
    # pending product, then its commit persists product + op atomically.
    session.add(product)
    record_operation(
        session,
        type_="product_created",
        product_id=product.id,
        qty_delta=0,
        payload={"code": product.code, "name": product.name},
    )
    return product, errors


def get_product(session: Session, product_id: str) -> Product | None:
    """Plain lookup; returns soft-deleted products too (edit page shows a banner)."""
    return session.get(Product, product_id)


_PRICE_FIELDS = ("cost_cents", "sale_cents", "catalog_cents")


def update_product(
    session: Session,
    product_id: str,
    *,
    code: str,
    name: str,
    category: str,
    cost_raw: str,
    sale_raw: str,
    catalog_raw: str,
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
            errors["code"] = "Код уже используется другим товаром — введите другой код."

    cost_cents = parse_optional_cents(cost_raw, errors, "cost")
    sale_cents = parse_optional_cents(sale_raw, errors, "sale")
    catalog_cents = parse_optional_cents(catalog_raw, errors, "catalog")

    if errors:
        return None, errors

    # Pitfall 7: snapshot old values BEFORE any mutation.
    old_prices = {field: getattr(product, field) for field in _PRICE_FIELDS}
    old_fields = {"code": product.code, "name": product.name, "category": product.category}
    new_prices = {
        "cost_cents": cost_cents,
        "sale_cents": sale_cents,
        "catalog_cents": catalog_cents,
    }
    new_fields = {"code": code, "name": name, "category": category or None}

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
    product.catalog_cents = catalog_cents

    # PD-3: one op per changed price field; the FIRST record_operation commit
    # also persists all staged product-row mutations atomically.
    for field in changed_prices:
        payload = {
            "field": field,
            "old_cents": old_prices[field],
            "new_cents": new_prices[field],
        }
        record_operation(
            session, type_="price_change", product_id=product.id, qty_delta=0, payload=payload
        )
    if changed_non_price:
        record_operation(
            session,
            type_="product_edited",
            product_id=product.id,
            qty_delta=0,
            payload={"fields": changed_non_price},
        )
    return product, {}


def soft_delete_product(session: Session, product_id: str) -> None:
    """D-20 / PD-4: plain product-row write, no ledger op. Idempotent."""
    product = session.get(Product, product_id)
    if product is None or product.deleted_at is not None:
        return
    product.deleted_at = utcnow_iso()
    session.commit()


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
