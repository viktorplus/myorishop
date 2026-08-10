"""Finance reports read service (FIN-08/FIN-11/FIN-12): Phase 17 is 100% read-only.

Mirrors app/services/reports.py's discipline: no operation/ledger writes
happen here, every function only ever SELECTs. Portable ORM only, no
SQLite-specific SQL (D-05 sync-readiness), matching every other service in
this codebase.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import DEFAULT_CURRENCY
from app.models import CASH_BUCKETS, CASH_CATEGORIES, Batch, CashMovement, Product, Warehouse


def cash_expense_total(
    session: Session, start_iso: str, end_iso: str, currency: str = DEFAULT_CURRENCY
) -> int:
    """Signed SUM of withdrawal+return cash rows in a UTC [start_iso, end_iso) period (FIN-11).

    D-01a: composes its category set from CASH_BUCKETS (never a hardcoded
    six-string list), so a future manual category addition is picked up
    automatically. Rows are already stored negative — net profit is a plain
    ADDITION of this value to gross profit (D-01a, never a subtraction).
    Empty period -> 0 (coalesce, never NULL). CUR-02: `currency` scopes the
    sum to ONE currency's rows, defaulting to RUB so every pre-existing call
    site keeps working unchanged.
    """
    cats = CASH_BUCKETS["withdrawal"] + CASH_BUCKETS["return"]
    return session.scalar(
        select(func.coalesce(func.sum(CashMovement.amount_cents), 0)).where(
            CashMovement.category.in_(cats),
            CashMovement.created_at >= start_iso,
            CashMovement.created_at < end_iso,
            CashMovement.currency == currency,
        )
    )


def stock_valuation(session: Session, currency: str = DEFAULT_CURRENCY) -> dict:
    """Point-in-time cost/sale value of active stock, scoped to ONE currency (FIN-12/D-02/CUR-02).

    Rewritten from product-level to a Batch-level, currency-scoped
    aggregation: Batch always has a NOT-NULL warehouse_id, so no NULL-currency
    bucket is needed (unlike Operation, see reports.sales_profit_report). Joins
    Batch to Product (active only) and to Warehouse (Warehouse.currency ==
    currency), restricted to Batch.quantity > 0.
    cost_value_cents = SUM(Batch.quantity * COALESCE(Batch.cost_cents,
    Product.cost_cents)) — a batch's own cost snapshot wins, falling back to
    the product card when unset. sale_value_cents prefers Batch.price_cents
    (the existing per-batch sale-price snapshot, D-02 in receipts.py) over
    Product.sale_cents — a deliberate upgrade to the more precise per-lot
    figure, made possible by this batch-level join already existing for the
    currency scoping. A NULL COALESCE result makes the SUM term NULL, which
    SQL SUM skips (excluded, never zero-filled, D-02a); its count is surfaced
    separately via *_unknown_count, counting DISTINCT products (mirrors the
    old product-level semantics) under the same quantity>0 + active-product +
    currency scope. Returned dict key names are unchanged — callers
    (dashboard.py) are unaffected by this rewrite. Takes NO period argument
    (D-02b) — always "as of now".
    """
    active = Product.deleted_at.is_(None)
    scope = (Batch.quantity > 0, active, Warehouse.currency == currency)
    cost_expr = func.coalesce(Batch.cost_cents, Product.cost_cents)
    sale_expr = func.coalesce(Batch.price_cents, Product.sale_cents)

    base = (
        select(Batch)
        .join(Product, Batch.product_id == Product.id)
        .join(Warehouse, Batch.warehouse_id == Warehouse.id)
    )
    cost_value_cents = session.scalar(
        base.with_only_columns(func.coalesce(func.sum(Batch.quantity * cost_expr), 0)).where(
            *scope
        )
    )
    sale_value_cents = session.scalar(
        base.with_only_columns(func.coalesce(func.sum(Batch.quantity * sale_expr), 0)).where(
            *scope
        )
    )
    cost_unknown_count = session.scalar(
        base.with_only_columns(func.count(func.distinct(Batch.product_id))).where(
            *scope, cost_expr.is_(None)
        )
    )
    sale_unknown_count = session.scalar(
        base.with_only_columns(func.count(func.distinct(Batch.product_id))).where(
            *scope, sale_expr.is_(None)
        )
    )
    return {
        "cost_value_cents": cost_value_cents,
        "sale_value_cents": sale_value_cents,
        "cost_unknown_count": cost_unknown_count,
        "sale_unknown_count": sale_unknown_count,
    }


def cash_flow_report(
    session: Session, start_iso: str, end_iso: str, currency: str = DEFAULT_CURRENCY
) -> dict:
    """Income-vs-expense grouping of a UTC [start_iso, end_iso) period (FIN-08).

    Each CASH_CATEGORIES key present in the period becomes exactly one row,
    placed in income (CASH_BUCKETS["sale"] + CASH_BUCKETS["deposit"]) XOR
    expense (CASH_BUCKETS["withdrawal"] + CASH_BUCKETS["return"]) via
    server-side bucket membership — never a hardcoded category-string
    comparison. Rows are emitted in CASH_CATEGORIES key order so the report
    is stable across calls. movement_count counts only rows actually placed
    in a bucket (len(income) + len(expense)), so a category outside both
    bucket sets can never be silently double-dropped-yet-counted. CUR-02:
    `currency` scopes the whole report to ONE currency's rows.

    RECONCILIATION (D-05, hard invariant): expense_total_cents for a period
    MUST equal cash_expense_total(session, start_iso, end_iso, currency) for
    the same bounds — the cash-flow report and the net-profit tile can never
    disagree.
    """
    income_cats = CASH_BUCKETS["sale"] + CASH_BUCKETS["deposit"]
    expense_cats = CASH_BUCKETS["withdrawal"] + CASH_BUCKETS["return"]

    rows = session.execute(
        select(CashMovement.category, func.sum(CashMovement.amount_cents))
        .where(
            CashMovement.created_at >= start_iso,
            CashMovement.created_at < end_iso,
            CashMovement.currency == currency,
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
