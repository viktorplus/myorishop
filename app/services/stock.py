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
from app.services.batches import scoped_quantities


def effective_low_stock_threshold(product: Product) -> int:
    """Product's own threshold if set (even 0), else the global default."""
    return (
        product.low_stock_threshold
        if product.low_stock_threshold is not None
        else settings.low_stock_threshold
    )


def low_stock_products(session: Session) -> list[Product]:
    """Active products at or below their effective threshold, most urgent first.

    Quick 261026-wha: for an operator, only products ever stocked in their
    warehouses, compared by the stock there (see batches.scoped_quantities).
    """
    products = list(
        session.scalars(select(Product).where(Product.deleted_at.is_(None))).all()
    )
    scoped = scoped_quantities(session)
    if scoped is None:
        qty = {p.id: p.quantity for p in products}
    else:
        products = [p for p in products if p.id in scoped]
        qty = scoped
    low = [p for p in products if qty[p.id] <= effective_low_stock_threshold(p)]
    low.sort(key=lambda p: qty[p.id])
    return low


def all_active_products(session: Session) -> list[Product]:
    """Every non-deleted product, ordered by name_lc, for the full stock table.

    Quick 261026-wha: for an operator, only products ever stocked in their
    warehouses.
    """
    products = list(
        session.scalars(
            select(Product).where(Product.deleted_at.is_(None)).order_by(Product.name_lc)
        ).all()
    )
    scoped = scoped_quantities(session)
    return products if scoped is None else [p for p in products if p.id in scoped]
