"""Customer service (CST-01/02): CRUD, Cyrillic-safe search, purchase history.

A2: no unique constraint on Customer — duplicates are allowed (walk-in
quick-create tolerance), so no IntegrityError guard is needed on writes.
search_lc is a Cyrillic-safe shadow of "name surname consultant", maintained
by this service via Python str.lower() — SQLite lower()/LIKE cannot fold
Cyrillic (mirrors Product.name_lc / catalog.search_products, D-27).
"""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core import local_day_bounds_utc, new_id
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


def _period_starts(today: date) -> dict[str, date]:
    """Calendar period starts (CUST-07/D-05) for the month/quarter/year containing `today`.

    Stdlib date.replace only — zero new date-math dependencies (CLAUDE.md:
    this phase installs nothing extra; the quarter expression below is one
    verified line). Standard Jan-Mar/Apr-Jun/Jul-Sep/Oct-Dec calendar
    quarters.
    """
    return {
        "month": today.replace(day=1),
        "quarter": today.replace(month=3 * ((today.month - 1) // 3) + 1, day=1),
        "year": today.replace(month=1, day=1),
    }


def _spend_stmt(customer_id: str, start_iso: str, end_iso: str):
    """Unexecuted net-spend Select for one customer over a half-open UTC window (CUST-07/D-06).

    Returns the Select itself, NOT executed here, so the portability guard
    (Task 3) can compile it without a session.

    D-06, one formula for both op types, no branching: a `sale` op has
    qty_delta<0 (positive revenue); a `return` op has qty_delta>0 at the
    SAME frozen unit_price_cents (negative revenue, D-07 frozen copy —
    returns.py). The sum nets returned revenue automatically. A return is
    attributed to the window containing its OWN return date, not the origin
    sale's date (RESEARCH Pitfall 8, cash-basis): a June sale returned in
    July makes July's total negative. That is arithmetically correct and
    matches how the Finance pages already book the debit (returns.py
    register_return) — do not "fix" it by re-attributing to the origin sale.

    Double coalesce (RESEARCH Pitfall 4, the likeliest first bug in this
    phase): unit_price_cents is nullable, NULL * anything is NULL, and
    SUM() over zero rows returns NULL. The inner coalesce saves a
    price-less line from silently contributing nothing; the outer one
    saves a zero-order customer from rendering None. Mirrors the shipped
    returns.py `func.coalesce(func.sum(...), 0)` precedent.

    Bounds are half-open [start_iso, end_iso) — >= and <, never <=. No
    SQLite/PostgreSQL date-manipulation SQL function of any kind appears in
    this statement (the class CLAUDE.md bans outright): created_at is a
    String(32) holding utcnow_iso() output, and ISO-8601 UTC strings sort
    lexicographically == chronologically (core.py). The window is computed
    in PYTHON (local_day_bounds_utc) and passed as bound params — this is
    the load-bearing portability rule; reverse it and the PostgreSQL
    migration breaks (CLAUDE.md, explicit).
    """
    return (
        select(
            func.coalesce(
                func.sum(-Operation.qty_delta * func.coalesce(Operation.unit_price_cents, 0)),
                0,
            )
        )
        .join(Sale, Operation.sale_id == Sale.id)
        .where(
            Sale.customer_id == customer_id,
            Operation.type.in_(("sale", "return")),
            Operation.created_at >= start_iso,
            Operation.created_at < end_iso,
        )
    )


def _spend_window(session: Session, customer_id: str, start_iso: str, end_iso: str) -> int:
    """Execute `_spend_stmt` for one [start_iso, end_iso) window; always an int (never None)."""
    return session.scalar(_spend_stmt(customer_id, start_iso, end_iso))


def spend_totals(session: Session, customer_id: str, today: date | None = None) -> dict[str, int]:
    """Net spend in cents for the current calendar month/quarter/year, period-to-date (CUST-07).

    `today` is injectable and this function never reads the real calendar
    internally (RESEARCH Pitfall 7: today is 2026-07-17 and July IS Q3's
    first month, so month-to-date and quarter-to-date are currently
    IDENTICAL — a test asserting they differ passes in July but would fail
    in, say, February. Injection is also the only way to deterministically
    test "a sale 13 months ago is excluded from the year window"). Mirrors
    how stale_products isolates today_local (reports.py).

    Three separate cheap aggregates, not one query fused with CASE WHEN
    conditional sums (RESEARCH Pitfall 6) — that hurts readability and
    saves nothing at single-operator scale. See `_spend_stmt`'s docstring
    for the D-06 netting formula and the D-05/Pitfall-8 cash-basis rule.
    """
    if today is None:
        today = datetime.now(ZoneInfo(settings.display_tz)).date()
    totals: dict[str, int] = {}
    for name, start in _period_starts(today).items():
        start_iso, end_iso = local_day_bounds_utc(start, today, settings.display_tz)
        totals[name] = _spend_window(session, customer_id, start_iso, end_iso)
    return totals


def spend_view(session: Session, customer_id: str, today: date | None = None) -> dict:
    """`spend_totals` reshaped for the detail route template (Plan 05).

    Returns {"month": {"cents": int, "start_iso": str}, "quarter": {...},
    "year": {...}} where start_iso is start.isoformat() — a STRING, not a
    date object. This is load-bearing and closes a real crash: the
    `| ru_date` filter is format_ru_date (core.py), which calls
    date.fromisoformat(iso) on a STRING; date.fromisoformat(date(...))
    raises TypeError. UI-SPEC Interaction 15 renders
    {{ period_start | ru_date }} for the tile captions, so the date-to-
    string conversion must happen HERE, in the service — the date object
    must never reach the template.
    """
    if today is None:
        today = datetime.now(ZoneInfo(settings.display_tz)).date()
    view: dict = {}
    for name, start in _period_starts(today).items():
        start_iso, end_iso = local_day_bounds_utc(start, today, settings.display_tz)
        cents = _spend_window(session, customer_id, start_iso, end_iso)
        view[name] = {"cents": cents, "start_iso": start.isoformat()}
    return view
