"""Reference dictionary service (CAT-02): plain CRUD, helper table only.

D-24: the dictionary is a HELPER — products remain the catalog source of
truth. Dictionary writes never touch Product rows and never go through
the operations ledger; plain session.commit() is the whole write path.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import new_id
from app.models import Dictionary

DUPLICATE_ERROR = "Код уже есть в справочнике — отредактируйте существующую строку."


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
    entry = Dictionary(id=new_id(), code=code, name=name)
    session.add(entry)
    session.commit()
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
    session.commit()
    return entry, {}


def list_entries(session: Session) -> list[Dictionary]:
    """All pairs ordered by code (the /dictionary table order)."""
    return list(session.scalars(select(Dictionary).order_by(Dictionary.code)))


def lookup(session: Session, code: str) -> Dictionary | None:
    """Exact match on the stripped code (A1: codes are ASCII digits)."""
    code = code.strip()
    if not code:
        return None
    return session.scalars(select(Dictionary).where(Dictionary.code == code)).first()
