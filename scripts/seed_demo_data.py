"""Fill the local database with demo data for manual testing (UAT).

Run: uv run python scripts/seed_demo_data.py [--force]

Writes go through the normal service layer (register_receipt,
register_sale, create_customer, dictionary.add_entry) so the append-only
ledger and stock projection stay consistent - this is not a raw SQL dump.

Pair with scripts/reset_demo_data.py to wipe the database back to empty
before seeding again (products/customers have no delete path once sold
against, so re-running this script on top of existing data just adds
more rows instead of resetting them).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SessionLocal  # noqa: E402
from app.services import customers as customers_service  # noqa: E402
from app.services import dictionary as dictionary_service  # noqa: E402
from app.services import receipts as receipts_service  # noqa: E402
from app.services import sales as sales_service  # noqa: E402

# code, name, category, cost, sale, catalog, qty
PRODUCTS = [
    (
        "32021",
        "Тушь для ресниц The One Wonder Lash",
        "Декоративная косметика",
        "450.00",
        "690.00",
        "890.00",
        "15",
    ),
    (
        "31670",
        "Крем для лица Optimals Increase",
        "Уход за лицом",
        "380.00",
        "590.00",
        "750.00",
        "8",
    ),
    ("42125", "Дезодорант-спрей North for Him", "Парфюмерия", "210.00", "350.00", "420.00", "20"),
    ("33456", "Шампунь Nature Secrets", "Уход за волосами", "260.00", "420.00", "490.00", "12"),
    (
        "50012",
        "Гель для душа Milk & Honey Gold",
        "Уход за телом",
        "300.00",
        "480.00",
        "560.00",
        "5",
    ),
]

# code -> name only, never purchased (demonstrates the reference dictionary)
DICTIONARY_ENTRIES = [
    ("60001", "Помада Giordani Gold"),
    ("60002", "Тональный крем Even Out"),
]

# name, surname, consultant_number
CUSTOMERS = [
    ("Анна", "Иванова", "RU1023456"),
    ("Мария", "Петрова", "RU2045678"),
    ("Ольга", "", ""),
]

# customer index (None = walk-in), [(code, qty, price), ...]
SALES = [
    (0, [("32021", "2", "690.00"), ("42125", "1", "350.00")]),
    (1, [("31670", "1", "590.00")]),
    (None, [("33456", "3", "420.00")]),
]


def main() -> None:
    force = "--force" in sys.argv
    with SessionLocal() as session:
        existing = receipts_service.recent_receipts(session, limit=1)
        if existing and not force:
            print(
                "Database already has data. Run scripts/reset_demo_data.py first, "
                "or pass --force to seed on top of it anyway."
            )
            raise SystemExit(1)

        print("Seeding products via receipts...")
        for code, name, category, cost, sale, catalog, qty in PRODUCTS:
            result, errors = receipts_service.register_receipt(
                session,
                code=code,
                name=name,
                qty_raw=qty,
                cost_raw=cost,
                sale_raw=sale,
                catalog_raw=catalog,
            )
            if errors:
                print(f"  ! {code} {name}: {errors}")
                continue
            product = result["product"]
            product.category = category
            session.commit()
            print(f"  + {code} {name} (qty={qty})")

        print("Seeding dictionary entries...")
        for code, name in DICTIONARY_ENTRIES:
            _, errors = dictionary_service.add_entry(session, code=code, name=name)
            if errors:
                print(f"  ! {code} {name}: {errors}")
                continue
            print(f"  + {code} {name}")

        print("Seeding customers...")
        customer_ids = []
        for name, surname, consultant_number in CUSTOMERS:
            customer, errors = customers_service.create_customer(
                session, name=name, surname=surname, consultant_number=consultant_number
            )
            if errors:
                print(f"  ! {name}: {errors}")
                customer_ids.append(None)
                continue
            customer_ids.append(customer.id)
            print(f"  + {name} {surname}".rstrip())

        print("Seeding sales...")
        for customer_idx, lines in SALES:
            customer_id = customer_ids[customer_idx] if customer_idx is not None else None
            codes = [line[0] for line in lines]
            qtys = [line[1] for line in lines]
            prices = [line[2] for line in lines]
            result, errors = sales_service.register_sale(
                session,
                customer_id=customer_id,
                codes=codes,
                qtys=qtys,
                prices=prices,
                confirm="1",  # demo data may legitimately oversell a fresh line
            )
            if errors or (result and "oversell" in result):
                print(f"  ! sale for customer_idx={customer_idx}: {errors or result}")
                continue
            who = "walk-in" if customer_id is None else CUSTOMERS[customer_idx][0]
            print(f"  + sale for {who} ({result['line_count']} line(s))")

    print("Done. Start the app and open http://127.0.0.1:8000 to see the demo data.")


if __name__ == "__main__":
    main()
