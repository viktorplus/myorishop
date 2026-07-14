"""Reference dictionary service (CAT-02): plain CRUD, helper table only.

D-24: the dictionary is a HELPER — products remain the catalog source of
truth. Dictionary writes never touch Product rows and never go through
the operations ledger; plain session.commit() is the whole write path.
"""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import new_id
from app.models import Dictionary
from app.services.pagination import LIST_PAGE_SIZE

DUPLICATE_ERROR = "Код уже есть в справочнике — отредактируйте существующую строку."

# T-14-06: sort resolved through this fixed allow-list, never string-
# interpolated into order_by().
_SORT_MAP = {"name": Dictionary.name_lc.asc()}


def _validate(
    session: Session, code: str, name: str, *, exclude_id: str | None = None
) -> tuple[str, str, dict[str, str]]:
    """Shared strip + validation; duplicate check optionally excludes self."""
    errors: dict[str, str] = {}
    code = code.strip()
    name = name.strip()
    if not code:
        errors["code"] = "Укажите код."
    if not name:
        errors["name"] = "Укажите название."
    if code:
        stmt = select(Dictionary).where(Dictionary.code == code)
        if exclude_id is not None:
            stmt = stmt.where(Dictionary.id != exclude_id)
        if session.scalars(stmt).first() is not None:
            errors["code"] = DUPLICATE_ERROR
    return code, name, errors


def add_entry(
    session: Session, *, code: str, name: str
) -> tuple[Dictionary | None, dict[str, str]]:
    """Create a code -> name pair; returns (entry, {}) or (None, RU errors)."""
    code, name, errors = _validate(session, code, name)
    if errors:
        return None, errors
    entry = Dictionary(id=new_id(), code=code, name=name, name_lc=name.lower())
    session.add(entry)
    # WR-02: the SELECT above is check-then-act — a duplicate landing between
    # check and commit (second tab, retried request) raises IntegrityError
    # from uq_dictionary_code; translate it into the same RU error shape.
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return None, {"code": DUPLICATE_ERROR}
    return entry, {}


def update_entry(
    session: Session, entry_id: str, *, code: str, name: str
) -> tuple[Dictionary | None, dict[str, str]]:
    """Edit a pair in place; duplicate-code check excludes the row itself."""
    entry = session.get(Dictionary, entry_id)
    if entry is None:
        return None, {"entry": "Строка справочника не найдена."}
    code, name, errors = _validate(session, code, name, exclude_id=entry_id)
    if errors:
        return None, errors
    entry.code = code
    entry.name = name
    entry.name_lc = name.lower()
    # WR-02: same race guard as add_entry — see comment there.
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return None, {"code": DUPLICATE_ERROR}
    return entry, {}


def list_entries(
    session: Session,
    *,
    code: str = "",
    name: str = "",
    sort: str = "",
    page: int = 0,
) -> dict:
    """Filtered/sorted/paginated read over the dictionary (LIST-01/02/03).

    6,856 rows live today (RESEARCH.md) — the largest list in the app, so
    filtering/sorting/paging happen in SQL (LIMIT/OFFSET + a matching COUNT
    query), mirroring app/services/operations.py's history_view shape.

    T-14-07: code is ASCII digits (A1) so func.lower() is safe; name is
    Cyrillic and matched against the name_lc shadow column instead (SQLite
    lower()/LIKE cannot fold Cyrillic) — mirrors catalog.search_products.
    T-14-08: page is clamped into [0, total_pages - 1] before use in offset().
    """
    filters = []
    code = code.strip()
    name = name.strip()
    if code:
        filters.append(func.lower(Dictionary.code).contains(code.lower(), autoescape=True))
    if name:
        filters.append(Dictionary.name_lc.contains(name.lower(), autoescape=True))

    total = session.scalar(
        select(func.count()).select_from(Dictionary).where(*filters)
    )
    total_pages = max(1, -(-total // LIST_PAGE_SIZE))
    page = max(0, min(page, total_pages - 1))

    stmt = (
        select(Dictionary)
        .where(*filters)
        .order_by(_SORT_MAP.get(sort, Dictionary.code))
        .limit(LIST_PAGE_SIZE)
        .offset(page * LIST_PAGE_SIZE)
    )
    entries = list(session.scalars(stmt))
    return {
        "entries": entries,
        "total": total,
        "total_pages": total_pages,
        "page": page,
        "code": code,
        "name": name,
        "sort": sort,
    }


def lookup(session: Session, code: str) -> Dictionary | None:
    """Exact match on the stripped code (A1: codes are ASCII digits)."""
    code = code.strip()
    if not code:
        return None
    return session.scalars(select(Dictionary).where(Dictionary.code == code)).first()
