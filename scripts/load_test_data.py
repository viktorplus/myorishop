"""Load a precisely-sized test dataset for manual QA (quick task 260721-fu0).

Run: uv run python scripts/load_test_data.py

Creates 10 products, 10 customers, and exactly 10 operations of EACH of the
9 OPERATION_TYPES values (90 operation rows total) — via the real
service-layer functions ONLY (register_receipt, register_sale,
register_writeoff, register_return, register_correction, register_transfer,
create_product, update_product). Never a raw ORM insert into the Operation or
CashMovement tables.

Meant to run against a just-reset (or fresh) database — refuses if any
Product already exists, so it does not need its own reset logic
(scripts/reset_business_data.py already covers that).

Pair: run scripts/reset_business_data.py first, then this script.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select  # noqa: E402

from app.core import new_id  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    OPERATION_TYPES,
    WRITEOFF_REASONS,
    Operation,
    Product,
    Warehouse,
)
from app.services.batches import active_warehouses  # noqa: E402
from app.services.catalog import create_product, update_product  # noqa: E402
from app.services.corrections import register_correction  # noqa: E402
from app.services.customers import create_customer  # noqa: E402
from app.services.receipts import register_receipt  # noqa: E402
from app.services.returns import register_return  # noqa: E402
from app.services.sales import register_sale  # noqa: E402
from app.services.transfers import register_transfer  # noqa: E402
from app.services.writeoffs import register_writeoff  # noqa: E402

NOT_EMPTY_ERROR = "База не пуста — сначала выполните scripts/reset_business_data.py."

_CATEGORIES = (
    "Декоративная косметика",
    "Уход за лицом",
    "Уход за телом",
    "Парфюмерия",
    "Уход за волосами",
)
_REASON_CODES = list(WRITEOFF_REASONS)


def _ensure_warehouse(session, name: str) -> Warehouse:
    """Create a plain active warehouse. Structural data, NOT removed by
    scripts/reset_business_data.py (which intentionally preserves every
    warehouse) — an expected, permanent side effect of this script."""
    wh = Warehouse(id=new_id(), name=name)
    session.add(wh)
    session.commit()
    return wh


def load_test_data(session) -> dict:
    """Create 10 customers + 90 operation rows (10 of each OPERATION_TYPES
    value) via the service layer only. Returns a summary dict on success, or
    `{"error": <RU message>}` with ZERO writes if the database is not empty
    (a Product already exists).
    """
    if session.scalars(select(Product)).first() is not None:
        return {"error": NOT_EMPTY_ERROR}

    # Step 1: 10 products -> 10 product_created ops.
    products = []
    for i in range(1, 11):
        product, errors = create_product(
            session,
            code=f"TD-{i:03d}",
            name=f"Тестовый товар {i}",
            category=_CATEGORIES[i % len(_CATEGORIES)],
            cost_raw="100.00",
            sale_raw="150.00",
        )
        if errors:
            raise RuntimeError(f"create_product failed for TD-{i:03d}: {errors}")
        products.append(product)

    # Step 2: 10 customers.
    customers = []
    for i in range(1, 11):
        customer, errors = create_customer(
            session,
            name=f"Клиент {i}",
            surname=f"Тестовый{i}",
            consultant_number=f"TD{i:04d}",
        )
        if errors:
            raise RuntimeError(f"create_customer failed for Клиент {i}: {errors}")
        customers.append(customer)

    # Receipts need an active warehouse; reuse one if the DB already has one
    # (a real just-reset install always does — reset_business_data.py never
    # touches warehouses), otherwise create one.
    existing_warehouses = active_warehouses(session)
    receipt_warehouse = existing_warehouses[0] if existing_warehouses else _ensure_warehouse(
        session, "Тестовый склад А"
    )

    # Step 3: 10 receipts, one per product -> 10 receipt ops. Prices match
    # the just-created card exactly, so no incidental price_change op fires.
    batch_ids: dict[str, str] = {}
    for product in products:
        result, errors = register_receipt(
            session,
            code=product.code,
            name=product.name,
            qty_raw="30",
            cost_raw="100.00",
            sale_raw="150.00",
            warehouse_id=receipt_warehouse.id,
            batch_choice="new",
        )
        if errors:
            raise RuntimeError(f"register_receipt failed for {product.code}: {errors}")
        batch_ids[product.id] = result["batch"].id

    # Step 4: 10 sales, one product per sale -> 10 sale ops.
    sale_op_ids: dict[str, str] = {}
    for product, customer in zip(products, customers, strict=True):
        result, errors = register_sale(
            session,
            customer_id=customer.id,
            codes=[product.code],
            qtys=["2"],
            prices=["150.00"],
            batch_ids=[batch_ids[product.id]],
        )
        if errors or (result and ("oversell" in result or "below_minimum" in result)):
            raise RuntimeError(f"register_sale failed for {product.code}: {errors or result}")
        sale_op = session.scalars(
            select(Operation)
            .where(
                Operation.type == "sale",
                Operation.sale_id == result["header"].id,
                Operation.product_id == product.id,
            )
            .order_by(Operation.created_at.desc(), Operation.seq.desc())
        ).first()
        sale_op_ids[product.id] = sale_op.id

    # Step 5: 10 returns, one per sale op -> 10 return ops.
    for product in products:
        _, errors = register_return(
            session, origin_op_id=sale_op_ids[product.id], qty_raw="1"
        )
        if errors:
            raise RuntimeError(f"register_return failed for {product.code}: {errors}")

    # Step 6: 10 writeoffs, one per product -> 10 writeoff ops.
    for i, product in enumerate(products):
        _, errors = register_writeoff(
            session,
            code=product.code,
            name=product.name,
            qty_raw="1",
            reason_code=_REASON_CODES[i % len(_REASON_CODES)],
            note="Тестовое списание",
            batch_id=batch_ids[product.id],
        )
        if errors:
            raise RuntimeError(f"register_writeoff failed for {product.code}: {errors}")

    # Step 7: 10 corrections, one per product -> 10 correction ops. Delta
    # mode with a nonzero positive value sidesteps needing to know the
    # current batch quantity.
    for product in products:
        _, errors = register_correction(
            session,
            code=product.code,
            mode="delta",
            value_raw="1",
            note="Тестовая корректировка",
            batch_id=batch_ids[product.id],
        )
        if errors:
            raise RuntimeError(f"register_correction failed for {product.code}: {errors}")

    # Step 8: one extra warehouse — needed as the transfer destination.
    dest_warehouse = _ensure_warehouse(session, "Тестовый склад Б")

    # Step 9: 5 transfers, one per the FIRST 5 products only -> 5 calls x 2
    # rows/call = 10 transfer ops total. Do NOT call this 10 times.
    for product in products[:5]:
        _, errors = register_transfer(
            session,
            code=product.code,
            name=product.name,
            qty_raw="2",
            batch_id=batch_ids[product.id],
            dest_warehouse_id=dest_warehouse.id,
        )
        if errors:
            raise RuntimeError(f"register_transfer failed for {product.code}: {errors}")

    # Step 10: 10 updates, one per product -> 10 product_edited + 10
    # price_change ops (name is non-price, sale_raw changes the price).
    for product in products:
        _, errors = update_product(
            session,
            product.id,
            code=product.code,
            name=f"{product.name} (изм.)",
            category=product.category,
            cost_raw="100.00",
            sale_raw="199.00",
        )
        if errors:
            raise RuntimeError(f"update_product failed for {product.code}: {errors}")

    operations_by_type = dict(
        session.execute(select(Operation.type, func.count()).group_by(Operation.type)).all()
    )
    return {
        "customers": len(customers),
        "products": len(products),
        "operations_by_type": {t: operations_by_type.get(t, 0) for t in OPERATION_TYPES},
        "extra_warehouse": dest_warehouse.name,
    }


def main() -> None:
    with SessionLocal() as session:
        summary = load_test_data(session)
        if summary.get("error"):
            print(summary["error"])
            sys.exit(1)

        print(f"Создано: {summary['customers']} клиентов")
        ops = summary["operations_by_type"]
        print("Операции: " + ", ".join(f"{t}={ops[t]}" for t in OPERATION_TYPES))
        print(
            f"Товаров: {summary['products']} "
            f'(+ 1 доп. склад «{summary["extra_warehouse"]}» для операций перемещения)'
        )


if __name__ == "__main__":
    main()
