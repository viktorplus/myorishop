"""Catalog service (CAT-01): create/list products, fat service (D-11).

Contract: Product-field writes live in app/services/*; Operation rows and
products.quantity writes stay ONLY in app/services/ledger.record_operation.
The catalog stages Product mutations WITHOUT committing and lets
record_operation's internal commit close the transaction atomically (D-30).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import new_id, to_cents
from app.models import Product
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
