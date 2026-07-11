"""Warehouse service (WH-01): plain CRUD + warn-but-allow last-warehouse guard.

D-08: this backs a single settings-style page (/warehouses), not a full
Products-style list+search+/new+/{id}/edit CRUD scaffold. D-09: deleted
rows must NEVER be filtered out of list_warehouses — the management page
keeps them visible (grayed out, restorable), unlike Product.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import new_id, utcnow_iso
from app.models import Warehouse

NAME_REQUIRED_ERROR = "Укажите название склада."
WAREHOUSE_NOT_FOUND_ERROR = "Склад не найден."


def list_warehouses(session: Session) -> list[Warehouse]:
    """ALL rows, active + deleted (D-09) — sorted active-first, then by name.

    Cardinality is small (D-10: "a handful"), so sorting in Python after
    fetch avoids relying on ORDER BY over a boolean-ish expression. This
    query MUST NOT filter by deleted_at (Pitfall 2).
    """
    rows = list(session.scalars(select(Warehouse)))
    return sorted(rows, key=lambda w: (w.deleted_at is not None, w.name))


def add_warehouse(
    session: Session, *, name: str, address: str
) -> tuple[Warehouse | None, dict[str, str]]:
    """Create a warehouse; requires non-blank name. No uniqueness check (D-04)."""
    name = name.strip()
    address = address.strip()
    errors: dict[str, str] = {}
    if not name:
        errors["name"] = NAME_REQUIRED_ERROR
    if errors:
        return None, errors
    warehouse = Warehouse(id=new_id(), name=name, address=address or None)
    session.add(warehouse)
    session.commit()
    return warehouse, {}


def update_warehouse(
    session: Session, warehouse_id: str, *, name: str, address: str
) -> tuple[Warehouse | None, dict[str, str]]:
    """Edit an existing warehouse in place; unknown id is a distinct error."""
    warehouse = session.get(Warehouse, warehouse_id)
    if warehouse is None:
        return None, {"warehouse": WAREHOUSE_NOT_FOUND_ERROR}
    name = name.strip()
    address = address.strip()
    errors: dict[str, str] = {}
    if not name:
        errors["name"] = NAME_REQUIRED_ERROR
    if errors:
        return None, errors
    warehouse.name = name
    warehouse.address = address or None
    session.commit()
    return warehouse, {}


def restore_warehouse(session: Session, warehouse_id: str) -> None:
    """Clear deleted_at; idempotent no-op if already active or unknown id."""
    warehouse = session.get(Warehouse, warehouse_id)
    if warehouse is None or warehouse.deleted_at is None:
        return
    warehouse.deleted_at = None
    session.commit()


def soft_delete_warehouse(
    session: Session, warehouse_id: str, *, confirm: bool = False
) -> tuple[bool, dict]:
    """Soft-delete one warehouse; warn-but-allow if it is the last active one.

    Returns (deleted, warning):
      (True, {})                -> deleted (not last-active, or confirm=True)
      (False, {})                -> unknown id or already deleted (no-op)
      (False, {"warehouse": w})  -> blocked pending confirm=1 re-POST,
                                     ZERO writes staged
    """
    warehouse = session.get(Warehouse, warehouse_id)
    if warehouse is None or warehouse.deleted_at is not None:
        return False, {}

    if not confirm:
        active_count = session.scalar(
            select(func.count())
            .select_from(Warehouse)
            .where(Warehouse.deleted_at.is_(None))
        )
        if active_count <= 1:
            return False, {"warehouse": warehouse}

    warehouse.deleted_at = utcnow_iso()
    session.commit()
    return True, {}
