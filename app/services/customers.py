"""Customer service (CST-01/02): CRUD, Cyrillic-safe search, purchase history.

A2: no unique constraint on Customer — duplicates are allowed (walk-in
quick-create tolerance), so no IntegrityError guard is needed on writes.
search_lc is a Cyrillic-safe shadow of "name surname consultant", maintained
by this service via Python str.lower() — SQLite lower()/LIKE cannot fold
Cyrillic (mirrors Product.name_lc / catalog.search_products, D-27).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import new_id
from app.models import Customer, Operation, Product, Sale
from app.services.catalog import split_match

NAME_REQUIRED_ERROR = "Укажите имя покупателя."


def _search_lc(name: str, surname: str | None, consultant_number: str | None) -> str:
    return " ".join(p for p in (name, surname, consultant_number) if p).strip().lower()


def create_customer(
    session: Session,
    *,
    name: str,
    surname: str,
    consultant_number: str,
) -> tuple[Customer | None, dict[str, str]]:
    """Create a customer; returns (customer, {}) or (None, RU errors)."""
    errors: dict[str, str] = {}
    name = name.strip()
    surname = surname.strip()
    consultant_number = consultant_number.strip()

    if not name:
        errors["name"] = NAME_REQUIRED_ERROR
        return None, errors

    customer = Customer(
        id=new_id(),
        name=name,
        surname=surname or None,
        consultant_number=consultant_number or None,
    )
    customer.search_lc = _search_lc(name, surname, consultant_number)
    session.add(customer)
    session.commit()
    return customer, {}


def update_customer(
    session: Session,
    customer_id: str,
    *,
    name: str,
    surname: str,
    consultant_number: str,
) -> tuple[Customer | None, dict[str, str]]:
    """Update a customer's fields and refresh search_lc."""
    customer = session.get(Customer, customer_id)
    if customer is None:
        return None, {"customer": "Покупатель не найден."}

    errors: dict[str, str] = {}
    name = name.strip()
    surname = surname.strip()
    consultant_number = consultant_number.strip()

    if not name:
        errors["name"] = NAME_REQUIRED_ERROR
        return None, errors

    customer.name = name
    customer.surname = surname or None
    customer.consultant_number = consultant_number or None
    customer.search_lc = _search_lc(name, surname, consultant_number)
    session.commit()
    return customer, {}


def get_customer(session: Session, customer_id: str) -> Customer | None:
    """Plain lookup; returns None for an unknown id."""
    return session.get(Customer, customer_id)


def search_customers(session: Session, q: str) -> list[Customer]:
    """Ranked-free, capped, Cyrillic-safe customer search (CST-01).

    D-27 mirror: the query is lowered in PYTHON and compared against the
    search_lc shadow — SQLite lower()/LIKE fold ASCII only.
    """
    q_lc = q.strip().lower()
    stmt = select(Customer)
    if q_lc:
        stmt = stmt.where(Customer.search_lc.contains(q_lc, autoescape=True))
    stmt = stmt.order_by(Customer.search_lc).limit(20)
    return list(session.scalars(stmt))


def customer_search_view(session: Session, q: str) -> dict:
    """Shared context for the list page AND the search partial (mirrors catalog.search_view)."""
    q_lc = q.strip().lower()
    rows = [
        {
            "customer": customer,
            "name_seg": split_match(f"{customer.name} {customer.surname or ''}".strip(), q_lc),
            "consultant_seg": split_match(customer.consultant_number or "", q_lc),
        }
        for customer in search_customers(session, q)
    ]
    return {"q": q, "rows": rows}


def purchase_history(session: Session, customer_id: str) -> list[dict]:
    """Sale ops for one customer joined to their products, newest first (CST-02).

    Reads the FROZEN op.unit_price_cents — never the current Product price.
    """
    rows = session.execute(
        select(Operation, Product)
        .join(Sale, Operation.sale_id == Sale.id)
        .join(Product, Operation.product_id == Product.id)
        .where(Sale.customer_id == customer_id, Operation.type == "sale")
        .order_by(Operation.created_at.desc(), Operation.seq.desc())
    ).all()
    return [{"op": op, "product": product} for op, product in rows]
