"""Finance reports read service (FIN-08/FIN-11/FIN-12): Phase 17 is 100% read-only.

Mirrors app/services/reports.py's discipline: no operation/ledger writes
happen here, every function only ever SELECTs. Portable ORM only, no
SQLite-specific SQL (D-05 sync-readiness), matching every other service in
this codebase.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CASH_BUCKETS, CASH_CATEGORIES, CashMovement, Product


def cash_expense_total(session: Session, start_iso: str, end_iso: str) -> int:
    """Signed SUM of withdrawal+return cash rows in a UTC [start_iso, end_iso) period (FIN-11).

    D-01a: composes its category set from CASH_BUCKETS (never a hardcoded
    six-string list), so a future manual category addition is picked up
    automatically. Rows are already stored negative — net profit is a plain
    ADDITION of this value to gross profit (D-01a, never a subtraction).
    Empty period -> 0 (coalesce, never NULL).
    """
    cats = CASH_BUCKETS["withdrawal"] + CASH_BUCKETS["return"]
    return session.scalar(
        select(func.coalesce(func.sum(CashMovement.amount_cents), 0)).where(
            CashMovement.category.in_(cats),
            CashMovement.created_at >= start_iso,
            CashMovement.created_at < end_iso,
        )
    )


def stock_valuation(session: Session) -> dict:
    """Point-in-time cost/sale value of active stock (FIN-12/D-02).

    D-02: product-level valuation (batch-level cost is NOT used — Batch has
    no cost column). A NULL cost_cents/sale_cents makes the SUM term NULL,
    which SQL SUM skips (excluded, never zero-filled, D-02a) — its count is
    surfaced separately via *_unknown_count (restricted to quantity>0 rows,
    so a zero-stock product with an unset price is not a caveat worth
    flagging). Soft-deleted products (deleted_at set) are excluded from
    every sum/count. Takes NO period argument (D-02b) — always "as of now".
    """
    active = Product.deleted_at.is_(None)
    cost_value_cents = session.scalar(
        select(func.coalesce(func.sum(Product.quantity * Product.cost_cents), 0)).where(active)
    )
    sale_value_cents = session.scalar(
        select(func.coalesce(func.sum(Product.quantity * Product.sale_cents), 0)).where(active)
    )
    cost_unknown_count = session.scalar(
        select(func.count())
        .select_from(Product)
        .where(active, Product.cost_cents.is_(None), Product.quantity > 0)
    )
    sale_unknown_count = session.scalar(
        select(func.count())
        .select_from(Product)
        .where(active, Product.sale_cents.is_(None), Product.quantity > 0)
    )
    return {
        "cost_value_cents": cost_value_cents,
        "sale_value_cents": sale_value_cents,
        "cost_unknown_count": cost_unknown_count,
        "sale_unknown_count": sale_unknown_count,
    }


def cash_flow_report(session: Session, start_iso: str, end_iso: str) -> dict:
    """Income-vs-expense grouping of a UTC [start_iso, end_iso) period (FIN-08).

    Each CASH_CATEGORIES key present in the period becomes exactly one row,
    placed in income (CASH_BUCKETS["sale"] + CASH_BUCKETS["deposit"]) XOR
    expense (CASH_BUCKETS["withdrawal"] + CASH_BUCKETS["return"]) via
    server-side bucket membership — never a hardcoded category-string
    comparison. Rows are emitted in CASH_CATEGORIES key order so the report
    is stable across calls. movement_count counts only rows actually placed
    in a bucket (len(income) + len(expense)), so a category outside both
    bucket sets can never be silently double-dropped-yet-counted.

    RECONCILIATION (D-05, hard invariant): expense_total_cents for a period
    MUST equal cash_expense_total(session, start_iso, end_iso) for the same
    bounds — the cash-flow report and the net-profit tile can never disagree.
    """
    income_cats = CASH_BUCKETS["sale"] + CASH_BUCKETS["deposit"]
    expense_cats = CASH_BUCKETS["withdrawal"] + CASH_BUCKETS["return"]

    rows = session.execute(
        select(CashMovement.category, func.sum(CashMovement.amount_cents))
        .where(
            CashMovement.created_at >= start_iso,
            CashMovement.created_at < end_iso,
        )
        .group_by(CashMovement.category)
    ).all()
    totals_by_category = dict(rows)

    income: list[dict] = []
    expense: list[dict] = []
    for category in CASH_CATEGORIES:
        if category not in totals_by_category:
            continue
        entry = {"category": category, "total_cents": totals_by_category[category]}
        if category in income_cats:
            income.append(entry)
        elif category in expense_cats:
            expense.append(entry)

    return {
        "income": income,
        "income_total_cents": sum(entry["total_cents"] for entry in income),
        "expense": expense,
        "expense_total_cents": sum(entry["total_cents"] for entry in expense),
        "movement_count": len(income) + len(expense),
    }
