"""Active catalog service (DASH-02, D-01/D-02): get/set the singleton row.

Both the catalog number and close date are fully manual (D-01) — never
derived from app.services.catalogs.scan_catalog_files()'s PDF-filename
scan. The row is a singleton by SERVICE-layer convention (get-or-create
below), mirroring how `Batch` has no standalone CRUD lifecycle by
convention rather than a DB constraint (app/models.py).
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import new_id, utcnow_iso
from app.models import ActiveCatalog

# Copy taken verbatim from 23-UI-SPEC.md's Copywriting Contract, "Error
# state — catalog form (D-02)".
NUMBER_TOO_LONG_ERROR = "Слишком длинный номер каталога."
CLOSE_DATE_ERROR = "Проверьте дату закрытия каталога."

# WR-05 style guard: mirrors ActiveCatalog.number's declared String(20)
# column width (app/models.py), matching app/services/customers.py's
# _ADDRESS_MAX_LEN pattern.
_NUMBER_MAX_LEN = 20


def get_active_catalog(session: Session) -> ActiveCatalog | None:
    """The single active-catalog row, or None if never configured yet.

    A missing/never-configured active catalog is a placeholder state, not
    an error (23-CONTEXT.md) — every consumer must handle None.
    """
    return session.scalars(
        select(ActiveCatalog).order_by(ActiveCatalog.created_at).limit(1)
    ).first()


def set_active_catalog(
    session: Session, *, number: str, close_date: str
) -> tuple[ActiveCatalog | None, dict[str, str]]:
    """Save the active-catalog number/close-date singleton row.

    Both fields are independently optional (stripped-empty -> stored NULL);
    no cross-field validation. Returns (row, {}) on success or (None,
    errors) with RU messages — on any error nothing is written.
    """
    errors: dict[str, str] = {}
    number = number.strip()
    close_date = close_date.strip()

    if len(number) > _NUMBER_MAX_LEN:
        errors["number"] = NUMBER_TOO_LONG_ERROR
    if close_date:
        try:
            date.fromisoformat(close_date)
        except ValueError:
            errors["close_date"] = CLOSE_DATE_ERROR

    if errors:
        return None, errors

    row = get_active_catalog(session)
    if row is None:
        row = ActiveCatalog(id=new_id(), created_at=utcnow_iso())
        session.add(row)
    row.number = number or None
    row.close_date = close_date or None
    row.updated_at = utcnow_iso()
    session.commit()
    return row, {}


def _row_count(session: Session) -> int:
    """Test/introspection helper: total row count in active_catalog."""
    return session.scalar(select(func.count()).select_from(ActiveCatalog))
