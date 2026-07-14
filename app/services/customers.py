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
from app.services.pagination import paginate

NAME_REQUIRED_ERROR = "Укажите имя покупателя."
NAME_TOO_LONG_ERROR = "Слишком длинное имя."
SURNAME_TOO_LONG_ERROR = "Слишком длинная фамилия."
CONSULTANT_NUMBER_TOO_LONG_ERROR = "Слишком длинный номер консультанта."

# WR-05: mirror the declared column lengths (app/models.py Customer) here so
# an overlong value is rejected in the service layer instead of silently
# truncated by SQLite today and hard-erroring after a future PostgreSQL
# migration (CLAUDE.md: "same models will run on PostgreSQL later").
_NAME_MAX_LEN = 200
_SURNAME_MAX_LEN = 200
_CONSULTANT_NUMBER_MAX_LEN = 50


def _search_lc(name: str, surname: str | None, consultant_number: str | None) -> str:
    return " ".join(p for p in (name, surname, consultant_number) if p).strip().lower()


def _validate_lengths(
    name: str, surname: str, consultant_number: str, errors: dict[str, str]
) -> None:
    """WR-05: shared max-length guard for create_customer/update_customer."""
    if len(name) > _NAME_MAX_LEN:
        errors["name"] = NAME_TOO_LONG_ERROR
    if len(surname) > _SURNAME_MAX_LEN:
        errors["surname"] = SURNAME_TOO_LONG_ERROR
    if len(consultant_number) > _CONSULTANT_NUMBER_MAX_LEN:
        errors["consultant_number"] = CONSULTANT_NUMBER_TOO_LONG_ERROR


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

    _validate_lengths(name, surname, consultant_number, errors)
    if errors:
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

    _validate_lengths(name, surname, consultant_number, errors)
    if errors:
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


# LIST-01..03: allow-list of sort keys for list_customers_view — never
# string-interpolated into a sort expression (T-14-18 mitigation).
_SORT_MAP = {
    "surname": lambda c: (c.surname or "").lower(),
    "consultant_number": lambda c: (c.consultant_number or "").lower(),
}


def list_customers_view(
    session: Session,
    *,
    name: str = "",
    surname: str = "",
    consultant_number: str = "",
    sort: str = "",
    page: int = 0,
) -> dict:
    """Filter/sort/page context for the /customers list (LIST-01..03).

    Independent per-column Python-side filters — a DIFFERENT query shape
    from search_customers/customer_search_view's combined search_lc match,
    which stay untouched for the sale-form customer picker.
    """
    name = name.strip()
    surname = surname.strip()
    consultant_number = consultant_number.strip()

    rows = list(session.scalars(select(Customer)))

    if name:
        name_lc = name.lower()
        rows = [c for c in rows if name_lc in c.name.lower()]
    if surname:
        surname_lc = surname.lower()
        rows = [c for c in rows if surname_lc in (c.surname or "").lower()]
    if consultant_number:
        consultant_lc = consultant_number.lower()
        rows = [c for c in rows if consultant_lc in (c.consultant_number or "").lower()]

    rows.sort(key=_SORT_MAP.get(sort, lambda c: c.name.lower()))

    page_rows, total, total_pages = paginate(rows, page)
    return {
        "rows": page_rows,
        "total": total,
        "total_pages": total_pages,
        "page": page,
        "name": name,
        "surname": surname,
        "consultant_number": consultant_number,
        "sort": sort,
    }


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
