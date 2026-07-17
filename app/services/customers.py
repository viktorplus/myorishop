"""Customer service (CST-01/02): CRUD, Cyrillic-safe search, purchase history.

A2: no unique constraint on Customer — duplicates are allowed (walk-in
quick-create tolerance), so no IntegrityError guard is needed on writes.
search_lc is a Cyrillic-safe shadow of "name surname consultant", maintained
by this service via Python str.lower() — SQLite lower()/LIKE cannot fold
Cyrillic (mirrors Product.name_lc / catalog.search_products, D-27).
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core import new_id
from app.models import CONTACT_KINDS, Customer, CustomerContact, Operation, Product, Sale
from app.services.catalog import split_match
from app.services.pagination import paginate

NAME_REQUIRED_ERROR = "Укажите имя покупателя."
NAME_TOO_LONG_ERROR = "Слишком длинное имя."
SURNAME_TOO_LONG_ERROR = "Слишком длинная фамилия."
CONSULTANT_NUMBER_TOO_LONG_ERROR = "Слишком длинный номер консультанта."
# Phase 21 (D-02/CUST-05): copy taken verbatim from 21-UI-SPEC.md.
ADDRESS_TOO_LONG_ERROR = "Адрес слишком длинный — не больше 300 символов."
# Phase 21 (D-01/CUST-01..04): copy taken verbatim from 21-UI-SPEC.md.
CONTACT_VALUE_TOO_LONG_ERROR = "Значение слишком длинное — не больше 300 символов."

# WR-05: mirror the declared column lengths (app/models.py Customer) here so
# an overlong value is rejected in the service layer instead of silently
# truncated by SQLite today and hard-erroring after a future PostgreSQL
# migration (CLAUDE.md: "same models will run on PostgreSQL later").
# Phase 21: _ADDRESS_MAX_LEN mirrors Customer.address's declared String(300).
# _CONTACT_VALUE_MAX_LEN mirrors CustomerContact.value's declared String(300).
_NAME_MAX_LEN = 200
_SURNAME_MAX_LEN = 200
_CONSULTANT_NUMBER_MAX_LEN = 50
_ADDRESS_MAX_LEN = 300
_CONTACT_VALUE_MAX_LEN = 300


def _search_lc(name: str, surname: str | None, consultant_number: str | None) -> str:
    return " ".join(p for p in (name, surname, consultant_number) if p).strip().lower()


def _validate_lengths(
    name: str, surname: str, consultant_number: str, address: str, errors: dict[str, str]
) -> None:
    """WR-05: shared max-length guard for create_customer/update_customer."""
    if len(name) > _NAME_MAX_LEN:
        errors["name"] = NAME_TOO_LONG_ERROR
    if len(surname) > _SURNAME_MAX_LEN:
        errors["surname"] = SURNAME_TOO_LONG_ERROR
    if len(consultant_number) > _CONSULTANT_NUMBER_MAX_LEN:
        errors["consultant_number"] = CONSULTANT_NUMBER_TOO_LONG_ERROR
    if len(address) > _ADDRESS_MAX_LEN:
        errors["address"] = ADDRESS_TOO_LONG_ERROR


def _validate_contacts(contacts: dict[str, list[str]], errors: dict[str, str]) -> None:
    """Validate a full `contacts` payload BEFORE any write (T-21-09, T-21-04).

    An unknown kind is NOT operator-reachable — the route binds four fixed
    Form params, so it is a programmer error, not a form error. Raises
    ValueError, matching record_operation's treatment of an unknown
    operation type (ledger.py:74-75). Blank values are discarded silently
    (never an error) — UI-SPEC Interaction 6's always-present blank row
    depends on this. Errors are keyed by kind, not row index, matching the
    UI-SPEC's one-{% if errors.KIND %}-per-section markup.
    """
    for kind, values in contacts.items():
        if kind not in CONTACT_KINDS:
            raise ValueError(f"unknown contact kind: {kind!r}")
        for value in values:
            value = value.strip()
            if not value:
                continue
            if len(value) > _CONTACT_VALUE_MAX_LEN:
                errors[kind] = CONTACT_VALUE_TOO_LONG_ERROR


def _replace_contacts(session: Session, customer_id: str, contacts: dict[str, list[str]]) -> None:
    """Delete-all-then-reinsert (D-01): full replace, never append.

    commit=False semantics — never commits; the caller owns the single
    create_customer/update_customer transaction. Legal because
    customer_contacts is an ordinary mutable table (APPEND_ONLY_TRIGGERS
    cover only operations/cash_movements, app/db.py). label is always None
    this phase — the column ships unused (Plan 01, RESEARCH Open Question 1).

    created_at is stamped explicitly with a monotonically increasing
    microsecond offset (rather than the column's utcnow_iso() default, which
    has one-second resolution) so contacts_by_kind's `ORDER BY (created_at,
    id)` preserves the caller's submitted order even when every row of one
    replace lands in the same second — id (a random UUID4) is not a
    submission-order tie-break on its own.
    """
    session.execute(delete(CustomerContact).where(CustomerContact.customer_id == customer_id))
    base = datetime.now(UTC)
    offset = 0
    for kind, values in contacts.items():
        for value in values:
            value = value.strip()
            if not value:
                continue
            session.add(
                CustomerContact(
                    id=new_id(),
                    customer_id=customer_id,
                    kind=kind,
                    value=value,
                    label=None,
                    created_at=(base + timedelta(microseconds=offset)).isoformat(),
                )
            )
            offset += 1


def create_customer(
    session: Session,
    *,
    name: str,
    surname: str,
    consultant_number: str,
    address: str = "",
    contacts: dict[str, list[str]] | None = None,
) -> tuple[Customer | None, dict[str, str]]:
    """Create a customer; returns (customer, {}) or (None, RU errors).

    address (D-02/CUST-05) defaults to "" so app/routes/sales.py's quick-create
    call (the sale form's inline new-customer flow) keeps working unchanged.

    contacts (D-01/CUST-01..04) is a two-state contract:
    - None (default) -> no contacts are written. This is what keeps
      app/routes/sales.py:355's quick-create call working unchanged.
    - a dict -> full replace: every non-blank value in the dict is inserted
      as a CustomerContact row. A dict that omits a CONTACT_KINDS key simply
      inserts nothing for that kind (there is nothing to replace yet on
      create). The form (Plan 04) always posts all four keys.
    """
    errors: dict[str, str] = {}
    name = name.strip()
    surname = surname.strip()
    consultant_number = consultant_number.strip()
    address = address.strip()

    if not name:
        errors["name"] = NAME_REQUIRED_ERROR
        return None, errors

    _validate_lengths(name, surname, consultant_number, address, errors)
    if contacts is not None:
        _validate_contacts(contacts, errors)
    if errors:
        return None, errors

    customer = Customer(
        id=new_id(),
        name=name,
        surname=surname or None,
        consultant_number=consultant_number or None,
        address=address or None,
    )
    customer.search_lc = _search_lc(name, surname, consultant_number)
    session.add(customer)
    if contacts is not None:
        # PRAGMA foreign_keys=ON is active: the parent row must exist before
        # inserting children, so flush before _replace_contacts.
        session.flush()
        _replace_contacts(session, customer.id, contacts)
    session.commit()
    return customer, {}


def update_customer(
    session: Session,
    customer_id: str,
    *,
    name: str,
    surname: str,
    consultant_number: str,
    address: str = "",
    contacts: dict[str, list[str]] | None = None,
) -> tuple[Customer | None, dict[str, str]]:
    """Update a customer's fields and refresh search_lc.

    address (D-02/CUST-05) defaults to "" — see create_customer's docstring
    for why the default is load-bearing.

    contacts (D-01/CUST-01..04) is the same two-state contract as
    create_customer: None leaves existing contacts untouched; a dict fully
    replaces them (a dict that omits a kind clears that kind).
    """
    customer = session.get(Customer, customer_id)
    if customer is None:
        return None, {"customer": "Покупатель не найден."}

    errors: dict[str, str] = {}
    name = name.strip()
    surname = surname.strip()
    consultant_number = consultant_number.strip()
    address = address.strip()

    if not name:
        errors["name"] = NAME_REQUIRED_ERROR
        return None, errors

    _validate_lengths(name, surname, consultant_number, address, errors)
    if contacts is not None:
        _validate_contacts(contacts, errors)
    if errors:
        return None, errors

    customer.name = name
    customer.surname = surname or None
    customer.consultant_number = consultant_number or None
    customer.address = address or None
    customer.search_lc = _search_lc(name, surname, consultant_number)
    if contacts is not None:
        _replace_contacts(session, customer.id, contacts)
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


def contacts_by_kind(session: Session, customer_id: str) -> dict[str, list[CustomerContact]]:
    """All CustomerContact rows for one customer, bucketed by kind (CUST-01..04).

    Every CONTACT_KINDS key is always present, mapping to a possibly-empty
    list, in CONTACT_KINDS order (phone, telegram, email, social) — the form
    (Plan 04) renders one blank row for an empty kind, the detail page
    (Plan 05) omits an empty kind; neither should have to guard for a
    missing key. Within each kind rows are ordered by (created_at, id):
    created_at alone is not sufficient because utcnow_iso() has one-second
    resolution and a full-replace inserts every row of a save inside the
    same second, so id is the stable tie-break.

    One query, not one per kind (no relationship()/lazy loader here, so
    keeping it flat is entirely on this function — the N+1 shape this
    codebase avoids elsewhere).
    """
    rows = session.scalars(
        select(CustomerContact)
        .where(CustomerContact.customer_id == customer_id)
        .order_by(CustomerContact.created_at, CustomerContact.id)
    ).all()

    buckets: dict[str, list[CustomerContact]] = {kind: [] for kind in CONTACT_KINDS}
    for row in rows:
        buckets[row.kind].append(row)
    return buckets


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
