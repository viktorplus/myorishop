"""Reports read service (RPT-01/RPT-03/RPT-04): Phase 6 is 100% read-only.

No operation types are added here and no ledger writes happen here — every
function in this module only ever SELECTs. Portable ORM only, no
SQLite-specific SQL (D-05 sync-readiness), matching every other service in
this codebase.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Operation, Product


def sales_profit_report(session: Session, start_iso: str, end_iso: str) -> dict:
    """Sales/profit totals and per-product breakdown for a UTC [start_iso, end_iso) period.

    RESEARCH Pitfall 2: unit_cost_cents is nullable — a sale line whose cost
    was never entered contributes its full revenue to totals["revenue_cents"]
    but is EXCLUDED from cost_cents/profit_cents (never treated as
    zero-cost, which would silently inflate profit by the line's whole
    revenue). Its count is surfaced separately as cost_unknown_count so the
    caller can show a visible caveat instead of a silently wrong number.

    RESEARCH Pitfall 5: this report is historical — it deliberately does
    NOT filter Product.deleted_at, so a product soft-deleted after the
    period still appears in a report for a period before its deletion.
    """
    rows = session.execute(
        select(Operation, Product)
        .join(Product, Operation.product_id == Product.id)
        .where(
            Operation.type == "sale",
            Operation.created_at >= start_iso,
            Operation.created_at < end_iso,
        )
    ).all()

    entries: dict[str, dict] = {}
    cost_unknown_count = 0
    for op, product in rows:
        qty = -op.qty_delta
        entry = entries.setdefault(
            product.id,
            {
                "product": product,
                "qty": 0,
                "revenue_cents": 0,
                "cost_cents": 0,
                "profit_cents": 0,
            },
        )
        entry["qty"] += qty
        revenue = (op.unit_price_cents or 0) * qty
        entry["revenue_cents"] += revenue
        if op.unit_cost_cents is not None:
            cost = op.unit_cost_cents * qty
            entry["cost_cents"] += cost
            entry["profit_cents"] += revenue - cost
        else:
            cost_unknown_count += 1

    by_product = sorted(entries.values(), key=lambda e: e["qty"], reverse=True)

    totals = {
        "units_sold": sum(e["qty"] for e in by_product),
        "revenue_cents": sum(e["revenue_cents"] for e in by_product),
        "cost_cents": sum(e["cost_cents"] for e in by_product),
        "profit_cents": sum(e["profit_cents"] for e in by_product),
        "cost_unknown_count": cost_unknown_count,
    }

    return {
        "totals": totals,
        "by_product": by_product,
        "cost_unknown_count": cost_unknown_count,
    }
