"""Stock report read service (RPT-02): current stock + low-stock action list.

Read-only — no writes happen here. `Product.quantity` is already the
authoritative cached projection (D-09), so this module does no ledger
recomputation; the only real logic is the effective-threshold fallback
(D-04/D-05): a product's own `low_stock_threshold` wins when set, even when
it is explicitly `0` — Pitfall 3 is a bare "or" silently treating that `0`
as falsy and wrongly falling through to the global default. Portable ORM
only, no SQLite-specific SQL (D-05 sync-readiness).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Product


def effective_low_stock_threshold(product: Product) -> int:
    """Product's own threshold if set (even 0), else the global default."""
    return (
        product.low_stock_threshold
        if product.low_stock_threshold is not None
        else settings.low_stock_threshold
    )


def low_stock_products(session: Session) -> list[Product]:
    """Active products at or below their effective threshold, most urgent first."""
    products = list(
        session.scalars(select(Product).where(Product.deleted_at.is_(None))).all()
    )
    low = [p for p in products if p.quantity <= effective_low_stock_threshold(p)]
    low.sort(key=lambda p: p.quantity)
    return low


def all_active_products(session: Session) -> list[Product]:
    """Every non-deleted product, ordered by name_lc, for the full stock table."""
    return list(
        session.scalars(
            select(Product).where(Product.deleted_at.is_(None)).order_by(Product.name_lc)
        ).all()
    )
