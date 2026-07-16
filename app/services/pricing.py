"""Catalog price lookups (CAT-05): read-only helpers over catalog_prices.

D-09: one row per code = that code's LAST catalog appearance, not a
multi-catalog price history (the table holds 6856 rows for 6856 codes —
see 18-RESEARCH.md State of the Art). These helpers surface the latest
known price for a code (used to autofill a new product's catalog/purchase
price) and the full history.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CatalogPrice


def latest_price_for_code(session: Session, code: str) -> CatalogPrice | None:
    """Most recent catalog price for a code (newest catalog first).

    "Newest" = highest (year, number). Returns None when the code appears
    in no imported catalog. D-08/D-22: no longer filters on consumer_cents —
    a consultant-only row (ДЦ present, ПЦ NULL) is returned like any other,
    instead of being silently starved.
    """
    code = (code or "").strip()
    if not code:
        return None
    return session.scalars(
        select(CatalogPrice)
        .where(CatalogPrice.code == code)
        .order_by(CatalogPrice.year.desc(), CatalogPrice.number.desc())
        .limit(1)
    ).first()


def reference_prices_for_code(session: Session, code: str) -> tuple[int | None, int | None]:
    """(ДЦ, ПЦ) reference prices for a code, independently of one another.

    D-05: consultant_cents pairs to ДЦ, consumer_cents pairs to ПЦ.
    D-08/D-22: ДЦ is never gated on ПЦ's presence — a consultant-only row
    still yields its ДЦ. D-07: an unknown code returns (None, None) as a
    first-class result, not an error (the MAIN path for most live products).
    """
    row = latest_price_for_code(session, code)
    if row is None:
        return (None, None)
    return (row.consultant_cents, row.consumer_cents)


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
