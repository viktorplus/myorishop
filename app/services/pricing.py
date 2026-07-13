"""Catalog price lookups (CAT-05): read-only helpers over catalog_prices.

The table holds the full per-catalog price history imported from the xlsx
price lists. These helpers surface the latest known price for a code (used to
autofill a new product's catalog/purchase price) and the full history.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CatalogPrice


def latest_price_for_code(session: Session, code: str) -> CatalogPrice | None:
    """Most recent catalog price for a code (newest catalog first).

    "Newest" = highest (year, number). Only rows carrying a consumer price
    are considered, so the returned row always has consumer_cents set.
    Returns None when the code appears in no imported catalog.
    """
    code = (code or "").strip()
    if not code:
        return None
    return session.scalars(
        select(CatalogPrice)
        .where(
            CatalogPrice.code == code,
            CatalogPrice.consumer_cents.is_not(None),
        )
        .order_by(CatalogPrice.year.desc(), CatalogPrice.number.desc())
        .limit(1)
    ).first()


def price_history_for_code(session: Session, code: str) -> list[CatalogPrice]:
    """All catalog prices for a code, newest catalog first (product card view)."""
    code = (code or "").strip()
    if not code:
        return []
    return list(
        session.scalars(
            select(CatalogPrice)
            .where(CatalogPrice.code == code)
            .order_by(CatalogPrice.year.desc(), CatalogPrice.number.desc())
        )
    )


def prices_for_catalog(session: Session, year: int, number: int) -> dict[str, CatalogPrice]:
    """Map code -> price row for one catalog issue (catalog detail view)."""
    rows = session.scalars(
        select(CatalogPrice).where(CatalogPrice.year == year, CatalogPrice.number == number)
    )
    return {row.code: row for row in rows}
