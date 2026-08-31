"""Storage-place read view (todo 2026-08-31): where each batch physically lies.

Read-only — no writes happen here. The place is NOT a new column: the operator
already records it per batch, so this module derives it (`batch_place`) from
the existing `Batch.location` (the WH-02 free-text tag filled by the receipt
form) with a fallback to `Batch.comment` (LOT-04) — the field the warehouse
inventory of 2026-08-31 actually used («полка 59»). Batches with neither read
as UNKNOWN_PLACE rather than disappearing: a batch with stock is physically
somewhere, and hiding it would make the page lie about the warehouse.

Only open batches (quantity > 0) are listed — an emptied batch holds nothing
and its place is meaningless. Small cardinality (one row per open batch),
so filtering/sorting is Python-side after one query, then the shared
pagination slicer, exactly like catalog.list_products_view.

D-27: the search query is lowered in PYTHON and compared against `name_lc` —
SQLite lower()/LIKE fold ASCII only, so Cyrillic never round-trips through
SQL lower(). Portable ORM only, no SQLite-specific SQL (D-05).
"""

import re
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Batch, Product, Warehouse
from app.services.pagination import LIST_PAGE_SIZE

UNKNOWN_PLACE = "Место не указано"

# Splits a place label into text/number runs so «полка 5» sorts before
# «полка 39» (plain string order puts "39" first). re.split with ONE capture
# group alternates strictly: even indices are text, odd indices are digits —
# so two keys never compare an int against a str at the same position.
_DIGITS = re.compile(r"(\d+)")


def batch_place(batch: Batch) -> str:
    """The batch's storage place: `location`, else `comment`, else UNKNOWN_PLACE."""
    return (batch.location or "").strip() or (batch.comment or "").strip() or UNKNOWN_PLACE


def place_sort_key(place: str) -> tuple:
    """Natural order («полка 5» < «полка 39»); UNKNOWN_PLACE always last."""
    parts = _DIGITS.split(place)
    return (place == UNKNOWN_PLACE, [int(p) if p.isdigit() else p.lower() for p in parts])


def _open_rows(session: Session) -> list[dict]:
    """Every open batch joined to its product and warehouse, place resolved."""
    rows = session.execute(
        select(Batch, Product, Warehouse)
        .join(Product, Batch.product_id == Product.id)
        .join(Warehouse, Batch.warehouse_id == Warehouse.id)
        .where(Batch.quantity > 0)
    ).all()
    return [{"batch": b, "product": p, "warehouse": w, "place": batch_place(b)} for b, p, w in rows]


def place_summary(rows: list[dict]) -> list[dict]:
    """Places with their batch/piece counts, natural order, unknown last."""
    totals: dict[str, dict] = defaultdict(lambda: {"batches": 0, "quantity": 0})
    for row in rows:
        entry = totals[row["place"]]
        entry["batches"] += 1
        entry["quantity"] += row["batch"].quantity
    return [
        {"place": place, **entry}
        for place, entry in sorted(totals.items(), key=lambda kv: place_sort_key(kv[0]))
    ]


def list_locations_view(session: Session, *, q: str = "", place: str = "", page: int = 0) -> dict:
    """Two views behind one URL, chosen by whether anything is asked for.

    No query and no place -> `mode="places"`: the warehouse map, one row per
    place, which doubles as the navigation to a single shelf. With a query
    and/or a place -> `mode="rows"`: the matching batches themselves, so
    "где лежит 35532?" is answered by typing the code.

    A place filter is an EXACT match (its value comes from the page's own
    place list), while the query is a substring of the code or the name.
    """
    rows = _open_rows(session)
    places = place_summary(rows)

    place_q = place.strip()
    if place_q:
        rows = [r for r in rows if r["place"] == place_q]
    q_lc = q.strip().lower()  # Python folds Cyrillic; SQL lower() cannot
    if q_lc:
        rows = [
            r
            for r in rows
            if q_lc in (r["product"].name_lc or r["product"].name.lower())
            or q_lc in (r["product"].code or "").lower()
        ]

    mode = "rows" if (q_lc or place_q) else "places"
    if mode == "rows":
        rows.sort(
            key=lambda r: (
                place_sort_key(r["place"]),
                r["product"].name_lc or r["product"].name.lower(),
                r["batch"].expiry or "",
            )
        )
        listing: list = rows
    else:
        listing = places

    total = len(listing)
    total_pages = max(1, -(-total // LIST_PAGE_SIZE))
    # Clamp BEFORE returning `page`: an out-of-range page must report the page
    # it actually rendered, or the pagination bar highlights a page nobody sees.
    page = max(0, min(page, total_pages - 1))
    start = page * LIST_PAGE_SIZE
    return {
        "mode": mode,
        "rows": listing[start : start + LIST_PAGE_SIZE] if mode == "rows" else [],
        "places_page": listing[start : start + LIST_PAGE_SIZE] if mode == "places" else [],
        "places": places,
        "q": q,
        "place": place_q,
        "page": page,
        "total": total,
        "total_pages": total_pages,
    }
